from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db, now
from ..models import (
    DepartmentMembership,
    Shift,
    ShiftAssignment,
    TeamMembership,
    User,
    WorkerAvailability,
    WorkerSkill,
)
from ..schemas import Input, WorkerInput
from ..security import admin, current_user, fail, scoped
from ..services.authentication import issue_invitation
from ..services.common import audit, record_dict
from ..services import workforce as service

router = APIRouter(tags=["Workforce"])


@router.get("/workers")
def workers(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    department_id: str | None = None,
    team_id: str | None = None,
    shift_id: str | None = None,
    active: bool | None = None,
    q: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    query = service.visible_workers_query(db, user)
    if department_id:
        query = query.where(
            User.id.in_(
                select(DepartmentMembership.user_id).where(
                    DepartmentMembership.department_id == department_id, DepartmentMembership.active.is_(True)
                )
            )
        )
    if team_id:
        query = query.where(
            User.id.in_(
                select(TeamMembership.user_id).where(
                    TeamMembership.team_id == team_id, TeamMembership.active.is_(True)
                )
            )
        )
    if shift_id:
        query = query.where(
            User.id.in_(
                select(ShiftAssignment.user_id).where(
                    ShiftAssignment.shift_id == shift_id, ShiftAssignment.active.is_(True)
                )
            )
        )
    if active is not None:
        query = query.where(User.active == active)
    if q:
        query = query.where(User.name.ilike(f"%{q[:100]}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            service.worker_detail(db, item)
            for item in db.scalars(query.order_by(User.name).offset((page - 1) * limit).limit(limit))
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("/workers", status_code=201)
def create_worker(values: WorkerInput, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    return service.save_worker(db, user, values)


@router.get("/workers/{record_id}")
def worker(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    item = db.scalar(service.visible_workers_query(db, user).where(User.id == record_id))
    if not item:
        fail(404, "Worker not found.")
    return service.worker_detail(db, item)


@router.put("/workers/{record_id}")
def update_worker(
    record_id: str, values: WorkerInput, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    return service.save_worker(db, user, values, scoped(db, User, record_id, user))


class PinReset(Input):
    identity_verified: bool
    verification_note: str = Field(min_length=10, max_length=2000)


@router.post("/workers/{record_id}/pin-reset")
def pin_reset(
    record_id: str, values: PinReset, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    target = scoped(db, User, record_id, user)
    if target.role != "worker" or not values.identity_verified:
        fail(422, "Verify the worker's identity before issuing a PIN reset link.")
    departments = db.scalars(
        select(DepartmentMembership).where(
            DepartmentMembership.user_id == target.id, DepartmentMembership.active.is_(True)
        )
    ).all()
    if not departments:
        admin(user)
    for membership in departments:
        service.require_workforce(db, user, membership.department_id)
    url = issue_invitation(db, user, target, "pin_reset")
    audit(
        db,
        user,
        user.organization_id,
        "worker.pin_reset.requested",
        "user",
        target.id,
        purpose=values.verification_note,
    )
    return {
        "activation_url": url,
        "message": "Give this private link to the verified worker. They choose their own PIN.",
    }


class AvailabilityInput(Input):
    starts_at: datetime
    ends_at: datetime
    status: str = Field(pattern="^(absent|unavailable|leave|available)$")
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def ordered(self):
        if not self.starts_at.tzinfo or not self.ends_at.tzinfo or self.ends_at <= self.starts_at:
            raise ValueError("Use timezone-aware times with the end after the start")
        return self


@router.post("/workers/{record_id}/availability", status_code=201)
def availability(
    record_id: str,
    values: AvailabilityInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    worker = scoped(db, User, record_id, user)
    if worker.role != "worker":
        fail(422, "Choose a worker account.")
    memberships = db.scalars(
        select(DepartmentMembership).where(
            DepartmentMembership.user_id == worker.id, DepartmentMembership.active.is_(True)
        )
    ).all()
    if not memberships:
        admin(user)
    for membership in memberships:
        service.require_workforce(db, user, membership.department_id)
    item = WorkerAvailability(
        organization_id=user.organization_id, user_id=worker.id, recorded_by=user.id, **values.model_dump()
    )
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        user.organization_id,
        "worker.availability.changed",
        "user",
        worker.id,
        after=record_dict(item),
    )
    return record_dict(item)


@router.put("/workers/{record_id}/availability/{availability_id}")
def update_availability(
    record_id: str,
    availability_id: str,
    values: AvailabilityInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    worker = scoped(db, User, record_id, user)
    item = scoped(db, WorkerAvailability, availability_id, user)
    if item.user_id != worker.id or worker.role != "worker":
        fail(404, "Availability record not found.")
    memberships = list(
        db.scalars(
            select(DepartmentMembership).where(
                DepartmentMembership.user_id == worker.id, DepartmentMembership.active.is_(True)
            )
        )
    )
    if not memberships:
        admin(user)
    for membership in memberships:
        service.require_workforce(db, user, membership.department_id)
    before = record_dict(item)
    for field, value in values.model_dump().items():
        setattr(item, field, value)
    item.recorded_by = user.id
    audit(
        db,
        user,
        user.organization_id,
        "worker.availability.corrected",
        "user",
        worker.id,
        before=before,
        after=record_dict(item),
        purpose=values.reason,
    )
    return record_dict(item)


class AssignmentInput(Input):
    user_id: str
    shift_id: str
    department_id: str
    starts_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ends_on: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("starts_on", "ends_on")
    @classmethod
    def real_date(cls, value):
        if value:
            date.fromisoformat(value)
        return value


class QualificationInput(Input):
    qualification: str = Field(default="", max_length=200)
    expires_on: date | None = None


@router.put("/workers/{record_id}/qualifications/{skill_id}")
def qualification(
    record_id: str,
    skill_id: str,
    values: QualificationInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    worker = scoped(db, User, record_id, user)
    memberships = db.scalars(
        select(DepartmentMembership).where(
            DepartmentMembership.user_id == worker.id, DepartmentMembership.active.is_(True)
        )
    ).all()
    if not memberships:
        admin(user)
    for membership in memberships:
        service.require_workforce(db, user, membership.department_id)
    item = scoped(db, WorkerSkill, skill_id, user)
    if item.user_id != worker.id:
        fail(404, "Qualification not found.")
    before = record_dict(item)
    item.qualification = values.qualification
    item.expires_on = values.expires_on.isoformat() if values.expires_on else None
    audit(
        db,
        user,
        user.organization_id,
        "worker.qualification.updated",
        "user",
        worker.id,
        before,
        record_dict(item),
    )
    return record_dict(item)


@router.get("/shift-assignments")
def shift_assignments(user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    from ..security import department_ids

    query = select(ShiftAssignment).where(
        ShiftAssignment.organization_id == user.organization_id,
        ShiftAssignment.department_id.in_(department_ids(db, user)),
    )
    if user.role == "worker":
        query = query.where(ShiftAssignment.user_id == user.id)
    return [record_dict(item) for item in db.scalars(query)]


@router.post("/shift-assignments", status_code=201)
def assign_shift(values: AssignmentInput, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    from ..security import department_ids

    service.require_workforce(db, user, values.department_id)
    target = scoped(db, User, values.user_id, user)
    shift = scoped(db, Shift, values.shift_id, user)
    if not shift.active or values.department_id not in department_ids(db, target):
        fail(422, "Choose an active shift and a person belonging to this department.")
    if values.ends_on and values.ends_on < values.starts_on:
        fail(422, "End date must follow start date.")
    item = ShiftAssignment(organization_id=user.organization_id, **values.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, user.organization_id, "shift.assigned", "user", target.id, after=record_dict(item))
    return record_dict(item)


@router.delete("/shift-assignments/{record_id}")
def end_assignment(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    item = scoped(db, ShiftAssignment, record_id, user)
    service.require_workforce(db, user, item.department_id)
    item.active = False
    item.ends_on = now().date().isoformat()
    audit(db, user, user.organization_id, "shift.assignment.ended", "shift_assignment", item.id)
    return {"status": "ended"}
