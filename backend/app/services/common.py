from datetime import datetime

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from ..models import AuditLog, BackgroundJob, Notification, User

SECRET_FIELDS = {
    "password_hash",
    "pin_hash",
    "token_hash",
    "csrf_hash",
    "storage_key",
    "request_hash",
    "offline_key",
}


def record_dict(record, exclude: set[str] | None = None) -> dict:
    blocked = SECRET_FIELDS | (exclude or set())
    return {
        column.key: getattr(record, column.key)
        for column in inspect(record).mapper.column_attrs
        if column.key not in blocked
    }


def json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: json_safe(item)
            for key, item in value.items()
            if key not in SECRET_FIELDS and key not in {"password", "pin", "token", "confirm"}
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def audit(
    db: Session,
    user: User | None,
    organization_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before=None,
    after=None,
    purpose="",
):
    db.add(
        AuditLog(
            organization_id=organization_id,
            actor_id=user.id if user else None,
            actor_role=user.role if user else "system",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=json_safe(before or {}),
            after=json_safe(after or {}),
            purpose=purpose,
        )
    )


def notify(
    db: Session,
    organization_id: str,
    user_id: str,
    event_key: str,
    title: str,
    body: str,
    href: str,
    category: str = "action_required",
):
    existing = db.scalar(
        select(Notification.id).where(Notification.user_id == user_id, Notification.event_key == event_key)
    )
    if not existing:
        db.add(
            Notification(
                organization_id=organization_id,
                user_id=user_id,
                event_key=event_key,
                title=title,
                body=body,
                href=href,
                category=category,
            )
        )
        db.flush()


def enqueue(
    db: Session, kind: str, key: str, payload: dict, organization_id=None, actor_id=None
) -> BackgroundJob:
    existing = db.scalar(select(BackgroundJob).where(BackgroundJob.dedupe_key == key))
    if existing:
        return existing
    job = BackgroundJob(
        kind=kind, dedupe_key=key, payload=payload, organization_id=organization_id, actor_id=actor_id
    )
    db.add(job)
    db.flush()
    return job
