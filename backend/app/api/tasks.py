from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import (
    FileAsset,
    Organization,
    Task,
    TaskAssignment,
    TaskComment,
    TaskEvidence,
    TaskHistory,
    TaskTemplate,
    User,
)
from ..schemas import Input, TaskAction, TaskInput
from ..security import current_user, department_ids, fail, require_department, scoped
from ..services import tasks as service
from ..services.common import audit, json_safe, notify, record_dict

router = APIRouter(tags=["Tasks"])


class EvidenceLink(Input):
    asset_id: str


class AssociationInput(Input):
    text: str = Field(min_length=1, max_length=20000)
    department_id: str


@router.post("/task-associations")
def associations(values: AssociationInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    import re

    require_department(db, user, values.department_id)
    source = values.text.casefold()
    words = set(re.findall(r"\w{4,}", source))
    matches = []
    for task in db.scalars(
        service.task_query(db, user).where(
            Task.department_id == values.department_id, Task.status != "closed"
        )
    ):
        common = words & set(re.findall(r"\w{4,}", task.title.casefold()))
        exact = task.id in source or task.title.casefold() in source
        if exact or len(common) >= 2:
            matches.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "score": 100 if exact else len(common),
                    "basis": "Exact task reference"
                    if exact
                    else "Shared words: " + ", ".join(sorted(common)),
                }
            )
    return {"items": sorted(matches, key=lambda item: -item["score"])[:5], "confirmation_required": True}


@router.get("/tasks/{record_id}/evidence")
def evidence(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = service.visible_task(db, user, record_id)
    return [
        record_dict(asset)
        for asset in db.scalars(
            select(FileAsset)
            .join(TaskEvidence, TaskEvidence.asset_id == FileAsset.id)
            .where(TaskEvidence.task_id == task.id)
        )
    ]


@router.post("/tasks/{record_id}/evidence", status_code=201)
def attach_evidence(
    record_id: str, values: EvidenceLink, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    task = service.visible_task(db, user, record_id)
    require_department(db, user, task.department_id, "manage")
    asset = scoped(db, FileAsset, values.asset_id, user)
    if (
        task.status == "closed"
        or asset.owner_id != user.id
        or asset.department_id != task.department_id
        or asset.deleted_at
        or asset.retention_until <= now()
    ):
        fail(422, "Attach your own retained evidence to an open task in the same department.")
    link = db.scalar(
        select(TaskEvidence).where(TaskEvidence.task_id == task.id, TaskEvidence.asset_id == asset.id)
    )
    if not link:
        link = TaskEvidence(
            organization_id=user.organization_id, task_id=task.id, asset_id=asset.id, linked_by=user.id
        )
        db.add(link)
        audit(
            db,
            user,
            user.organization_id,
            "task.evidence.attached",
            "task",
            task.id,
            after={"asset_id": asset.id},
        )
        for person in service.recipients(db, task):
            notify(
                db,
                user.organization_id,
                person,
                f"task:{task.id}:evidence:{asset.id}",
                "Task instructions include new evidence",
                task.title,
                f"/workspace/tasks/{task.id}",
            )
    return record_dict(asset)


@router.get("/tasks")
def tasks(
    department_id: str | None = None,
    worker_id: str | None = None,
    team_id: str | None = None,
    category: str | None = None,
    due_before: date | None = None,
    status: str | None = None,
    priority: str | None = None,
    q: str = "",
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = service.task_query(db, user)
    for column, value in [
        (Task.department_id, department_id),
        (Task.status, status),
        (Task.priority, priority),
        (Task.team_id, team_id),
        (Task.category, category),
    ]:
        if value:
            query = query.where(column == value)
    if q:
        query = query.where(Task.title.ilike(f"%{q[:100]}%"))
    if due_before:
        zone = ZoneInfo(db.get(Organization, user.organization_id).timezone)
        query = query.where(Task.deadline <= datetime.combine(due_before, time.max, zone))
    if worker_id:
        from ..models import TeamMembership

        query = query.where(
            Task.id.in_(
                select(TaskAssignment.task_id).where(
                    TaskAssignment.ended_at.is_(None),
                    (TaskAssignment.user_id == worker_id)
                    | TaskAssignment.team_id.in_(
                        select(TeamMembership.team_id).where(
                            TeamMembership.user_id == worker_id, TeamMembership.active.is_(True)
                        )
                    ),
                )
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            record_dict(item)
            for item in db.scalars(
                query.order_by(Task.created_at.desc()).offset((page - 1) * limit).limit(limit)
            )
        ],
        "total": total,
    }


@router.post("/tasks", status_code=201)
def create(values: TaskInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.task_detail(db, user, service.create_task(db, user, values))


@router.get("/tasks/{record_id}")
def detail(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.task_detail(db, user, service.visible_task(db, user, record_id))


@router.post("/tasks/{record_id}/actions")
def action(
    record_id: str, values: TaskAction, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    task = service.transition(db, user, service.visible_task(db, user, record_id), values)
    return service.task_detail(db, user, task)


class Reassignment(Input):
    worker_id: str | None = None
    team_id: str | None = None
    lead_id: str | None = None
    reason: str = Field(min_length=3, max_length=2000)
    version: int


@router.post("/tasks/{record_id}/reassign")
def reassign(
    record_id: str, values: Reassignment, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    task = service.visible_task(db, user, record_id)
    if task.version != values.version:
        fail(409, "Task changed. Refresh before reassigning.")
    return record_dict(
        service.reassign(db, user, task, values.worker_id, values.team_id, values.lead_id, values.reason)
    )


class BulkReassignment(Input):
    task_ids: list[str] = Field(min_length=1, max_length=100)
    worker_id: str
    reason: str = Field(min_length=3, max_length=2000)


@router.post("/task-reassignments")
def bulk_reassign(
    values: BulkReassignment, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    results = []
    for task_id in set(values.task_ids):
        task = service.visible_task(db, user, task_id)
        if task.assignment_type != "individual":
            fail(422, "Bulk worker reassignment supports individual tasks only.")
        results.append(
            record_dict(service.reassign(db, user, task, values.worker_id, None, None, values.reason))
        )
    return {"items": results}


class Comment(Input):
    text: str = Field(min_length=1, max_length=10000)
    internal: bool = False


@router.post("/tasks/{record_id}/comments", status_code=201)
def comment(
    record_id: str, values: Comment, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    task = service.visible_task(db, user, record_id)
    if values.internal:
        require_department(db, user, task.department_id, "manage")
    item = TaskComment(
        organization_id=user.organization_id, task_id=task.id, author_id=user.id, **values.model_dump()
    )
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        user.organization_id,
        "task.comment",
        "task",
        task.id,
        after={"comment_id": item.id, "internal": item.internal},
    )
    return record_dict(item)


class TaskEdit(Input):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(max_length=10000)
    instructions: str = Field(max_length=10000)
    priority: Literal["normal", "important", "urgent", "critical"] | None
    critical: bool
    verification_required: bool
    deadline: datetime | None
    reason: str = Field(min_length=3, max_length=2000)
    version: int


@router.put("/tasks/{record_id}")
def edit(record_id: str, values: TaskEdit, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = service.visible_task(db, user, record_id)
    require_department(db, user, task.department_id, "manage")
    if task.version != values.version or task.status in {"verified", "closed"}:
        fail(409, "Refresh this task. Verified or closed work cannot be edited.")
    if values.deadline and not values.deadline.tzinfo:
        fail(422, "Deadline must include a timezone.")
    if task.critical and not values.critical:
        fail(422, "A critical task cannot lose its review requirement.")
    before = record_dict(task)
    for key, value in values.model_dump(exclude={"reason", "version"}).items():
        setattr(task, key, value)
    task.critical = task.critical or task.priority == "critical"
    task.verification_required = task.verification_required or task.critical
    db.add(
        TaskHistory(
            organization_id=user.organization_id,
            task_id=task.id,
            actor_id=user.id,
            action="edited",
            detail={"reason": values.reason, "before": json_safe(before)},
        )
    )
    db.flush()
    audit(
        db,
        user,
        user.organization_id,
        "task.edited",
        "task",
        task.id,
        before,
        record_dict(task),
        values.reason,
    )
    for recipient in service.recipients(db, task):
        notify(
            db,
            user.organization_id,
            recipient,
            f"task:{task.id}:v{task.version}:edited",
            "Task instructions or deadline changed",
            values.reason,
            f"/workspace/tasks/{task.id}",
        )
    return record_dict(task)


@router.get("/allocation-suggestions")
def suggestions(
    department_id: str,
    required_skills: str = "",
    shift_id: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_department(db, user, department_id, "manage")
    return {
        "items": service.allocation_candidates(
            db, user, department_id, [s.strip() for s in required_skills.split(",") if s.strip()], shift_id
        ),
        "review_required": True,
    }


class TemplateInput(Input):
    task: TaskInput
    recurrence_minutes: int | None = Field(default=None, ge=15, le=525600)
    next_run: datetime | None = None
    active: bool = True
    auto_allocate: bool = False


@router.get("/task-templates")
def templates(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        record_dict(item)
        for item in db.scalars(
            select(TaskTemplate).where(
                TaskTemplate.organization_id == user.organization_id,
                TaskTemplate.department_id.in_(department_ids(db, user, "manage")),
            )
        )
    ]


@router.post("/task-templates", status_code=201)
def template(values: TemplateInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_department(db, user, values.task.department_id, "manage")
    if values.next_run and not values.next_run.tzinfo:
        fail(422, "Schedule must include a timezone.")
    if values.auto_allocate and (
        values.task.critical
        or values.task.priority not in {None, "normal"}
        or values.task.assignment_type != "individual"
    ):
        fail(422, "Automatic allocation is only available for approved routine individual work.")
    item = TaskTemplate(
        organization_id=user.organization_id,
        department_id=values.task.department_id,
        title=values.task.title,
        definition={**values.task.model_dump(mode="json"), "_auto_allocate": values.auto_allocate},
        recurrence_minutes=values.recurrence_minutes,
        next_run=values.next_run or now(),
        active=values.active,
        created_by=user.id,
    )
    db.add(item)
    db.flush()
    audit(db, user, user.organization_id, "template.created", "task_template", item.id)
    return record_dict(item)


@router.post("/task-templates/{record_id}/apply", status_code=201)
def apply_template(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = scoped(db, TaskTemplate, record_id, user)
    require_department(db, user, item.department_id, "manage")
    task = service.create_task(db, user, service.template_values(db, user, item))
    task.template_id = item.id
    return record_dict(task)


@router.delete("/task-templates/{record_id}")
def stop_template(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = scoped(db, TaskTemplate, record_id, user)
    require_department(db, user, item.department_id, "manage")
    item.active = False
    audit(db, user, user.organization_id, "template.stopped", "task_template", item.id)
    return {"status": "inactive"}
