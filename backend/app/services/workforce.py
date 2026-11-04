from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import now
from ..models import (
    DepartmentMembership,
    Shift,
    ShiftAssignment,
    Skill,
    Task,
    TaskAssignment,
    Team,
    TeamMembership,
    User,
    WorkerAvailability,
    WorkerSkill,
)
from ..schemas import WorkerInput
from ..security import department_ids, fail, require_department, scoped, token
from .authentication import issue_invitation
from .common import audit, record_dict


def require_workforce(db: Session, actor: User, department_id: str):
    if actor.role == "organization":
        return
    require_department(db, actor, department_id, "workforce")


def visible_workers_query(db: Session, user: User):
    query = select(User).where(User.organization_id == user.organization_id, User.role == "worker")
    if user.role == "worker":
        return query.where(User.id == user.id)
    if user.role != "organization":
        query = query.where(
            User.id.in_(
                select(DepartmentMembership.user_id).where(
                    DepartmentMembership.department_id.in_(department_ids(db, user)),
                    DepartmentMembership.active.is_(True),
                )
            )
        )
    return query


def worker_detail(db: Session, worker: User):
    result = record_dict(worker)
    result["departments"] = [
        record_dict(item)
        for item in db.scalars(select(DepartmentMembership).where(DepartmentMembership.user_id == worker.id))
    ]
    result["teams"] = [
        record_dict(item)
        for item in db.scalars(select(TeamMembership).where(TeamMembership.user_id == worker.id))
    ]
    result["shifts"] = [
        record_dict(item)
        for item in db.scalars(select(ShiftAssignment).where(ShiftAssignment.user_id == worker.id))
    ]
    result["skills"] = [
        {**record_dict(item), "name": name}
        for item, name in db.execute(
            select(WorkerSkill, Skill.name).join(Skill).where(WorkerSkill.user_id == worker.id)
        )
    ]
    result["availability"] = [
        record_dict(item)
        for item in db.scalars(
            select(WorkerAvailability)
            .where(WorkerAvailability.user_id == worker.id)
            .order_by(WorkerAvailability.starts_at.desc())
            .limit(100)
        )
    ]
    return result


def save_worker(db: Session, actor: User, values: WorkerInput, worker: User | None = None):
    if actor.role not in {"organization", "supervisor"}:
        fail(403, "Workforce management access is required.")
    for department_id in values.department_ids:
        require_workforce(db, actor, department_id)
        require_department(db, actor, department_id, active=True)
    teams = [scoped(db, Team, team_id, actor) for team_id in values.team_ids]
    if any(not team.active or team.department_id not in values.department_ids for team in teams):
        fail(422, "Every selected team must be active and belong to a selected department.")
    if values.shift_id and not scoped(db, Shift, values.shift_id, actor).active:
        fail(422, "Choose an active shift.")
    is_new = worker is None
    if worker:
        if worker.role != "worker":
            fail(422, "This is not a worker account.")
        for membership in db.scalars(
            select(DepartmentMembership).where(
                DepartmentMembership.user_id == worker.id, DepartmentMembership.active.is_(True)
            )
        ):
            require_workforce(db, actor, membership.department_id)
    else:
        employee_code = values.employee_code or "EMP-" + token()[:8].upper().replace("_", "X").replace(
            "-", "Y"
        )
        if db.scalar(
            select(User.id).where(
                User.organization_id == actor.organization_id, User.employee_code == employee_code
            )
        ):
            fail(409, "This Employee ID is already in use.")
        worker = User(
            organization_id=actor.organization_id,
            role="worker",
            name=values.name,
            employee_code=employee_code,
        )
        db.add(worker)
        db.flush()
    before = record_dict(worker)
    worker.name, worker.phone, worker.profile = values.name, values.phone, values.profile
    if values.employee_code and values.employee_code != worker.employee_code:
        fail(422, "Employee IDs are stable. Update profile details without changing identity.")
    memberships = db.scalars(
        select(DepartmentMembership).where(DepartmentMembership.user_id == worker.id)
    ).all()
    removed = {m.department_id for m in memberships if m.active} - set(values.department_ids)
    if removed and db.scalar(
        select(Task.id)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(
            Task.department_id.in_(removed),
            Task.status != "closed",
            TaskAssignment.user_id == worker.id,
            TaskAssignment.ended_at.is_(None),
        )
        .limit(1)
    ):
        fail(409, "Reassign this worker's open tasks before removing their department access.")
    for membership in memberships:
        membership.active = membership.department_id in values.department_ids
        membership.primary = membership.department_id == values.primary_department_id
    for department_id in values.department_ids:
        if not any(item.department_id == department_id for item in memberships):
            db.add(
                DepartmentMembership(
                    organization_id=actor.organization_id,
                    user_id=worker.id,
                    department_id=department_id,
                    primary=department_id == values.primary_department_id,
                    permissions=["view"],
                )
            )
    team_memberships = db.scalars(select(TeamMembership).where(TeamMembership.user_id == worker.id)).all()
    for membership in team_memberships:
        membership.active = membership.team_id in values.team_ids
    for team_id in values.team_ids:
        if not any(item.team_id == team_id for item in team_memberships):
            db.add(TeamMembership(organization_id=actor.organization_id, user_id=worker.id, team_id=team_id))
    names = sorted(set(value.strip().lower() for value in values.skills if value.strip()))
    for owned, name in db.execute(
        select(WorkerSkill, Skill.name).join(Skill).where(WorkerSkill.user_id == worker.id)
    ):
        if name not in names:
            audit(
                db,
                actor,
                actor.organization_id,
                "worker.qualification.removed",
                "user",
                worker.id,
                before={**record_dict(owned), "name": name},
            )
            db.delete(owned)
    for name in names:
        skill = db.scalar(
            select(Skill).where(Skill.organization_id == actor.organization_id, Skill.name == name)
        )
        if not skill:
            skill = Skill(organization_id=actor.organization_id, name=name)
            db.add(skill)
            db.flush()
        if not db.scalar(
            select(WorkerSkill.id).where(WorkerSkill.user_id == worker.id, WorkerSkill.skill_id == skill.id)
        ):
            db.add(WorkerSkill(organization_id=actor.organization_id, user_id=worker.id, skill_id=skill.id))
    if values.shift_id:
        current = db.scalar(
            select(ShiftAssignment).where(
                ShiftAssignment.user_id == worker.id,
                ShiftAssignment.shift_id == values.shift_id,
                ShiftAssignment.active.is_(True),
            )
        )
        if not current:
            db.add(
                ShiftAssignment(
                    organization_id=actor.organization_id,
                    user_id=worker.id,
                    department_id=values.primary_department_id,
                    shift_id=values.shift_id,
                    starts_on=now().date().isoformat(),
                )
            )
    activation_url = issue_invitation(db, actor, worker, "worker_activation") if is_new else None
    db.flush()
    # Adding a member to a shared task cannot bypass qualification checks.
    for task in db.scalars(
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(
            TaskAssignment.team_id.in_(values.team_ids),
            TaskAssignment.ended_at.is_(None),
            Task.status != "closed",
        )
    ):
        reason = eligibility(db, actor, worker.id, task.department_id, task.required_skills, task.shift_id)
        if reason and worker.active:
            fail(409, f"Team has open work '{task.title}': {reason}")
    audit(
        db,
        actor,
        actor.organization_id,
        "worker.created" if is_new else "worker.updated",
        "user",
        worker.id,
        before if not is_new else {},
        {
            "name": worker.name,
            "department_ids": values.department_ids,
            "team_ids": values.team_ids,
            "skills": values.skills,
        },
    )
    return {**worker_detail(db, worker), **({"activation_url": activation_url} if activation_url else {})}


def eligibility(
    db: Session,
    actor: User,
    worker_id: str,
    department_id: str,
    required_skills: list[str],
    shift_id: str | None = None,
):
    worker = scoped(db, User, worker_id, actor)
    if worker.role != "worker" or not worker.active:
        return "Worker is not active."
    if department_id not in department_ids(db, worker):
        return "Worker does not belong to this department."
    unavailable = db.scalar(
        select(WorkerAvailability.id).where(
            WorkerAvailability.user_id == worker_id,
            WorkerAvailability.starts_at <= now(),
            WorkerAvailability.ends_at > now(),
            WorkerAvailability.status.in_(["absent", "unavailable", "leave"]),
        )
    )
    if unavailable:
        return "Worker is currently unavailable."
    owned_skills = set(
        db.scalars(
            select(Skill.name)
            .join(WorkerSkill)
            .where(
                WorkerSkill.user_id == worker_id,
                (WorkerSkill.expires_on.is_(None)) | (WorkerSkill.expires_on >= now().date().isoformat()),
            )
        )
    )
    if not {skill.lower() for skill in required_skills}.issubset(owned_skills):
        return "Worker does not have all required qualifications."
    if shift_id and not db.scalar(
        select(ShiftAssignment.id).where(
            ShiftAssignment.user_id == worker_id,
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.department_id == department_id,
            ShiftAssignment.active.is_(True),
            ShiftAssignment.starts_on <= now().date().isoformat(),
            (ShiftAssignment.ends_on.is_(None)) | (ShiftAssignment.ends_on >= now().date().isoformat()),
        )
    ):
        return "Worker is not assigned to this shift."
    return None
