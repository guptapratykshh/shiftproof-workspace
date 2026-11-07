from typing import Literal
import time

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..db import get_db, now
from ..models import Clarification, Conflict, ConflictReport, Department, Organization, Report, ReportReview, ReportTaskLink, ReportVersion, Task, User
from ..schemas import Input, ReportInput
from ..security import current_user, department_ids, fail, require_department, scoped
from ..services import reports as service
from ..services.contradictions import compare
from ..services.common import audit, notify, record_dict

router = APIRouter(tags=["Reports and clarification"])


@router.get("/reports")
def reports(
    department_id: str | None = None,
    status: str | None = None,
    needs_attention: bool | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    query = service.report_query(db, user)
    for column, value in [
        (Report.department_id, department_id),
        (Report.status, status),
        (Report.category, category),
        (Report.needs_attention, needs_attention),
    ]:
        if value is not None:
            query = query.where(column == value)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    # Lists expose operational metadata only; individual contents have separate privacy gates.
    return {
        "items": [
            record_dict(item, {"request_hash", "client_request_id"})
            for item in db.scalars(
                query.order_by(Report.created_at.desc()).offset((page - 1) * limit).limit(limit)
            )
        ],
        "total": total,
    }


@router.post("/reports", status_code=201)
def submit(
    values: ReportInput,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    # A report has a stable submission key. MongoDB aborts conflicting snapshot
    # transactions rather than waiting for a SQL row lock; retry the entire
    # idempotent operation with fresh authorization and a fresh snapshot.
    for attempt in range(6):
        try:
            item = service.submit(db, user, values)
            if db.bind.dialect.name == "mongodb":
                db.commit()
            return {"status": "submitted", "report": record_dict(item)}
        except StaleDataError:
            if db.bind.dialect.name != "mongodb" or attempt == 5:
                raise
            db.rollback()
            time.sleep(0.15 * 2**attempt)
            user = current_user(request, db)


@router.get("/reports/{record_id}")
def detail(
    record_id: str,
    purpose: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    return service.report_detail(db, user, service.accessible_report(db, user, record_id, purpose))


class Correction(Input):
    report: ReportInput
    reason: str = Field(min_length=3, max_length=2000)
    version: int


@router.post("/reports/{record_id}/corrections", status_code=201)
def correct(
    record_id: str,
    values: Correction,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    item = service.accessible_report(db, user, record_id, purpose=values.reason)
    if item.author_id != user.id:
        fail(403, "Only the original reporter can correct their report. Request clarification instead.")
    if item.version != values.version:
        fail(409, "This report changed. Refresh before correcting it.")
    service.validate_sources(db, user, values.report)
    if (
        values.report.department_id,
        values.report.team_id,
        values.report.shift_id,
        values.report.occurred_at,
    ) != (item.department_id, item.team_id, item.shift_id, item.occurred_at):
        fail(422, "A correction preserves its original department, team, shift and occurrence time.")
    service.lock_comparison_context(db, user, item.department_id)
    version = service.append_version(db, user, item, values.report, values.reason)
    service.detect_conflicts(db, item, version)
    if values.report.immediate_safety and not item.immediate_safety:
        from ..services.alerts import create_alert

        item.immediate_safety = True
        create_alert(
            db,
            user,
            item.department_id,
            "Immediate safety concern in report correction",
            item.id,
            immediate=True,
        )
    item.category = values.report.fields.category
    item.status = "submitted"
    item.verified_at = item.verified_by = item.resolved_at = None
    item.needs_attention = True
    service.attention(db, item, f"correction:{item.latest_version}", values.reason)
    audit(
        db,
        user,
        user.organization_id,
        "report.corrected",
        "report",
        item.id,
        after={"version": item.latest_version},
        purpose=values.reason,
    )
    db.flush()
    return service.report_detail(db, user, item)


class Review(Input):
    action: Literal["review", "verify", "clarify", "escalate", "resolve"]
    note: str = Field(min_length=3, max_length=10000)
    version: int


@router.post("/reports/{record_id}/review")
def review(
    record_id: str,
    values: Review,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    item = service.accessible_report(db, user, record_id, values.note)
    require_department(db, user, item.department_id, "review")
    if values.version != item.version:
        fail(409, "Review the latest version before deciding.")
    if values.action == "review":
        if item.status == "submitted":
            item.status = "reviewed"
        # Reviewing a report does not remove uncertainty or resolve its conditions.
    elif values.action == "verify":
        item.status, item.verified_at, item.verified_by = "verified", now(), user.id
        # Verification confirms accuracy, never silently resolves the issue.
    elif values.action == "clarify":
        unanswered = db.scalar(
            select(func.count())
            .select_from(Clarification)
            .where(Clarification.report_id == item.id, Clarification.responded_at.is_(None))
        )
        if unanswered >= 3:
            fail(
                409,
                "Three questions are already awaiting a response. Review existing uncertainty instead of repeating questions.",
            )
        clarification = Clarification(
            organization_id=user.organization_id,
            report_id=item.id,
            requested_by=user.id,
            recipient_id=item.author_id,
            question=values.note,
        )
        db.add(clarification)
        db.flush()
        notify(
            db,
            user.organization_id,
            item.author_id,
            f"clarification:{clarification.id}",
            "Clarification requested",
            values.note,
            f"/workspace/reports/{item.id}",
        )
        item.needs_attention = True
    elif values.action == "escalate":
        from ..services.alerts import create_alert

        create_alert(db, user, item.department_id, "Report escalated for action", item.id)
        item.needs_attention = True
    else:
        from ..models import Alert

        unfinished = db.scalar(
            select(Task.id)
            .join(ReportTaskLink, ReportTaskLink.task_id == Task.id)
            .where(ReportTaskLink.report_id == item.id, Task.status != "closed")
        )
        conflict = db.scalar(
            select(Conflict.id)
            .join(ConflictReport, ConflictReport.conflict_id == Conflict.id)
            .where(ConflictReport.report_id == item.id, Conflict.status != "resolved")
        )
        alert = db.scalar(select(Alert.id).where(Alert.report_id == item.id, Alert.status != "resolved"))
        if item.status != "verified" or unfinished or conflict or alert:
            fail(
                409,
                "Verify this report and finish linked actions, conflicts and alerts before resolving the issue.",
            )
        item.resolved_at, item.needs_attention = now(), False
    db.add(
        ReportReview(
            organization_id=user.organization_id,
            report_id=item.id,
            reviewer_id=user.id,
            action=values.action,
            note=values.note,
            version_number=item.latest_version,
        )
    )
    audit(db, user, user.organization_id, f"report.{values.action}", "report", item.id, purpose=values.note)
    db.flush()
    return record_dict(item)


class ExistingTask(Input):
    task_id: str
    note: str = Field(min_length=10, max_length=5000)
    version: int


@router.post("/reports/{record_id}/tasks", status_code=201)
def link_task(
    record_id: str,
    values: ExistingTask,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    from ..services.tasks import visible_task

    report = service.accessible_report(db, user, record_id, values.note)
    require_department(db, user, report.department_id, "review")
    if values.version != report.version:
        fail(409, "Review the latest report before linking work.")
    task = visible_task(db, user, values.task_id)
    if task.department_id != report.department_id:
        fail(422, "Use a cross-department follow-up to link work in another department.")
    existing = db.scalar(
        select(ReportTaskLink).where(ReportTaskLink.report_id == report.id, ReportTaskLink.task_id == task.id)
    )
    if existing:
        return record_dict(existing)
    link = ReportTaskLink(
        organization_id=user.organization_id, report_id=report.id, task_id=task.id, linked_by=user.id
    )
    db.add(link)
    report.updated_at = now()
    db.add(
        ReportReview(
            organization_id=user.organization_id,
            report_id=report.id,
            reviewer_id=user.id,
            action="task_linked",
            note=values.note,
            version_number=report.latest_version,
        )
    )
    audit(
        db,
        user,
        user.organization_id,
        "report.task_linked",
        "report",
        report.id,
        after={"task_id": task.id},
        purpose=values.note,
    )
    db.flush()
    return record_dict(link)


class ClarificationResponse(Input):
    response_type: Literal["confirm", "correct", "context", "uncertain"]
    response: str = Field(min_length=1, max_length=10000)
    conversation_id: str | None = None
    conversation_revision: int | None = None


@router.get("/clarifications")
def clarifications(user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    query = select(Clarification).where(Clarification.organization_id == user.organization_id)
    if user.role == "worker":
        query = query.where(Clarification.recipient_id == user.id)
    else:
        query = query.where(
            Clarification.report_id.in_(service.report_query(db, user).with_only_columns(Report.id))
        )
    return [
        record_dict(item) for item in db.scalars(query.order_by(Clarification.created_at.desc()).limit(200))
    ]


@router.post("/clarifications/{record_id}/response")
def respond(
    record_id: str,
    values: ClarificationResponse,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    item = scoped(db, Clarification, record_id, user)
    if item.recipient_id != user.id:
        fail(403, "Only the requested person can answer.")
    if item.responded_at:
        fail(409, "This answer is already recorded. Submit a report correction for further changes.")
    if values.conversation_id:
        from ..services.conversations import accessible
        conversation = accessible(db, user, values.conversation_id)
        if conversation.clarification_id != item.id or conversation.revision != values.conversation_revision or conversation.status != "ready":
            fail(409, "Review the latest clarification conversation before sending.")
        if not conversation.state.get("answer"):
            fail(422, "Answer the clarification before sending.")
        values.response, values.response_type = conversation.state["answer"], conversation.state["answer_type"]
        conversation.status = "submitted"
    item.response_type, item.response, item.responded_at = values.response_type, values.response, now()
    report = db.get(Report, item.report_id)
    service.attention(db, report, f"clarified:{item.id}", "A clarification response is ready for review.")
    if item.conflict_id:
        conflict = db.get(Conflict, item.conflict_id)
        for reviewer in service.reviewers(db, conflict.department_id):
            notify(db, user.organization_id, reviewer, f"clarification:{item.id}:answered",
                   "A clarification response is ready", "Review the related observations before resolving the difference.",
                   f"/workspace/conflicts/{conflict.id}")
    audit(
        db,
        user,
        user.organization_id,
        "clarification.responded",
        "clarification",
        item.id,
        after={"response_type": item.response_type},
    )
    return record_dict(item)


@router.get("/conflicts")
def conflicts(user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    allowed = department_ids(db, user)
    related = select(ConflictReport.conflict_id).join(Report, Report.id == ConflictReport.report_id).where(Report.department_id.in_(allowed))
    query = select(Conflict).where(Conflict.organization_id == user.organization_id,
                                 or_(Conflict.department_id.in_(allowed), Conflict.id.in_(related)))
    if user.role == "worker":
        query = query.where(
            Conflict.id.in_(
                select(ConflictReport.conflict_id)
                .join(Report, Report.id == ConflictReport.report_id)
                .where(Report.author_id == user.id)
            )
        )
    items = []
    review_departments = department_ids(db, user, "review") if user.role == "supervisor" else []
    for item in db.scalars(query.order_by(Conflict.created_at.desc()).limit(200)):
        value = record_dict(item)
        if item.department_id not in review_departments:
            # Comparison values and supervisor notes contain the other worker's
            # private report. The detail route has its own access/purpose gate.
            value.update(title="Related reports need comparison",
                         discrepancy="A supervisor is reviewing related reports. Respond to your own clarification request.",
                         resolution="")
        items.append(value)
    return items


@router.get("/conflicts/{record_id}")
def conflict_detail(
    record_id: str,
    purpose: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    item = scoped(db, Conflict, record_id, user)
    links = list(db.scalars(select(ConflictReport).where(ConflictReport.conflict_id == item.id)))
    rows = [(link, db.get(Report, link.report_id)) for link in links]
    review = set(department_ids(db, user, "review"))
    if not any(report.department_id in review for _, report in rows):
        fail(403, "Supervisor review permission is required for this comparison.")
    from ..services.comparisons import linked_departments
    departments = {r.department_id for _, r in rows}
    if len(departments) > 1 and not any(
        {link.source_department_id, link.receiving_department_id} == departments
        for link in linked_departments(db, user.organization_id, item.department_id)):
        fail(403, "The department comparison link is no longer active.")
    sources, shared, versions = [], [], []
    keys = {"category", "quantity", "unit", "quantity_stage", "transfer_complete", "transfer_reference",
            "batch", "order", "machine", "task_reference", "reference_period", "observation_time",
            "quality_status", "dispatch_status", "machine_status", "task_status"}
    for link, report in rows:
        version = db.scalar(select(ReportVersion).where(ReportVersion.report_id == report.id, ReportVersion.number == link.version_number))
        versions.append((report, version))
        if report.department_id in review:
            service.check_sensitive_access(db, user, report.department_id, purpose)
            sources.append({"linked_version": link.version_number, **service.report_detail(db, user, report)})
        else:
            shared.append({"department": db.get(Department, report.department_id).name,
                "version": link.version_number, "fields": {k: v for k, v in version.fields.items() if k in keys},
                "responses": [c.response_type for c in db.scalars(select(Clarification).where(
                    Clarification.conflict_id == item.id, Clarification.report_id == report.id)) if c.responded_at]})
    findings = []
    if len(versions) == 2:
        (a, va), (b, vb) = versions
        if va and vb:
            findings = compare(va.fields, vb.fields, a, b, db.get(Organization, user.organization_id).timezone,
                               cross_department=a.department_id != b.department_id)
            if a.department_id == b.department_id and not any(f["field"] == "quantity" for f in findings):
                from ..models import ReportConversation
                from ..services.retention import expired
                frozen = {a.id: va, b.id: vb}
                for conversation in db.scalars(select(ReportConversation).where(
                    ReportConversation.organization_id == user.organization_id,
                    ReportConversation.report_id.in_(list(frozen)),
                    ReportConversation.status == "submitted",
                )):
                    own = frozen[conversation.report_id]
                    draft = conversation.state.get("draft", {})
                    if expired(db, conversation) or draft.get("fields") != own.fields or draft.get("text") != own.text:
                        continue
                    for evidence in conversation.state.get("findings", []):
                        peer = frozen.get(evidence["report_id"])
                        finding = evidence["finding"]
                        if (peer and peer.number == evidence["version_number"]
                                and finding["category"] == "quantity_context"
                                and not any(f["category"] == "quantity_context" for f in findings)):
                            findings.append(finding)
    return {**record_dict(item), "reports": sources, "shared_sources": shared,
            "can_resolve": item.department_id in review, "findings": findings}


class Resolution(Input):
    resolution: str = Field(min_length=10, max_length=10000)
    version: int


@router.post("/conflicts/{record_id}/resolve")
def resolve_conflict(
    record_id: str,
    values: Resolution,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    item = scoped(db, Conflict, record_id, user)
    require_department(db, user, item.department_id, "review", active=True)
    from ..services.comparisons import linked_departments
    departments = {db.get(Report, link.report_id).department_id for link in db.scalars(
        select(ConflictReport).where(ConflictReport.conflict_id == item.id))}
    if len(departments) > 1 and not any(
        {link.source_department_id, link.receiving_department_id} == departments
        for link in linked_departments(db, user.organization_id, item.department_id)):
        fail(403, "The department comparison link is no longer active.")
    if item.version != values.version or item.status == "resolved":
        fail(409, "Review the latest unresolved conflict first.")
    item.status, item.resolved_by, item.resolved_at, item.resolution = (
        "resolved",
        user.id,
        now(),
        values.resolution,
    )
    for link in db.scalars(select(ConflictReport).where(ConflictReport.conflict_id == item.id)):
        report = db.get(Report, link.report_id)
        notify(
            db,
            user.organization_id,
            report.author_id,
            f"conflict:{item.id}:resolved",
            "A supervisor reviewed the discrepancy",
            "Your original report remains in the history.",
            f"/workspace/reports/{report.id}",
        )
    audit(
        db,
        user,
        user.organization_id,
        "conflict.resolved",
        "conflict",
        item.id,
        after={"resolution": values.resolution},
    )
    db.flush()
    return record_dict(item)
