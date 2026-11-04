import asyncio
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db, now
from ..models import AuditLog, BackgroundJob, DeviceSession, Notification, User
from ..schemas import Input
from ..security import admin, current_user, fail, policy_value, scoped
from ..services.common import audit, record_dict

router = APIRouter(tags=["Notifications, audit and account"])


@router.get("/notifications")
def notifications(unread: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Notification).where(
        Notification.user_id == user.id, Notification.organization_id == user.organization_id
    )
    if unread:
        query = query.where(Notification.read_at.is_(None))
    return {
        "items": [
            record_dict(item)
            for item in db.scalars(query.order_by(Notification.created_at.desc()).limit(200))
        ],
        "unread": db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        ),
    }


@router.post("/notifications/{record_id}/read")
def read_notification(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = scoped(db, Notification, record_id, user)
    if item.user_id != user.id:
        fail(404, "Notification not found.")
    item.read_at = item.read_at or now()
    return record_dict(item)


@router.get("/events")
def events(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user_id, organization_id, session_id = user.id, user.organization_id, request.state.session.id
    # Release the request transaction before the long-lived stream.
    db.commit()

    async def stream():
        last = None
        for _ in range(60):
            if await request.is_disconnected():
                break
            with SessionLocal() as current:
                session = current.get(DeviceSession, session_id)
                person = current.get(User, user_id)
                idle_minutes = policy_value(current, organization_id, "security").get(
                    "idle_minutes", 60 if person and person.role == "worker" else 120
                )
                if (
                    not session
                    or session.revoked
                    or session.expires_at <= now()
                    or session.last_seen + timedelta(minutes=idle_minutes) <= now()
                    or not person
                    or not person.active
                ):
                    yield "event: expired\ndata: {}\n\n"
                    break
                latest = current.scalar(
                    select(Notification.id)
                    .where(Notification.user_id == user_id, Notification.organization_id == organization_id)
                    .order_by(Notification.created_at.desc())
                    .limit(1)
                )
                if latest != last:
                    yield f"event: update\ndata: {json.dumps({'latest': latest})}\n\n"
                    last = latest
                else:
                    yield ": heartbeat\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@router.get("/audit")
def history(
    action: str | None = None,
    entity_type: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    admin(user)
    query = select(AuditLog).where(AuditLog.organization_id == user.organization_id)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action[:100]}%"))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    sensitive_allowed = policy_value(db, user.organization_id, "privacy").get("admin_report_access", False)
    results = []
    for item in db.scalars(
        query.order_by(AuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit)
    ):
        value = record_dict(item)
        if item.entity_type in {"report", "conflict", "clarification", "follow_up"} and not sensitive_allowed:
            value.update(before={}, after={}, purpose="", redacted=True)
        results.append(value)
    return {"items": results, "total": db.scalar(select(func.count()).select_from(query.subquery()))}


@router.get("/operations/queue")
def queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    return [
        record_dict(item, {"payload", "result", "lease_token"})
        for item in db.scalars(
            select(BackgroundJob)
            .where(BackgroundJob.organization_id == user.organization_id)
            .order_by(BackgroundJob.created_at.desc())
            .limit(100)
        )
    ]


class Profile(Input):
    name: str = Field(min_length=2, max_length=200)
    phone: str = Field(default="", max_length=40)


@router.put("/profile")
def profile(values: Profile, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "worker":
        fail(403, "Ask your supervisor to update your workforce identity details.")
    before = {"name": user.name, "phone": user.phone}
    user.name, user.phone = values.name, values.phone
    audit(db, user, user.organization_id, "profile.updated", "user", user.id, before, values.model_dump())
    return record_dict(user)


@router.post("/orientation/complete")
def orientation(user: User = Depends(current_user)):
    user.profile = {**user.profile, "orientation_completed_at": now().isoformat()}
    return {"status": "complete"}
