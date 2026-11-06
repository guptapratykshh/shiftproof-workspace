from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import (
    Alert,
    AuditLog,
    Conflict,
    Department,
    DepartmentMembership,
    Handover,
    HandoverItem,
    HandoverItemAcknowledgement,
    HandoverRecipient,
    HandoverVersion,
    Organization,
    Report,
    Shift,
    ShiftAssignment,
    Takeover,
    Team,
    Task,
    User,
)
from ..schemas import Input
from ..security import current_user, department_ids, fail, require_department, scoped
from ..services.common import record_dict
from ..services.handovers import shift_window
from ..services.tasks import recipients, task_query

router = APIRouter(tags=["Workspace context"])


@router.get("/workspace/context")
def context(
    department_id: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    allowed = department_ids(db, user)
    if department_id:
        require_department(db, user, department_id)
        allowed = [department_id]
    org = db.get(Organization, user.organization_id)
    local = now().astimezone(ZoneInfo(org.timezone))
    assignments = list(
        db.scalars(
            select(ShiftAssignment).where(
                ShiftAssignment.user_id == user.id,
                ShiftAssignment.active.is_(True),
                ShiftAssignment.department_id.in_(allowed),
            )
        )
    )
    active_shifts = []
    for shift in db.scalars(select(Shift).where(Shift.organization_id == org.id, Shift.active.is_(True))):
        for day in (local.date() - timedelta(days=1), local.date()):
            if day.weekday() not in shift.days:
                continue
            start, end = shift_window(org, shift, day.isoformat())
            if start <= local < end and (
                user.role != "worker"
                or any(
                    a.shift_id == shift.id
                    and a.starts_on <= day.isoformat()
                    and (not a.ends_on or a.ends_on >= day.isoformat())
                    for a in assignments
                )
            ):
                active_shifts.append(
                    {
                        "id": shift.id,
                        "name": shift.name,
                        "starts_at": start,
                        "ends_at": end,
                        "shift_date": day.isoformat(),
                    }
                )
    attention = []

    def add(kind, item, title, reason, rank, href, responsible=None):
        attention.append(
            {
                "kind": kind,
                "id": item.id,
                "department_id": getattr(item, "department_id", None),
                "title": title,
                "reason": reason,
                "status": getattr(item, "status", "pending"),
                "rank": rank,
                "created_at": item.created_at,
                "responsible": responsible,
                "href": href,
            }
        )

    tasks = db.scalars(task_query(db, user)).all()
    for task in tasks:
        if task.department_id not in allowed or task.status == "closed":
            continue
        reason = (
            "Completion awaits approval"
            if task.status == "completed" and task.verification_required
            else "Work is blocked"
            if task.status == "blocked"
            else "Deadline has passed"
            if task.deadline and task.deadline < now()
            else None
        )
        if reason:
            owners = [db.get(User, person).name for person in recipients(db, task)]
            add(
                "task",
                task,
                task.title,
                reason,
                2 if task.critical else 4 if task.status == "blocked" else 5,
                f"/workspace/tasks/{task.id}",
                ", ".join(owners),
            )
    if user.role != "worker":
        for alert in db.scalars(
            select(Alert).where(
                Alert.organization_id == org.id, Alert.department_id.in_(allowed), Alert.status != "resolved"
            )
        ):
            add(
                "alert",
                alert,
                alert.title,
                "Immediate safety concern" if alert.immediate else "Critical response required",
                0 if alert.immediate else 1,
                f"/workspace/alerts/{alert.id}",
            )
        for conflict in db.scalars(
            select(Conflict).where(
                Conflict.organization_id == org.id,
                Conflict.department_id.in_(allowed),
                Conflict.status != "resolved",
            )
        ):
            add(
                "conflict",
                conflict,
                conflict.title,
                "Related reports need a decision",
                3,
                f"/workspace/conflicts/{conflict.id}",
            )
        for report in db.scalars(
            select(Report).where(
                Report.organization_id == org.id,
                Report.department_id.in_(allowed),
                Report.needs_attention.is_(True),
                Report.resolved_at.is_(None),
            )
        ):
            add(
                "report",
                report,
                f"{report.category.title()} report",
                "Review uncertainty, source and required evidence",
                2 if report.immediate_safety else 6,
                f"/workspace/reports/{report.id}",
                db.get(User, report.author_id).name,
            )
    receipts = db.scalars(select(HandoverRecipient).where(HandoverRecipient.user_id == user.id)).all()
    for receipt in receipts:
        version = db.get(HandoverVersion, receipt.version_id)
        handover = db.get(Handover, version.handover_id)
        if handover.department_id not in allowed or version.number != handover.latest_version:
            continue
        pending_critical = any(
            not db.scalar(
                select(HandoverItemAcknowledgement.id).where(
                    HandoverItemAcknowledgement.item_id == item.id,
                    HandoverItemAcknowledgement.user_id == user.id,
                )
            )
            for item in db.scalars(
                select(HandoverItem).where(
                    HandoverItem.version_id == version.id, HandoverItem.critical.is_(True)
                )
            )
        )
        if pending_critical or not receipt.acknowledged_at:
            add(
                "handover",
                handover,
                f"Handover version {version.number}",
                "Critical items await receipt" if pending_critical else "Overall receipt is pending",
                2 if pending_critical else 6,
                f"/workspace/handovers/{handover.id}",
            )
    takeovers = (
        [
            record_dict(item)
            for item in db.scalars(
                select(Takeover).where(
                    Takeover.user_id == user.id, Takeover.expires_at > now(), Takeover.revoked_at.is_(None)
                )
            )
        ]
        if user.role == "organization"
        else []
    )
    return {
        "shifts": active_shifts,
        "attention": sorted(attention, key=lambda item: (item["rank"], item["created_at"])),
        "takeovers": takeovers,
        "as_of": now(),
    }


class Orientation(Input):
    step: int = Field(ge=1, le=5)
    skipped: list[int] | None = None


@router.put("/orientation")
def orientation(values: Orientation, user: User = Depends(current_user)):
    if user.role != "supervisor":
        fail(403, "Supervisor orientation is only available to supervisors.")
    profile = {**user.profile, "orientation_step": str(values.step)}
    if values.skipped is not None:
        profile["orientation_skipped"] = values.skipped
    user.profile = profile
    return {"step": values.step, "skipped": profile.get("orientation_skipped", [])}


@router.get("/departments/{record_id}/overview")
def department_overview(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    require_department(db, user, record_id)
    if user.role == "worker":
        fail(403, "Department administration is for supervisors and administrators.")
    department = scoped(db, Department, record_id, user)
    people = []
    for membership in db.scalars(
        select(DepartmentMembership).where(
            DepartmentMembership.department_id == record_id, DepartmentMembership.active.is_(True)
        )
    ):
        person = db.get(User, membership.user_id)
        people.append(
            {
                "id": person.id,
                "name": person.name,
                "role": person.role,
                "active": person.active,
                "membership": record_dict(membership),
            }
        )
    activity = [
        record_dict(item, {"before", "after", "purpose"})
        for item in db.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == user.organization_id, AuditLog.entity_id == record_id)
            .order_by(AuditLog.created_at.desc())
            .limit(30)
        )
    ]
    return {
        **record_dict(department),
        "teams": [
            record_dict(team) for team in db.scalars(select(Team).where(Team.department_id == record_id))
        ],
        "people": people,
        "activity": activity,
    }


@router.get("/teams/{record_id}/overview")
def team_overview(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    from ..models import TeamMembership

    team = scoped(db, Team, record_id, user)
    require_department(db, user, team.department_id)
    if user.role == "worker":
        fail(403, "Team administration is for supervisors and administrators.")
    members = list(
        db.scalars(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(TeamMembership.team_id == team.id, TeamMembership.active.is_(True))
        )
    )
    tasks = list(db.scalars(task_query(db, user).where(Task.team_id == team.id)))
    supervisors = list(
        db.scalars(
            select(User)
            .join(DepartmentMembership, DepartmentMembership.user_id == User.id)
            .where(
                DepartmentMembership.department_id == team.department_id,
                DepartmentMembership.active.is_(True),
                User.role == "supervisor",
            )
        )
    )
    return {
        **record_dict(team),
        "people": [record_dict(person) for person in members],
        "supervisors": [record_dict(person) for person in supervisors],
        "tasks": [record_dict(task) for task in tasks],
    }


@router.get("/supervisors/{record_id}/overview")
def supervisor_overview(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    from ..security import admin
    from ..models import ResponsibilityMapping

    admin(user)
    person = scoped(db, User, record_id, user)
    if person.role not in {"supervisor", "organization"}:
        fail(404, "Supervisor not found.")
    return {
        **record_dict(person),
        "departments": [
            record_dict(m)
            for m in db.scalars(
                select(DepartmentMembership).where(
                    DepartmentMembership.user_id == person.id, DepartmentMembership.active.is_(True)
                )
            )
        ],
        "shifts": [
            record_dict(a)
            for a in db.scalars(select(ShiftAssignment).where(ShiftAssignment.user_id == person.id))
        ],
        "responsibilities": [
            record_dict(r)
            for r in db.scalars(
                select(ResponsibilityMapping).where(
                    (ResponsibilityMapping.supervisor_id == person.id)
                    | (ResponsibilityMapping.backup_id == person.id)
                )
            )
        ],
        "activity": [
            record_dict(event, {"before", "after", "purpose"})
            for event in db.scalars(
                select(AuditLog)
                .where(
                    AuditLog.organization_id == user.organization_id,
                    (AuditLog.actor_id == person.id) | (AuditLog.entity_id == person.id),
                )
                .order_by(AuditLog.created_at.desc())
                .limit(50)
            )
        ],
    }
