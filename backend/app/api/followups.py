from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Department, FollowUp, ReportTaskLink, Task, User
from ..schemas import Input, TaskInput
from ..security import current_user, department_ids, fail, require_department, scoped
from ..services.common import audit, notify, record_dict
from ..services.reports import accessible_report, reviewers

router = APIRouter(tags=["Cross-department follow-up"])


@router.get("/routing-departments")
def destinations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "worker":
        fail(403, "Supervisor review is required for routing.")
    return [
        {"id": item.id, "name": item.name}
        for item in db.scalars(
            select(Department).where(
                Department.organization_id == user.organization_id, Department.active.is_(True)
            )
        )
    ]


class Route(Input):
    report_id: str
    receiving_department_id: str
    note: str = Field(min_length=10, max_length=5000)


@router.post("/follow-ups", status_code=201)
def route(values: Route, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = accessible_report(db, user, values.report_id, values.note)
    require_department(db, user, report.department_id, "review")
    destination = scoped(db, Department, values.receiving_department_id, user)
    if not destination.active or destination.id == report.department_id:
        fail(422, "Choose another active department.")
    item = FollowUp(
        organization_id=user.organization_id,
        report_id=report.id,
        originating_department_id=report.department_id,
        receiving_department_id=destination.id,
        requested_by=user.id,
        note=values.note,
    )
    db.add(item)
    db.flush()
    for recipient in reviewers(db, destination.id):
        notify(
            db,
            user.organization_id,
            recipient,
            f"followup:{item.id}",
            "Another department requests follow-up",
            values.note,
            "/workspace/follow-ups",
        )
    report.needs_attention = True
    audit(
        db,
        user,
        user.organization_id,
        "report.follow_up.requested",
        "follow_up",
        item.id,
        after={"receiving_department_id": destination.id},
        purpose=values.note,
    )
    return record_dict(item)


@router.get("/follow-ups")
def followups(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "worker":
        fail(403, "Supervisor access is required.")
    allowed = department_ids(db, user)
    items = db.scalars(
        select(FollowUp)
        .where(
            FollowUp.organization_id == user.organization_id,
            or_(
                FollowUp.originating_department_id.in_(allowed), FollowUp.receiving_department_id.in_(allowed)
            ),
        )
        .order_by(FollowUp.created_at.desc())
        .limit(200)
    )
    return [
        {**record_dict(item), "task_status": db.get(Task, item.task_id).status if item.task_id else None}
        for item in items
    ]


@router.post("/follow-ups/{record_id}/assign", status_code=201)
def assign(
    record_id: str, values: TaskInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    from ..services.tasks import create_task

    item = scoped(db, FollowUp, record_id, user)
    require_department(db, user, item.receiving_department_id, "manage")
    if item.task_id or values.department_id != item.receiving_department_id:
        fail(409, "Follow-up is already assigned or the task department does not match.")
    # Claim once inside the transaction; rollback releases the claim if creation fails.
    claimed = db.execute(
        update(FollowUp)
        .where(FollowUp.id == item.id, FollowUp.task_id.is_(None), FollowUp.status == "requested")
        .values(status="assigning", accepted_by=user.id)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        fail(409, "Another supervisor has already assigned this follow-up.")
    # Receiving staff see the purpose-limited referral, not unrelated original evidence.
    values.source_report_id = None
    task = create_task(db, user, values)
    task.source_report_id = item.report_id
    db.add(
        ReportTaskLink(
            organization_id=user.organization_id,
            report_id=item.report_id,
            task_id=task.id,
            linked_by=user.id,
            follow_up=True,
        )
    )
    item.task_id, item.accepted_by, item.status = task.id, user.id, "assigned"
    for recipient in reviewers(db, item.originating_department_id):
        notify(
            db,
            user.organization_id,
            recipient,
            f"followup:{item.id}:assigned",
            "Linked follow-up assigned",
            task.title,
            "/workspace/follow-ups",
        )
    audit(
        db, user, user.organization_id, "follow_up.assigned", "follow_up", item.id, after={"task_id": task.id}
    )
    return record_dict(task)
