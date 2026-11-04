from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import (
    Department,
    DepartmentMembership,
    EscalationRule,
    FileAsset,
    Organization,
    OrganizationPolicy,
    ResponsibilityMapping,
    Shift,
    Takeover,
    Team,
    User,
)
from ..schemas import (
    DepartmentInput,
    Input,
    InviteInput,
    MembershipInput,
    OrganizationInput,
    ShiftInput,
    StateInput,
    TeamInput,
)
from ..security import admin, current_user, department_ids, fail, scoped
from ..services.common import audit, record_dict
from ..services import organization as service

router = APIRouter(tags=["Organization"])


@router.get("/organization")
def organization(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return record_dict(db.get(Organization, user.organization_id))


@router.put("/organization")
def update_organization(
    values: OrganizationInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    admin(user)
    org = db.get(Organization, user.organization_id)
    before = record_dict(org)
    if values.logo_asset_id:
        asset = scoped(db, FileAsset, values.logo_asset_id, user)
        if asset.kind not in {"logo", "photo"} or asset.deleted_at or asset.owner_id != user.id:
            fail(422, "The logo must be an image.")
    org.name, org.industry, org.contact, org.timezone = (
        values.name,
        values.industry,
        values.contact,
        values.timezone,
    )
    org.settings = {
        **org.settings,
        "contact_email": str(values.contact_email),
        "address": values.address,
        "logo_asset_id": values.logo_asset_id,
        "profile_completed": True,
    }
    org.onboarding_step = max(org.onboarding_step, 2)
    audit(db, user, org.id, "organization.updated", "organization", org.id, before, record_dict(org))
    return record_dict(org)


@router.get("/organization/onboarding")
def onboarding(user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    return service.onboarding_status(db, db.get(Organization, user.organization_id))


class OnboardingStep(Input):
    step: int = Field(ge=1, le=9)
    skip: bool = False


@router.post("/organization/onboarding")
def save_step(values: OnboardingStep, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    org = db.get(Organization, user.organization_id)
    if values.skip and values.step <= 5:
        fail(422, "The first five onboarding steps are required.")
    if values.skip:
        org.onboarding_skipped = sorted(set(org.onboarding_skipped + [values.step]))
    else:
        org.settings = {**org.settings, f"step_{values.step}": True}
    org.onboarding_step = min(values.step + 1, 9)
    return service.onboarding_status(db, org)


@router.post("/organization/activate")
def activate_organization(user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    org = db.get(Organization, user.organization_id)
    if not service.onboarding_status(db, org)["can_activate"]:
        fail(
            409,
            "Complete the first five steps, including an active primary supervisor, before activating operations.",
        )
    org.active = True
    audit(db, user, org.id, "organization.activated", "organization", org.id)
    return {"status": "active"}


@router.get("/departments")
def departments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        record_dict(item)
        for item in db.scalars(
            select(Department)
            .where(
                Department.organization_id == user.organization_id,
                Department.id.in_(department_ids(db, user)),
            )
            .order_by(Department.name)
        )
    ]


def unique_name(db, model, values, user, record_id=None):
    query = select(model.id).where(
        model.organization_id == user.organization_id, func.lower(model.name) == values.name.strip().lower()
    )
    if model is Team:
        query = query.where(Team.department_id == values.department_id)
    if record_id:
        query = query.where(model.id != record_id)
    if db.scalar(query):
        fail(
            409,
            "This name is already in use, including inactive records. Edit or reactivate the existing record.",
        )
    values.name = values.name.strip()


@router.post("/departments", status_code=201)
def create_department(
    values: DepartmentInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    admin(user)
    unique_name(db, Department, values, user)
    item = Department(organization_id=user.organization_id, **values.model_dump())
    db.add(item)
    db.flush()
    audit(
        db, user, user.organization_id, "department.created", "department", item.id, after=record_dict(item)
    )
    return record_dict(item)


@router.put("/departments/{record_id}")
def update_department(
    record_id: str, values: DepartmentInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    admin(user)
    item = scoped(db, Department, record_id, user)
    unique_name(db, Department, values, user, record_id)
    before = record_dict(item)
    for key, value in values.model_dump().items():
        setattr(item, key, value)
    audit(
        db, user, user.organization_id, "department.updated", "department", item.id, before, record_dict(item)
    )
    return record_dict(item)


@router.get("/teams")
def teams(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        record_dict(item)
        for item in db.scalars(
            select(Team)
            .where(
                Team.organization_id == user.organization_id, Team.department_id.in_(department_ids(db, user))
            )
            .order_by(Team.name)
        )
    ]


@router.post("/teams", status_code=201)
def create_team(values: TeamInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    parent = scoped(db, Department, values.department_id, user)
    if not parent.active:
        fail(409, "Choose an active department.")
    unique_name(db, Team, values, user)
    item = Team(organization_id=user.organization_id, **values.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, user.organization_id, "team.created", "team", item.id, after=record_dict(item))
    return record_dict(item)


@router.put("/teams/{record_id}")
def update_team(
    record_id: str, values: TeamInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    admin(user)
    item = scoped(db, Team, record_id, user)
    unique_name(db, Team, values, user, record_id)
    if item.department_id != values.department_id:
        fail(422, "A team's department cannot change; create a new team to preserve history.")
    before = record_dict(item)
    for key, value in values.model_dump().items():
        setattr(item, key, value)
    audit(db, user, user.organization_id, "team.updated", "team", item.id, before, record_dict(item))
    return record_dict(item)


@router.get("/shifts")
def shifts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        record_dict(item)
        for item in db.scalars(
            select(Shift).where(Shift.organization_id == user.organization_id).order_by(Shift.starts_at)
        )
    ]


def shift_warnings(db: Session, item: Shift):
    minutes = lambda value: int(value[:2]) * 60 + int(value[3:])

    def covers(shift):
        start, end = minutes(shift.starts_at), minutes(shift.ends_at)
        duration = (end - start) % 1440
        return {(day * 1440 + start + minute) % 10080 for day in shift.days for minute in range(duration)}

    occupied = covers(item)
    other_shifts = db.scalars(
        select(Shift).where(
            Shift.organization_id == item.organization_id, Shift.id != item.id, Shift.active.is_(True)
        )
    ).all()
    return [
        f"Overlaps with {other.name}. Check supervisor and worker coverage."
        for other in other_shifts
        if occupied & covers(other)
    ]


@router.post("/shifts", status_code=201)
def create_shift(values: ShiftInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    item = Shift(organization_id=user.organization_id, **values.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, user.organization_id, "shift.created", "shift", item.id, after=record_dict(item))
    return {**record_dict(item), "warnings": shift_warnings(db, item)}


@router.put("/shifts/{record_id}")
def update_shift(
    record_id: str, values: ShiftInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    admin(user)
    item = scoped(db, Shift, record_id, user)
    before = record_dict(item)
    for key, value in values.model_dump().items():
        setattr(item, key, value)
    audit(db, user, user.organization_id, "shift.updated", "shift", item.id, before, record_dict(item))
    return {**record_dict(item), "warnings": shift_warnings(db, item)}


@router.get("/supervisors")
def supervisors(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "worker":
        fail(403, "Supervisor directory access is not available to workers.")
    query = select(User).where(
        User.organization_id == user.organization_id, User.role.in_(["supervisor", "organization"])
    )
    if user.role != "organization":
        query = query.where(
            User.id.in_(
                select(DepartmentMembership.user_id).where(
                    DepartmentMembership.department_id.in_(department_ids(db, user)),
                    DepartmentMembership.active.is_(True),
                )
            )
        )
    result = []
    for item in db.scalars(query):
        memberships = db.scalars(
            select(DepartmentMembership).where(
                DepartmentMembership.user_id == item.id, DepartmentMembership.active.is_(True)
            )
        ).all()
        result.append({**record_dict(item), "departments": [record_dict(m) for m in memberships]})
    return result


@router.post("/supervisors/invite", status_code=201)
def invite(values: InviteInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.invite(db, user, values)


@router.post("/supervisors/{record_id}/resend")
def resend_invitation(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..services.authentication import issue_invitation

    admin(user)
    target = scoped(db, User, record_id, user)
    if target.verified or target.role == "worker":
        fail(409, "Use account recovery for activated accounts.")
    issue_invitation(db, user, target)
    audit(db, user, user.organization_id, "invitation.resent", "user", target.id)
    return {"status": "invited"}


class SupervisorPermissions(Input):
    departments: list[MembershipInput]


@router.put("/supervisors/{record_id}/permissions")
def permissions(
    record_id: str,
    values: SupervisorPermissions,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    supervisor = scoped(db, User, record_id, user)
    service.replace_supervisor_memberships(db, user, supervisor, values.departments)
    return {"status": "updated"}


@router.put("/users/{record_id}/state")
def account_state(
    record_id: str, values: StateInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return service.change_account_state(
        db, user, scoped(db, User, record_id, user), values.active, values.reason
    )


class TakeoverInput(Input):
    department_id: str
    reason: str = Field(min_length=10, max_length=2000)
    hours: int = Field(default=8, ge=1, le=24)


@router.get("/takeovers")
def takeovers(user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    return [
        record_dict(item)
        for item in db.scalars(
            select(Takeover).where(
                Takeover.organization_id == user.organization_id,
                Takeover.revoked_at.is_(None),
                Takeover.expires_at > now(),
            )
        )
    ]


@router.post("/takeovers", status_code=201)
def start_takeover(values: TakeoverInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    scoped(db, Department, values.department_id, user)
    item = Takeover(
        organization_id=user.organization_id,
        user_id=user.id,
        department_id=values.department_id,
        reason=values.reason,
        expires_at=now() + timedelta(hours=values.hours),
    )
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        user.organization_id,
        "takeover.started",
        "takeover",
        item.id,
        after=record_dict(item),
        purpose=values.reason,
    )
    return record_dict(item)


@router.delete("/takeovers/{record_id}")
def end_takeover(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    item = scoped(db, Takeover, record_id, user)
    item.revoked_at = now()
    audit(db, user, user.organization_id, "takeover.ended", "takeover", item.id)
    return {"status": "ended"}


DEFAULT_POLICIES = {
    "privacy": {
        "recording_consent_required": True,
        "admin_report_access": False,
        "admin_recording_access": False,
        "audio_retention_days": 30,
        "transcript_retention_days": 365,
        "evidence_retention_days": 365,
        "photos_allowed": True,
        "videos_allowed": True,
    },
    "security": {"idle_minutes": 60},
    "operations": {
        "deadline_reminder_minutes": 30,
        "handover_reminder_minutes": 15,
        "evidence_required_categories": [],
    },
}


@router.get("/policies")
def policies(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stored = {
        p.key: p.value
        for p in db.scalars(
            select(OrganizationPolicy).where(OrganizationPolicy.organization_id == user.organization_id)
        )
    }
    return {key: {**default, **stored.get(key, {})} for key, default in DEFAULT_POLICIES.items()}


class PolicyInput(Input):
    value: dict
    reason: str = Field(min_length=5, max_length=2000)


@router.put("/policies/{key}")
def update_policy(
    key: str, values: PolicyInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    admin(user)
    defaults = DEFAULT_POLICIES.get(key)
    if defaults is None or any(name not in defaults for name in values.value):
        fail(422, "Unknown policy settings.")
    for name, value in values.value.items():
        default = defaults[name]
        if type(value) is not type(default):
            fail(422, f"Invalid value for {name}.")
        if isinstance(value, int) and not isinstance(value, bool) and not 1 <= value <= 3650:
            fail(422, f"{name} must be between 1 and 3650.")
    if key == "privacy" and values.value.get("recording_consent_required") is False:
        fail(422, "Recording consent cannot be disabled.")
    item = db.scalar(
        select(OrganizationPolicy).where(
            OrganizationPolicy.organization_id == user.organization_id, OrganizationPolicy.key == key
        )
    )
    if not item:
        item = OrganizationPolicy(organization_id=user.organization_id, key=key, value={})
        db.add(item)
    before = item.value
    item.value = {**defaults, **item.value, **values.value}
    db.flush()
    audit(
        db, user, user.organization_id, "policy.updated", "policy", item.id, before, item.value, values.reason
    )
    return item.value


class MappingInput(Input):
    department_id: str
    supervisor_id: str
    backup_id: str | None = None
    team_id: str | None = None
    shift_id: str | None = None
    machine: str = Field(default="", max_length=160)
    area: str = Field(default="", max_length=160)
    category: str = Field(default="", max_length=60)


@router.get("/responsibilities")
def responsibilities(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        record_dict(item)
        for item in db.scalars(
            select(ResponsibilityMapping).where(
                ResponsibilityMapping.organization_id == user.organization_id,
                ResponsibilityMapping.department_id.in_(department_ids(db, user)),
            )
        )
    ]


@router.post("/responsibilities", status_code=201)
def create_mapping(values: MappingInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    scoped(db, Department, values.department_id, user)
    for target in [values.supervisor_id, values.backup_id]:
        if target:
            person = scoped(db, User, target, user)
            if (
                person.role != "supervisor"
                or not person.active
                or values.department_id not in department_ids(db, person, "review")
            ):
                fail(422, "Choose an active supervisor with review permission in this department.")
    if values.team_id and scoped(db, Team, values.team_id, user).department_id != values.department_id:
        fail(422, "Team belongs to a different department.")
    if values.shift_id:
        scoped(db, Shift, values.shift_id, user)
    item = ResponsibilityMapping(organization_id=user.organization_id, **values.model_dump())
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        user.organization_id,
        "responsibility.created",
        "responsibility",
        item.id,
        after=record_dict(item),
    )
    return record_dict(item)


@router.delete("/responsibilities/{record_id}")
def delete_mapping(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    item = scoped(db, ResponsibilityMapping, record_id, user)
    audit(
        db,
        user,
        user.organization_id,
        "responsibility.removed",
        "responsibility",
        item.id,
        before=record_dict(item),
    )
    db.delete(item)
    return {"status": "removed"}


class EscalationInput(Input):
    department_id: str
    acknowledge_minutes: int = Field(default=10, ge=1, le=240)
    backup_minutes: int = Field(default=10, ge=1, le=240)
    escalation_recipient_id: str | None = None
    channels: list[Literal["in_app", "email"]] = Field(default_factory=lambda: ["in_app"])
    active: bool = True


@router.get("/escalation-rules")
def escalation_rules(user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin(user)
    return [
        record_dict(item)
        for item in db.scalars(
            select(EscalationRule).where(EscalationRule.organization_id == user.organization_id)
        )
    ]


@router.put("/escalation-rules")
def set_escalation(
    values: EscalationInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    admin(user)
    scoped(db, Department, values.department_id, user)
    if values.escalation_recipient_id:
        target = scoped(db, User, values.escalation_recipient_id, user)
        if not target.active or target.role != "organization":
            fail(422, "Choose an active organization administrator for escalation.")
    item = db.scalar(select(EscalationRule).where(EscalationRule.department_id == values.department_id))
    before = record_dict(item) if item else {}
    if not item:
        item = EscalationRule(organization_id=user.organization_id, **values.model_dump())
        db.add(item)
    else:
        for key, value in values.model_dump().items():
            setattr(item, key, value)
    db.flush()
    audit(
        db,
        user,
        user.organization_id,
        "escalation_rule.updated",
        "escalation_rule",
        item.id,
        before,
        record_dict(item),
    )
    return record_dict(item)
