from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import now
from ..models import (
    Alert,
    Conflict,
    Department,
    DepartmentMembership,
    Handover,
    HandoverItem,
    HandoverRecipient,
    HandoverVersion,
    Organization,
    Report,
    ReportVersion,
    Shift,
    ShiftAssignment,
    Task,
    TaskAssignment,
    User,
)
from ..security import department_ids, fail, require_department
from .common import audit, json_safe, notify


def shift_window(organization: Organization, shift: Shift, day: str):
    calendar_day = date.fromisoformat(day)
    zone = ZoneInfo(organization.timezone)
    start = datetime.combine(calendar_day, time.fromisoformat(shift.starts_at), zone)
    end = datetime.combine(calendar_day, time.fromisoformat(shift.ends_at), zone)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def next_shift(db: Session, organization: Organization, after: datetime, preferred_id=None):
    candidates = []
    shifts = db.scalars(
        select(Shift).where(Shift.organization_id == organization.id, Shift.active.is_(True))
    ).all()
    for offset in range(8):
        day = after.astimezone(ZoneInfo(organization.timezone)).date() + timedelta(days=offset)
        for shift in shifts:
            if (preferred_id and shift.id != preferred_id) or day.weekday() not in shift.days:
                continue
            start, _ = shift_window(organization, shift, day.isoformat())
            if start >= after:
                candidates.append((start, shift.id, day.isoformat()))
    return min(candidates) if candidates else None


def compile_draft(db: Session, handover: Handover):
    org, shift = db.get(Organization, handover.organization_id), db.get(Shift, handover.shift_id)
    start, end = shift_window(org, shift, handover.shift_date)
    items = []
    query = select(Task).where(
        Task.organization_id == org.id,
        Task.department_id == handover.department_id,
        (Task.status != "closed") | (Task.closed_at.between(start, end)),
    )
    for task in db.scalars(query.order_by(Task.created_at)):
        owners = db.scalars(
            select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.ended_at.is_(None))
        ).all()
        items.append(
            {
                "source_type": "task",
                "source_id": task.id,
                "title": task.title,
                "critical": task.critical,
                "detail": json_safe(
                    {
                        "status": task.status,
                        "priority": task.priority,
                        "deadline": task.deadline,
                        "blocked_reason": task.blocked_reason,
                        "assignment_type": task.assignment_type,
                        "team_id": task.team_id,
                        "owners": [{"user_id": a.user_id, "team_id": a.team_id} for a in owners],
                        "transfer_pending": task.status not in {"closed", "verified"},
                    }
                ),
            }
        )
    for report in db.scalars(
        select(Report).where(
            Report.organization_id == org.id,
            Report.department_id == handover.department_id,
            (Report.occurred_at.between(start, end))
            | ((Report.resolved_at.is_(None)) & (Report.needs_attention.is_(True))),
        )
    ):
        version = db.scalar(
            select(ReportVersion).where(
                ReportVersion.report_id == report.id, ReportVersion.number == report.latest_version
            )
        )
        items.append(
            {
                "source_type": "report",
                "source_id": report.id,
                "title": f"{report.category.title()} report · {report.occurred_at.astimezone(ZoneInfo(org.timezone)).strftime('%d %b %H:%M')}",
                "critical": report.immediate_safety,
                "detail": {
                    "status": report.status,
                    "unresolved": report.resolved_at is None,
                    "needs_attention": report.needs_attention,
                    "source_version": report.latest_version,
                    "machine": version.fields.get("machine") if version else None,
                    "work_area": version.fields.get("work_area") if version else None,
                },
            }
        )
    for model, name in [(Alert, "alert"), (Conflict, "conflict")]:
        for item in db.scalars(
            select(model).where(
                model.organization_id == org.id,
                model.department_id == handover.department_id,
                model.status != "resolved",
            )
        ):
            items.append(
                {
                    "source_type": name,
                    "source_id": item.id,
                    "title": item.title,
                    "critical": name == "alert",
                    "detail": {"status": item.status, "unresolved": True},
                }
            )
    prior = list(
        db.scalars(
            select(HandoverRecipient)
            .join(HandoverVersion, HandoverVersion.id == HandoverRecipient.version_id)
            .join(Handover, Handover.id == HandoverVersion.handover_id)
            .where(
                Handover.department_id == handover.department_id,
                HandoverRecipient.acknowledged_at.is_(None),
                Handover.id != handover.id,
            )
        )
    )
    return {
        "items": items,
        "notes": handover.draft.get("notes", ""),
        "compiled_at": now().isoformat(),
        "window": {"starts_at": start.isoformat(), "ends_at": end.isoformat()},
        "pending_receipts": len(prior),
    }


def handover_query(db: Session, user: User):
    query = select(Handover).where(
        Handover.organization_id == user.organization_id, Handover.department_id.in_(department_ids(db, user))
    )
    if user.role == "worker":
        query = query.where(Handover.latest_version > 0)
    return query


def visible_handover(db: Session, user: User, record_id: str):
    item = db.scalar(handover_query(db, user).where(Handover.id == record_id))
    if not item:
        fail(404, "Handover not found.")
    return item


def publish(db: Session, handover: Handover, actor: User | None, changes: str, provisional=False):
    if actor:
        require_department(db, actor, handover.department_id, "publish")
    handover.draft = compile_draft(db, handover)
    organization = db.get(Organization, handover.organization_id)
    _, ending = shift_window(organization, db.get(Shift, handover.shift_id), handover.shift_date)
    incoming = next_shift(db, organization, ending, handover.incoming_shift_id)
    if incoming:
        handover.incoming_shift_id = incoming[1]
        handover.draft = {
            **handover.draft,
            "incoming": {"shift_id": incoming[1], "starts_at": incoming[0].isoformat()},
        }
    handover.latest_version += 1
    handover.status = "provisional" if provisional else "published"
    version = HandoverVersion(
        organization_id=handover.organization_id,
        handover_id=handover.id,
        number=handover.latest_version,
        snapshot=handover.draft,
        provisional=provisional,
        published_by=actor.id if actor else None,
        changes=changes,
    )
    db.add(version)
    db.flush()
    for item in handover.draft["items"]:
        db.add(HandoverItem(organization_id=handover.organization_id, version_id=version.id, **item))
    members = db.scalars(
        select(DepartmentMembership)
        .join(User, User.id == DepartmentMembership.user_id)
        .where(
            DepartmentMembership.department_id == handover.department_id,
            DepartmentMembership.active.is_(True),
            User.active.is_(True),
        )
    ).all()
    recipients = {
        m.user_id for m in members if (m.primary or m.backup) and db.get(User, m.user_id).role == "supervisor"
    }
    if handover.incoming_shift_id:
        incoming_date = incoming[2] if incoming else handover.shift_date
        recipients.update(
            db.scalars(
                select(ShiftAssignment.user_id)
                .join(User, User.id == ShiftAssignment.user_id)
                .where(
                    ShiftAssignment.shift_id == handover.incoming_shift_id,
                    ShiftAssignment.department_id == handover.department_id,
                    ShiftAssignment.active.is_(True),
                    User.active.is_(True),
                    ShiftAssignment.starts_on <= incoming_date,
                    (ShiftAssignment.ends_on.is_(None)) | (ShiftAssignment.ends_on >= incoming_date),
                )
            )
        )
    else:
        recipients.update(m.user_id for m in members)
    for recipient in recipients:
        db.add(
            HandoverRecipient(
                organization_id=handover.organization_id, version_id=version.id, user_id=recipient
            )
        )
        notify(
            db,
            handover.organization_id,
            recipient,
            f"handover:{handover.id}:v{version.number}",
            "Handover pending supervisor review"
            if provisional
            else f"Handover version {version.number} published",
            changes,
            f"/workspace/handovers/{handover.id}",
            "handover",
        )
    audit(
        db,
        actor,
        handover.organization_id,
        "handover.provisional" if provisional else "handover.published",
        "handover",
        handover.id,
        after={"number": version.number, "provisional": provisional, "changes": changes},
    )
    return version


def provisional_due(db: Session):
    for org in db.scalars(select(Organization).where(Organization.active.is_(True))):
        local = now().astimezone(ZoneInfo(org.timezone))
        for shift in db.scalars(select(Shift).where(Shift.organization_id == org.id, Shift.active.is_(True))):
            for day in [local.date() - timedelta(days=1), local.date()]:
                if day.weekday() not in shift.days:
                    continue
                _, end = shift_window(org, shift, day.isoformat())
                if not (end + timedelta(minutes=shift.grace_minutes) <= local < end + timedelta(hours=24)):
                    continue
                for dept in db.scalars(
                    select(Department).where(
                        Department.organization_id == org.id, Department.active.is_(True)
                    )
                ):
                    handover = db.scalar(
                        select(Handover)
                        .where(
                            Handover.department_id == dept.id,
                            Handover.shift_id == shift.id,
                            Handover.shift_date == day.isoformat(),
                        )
                        .with_for_update()
                    )
                    if not handover:
                        handover = Handover(
                            organization_id=org.id,
                            department_id=dept.id,
                            shift_id=shift.id,
                            shift_date=day.isoformat(),
                        )
                        db.add(handover)
                        db.flush()
                    if handover.latest_version == 0:
                        publish(
                            db,
                            handover,
                            None,
                            "Shift ended before publication. Pending Supervisor Review.",
                            provisional=True,
                        )
