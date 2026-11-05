from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import now
from ..models import (
    DepartmentMembership,
    Organization,
    Task,
    TaskAssignment,
    TaskDependency,
    TaskHistory,
    TaskVerification,
    Team,
    TeamMembership,
    User,
)
from ..schemas import TaskAction, TaskInput
from ..security import department_ids, fail, require_department, scoped
from .common import audit, notify, record_dict
from .workforce import eligibility


def allocation_candidates(db, actor, department_id, skills, shift_id=None):
    from .workforce import visible_workers_query

    result = []
    for worker in db.scalars(visible_workers_query(db, actor)):
        if eligibility(db, actor, worker.id, department_id, skills, shift_id):
            continue
        own_teams = list(
            db.scalars(
                select(TeamMembership.team_id).where(
                    TeamMembership.user_id == worker.id, TeamMembership.active.is_(True)
                )
            )
        )
        assignments = db.scalars(
            select(TaskAssignment).where(
                or_(TaskAssignment.user_id == worker.id, TaskAssignment.team_id.in_(own_teams))
            )
        ).all()
        workload = sum(a.ended_at is None and db.get(Task, a.task_id).status != "closed" for a in assignments)
        last_assigned = max((a.created_at.isoformat() for a in assignments), default="")
        result.append(
            {
                "worker_id": worker.id,
                "name": worker.name,
                "open_tasks": workload,
                "last_assigned": last_assigned,
            }
        )
    return sorted(result, key=lambda item: (item["open_tasks"], item["last_assigned"], item["worker_id"]))


def template_values(db, actor, template):
    from datetime import datetime, timedelta

    definition = {**template.definition}
    auto = definition.pop("_auto_allocate", False)
    if auto:
        if (
            definition.get("critical")
            or definition.get("priority") not in {None, "normal"}
            or definition.get("assignment_type") != "individual"
        ):
            fail(422, "Automatic allocation is limited to approved routine individual templates.")
        candidates = allocation_candidates(
            db,
            actor,
            template.department_id,
            definition.get("required_skills", []),
            definition.get("shift_id"),
        )
        if not candidates:
            fail(409, "No qualified, available worker is eligible for this recurring task.")
        definition["worker_id"] = candidates[0]["worker_id"]
    if definition.get("deadline"):
        original = datetime.fromisoformat(definition["deadline"])
        definition["deadline"] = (
            now() + max(original - template.created_at, timedelta(minutes=15))
        ).isoformat()
    return TaskInput.model_validate(definition)


def task_query(db: Session, user: User):
    query = select(Task).where(
        Task.organization_id == user.organization_id, Task.department_id.in_(department_ids(db, user))
    )
    if user.role == "worker":
        teams = select(TeamMembership.team_id).where(
            TeamMembership.user_id == user.id, TeamMembership.active.is_(True)
        )
        own = Task.id.in_(
            select(TaskAssignment.task_id).where(
                TaskAssignment.ended_at.is_(None),
                or_(TaskAssignment.user_id == user.id, TaskAssignment.team_id.in_(teams)),
            )
        )
        query = query.where(own)
    return query


def visible_task(db: Session, user: User, task_id: str):
    task = db.scalar(task_query(db, user).where(Task.id == task_id))
    if not task:
        fail(404, "Task not found.")
    return task


def recipients(db: Session, task: Task):
    assignment = db.scalar(
        select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.ended_at.is_(None))
    )
    if not assignment:
        return []
    if assignment.user_id:
        return [assignment.user_id]
    return list(
        db.scalars(
            select(TeamMembership.user_id)
            .join(User, User.id == TeamMembership.user_id)
            .where(
                TeamMembership.team_id == assignment.team_id,
                TeamMembership.active.is_(True),
                User.active.is_(True),
            )
        )
    )


def task_detail(db: Session, user: User, task: Task):
    from ..models import TaskComment, ReportTaskLink, Report
    from .reports import report_query

    comments = select(TaskComment).where(TaskComment.task_id == task.id)
    if user.role == "worker":
        comments = comments.where(TaskComment.internal.is_(False))
    return {
        **record_dict(task),
        "reports": [
            record_dict(report, {"request_hash", "client_request_id"})
            for report in db.scalars(
                report_query(db, user).where(
                    Report.id.in_(select(ReportTaskLink.report_id).where(ReportTaskLink.task_id == task.id))
                )
            )
        ],
        "assignments": [
            record_dict(item)
            for item in db.scalars(
                select(TaskAssignment)
                .where(TaskAssignment.task_id == task.id)
                .order_by(TaskAssignment.created_at)
            )
        ],
        "history": [
            record_dict(item)
            for item in db.scalars(
                select(TaskHistory).where(TaskHistory.task_id == task.id).order_by(TaskHistory.created_at)
            )
        ],
        "comments": [record_dict(item) for item in db.scalars(comments.order_by(TaskComment.created_at))],
        "verifications": [
            record_dict(item)
            for item in db.scalars(select(TaskVerification).where(TaskVerification.task_id == task.id))
        ],
        "dependencies": list(
            db.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task.id))
        ),
    }


def validate_assignment(
    db: Session, actor: User, task: Task, worker_id: str | None, team_id: str | None, lead_id: str | None
):
    if task.assignment_type == "individual":
        if not worker_id:
            fail(422, "Choose one responsible worker.")
        reason = eligibility(db, actor, worker_id, task.department_id, task.required_skills, task.shift_id)
        if reason:
            fail(422, reason)
    else:
        if not team_id or worker_id:
            fail(422, "Choose a team for this shared task.")
        team = scoped(db, Team, team_id, actor)
        if not team.active or team.department_id != task.department_id:
            fail(422, "Choose an active team in this department.")
        members = list(
            db.scalars(
                select(TeamMembership.user_id)
                .join(User, User.id == TeamMembership.user_id)
                .where(
                    TeamMembership.team_id == team.id, TeamMembership.active.is_(True), User.active.is_(True)
                )
            )
        )
        if not members:
            fail(422, "This team has no active workers.")
        if lead_id and lead_id not in members:
            fail(422, "The lead must be an active team member.")
        for member in members:
            reason = eligibility(db, actor, member, task.department_id, task.required_skills, task.shift_id)
            if reason:
                fail(422, f"A team member is ineligible: {reason}")


def create_task(db: Session, actor: User, values: TaskInput):
    require_department(db, actor, values.department_id, "manage", active=True)
    if not db.get(Organization, actor.organization_id).active:
        fail(409, "Activate the organization after completing required onboarding.")
    if values.shift_id:
        from ..models import Shift

        if not scoped(db, Shift, values.shift_id, actor).active:
            fail(422, "Choose an active shift.")
    if values.team_id:
        team = scoped(db, Team, values.team_id, actor)
        if not team.active or team.department_id != values.department_id:
            fail(422, "Choose an active team in this department.")
    if values.source_report_id:
        from .reports import accessible_report

        accessible_report(db, actor, values.source_report_id, purpose="Create linked corrective action")
    fields = values.model_dump(exclude={"worker_id", "lead_id", "depends_on"})
    task = Task(organization_id=actor.organization_id, created_by=actor.id, **fields)
    validate_assignment(db, actor, task, values.worker_id, values.team_id, values.lead_id)
    db.add(task)
    db.flush()
    if task.source_report_id:
        from ..models import ReportTaskLink

        db.add(
            ReportTaskLink(
                organization_id=actor.organization_id,
                report_id=task.source_report_id,
                task_id=task.id,
                linked_by=actor.id,
                follow_up=True,
            )
        )
    db.add(
        TaskAssignment(
            organization_id=actor.organization_id,
            task_id=task.id,
            user_id=values.worker_id if values.assignment_type == "individual" else None,
            team_id=values.team_id if values.assignment_type == "team" else None,
            lead_id=values.lead_id,
            assigned_by=actor.id,
        )
    )
    for dependency_id in set(values.depends_on):
        dependency = visible_task(db, actor, dependency_id)
        db.add(
            TaskDependency(
                organization_id=actor.organization_id, task_id=task.id, depends_on_id=dependency.id
            )
        )
    db.add(
        TaskHistory(
            organization_id=actor.organization_id,
            task_id=task.id,
            actor_id=actor.id,
            action="assigned",
            detail={"worker_id": values.worker_id, "team_id": values.team_id, "priority": task.priority},
        )
    )
    db.flush()
    for recipient in recipients(db, task):
        notify(
            db,
            actor.organization_id,
            recipient,
            f"task:{task.id}:assigned",
            "New task assigned",
            task.title,
            f"/workspace/tasks/{task.id}",
        )
    audit(db, actor, actor.organization_id, "task.created", "task", task.id, after=record_dict(task))
    return task


def transition(db: Session, actor: User, task: Task, values: TaskAction):
    if values.version != task.version:
        fail(409, "This task changed. Refresh before taking action.")
    action = values.action
    if action in {"verify", "reject", "close"}:
        require_department(db, actor, task.department_id, "review")
    elif actor.role != "worker":
        require_department(db, actor, task.department_id, "manage")
    elif actor.id not in recipients(db, task):
        fail(403, "Only an assigned worker can update this task.")
    if actor.role == "worker" and action in {"accept", "start", "resume"}:
        reason = eligibility(db, actor, actor.id, task.department_id, task.required_skills, task.shift_id)
        if reason:
            fail(409, reason + " Ask your supervisor to review the assignment.")
    before = task.status
    rules = {
        "accept": ({"assigned"}, "accepted"),
        "start": ({"accepted"}, "in_progress"),
        "block": ({"assigned", "accepted", "in_progress"}, "blocked"),
        "resume": ({"blocked"}, "in_progress"),
        "complete": ({"in_progress"}, "completed"),
        "verify": ({"completed"}, "verified"),
        "reject": ({"completed"}, "in_progress"),
        "close": ({"verified"}, "closed"),
    }
    permitted, target = rules[action]
    if before not in permitted:
        fail(409, f"Cannot {action} a task in {before.replace('_', ' ')} state.")
    if action in {"block", "reject"} and not values.reason.strip():
        fail(422, "Explain why the task is blocked or completion was rejected.")
    if action in {"start", "complete"}:
        unfinished = db.scalar(
            select(TaskDependency.id)
            .join(Task, Task.id == TaskDependency.depends_on_id)
            .where(TaskDependency.task_id == task.id, Task.status != "closed")
        )
        if unfinished:
            fail(409, "Complete and close dependent tasks first.")
    if action == "start" and not task.started_at:
        task.started_at = now()
    if action == "block":
        task.blocked_reason = values.reason
    if action == "resume":
        last_block = db.scalar(
            select(TaskHistory)
            .where(TaskHistory.task_id == task.id, TaskHistory.action == "block")
            .order_by(TaskHistory.created_at.desc())
        )
        target = last_block.detail.get("from", "in_progress") if last_block else "in_progress"
        task.blocked_reason = ""
    if action == "complete":
        task.completed_at = now()
        if not task.verification_required and not task.critical:
            target = "closed"
            task.closed_at = now()
            db.add(
                TaskHistory(
                    organization_id=actor.organization_id,
                    task_id=task.id,
                    actor_id=actor.id,
                    action="completed",
                    detail={"from": before, "to": "completed"},
                )
            )
    if action in {"verify", "reject"}:
        db.add(
            TaskVerification(
                organization_id=actor.organization_id,
                task_id=task.id,
                reviewer_id=actor.id,
                approved=action == "verify",
                reason=values.reason or "Completion verified",
            )
        )
    if action == "reject":
        task.completed_at = None
    if action == "close":
        task.closed_at = now()
    task.status = target
    if target == "closed":
        from ..models import FollowUp
        from .reports import reviewers

        for followup in db.scalars(select(FollowUp).where(FollowUp.task_id == task.id)):
            followup.status = "completed"
            for recipient in reviewers(db, followup.originating_department_id):
                notify(
                    db,
                    actor.organization_id,
                    recipient,
                    f"followup:{followup.id}:completed",
                    "Linked follow-up completed",
                    "Review the original issue before resolving it.",
                    f"/workspace/reports/{followup.report_id}",
                )
    db.add(
        TaskHistory(
            organization_id=actor.organization_id,
            task_id=task.id,
            actor_id=actor.id,
            action=action,
            detail={"from": before, "to": target, "reason": values.reason},
        )
    )
    db.flush()
    for recipient in recipients(db, task):
        if recipient != actor.id:
            notify(
                db,
                actor.organization_id,
                recipient,
                f"task:{task.id}:v{task.version}:{action}",
                f"Task {target.replace('_', ' ')}",
                values.reason or task.title,
                f"/workspace/tasks/{task.id}",
            )
    if target in {"completed", "blocked"}:
        supervisors = db.scalars(
            select(DepartmentMembership)
            .join(User, User.id == DepartmentMembership.user_id)
            .where(
                DepartmentMembership.department_id == task.department_id,
                DepartmentMembership.active.is_(True),
                User.role == "supervisor",
                User.active.is_(True),
            )
        ).all()
        for membership in supervisors:
            if "review" in membership.permissions:
                notify(
                    db,
                    actor.organization_id,
                    membership.user_id,
                    f"task:{task.id}:v{task.version}:attention",
                    "Task needs attention",
                    task.title,
                    f"/workspace/tasks/{task.id}",
                )
    audit(
        db,
        actor,
        actor.organization_id,
        f"task.{action}",
        "task",
        task.id,
        {"status": before},
        {"status": target},
        values.reason,
    )
    return task


def reassign(
    db: Session,
    actor: User,
    task: Task,
    worker_id: str | None,
    team_id: str | None,
    lead_id: str | None,
    reason: str,
):
    require_department(db, actor, task.department_id, "manage")
    if task.status in {"closed", "verified"}:
        fail(409, "Closed or verified work cannot be reassigned.")
    validate_assignment(db, actor, task, worker_id, team_id, lead_id)
    previous = recipients(db, task)
    for assignment in db.scalars(
        select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.ended_at.is_(None))
    ):
        assignment.ended_at = now()
    db.add(
        TaskAssignment(
            organization_id=actor.organization_id,
            task_id=task.id,
            user_id=worker_id if task.assignment_type == "individual" else None,
            team_id=team_id if task.assignment_type == "team" else None,
            lead_id=lead_id,
            assigned_by=actor.id,
            reason=reason,
        )
    )
    old_status = task.status
    task.status = "assigned"
    task.updated_at = now()  # Ownership changes must advance the optimistic version even before acceptance.
    task.completed_at = None
    if task.assignment_type == "team":
        task.team_id = team_id
    db.add(
        TaskHistory(
            organization_id=actor.organization_id,
            task_id=task.id,
            actor_id=actor.id,
            action="reassigned",
            detail={
                "previous_recipients": previous,
                "worker_id": worker_id,
                "team_id": team_id,
                "reason": reason,
                "previous_status": old_status,
            },
        )
    )
    db.flush()
    for recipient in set(previous + recipients(db, task)):
        notify(
            db,
            actor.organization_id,
            recipient,
            f"task:{task.id}:v{task.version}:reassigned",
            "Task responsibility changed",
            reason,
            f"/workspace/tasks/{task.id}",
        )
    audit(
        db,
        actor,
        actor.organization_id,
        "task.reassigned",
        "task",
        task.id,
        after={"worker_id": worker_id, "team_id": team_id},
        purpose=reason,
    )
    return task
