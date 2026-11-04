from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import now
from ..models import (
    Alert,
    AlertHistory,
    DepartmentMembership,
    EscalationRule,
    Report,
    ReportVersion,
    ResponsibilityMapping,
    User,
)
from ..security import department_ids, fail
from .common import audit, enqueue, notify


def email_alert(db: Session, alert: Alert, rule: EscalationRule | None, recipient_id: str, event: str):
    if not rule or "email" not in rule.channels:
        return
    from ..config import get_settings

    recipient = db.get(User, recipient_id)
    if (
        recipient
        and recipient.active
        and recipient.email
        and recipient.organization_id == alert.organization_id
    ):
        enqueue(
            db,
            "email",
            f"alert-email:{alert.id}:{event}:{recipient.id}",
            {
                "to": recipient.email,
                "subject": "ShiftProof: critical concern requires response",
                "text": f"A critical concern needs your review. Sign in to inspect the authorized record and acknowledge it. Reading this email does not acknowledge or resolve it.\n\n{get_settings().frontend_url}/workspace/alerts/{alert.id}",
            },
            alert.organization_id,
        )


def responsible(db: Session, department_id: str, report_id: str | None = None, backup=False):
    report = db.get(Report, report_id) if report_id else None
    fields = {}
    if report:
        version = db.scalar(
            select(ReportVersion).where(
                ReportVersion.report_id == report.id, ReportVersion.number == report.latest_version
            )
        )
        fields = version.fields if version else {}
    candidates = []
    for mapping in db.scalars(
        select(ResponsibilityMapping).where(ResponsibilityMapping.department_id == department_id)
    ):
        conditions = [
            (mapping.machine, fields.get("machine")),
            (mapping.area, fields.get("work_area")),
            (mapping.category, fields.get("category")),
            (mapping.team_id, report.team_id if report else None),
            (mapping.shift_id, report.shift_id if report else None),
        ]
        if all(not key or key == value for key, value in conditions):
            target_id = mapping.backup_id if backup else mapping.supervisor_id
            user = db.get(User, target_id) if target_id else None
            if user and user.active and department_id in department_ids(db, user, "review"):
                candidates.append((sum(bool(key) for key, _ in conditions), target_id))
    if candidates:
        return sorted(candidates, reverse=True)[0][1]
    memberships = db.scalars(
        select(DepartmentMembership)
        .join(User, User.id == DepartmentMembership.user_id)
        .where(
            DepartmentMembership.department_id == department_id,
            DepartmentMembership.active.is_(True),
            User.active.is_(True),
            User.role == "supervisor",
        )
    )
    for membership in memberships:
        if (membership.backup if backup else membership.primary) and "review" in membership.permissions:
            return membership.user_id
    return None


def create_alert(
    db: Session,
    actor: User,
    department_id: str,
    title: str,
    report_id=None,
    task_id=None,
    immediate=False,
    client_request_id=None,
):
    rule = db.scalar(
        select(EscalationRule).where(
            EscalationRule.department_id == department_id, EscalationRule.active.is_(True)
        )
    )
    target = responsible(db, department_id, report_id)
    item = Alert(
        organization_id=actor.organization_id,
        department_id=department_id,
        report_id=report_id,
        task_id=task_id,
        title=title,
        immediate=immediate,
        assigned_to=target,
        next_escalation=now() + timedelta(minutes=rule.acknowledge_minutes if rule else 10),
    )
    db.add(item)
    db.flush()
    db.add(
        AlertHistory(
            organization_id=actor.organization_id,
            alert_id=item.id,
            actor_id=actor.id,
            action="created",
            detail={"assigned_to": target, "immediate": immediate, "client_request_id": client_request_id},
        )
    )
    targets = (
        [target]
        if target
        else list(
            db.scalars(
                select(User.id).where(
                    User.organization_id == actor.organization_id,
                    User.role == "organization",
                    User.active.is_(True),
                )
            )
        )
    )
    for recipient in targets:
        email_alert(db, item, rule, recipient, "created")
        notify(
            db,
            actor.organization_id,
            recipient,
            f"alert:{item.id}:created",
            "Critical concern requires response",
            title,
            f"/workspace/alerts/{item.id}",
            "critical",
        )
    audit(
        db,
        actor,
        actor.organization_id,
        "alert.created",
        "alert",
        item.id,
        after={"assigned_to": target, "immediate": immediate},
    )
    return item


def alert_query(db: Session, user: User):
    query = select(Alert).where(
        Alert.organization_id == user.organization_id, Alert.department_id.in_(department_ids(db, user))
    )
    if user.role == "worker":
        query = query.where(
            or_(
                Alert.report_id.in_(select(Report.id).where(Report.author_id == user.id)),
                Alert.id.in_(
                    select(AlertHistory.alert_id).where(
                        AlertHistory.actor_id == user.id, AlertHistory.action == "created"
                    )
                ),
            )
        )
    return query


def accessible_alert(db: Session, user: User, record_id: str):
    item = db.scalar(alert_query(db, user).where(Alert.id == record_id))
    if not item:
        fail(404, "Alert not found.")
    return item


def escalate_due(db: Session):
    for alert in db.scalars(
        select(Alert)
        .where(Alert.status == "new", Alert.next_escalation <= now())
        .with_for_update(skip_locked=True)
    ):
        rule = db.scalar(
            select(EscalationRule).where(
                EscalationRule.department_id == alert.department_id, EscalationRule.active.is_(True)
            )
        )
        target = (
            responsible(db, alert.department_id, alert.report_id, backup=True)
            if alert.escalation_level == 0
            else (rule.escalation_recipient_id if rule else None)
        )
        recipients = (
            [target]
            if target and db.get(User, target).active
            else list(
                db.scalars(
                    select(User.id).where(
                        User.organization_id == alert.organization_id,
                        User.role == "organization",
                        User.active.is_(True),
                    )
                )
            )
        )
        alert.escalation_level += 1
        alert.assigned_to = target or (recipients[0] if recipients else None)
        alert.next_escalation = (
            now() + timedelta(minutes=rule.backup_minutes if rule else 10)
            if alert.escalation_level < 2
            else None
        )
        db.add(
            AlertHistory(
                organization_id=alert.organization_id,
                alert_id=alert.id,
                action="escalated",
                detail={"level": alert.escalation_level, "recipients": recipients},
            )
        )
        for recipient in recipients:
            email_alert(db, alert, rule, recipient, f"escalation:{alert.escalation_level}")
            notify(
                db,
                alert.organization_id,
                recipient,
                f"alert:{alert.id}:escalation:{alert.escalation_level}",
                "Unacknowledged critical concern",
                alert.title,
                f"/workspace/alerts/{alert.id}",
                "critical",
            )
        audit(
            db,
            None,
            alert.organization_id,
            "alert.escalated",
            "alert",
            alert.id,
            after={"level": alert.escalation_level, "recipients": recipients},
        )
