from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from ..db import now
from ..models import (
    Alert,
    Clarification,
    Conflict,
    ConflictReport,
    Department,
    DepartmentMembership,
    Handover,
    HandoverItem,
    HandoverItemAcknowledgement,
    HandoverRecipient,
    HandoverVersion,
    Organization,
    Report,
    ReportTaskLink,
    ReportVersion,
    Shift,
    ShiftAssignment,
    Task,
    Team,
    TeamMembership,
    User,
    WorkerAvailability,
)
from ..security import department_ids, fail
from .handovers import shift_window


def percent(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else None


def counts(items, attribute):
    return [
        {"name": name or "Unspecified", "value": value}
        for name, value in sorted(
            Counter(getattr(item, attribute) or "Unspecified" for item in items).items()
        )
    ]


def aggregate(db, user, start: datetime, end: datetime, filters: dict):
    allowed = department_ids(db, user)
    department = filters.get("department_id")
    if department:
        if department not in allowed:
            fail(403, "This department is outside your analytics scope.")
        allowed = [department]
    org = db.get(Organization, user.organization_id)
    zone = ZoneInfo(org.timezone)
    task_query = select(Task).where(Task.organization_id == org.id, Task.department_id.in_(allowed))
    report_query = select(Report).where(
        Report.organization_id == org.id, Report.department_id.in_(allowed), Report.submitted_at.is_not(None)
    )
    for model, key in [(Task, "team_id"), (Task, "shift_id"), (Task, "priority"), (Task, "status")]:
        if filters.get(key):
            task_query = task_query.where(getattr(model, key) == filters[key])
    for key in ("team_id", "shift_id", "category"):
        if filters.get(key):
            report_query = report_query.where(getattr(Report, key) == filters[key])
    if filters.get("status"):
        report_query = report_query.where(Report.status == filters["status"])
    tasks = list(
        db.scalars(
            task_query.where(
                or_(
                    Task.deadline.between(start, end),
                    (Task.deadline.is_(None)) & Task.created_at.between(start, end),
                )
            )
        )
    )
    reports = list(db.scalars(report_query.where(Report.submitted_at.between(start, end))))
    issues = list(
        db.scalars(
            report_query.where(
                Report.needs_attention.is_(True) | Report.resolved_at.is_not(None),
                Report.submitted_at <= end,
                (Report.resolved_at.is_(None)) | (Report.resolved_at >= start),
            )
        )
    )
    all_alerts_query = select(Alert).where(Alert.organization_id == org.id, Alert.department_id.in_(allowed))
    if any(filters.get(key) for key in ("team_id", "shift_id", "category")):
        all_alerts_query = all_alerts_query.where(
            Alert.report_id.in_(report_query.with_only_columns(Report.id))
        )
    alerts = list(db.scalars(all_alerts_query.where(Alert.created_at.between(start, end))))
    conflicts = list(
        db.scalars(
            select(Conflict).where(
                Conflict.organization_id == org.id,
                Conflict.department_id.in_(allowed),
                Conflict.created_at <= end,
                (Conflict.resolved_at.is_(None)) | (Conflict.resolved_at >= start),
            )
        )
    )
    worker_query = select(User).where(
        User.organization_id == org.id,
        User.role == "worker",
        User.id.in_(
            select(DepartmentMembership.user_id).where(
                DepartmentMembership.department_id.in_(allowed), DepartmentMembership.active.is_(True)
            )
        ),
    )
    if filters.get("team_id"):
        worker_query = worker_query.where(
            User.id.in_(
                select(TeamMembership.user_id).where(
                    TeamMembership.team_id == filters["team_id"], TeamMembership.active.is_(True)
                )
            )
        )
    if filters.get("shift_id"):
        worker_query = worker_query.where(
            User.id.in_(
                select(ShiftAssignment.user_id).where(
                    ShiftAssignment.shift_id == filters["shift_id"], ShiftAssignment.active.is_(True)
                )
            )
        )
    workers = list(db.scalars(worker_query))
    worker_ids = {worker.id for worker in workers}
    absences = set(
        db.scalars(
            select(WorkerAvailability.user_id).where(
                WorkerAvailability.user_id.in_(worker_ids),
                WorkerAvailability.starts_at <= now(),
                WorkerAvailability.ends_at > now(),
                WorkerAvailability.status.in_(["absent", "unavailable", "leave"]),
            )
        )
    )
    handover_query = select(Handover).where(
        Handover.organization_id == org.id, Handover.department_id.in_(allowed)
    )
    if filters.get("shift_id"):
        handover_query = handover_query.where(Handover.shift_id == filters["shift_id"])
    versions = list(
        db.scalars(
            select(HandoverVersion).where(
                HandoverVersion.handover_id.in_(handover_query.with_only_columns(Handover.id)),
                HandoverVersion.created_at.between(start, end),
            )
        )
    )
    version_ids = [v.id for v in versions]
    recipients = list(
        db.scalars(
            select(HandoverRecipient).where(
                HandoverRecipient.version_id.in_(version_ids), HandoverRecipient.required.is_(True)
            )
        )
    )
    critical_items = list(
        db.scalars(
            select(HandoverItem).where(
                HandoverItem.version_id.in_(version_ids), HandoverItem.critical.is_(True)
            )
        )
    )
    required_pairs = {
        (item.id, recipient.user_id)
        for item in critical_items
        for recipient in recipients
        if item.version_id == recipient.version_id
    }
    received_pairs = {
        (ack.item_id, ack.user_id)
        for ack in db.scalars(
            select(HandoverItemAcknowledgement).where(
                HandoverItemAcknowledgement.item_id.in_([item.id for item in critical_items]),
                HandoverItemAcknowledgement.created_at <= end,
            )
        )
    }
    closed = [task for task in tasks if task.closed_at and task.closed_at <= end]
    completed = [task for task in tasks if task.completed_at and task.completed_at <= end]
    deadline_completed = [task for task in completed if task.deadline]
    on_time = [task for task in deadline_completed if task.completed_at <= task.deadline]
    times = [
        (task.completed_at - task.started_at).total_seconds() / 3600
        for task in completed
        if task.started_at and task.completed_at >= task.started_at
    ]
    overdue = [
        task
        for task in tasks
        if task.deadline
        and task.deadline < min(now(), end)
        and not (task.closed_at and task.closed_at <= end)
    ]
    resolved = [issue for issue in issues if issue.resolved_at and start <= issue.resolved_at <= end]
    receipt_count = sum(bool(r.acknowledged_at and r.acknowledged_at <= end) for r in recipients)
    latest_versions = {}
    for version in versions:
        if (
            version.handover_id not in latest_versions
            or version.number > latest_versions[version.handover_id].number
        ):
            latest_versions[version.handover_id] = version
    publication_delays = []
    for handover_id, version in latest_versions.items():
        handover = db.get(Handover, handover_id)
        _, shift_end = shift_window(org, db.get(Shift, handover.shift_id), handover.shift_date)
        publication_delays.append(max(0, (version.created_at - shift_end).total_seconds() / 60))
    safety, quality = (
        [r for r in reports if r.category == "safety" or r.immediate_safety],
        [r for r in reports if r.category == "quality"],
    )
    report_ids = [r.id for r in reports]
    pending_clarifications = set(
        db.scalars(
            select(Clarification.report_id).where(
                Clarification.report_id.in_(report_ids), Clarification.responded_at.is_(None)
            )
        )
    )
    conflict_reports = set(
        db.scalars(select(ConflictReport.report_id).where(ConflictReport.report_id.in_(report_ids)))
    )
    corrective_ids = set(
        db.scalars(
            select(ReportTaskLink.task_id).where(
                ReportTaskLink.report_id.in_(report_ids), ReportTaskLink.follow_up.is_(True)
            )
        )
    ) | {task.id for task in tasks if task.source_report_id}
    metrics = {
        "on_time_completed": len(on_time),
        "delayed_completed": len(deadline_completed) - len(on_time),
        "average_publication_delay_minutes": round(sum(publication_delays) / len(publication_delays), 1)
        if publication_delays
        else None,
        "delayed_handovers": sum(value > 0 for value in publication_delays),
        "average_resolution_hours": round(
            sum((r.resolved_at - r.submitted_at).total_seconds() / 3600 for r in resolved) / len(resolved), 2
        )
        if resolved
        else None,
        "average_alert_acknowledgement_minutes": round(
            sum(
                (a.acknowledged_at - a.created_at).total_seconds() / 60
                for a in alerts
                if a.acknowledged_at and a.acknowledged_at <= end
            )
            / len([a for a in alerts if a.acknowledged_at and a.acknowledged_at <= end]),
            1,
        )
        if any(a.acknowledged_at and a.acknowledged_at <= end for a in alerts)
        else None,
        "total_workers": len(workers),
        "active_workers": sum(w.active for w in workers),
        "absent_workers": len(absences),
        "total_tasks": len(tasks),
        "completed_tasks": len(completed),
        "closed_tasks": len(closed),
        "pending_tasks": len(tasks) - len(closed),
        "overdue_tasks": len(overdue),
        "blocked_tasks": sum(t.status == "blocked" for t in tasks),
        "task_completion_rate": percent(len(closed), len(tasks)),
        "on_time_completion_rate": percent(len(on_time), len(deadline_completed)),
        "average_completion_hours": round(sum(times) / len(times), 2) if times else None,
        "safety_incidents": len(safety),
        "critical_incidents": sum(r.immediate_safety for r in safety),
        "open_safety_issues": sum(not r.resolved_at or r.resolved_at > end for r in safety),
        "resolved_safety_incidents": sum(bool(r.resolved_at and r.resolved_at <= end) for r in safety),
        "quality_issues": len(quality),
        "open_quality_issues": sum(not r.resolved_at or r.resolved_at > end for r in quality),
        "resolved_quality_issues": sum(bool(r.resolved_at and r.resolved_at <= end) for r in quality),
        "submitted_reports": len(reports),
        "reports_needing_attention": sum(r.needs_attention for r in reports),
        "reports_awaiting_review": sum(r.needs_attention and not r.verified_at for r in reports),
        "reports_awaiting_clarification": len(pending_clarifications),
        "reports_with_conflicts": len(conflict_reports),
        "issue_resolution_rate": percent(len(resolved), len(issues)),
        "issues_requiring_resolution": len(issues),
        "issues_resolved_in_period": len(resolved),
        "published_handovers": sum(not v.provisional for v in latest_versions.values()),
        "provisional_handovers": sum(v.provisional for v in latest_versions.values()),
        "pending_acknowledgements": len(recipients) - receipt_count,
        "handover_acknowledgement_rate": percent(receipt_count, len(recipients)),
        "critical_items_awaiting_acknowledgement": len(required_pairs - received_pairs),
        "critical_acknowledgement_rate": percent(len(required_pairs & received_pairs), len(required_pairs)),
        "unresolved_conflicts": sum(c.status != "resolved" for c in conflicts),
        "unacknowledged_alerts": sum(a.acknowledged_at is None for a in alerts),
        "open_critical_issues": sum(a.status != "resolved" for a in alerts),
        "pending_escalations": sum(a.escalation_level > 0 and a.status != "resolved" for a in alerts),
        "pending_corrective_actions": sum(t.id in corrective_ids and t.status != "closed" for t in tasks),
    }
    recurring = Counter()
    for report in quality:
        version = db.scalar(
            select(ReportVersion).where(
                ReportVersion.report_id == report.id, ReportVersion.number == report.latest_version
            )
        )
        if version:
            context = (
                version.fields.get("machine"),
                version.fields.get("work_area"),
                version.fields.get("batch"),
            )
            if any(context):
                recurring[" · ".join(value for value in context if value)] += 1
    metrics["recurring_quality_contexts"] = sum(count > 1 for count in recurring.values())
    trend = {}
    day = start.astimezone(zone).date()
    while day <= end.astimezone(zone).date():
        trend[day.isoformat()] = {
            "date": day.isoformat(),
            "reports": 0,
            "completed": 0,
            "safety": 0,
            "quality": 0,
            "handovers": 0,
            "acknowledgements": 0,
        }
        day += timedelta(days=1)

    def add(timestamp, key):
        date_key = timestamp.astimezone(zone).date().isoformat()
        if date_key in trend:
            trend[date_key][key] += 1

    for report in reports:
        add(report.submitted_at, "reports")
        if report.category == "quality":
            add(report.submitted_at, "quality")
        if report.category == "safety" or report.immediate_safety:
            add(report.submitted_at, "safety")
    for task in completed:
        add(task.completed_at, "completed")
    for version in versions:
        add(version.created_at, "handovers")
    for recipient in recipients:
        if recipient.acknowledged_at:
            add(recipient.acknowledged_at, "acknowledgements")
    departments = list(db.scalars(select(Department).where(Department.id.in_(allowed))))
    memberships = list(
        db.scalars(
            select(DepartmentMembership).where(
                DepartmentMembership.department_id.in_(allowed), DepartmentMembership.active.is_(True)
            )
        )
    )
    department_rows = []
    for dept in departments:
        scoped_tasks = [t for t in tasks if t.department_id == dept.id]
        scoped_alerts = [a for a in alerts if a.department_id == dept.id and a.status != "resolved"]
        scoped_overdue = sum(t.department_id == dept.id for t in overdue)
        department_rows.append(
            {
                "id": dept.id,
                "name": dept.name,
                "closed": sum(t in closed for t in scoped_tasks),
                "pending": sum(t not in closed for t in scoped_tasks),
                "blocked": sum(t.status == "blocked" for t in scoped_tasks),
                "overdue": scoped_overdue,
                "critical": len(scoped_alerts),
                "workers": sum(m.user_id in worker_ids for m in memberships if m.department_id == dept.id),
                "reports": sum(r.department_id == dept.id for r in reports),
                "safety": sum(r.department_id == dept.id for r in safety),
                "quality": sum(r.department_id == dept.id for r in quality),
                "health": "critical"
                if scoped_alerts
                else "needs_attention"
                if scoped_overdue or any(t.status == "blocked" for t in scoped_tasks)
                else "healthy",
            }
        )
    shift_rows = []
    for shift in db.scalars(select(Shift).where(Shift.organization_id == org.id)):
        scheduled = set(
            db.scalars(
                select(ShiftAssignment.user_id).where(
                    ShiftAssignment.shift_id == shift.id,
                    ShiftAssignment.department_id.in_(allowed),
                    ShiftAssignment.active.is_(True),
                    ShiftAssignment.user_id.in_(worker_ids),
                )
            )
        )
        shift_rows.append(
            {
                "id": shift.id,
                "name": shift.name,
                "workers": len(scheduled),
                "reports": sum(r.shift_id == shift.id for r in reports),
                "safety": sum(r.shift_id == shift.id for r in safety),
                "quality": sum(r.shift_id == shift.id for r in quality),
            }
        )
    team_rows = [
        {
            "id": team.id,
            "name": team.name,
            "workers": len(
                set(
                    db.scalars(
                        select(TeamMembership.user_id).where(
                            TeamMembership.team_id == team.id,
                            TeamMembership.user_id.in_(worker_ids),
                            TeamMembership.active.is_(True),
                        )
                    )
                )
            ),
        }
        for team in db.scalars(select(Team).where(Team.department_id.in_(allowed)))
    ]
    supervisors = list(
        db.scalars(
            select(User).where(
                User.organization_id == org.id, User.role == "supervisor", User.active.is_(True)
            )
        )
    )
    coverage = [
        {
            "department_id": dept.id,
            "department": dept.name,
            "primary": any(
                m.department_id == dept.id and m.primary and any(s.id == m.user_id for s in supervisors)
                for m in memberships
            ),
            "backup": any(
                m.department_id == dept.id and m.backup and any(s.id == m.user_id for s in supervisors)
                for m in memberships
            ),
        }
        for dept in departments
        if dept.active
    ]
    handover_departments = []
    for dept in departments:
        selected_versions = [v for v in versions if db.get(Handover, v.handover_id).department_id == dept.id]
        selected_ids = {v.id for v in selected_versions}
        required = [r for r in recipients if r.version_id in selected_ids]
        items = {i.id for i in critical_items if i.version_id in selected_ids}
        handover_departments.append(
            {
                "name": dept.name,
                "published": len({v.handover_id for v in selected_versions}),
                "pending": sum(not r.acknowledged_at or r.acknowledged_at > end for r in required),
                "critical_pending": sum(pair[0] in items for pair in required_pairs - received_pairs),
            }
        )
    supervisor_workload = []
    for supervisor in supervisors:
        managed = {
            m.department_id for m in memberships if m.user_id == supervisor.id and "review" in m.permissions
        }
        if managed:
            supervisor_workload.append(
                {
                    "name": supervisor.name,
                    "reports": sum(
                        r.department_id in managed and r.needs_attention and not r.verified_at
                        for r in reports
                    ),
                    "approvals": sum(
                        t.department_id in managed and t.status == "completed" and t.verification_required
                        for t in tasks
                    ),
                    "alerts": sum(a.assigned_to == supervisor.id and a.status != "resolved" for a in alerts),
                }
            )
    metrics["active_departments"] = sum(d.active for d in departments)
    metrics["active_supervisors"] = len(
        {m.user_id for m in memberships if any(s.id == m.user_id for s in supervisors)}
    )
    heatmap = [
        {
            "department": d.name,
            "shift": s["name"],
            "issues": sum(
                r.department_id == d.id
                and r.shift_id == s["id"]
                and (r.category in {"safety", "quality"} or r.immediate_safety)
                for r in reports
            ),
        }
        for d in departments
        for s in shift_rows
    ]
    return {
        "metrics": metrics,
        "trends": list(trend.values()),
        "departments": department_rows,
        "shifts": shift_rows,
        "teams": team_rows,
        "task_status": counts(tasks, "status"),
        "task_priority": counts(tasks, "priority"),
        "report_categories": counts(reports, "category"),
        "recurring_quality": [
            {"name": name, "value": value} for name, value in recurring.items() if value > 1
        ],
        "coverage": coverage,
        "supervisor_workload": supervisor_workload,
        "handover_departments": handover_departments,
        "heatmap": heatmap,
        "has_data": bool(tasks or reports or versions or workers),
        "cohorts": {
            "tasks": "Tasks with a deadline in the selected period, or created in it when no deadline exists. Closure/completion is counted through period end.",
            "on_time": "Completed tasks in that task cohort with a deadline; completion timestamp must be at or before deadline.",
            "issues": "Reports needing action created through period end and unresolved at period start, including those created during the period. Numerator: this cohort resolved in the period.",
            "handovers": "All required recipient receipts for versions published in the selected period; received by period end. Critical receipt denominator is each critical item × each required recipient.",
            "workforce": "Current accounts and active memberships, not historical attendance. Absent means unavailable now. Scheduled workers are distinct from active accounts.",
            "reports": "Submitted reports in the period; corrections do not create additional reports.",
            "publication": "Latest version in the period per handover determines published/provisional composition; delay is minutes after the outgoing shift end, floored at zero.",
            "supervisors": "Current review responsibilities. Reports and approvals may appear for multiple authorized reviewers; alert workload follows the current designated recipient.",
            "filters": "Department applies across all modules. Team/priority/status apply to their relevant operational records; category filters reporting and linked alerts. No inferred historical presence.",
        },
    }
