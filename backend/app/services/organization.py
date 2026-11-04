from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import now
from ..models import Department, DepartmentMembership, DeviceSession, Organization, Shift, Team, User
from ..schemas import InviteInput, MembershipInput
from ..security import admin, fail, scoped
from .authentication import issue_invitation
from .common import audit, record_dict


def onboarding_status(db: Session, organization: Organization):
    org_id = organization.id
    count = lambda model: (
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.organization_id == org_id, model.active.is_(True))
        )
        or 0
    )
    supervisors = (
        db.scalar(
            select(func.count())
            .select_from(DepartmentMembership)
            .join(User, User.id == DepartmentMembership.user_id)
            .where(
                DepartmentMembership.organization_id == org_id,
                DepartmentMembership.active.is_(True),
                DepartmentMembership.primary.is_(True),
                User.role == "supervisor",
                User.active.is_(True),
            )
        )
        or 0
    )
    complete = [
        bool(organization.settings.get("profile_completed")),
        count(Department) > 0,
        count(Team) > 0,
        count(Shift) > 0,
        supervisors > 0,
    ]
    names = [
        "Organization profile",
        "Departments",
        "Teams and production lines",
        "Shift structure",
        "Active primary supervisors",
        "Responsibility mapping",
        "Escalation rules",
        "Privacy policy",
        "Final review",
    ]
    steps = [
        {
            "number": i + 1,
            "name": name,
            "required": i < 5,
            "status": ("completed" if complete[i] else "pending")
            if i < 5
            else (
                "skipped"
                if i + 1 in organization.onboarding_skipped
                else "completed"
                if organization.settings.get(f"step_{i + 1}")
                else "pending"
            ),
        }
        for i, name in enumerate(names)
    ]
    return {
        "steps": steps,
        "can_activate": all(complete),
        "active": organization.active,
        "current_step": organization.onboarding_step,
    }


def replace_supervisor_memberships(
    db: Session, actor: User, supervisor: User, memberships: list[MembershipInput]
):
    admin(actor)
    if supervisor.role != "supervisor" or not memberships:
        fail(422, "Supervisors need at least one assigned department.")
    if len({item.department_id for item in memberships}) != len(memberships):
        fail(422, "Department assignments must be unique.")
    existing = db.scalars(
        select(DepartmentMembership).where(DepartmentMembership.user_id == supervisor.id)
    ).all()
    before = [record_dict(item) for item in existing]
    for item in existing:
        item.active = False
    for values in memberships:
        department = scoped(db, Department, values.department_id, actor)
        if not department.active:
            fail(409, "Cannot assign an inactive department.")
        if values.primary and values.backup:
            fail(422, "Choose primary or backup, not both.")
        if values.primary and not {"review", "manage", "publish"}.issubset(values.permissions):
            fail(422, "Primary alert supervisors need manage, review and publish permissions.")
        if values.primary:
            other = db.scalar(
                select(DepartmentMembership)
                .join(User, User.id == DepartmentMembership.user_id)
                .where(
                    DepartmentMembership.department_id == department.id,
                    DepartmentMembership.user_id != supervisor.id,
                    DepartmentMembership.primary.is_(True),
                    DepartmentMembership.active.is_(True),
                    User.role == "supervisor",
                )
            )
            if other:
                fail(
                    409,
                    "This department already has a primary supervisor. Update the current designation first.",
                )
        membership = next((item for item in existing if item.department_id == department.id), None)
        if not membership:
            membership = DepartmentMembership(
                organization_id=actor.organization_id, user_id=supervisor.id, department_id=department.id
            )
            db.add(membership)
        membership.primary, membership.backup = values.primary, values.backup
        membership.permissions = sorted(set(values.permissions) | {"view"})
        membership.active = True
    audit(
        db,
        actor,
        actor.organization_id,
        "supervisor.permissions.changed",
        "user",
        supervisor.id,
        {"memberships": before},
        {"memberships": [item.model_dump() for item in memberships]},
    )


def invite(db: Session, actor: User, values: InviteInput):
    admin(actor)
    email = str(values.email).lower()
    if db.scalar(select(User).where(User.organization_id == actor.organization_id, User.email == email)):
        fail(409, "This person already has an account in your organization.")
    if values.role == "organization" and db.scalar(
        select(User.id).where(User.role == "organization", User.email == email)
    ):
        fail(409, "This administrator email already belongs to an organization.")
    user = User(
        organization_id=actor.organization_id,
        role=values.role,
        name=values.name,
        email=email,
        phone=values.phone,
    )
    db.add(user)
    db.flush()
    if values.role == "supervisor":
        replace_supervisor_memberships(db, actor, user, values.departments)
    issue_invitation(db, actor, user)
    audit(
        db,
        actor,
        actor.organization_id,
        "user.invited",
        "user",
        user.id,
        after={"role": user.role, "email": user.email},
    )
    return record_dict(user)


def change_account_state(db: Session, actor: User, target: User, active: bool, reason: str):
    admin(actor)
    # Serialize invariant checks across both PostgreSQL and local SQLite writers.
    db.execute(update(Organization).where(Organization.id == actor.organization_id).values(updated_at=now()))
    if not active and target.role == "organization" and target.active:
        remaining = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.organization_id == actor.organization_id,
                User.role == "organization",
                User.active.is_(True),
            )
        )
        if remaining <= 1:
            fail(409, "At least one active organization administrator must remain.")
    if active and not target.verified:
        fail(409, "The person must activate their own account first.")
    target.active = active
    if not active:
        db.execute(update(DeviceSession).where(DeviceSession.user_id == target.id).values(revoked=True))
    audit(
        db,
        actor,
        actor.organization_id,
        "user.state.changed",
        "user",
        target.id,
        after={"active": active},
        purpose=reason,
    )
    return record_dict(target)
