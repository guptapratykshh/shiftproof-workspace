from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import Alert, AlertHistory, Task, User
from ..schemas import Input
from ..security import current_user, fail, require_department, scoped
from ..services import alerts as service
from ..services.common import audit, record_dict

router = APIRouter(tags=["Critical alerts"])


@router.get("/alerts")
def alerts(user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    return [
        record_dict(item)
        for item in db.scalars(service.alert_query(db, user).order_by(Alert.created_at.desc()).limit(200))
    ]


@router.get("/alerts/{record_id}")
def detail(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    item = service.accessible_alert(db, user, record_id)
    return {
        **record_dict(item),
        "history": [
            record_dict(history)
            for history in db.scalars(
                select(AlertHistory).where(AlertHistory.alert_id == item.id).order_by(AlertHistory.created_at)
            )
        ],
    }


class ImmediateAlert(Input):
    department_id: str
    title: str = Field(min_length=3, max_length=200)
    client_request_id: str | None = Field(default=None, min_length=16, max_length=80)


@router.post("/alerts/immediate", status_code=201)
def immediate(values: ImmediateAlert, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    require_department(db, user, values.department_id, active=True)
    db.execute(update(User).where(User.id == user.id).values(updated_at=now()))
    if values.client_request_id:
        existing = db.scalar(
            select(Alert)
            .join(AlertHistory, AlertHistory.alert_id == Alert.id)
            .where(
                Alert.organization_id == user.organization_id,
                AlertHistory.actor_id == user.id,
                AlertHistory.action == "created",
                AlertHistory.detail["client_request_id"].as_string() == values.client_request_id,
            )
        )
        if existing:
            if existing.department_id != values.department_id:
                fail(409, "This alert was already sent for a different department.")
            return record_dict(existing)
    return record_dict(
        service.create_alert(
            db,
            user,
            values.department_id,
            values.title,
            immediate=True,
            client_request_id=values.client_request_id,
        )
    )


class AlertAction(Input):
    action: Literal["acknowledge", "assign", "verify", "resolve"]
    note: str = Field(default="", max_length=10000)
    task_id: str | None = None
    version: int


@router.post("/alerts/{record_id}/actions")
def action(
    record_id: str, values: AlertAction, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    item = service.accessible_alert(db, user, record_id)
    if values.action == "acknowledge" and user.role == "organization" and item.assigned_to == user.id:
        pass  # Organization escalation can be received without granting sensitive source access.
    else:
        require_department(db, user, item.department_id, "review")
    if item.version != values.version:
        fail(409, "This alert changed. Refresh before continuing.")
    before = item.status
    if values.action == "acknowledge":
        if item.status != "new":
            fail(409, "This alert has already been acknowledged.")
        item.status, item.acknowledged_at, item.acknowledged_by, item.next_escalation = (
            "acknowledged",
            now(),
            user.id,
            None,
        )
    elif values.action == "assign":
        if not values.task_id or item.status not in {"acknowledged", "in_progress"}:
            fail(422, "Acknowledge this alert and choose a corrective task.")
        task = scoped(db, Task, values.task_id, user)
        if task.department_id != item.department_id or not task.critical or not task.verification_required:
            fail(422, "Choose a critical task in this department with required verification.")
        if item.report_id and task.source_report_id != item.report_id:
            fail(422, "The corrective task must link to this alert's source report.")
        item.task_id, item.status = task.id, "in_progress"
    elif values.action == "verify":
        if len(values.note) < 10 or item.status not in {"acknowledged", "in_progress"}:
            fail(422, "Review the source and describe the verified resolution.")
        if item.task_id and db.get(Task, item.task_id).status != "closed":
            fail(409, "Complete, verify and close the corrective task first.")
        item.status, item.resolution = "verified", values.note
    else:
        if item.status != "verified":
            fail(409, "An authorized reviewer must verify resolution before closure.")
        item.status, item.resolved_at = "resolved", now()
    db.add(
        AlertHistory(
            organization_id=user.organization_id,
            alert_id=item.id,
            actor_id=user.id,
            action=values.action,
            detail={"from": before, "to": item.status, "note": values.note, "task_id": item.task_id},
        )
    )
    audit(
        db,
        user,
        user.organization_id,
        f"alert.{values.action}",
        "alert",
        item.id,
        {"status": before},
        {"status": item.status},
        values.note,
    )
    db.flush()
    return record_dict(item)
