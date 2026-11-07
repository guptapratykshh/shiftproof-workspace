import hashlib
import json
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import now
from ..models import (
    AIExtraction,
    Alert,
    AlertHistory,
    Clarification,
    Conflict,
    ConflictReport,
    Department,
    DepartmentMembership,
    FileAsset,
    Organization,
    Report,
    ReportEvidence,
    ReportReview,
    ReportTaskLink,
    ReportVersion,
    Shift,
    Team,
    TeamMembership,
    Transcript,
    User,
)
from ..schemas import ReportInput
from ..security import department_ids, fail, policy_value, require_department, scoped
from .common import audit, notify, record_dict
from .contradictions import summary
from .retention import retained_record


def report_query(db: Session, user: User):
    query = select(Report).where(
        Report.organization_id == user.organization_id, Report.department_id.in_(department_ids(db, user))
    )
    if user.role == "worker":
        query = query.where(Report.author_id == user.id)
    return query


def check_sensitive_access(db: Session, user: User, department_id: str, purpose: str, evidence=False):
    require_department(db, user, department_id)
    if user.role == "organization":
        key = "admin_recording_access" if evidence else "admin_report_access"
        takeover = department_id in department_ids(db, user, "review")
        if not takeover and not policy_value(db, user.organization_id, "privacy").get(key, False):
            fail(
                403,
                "Organization privacy policy restricts individual records. An authorized, time-limited takeover is required.",
            )
        if len(purpose.strip()) < 10:
            fail(422, "Provide a purpose for sensitive administrative access (at least 10 characters).")
    elif evidence and user.role == "supervisor":
        require_department(db, user, department_id, "evidence")


def accessible_report(db: Session, user: User, report_id: str, purpose=""):
    report = db.scalar(report_query(db, user).where(Report.id == report_id))
    if not report:
        fail(404, "Report not found.")
    check_sensitive_access(db, user, report.department_id, purpose)
    if user.role == "organization":
        audit(db, user, user.organization_id, "report.accessed", "report", report.id, purpose=purpose)
    return report


def reviewers(db: Session, department_id: str):
    return [
        m.user_id
        for m in db.scalars(
            select(DepartmentMembership)
            .join(User, User.id == DepartmentMembership.user_id)
            .where(
                DepartmentMembership.department_id == department_id,
                DepartmentMembership.active.is_(True),
                User.active.is_(True),
                User.role == "supervisor",
            )
        )
        if "review" in m.permissions
    ]


def attention(db: Session, report: Report, event: str, message: str):
    for recipient in reviewers(db, report.department_id):
        notify(
            db,
            report.organization_id,
            recipient,
            f"report:{report.id}:{event}",
            "Report needs attention",
            message,
            f"/workspace/reports/{report.id}",
        )


def validate_sources(db: Session, user: User, values: ReportInput):
    require_department(db, user, values.department_id, active=True)
    if not db.get(Organization, user.organization_id).active:
        fail(409, "The organization must complete activation before submitting operational reports.")
    if values.occurred_at > now() + timedelta(minutes=5):
        fail(422, "Occurrence time cannot be in the future.")
    if values.team_id:
        team = scoped(db, Team, values.team_id, user)
        if not team.active or team.department_id != values.department_id:
            fail(422, "Choose an active team in the report department.")
        if user.role == "worker" and not db.scalar(
            select(TeamMembership.id).where(
                TeamMembership.team_id == team.id,
                TeamMembership.user_id == user.id,
                TeamMembership.active.is_(True),
            )
        ):
            fail(403, "This team is not one of your memberships.")
    if values.shift_id:
        scoped(db, Shift, values.shift_id, user)
    if values.immediate_alert_id:
        alert = scoped(db, Alert, values.immediate_alert_id, user)
        owner = db.scalar(
            select(AlertHistory.id).where(
                AlertHistory.alert_id == alert.id,
                AlertHistory.actor_id == user.id,
                AlertHistory.action == "created",
            )
        )
        if (
            not owner
            or alert.department_id != values.department_id
            or not values.immediate_safety
            or alert.report_id
        ):
            fail(422, "Link only your own unlinked safety alert from this department.")
    if values.transcript_id:
        transcript = scoped(db, Transcript, values.transcript_id, user)
        if transcript.author_id != user.id:
            fail(403, "Use your own transcript.")
    if values.extraction_id:
        extraction = scoped(db, AIExtraction, values.extraction_id, user)
        if extraction.author_id != user.id or extraction.transcript_id != values.transcript_id:
            fail(403, "The suggestion must belong to this transcript and account.")
    if values.task_id:
        from .tasks import visible_task

        task = visible_task(db, user, values.task_id)
        if task.department_id != values.department_id:
            fail(422, "The linked task must belong to the originating department.")
    for asset_id in set(values.evidence_ids):
        asset = scoped(db, FileAsset, asset_id, user)
        if asset.owner_id != user.id or asset.deleted_at or asset.department_id != values.department_id:
            fail(403, "Evidence must belong to you and this department.")
        if asset.retention_until and asset.retention_until <= now():
            fail(410, "This evidence has reached its retention limit.")


def append_version(db: Session, user: User, report: Report, values: ReportInput, reason=""):
    report.latest_version += 1
    version = ReportVersion(
        organization_id=user.organization_id,
        report_id=report.id,
        number=report.latest_version,
        text=values.text,
        fields=values.fields.model_dump(mode="json"),
        transcript_id=values.transcript_id,
        extraction_id=values.extraction_id,
        author_id=user.id,
        correction_reason=reason,
    )
    db.add(version)
    db.flush()
    for asset_id in set(values.evidence_ids):
        db.add(ReportEvidence(organization_id=user.organization_id, version_id=version.id, asset_id=asset_id))
    if values.task_id and not db.scalar(
        select(ReportTaskLink.id).where(
            ReportTaskLink.report_id == report.id, ReportTaskLink.task_id == values.task_id
        )
    ):
        db.add(
            ReportTaskLink(
                organization_id=user.organization_id,
                report_id=report.id,
                task_id=values.task_id,
                linked_by=user.id,
            )
        )
    return version


def detect_conflicts(db: Session, report: Report, version: ReportVersion):
    from .comparisons import candidates
    from .conversations import recorded_answer
    fields = version.fields
    for match in candidates(db, report, fields):
        previous, other, findings = match["report"], match["version"], match["findings"]
        already = db.scalar(
            select(ConflictReport.conflict_id).where(
                ConflictReport.report_id == report.id,
                ConflictReport.version_number == version.number,
                ConflictReport.conflict_id.in_(
                    select(ConflictReport.conflict_id).where(
                        ConflictReport.report_id == previous.id,
                        ConflictReport.version_number == other.number,
                    )
                ),
            )
        )
        if already:
            continue
        conflict = Conflict(
            organization_id=report.organization_id,
            department_id=match["owner_department_id"],
            title=" / ".join(finding["title"] for finding in findings)[:200],
            discrepancy=summary(findings),
        )
        db.add(conflict)
        db.flush()
        for source, number in [(report, version.number), (previous, other.number)]:
            source.needs_attention = True
            db.add(
                ConflictReport(
                    organization_id=report.organization_id,
                    conflict_id=conflict.id,
                    report_id=source.id,
                    version_number=number,
                )
            )
            own_fields = fields if source.id == report.id else other.fields
            peer_fields = other.fields if source.id == report.id else fields
            own_value = own_fields.get(findings[0]["field"])
            peer_value = peer_fields.get(findings[0]["field"])
            reference = own_fields.get("transfer_reference") or own_fields.get("batch") or own_fields.get("machine") or own_fields.get("order") or own_fields.get("task_reference") or "this work"
            question = f"For {reference}, your report says {own_value} {own_fields.get('unit') or ''}; a related report says {peer_value} {peer_fields.get('unit') or ''}. Please confirm your own observation, correct it, explain the time or transfer context, or say you are unsure."
            answered = recorded_answer(db, source.id, previous.id if source.id == report.id else report.id,
                                       other.number if source.id == report.id else version.number)
            clarification = Clarification(
                organization_id=report.organization_id,
                report_id=source.id,
                conflict_id=conflict.id,
                recipient_id=source.author_id,
                question=question,
                response=answered["text"] if answered else None,
                response_type=answered["response_type"] if answered else None,
                responded_at=now() if answered else None,
            )
            db.add(clarification)
            db.flush()
            notify(
                db,
                report.organization_id,
                source.author_id,
                f"clarification:{clarification.id}",
                "Verification pending" if answered else "A report needs clarification",
                "Your answer is saved. A supervisor will verify the related reports." if answered else question,
                f"/workspace/reports/{source.id}",
            )
        for department_id in {report.department_id, previous.department_id}:
            for recipient in reviewers(db, department_id):
                notify(db, report.organization_id, recipient, f"conflict:{conflict.id}",
                       "Related reports need verification", conflict.discrepancy,
                       f"/workspace/conflicts/{conflict.id}")


def lock_comparison_context(db: Session, user: User, department_id: str):
    # Two different workers can submit at once. A shared departmental write
    # forces one transaction to retry against the other's committed report,
    # avoiding two snapshots that each see no counterpart.
    from .comparisons import linked_departments
    ids = {department_id}
    for link in linked_departments(db, user.organization_id, department_id):
        ids.update([link.source_department_id, link.receiving_department_id])
    for identity in sorted(ids):
        db.execute(update(Department).where(Department.id == identity,
            Department.organization_id == user.organization_id).values(updated_at=now()))



def submit(db: Session, user: User, values: ReportInput):
    # Serialize one reporter's retries before checking the unique submission key.
    db.execute(update(User).where(User.id == user.id).values(updated_at=now()))
    request_value = values.model_dump(mode="json")
    for key in ("conversation_id", "conversation_revision"):
        if request_value[key] is None:
            request_value.pop(key)
    for key in ("quantity_stage", "transfer_reference", "transfer_complete"):
        if request_value["fields"].get(key) is None:
            request_value["fields"].pop(key, None)
    fingerprint = hashlib.sha256(json.dumps(request_value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    existing = db.scalar(
        select(Report).where(
            Report.organization_id == user.organization_id,
            Report.author_id == user.id,
            Report.client_request_id == values.client_request_id,
        )
    )
    if existing:
        if existing.request_hash != fingerprint:
            fail(
                409,
                "This submission key was already used with different information. Review the saved report.",
            )
        return existing
    validate_sources(db, user, values)
    lock_comparison_context(db, user, values.department_id)
    from .conversations import verify_submission
    conversation = verify_submission(db, user, values)
    fields = values.fields
    required_evidence = policy_value(db, user.organization_id, "operations").get(
        "evidence_required_categories", []
    )
    needs_attention = bool(
        values.immediate_safety
        or fields.category in {"safety", "quality"}
        or fields.uncertainty
        or (conversation and conversation.state.get("unresolved"))
        or fields.safety_implication
        or fields.quality_implication
        or (fields.category in required_evidence and not values.evidence_ids)
    )
    report = Report(
        organization_id=user.organization_id,
        author_id=user.id,
        department_id=values.department_id,
        team_id=values.team_id,
        shift_id=values.shift_id,
        client_request_id=values.client_request_id,
        request_hash=fingerprint,
        occurred_at=values.occurred_at,
        submitted_at=now(),
        category=fields.category,
        status="submitted",
        immediate_safety=values.immediate_safety,
        needs_attention=needs_attention,
    )
    db.add(report)
    db.flush()
    version = append_version(db, user, report, values)
    if conversation:
        conversation.report_id, conversation.status = report.id, "submitted"
        db.flush()
    if values.immediate_safety:
        from .alerts import create_alert

        if values.immediate_alert_id:
            alert = db.get(Alert, values.immediate_alert_id)
            alert.report_id = report.id
            db.add(
                AlertHistory(
                    organization_id=user.organization_id,
                    alert_id=alert.id,
                    actor_id=user.id,
                    action="source_linked",
                    detail={"report_id": report.id},
                )
            )
            audit(
                db,
                user,
                user.organization_id,
                "alert.source_linked",
                "alert",
                alert.id,
                after={"report_id": report.id},
            )
        else:
            create_alert(
                db, user, report.department_id, "Immediate safety concern", report.id, immediate=True
            )
    if needs_attention:
        attention(db, report, "submitted", "Review the confirmed report and its source.")
    detect_conflicts(db, report, version)
    audit(
        db,
        user,
        user.organization_id,
        "report.submitted",
        "report",
        report.id,
        after={"version": version.number, "needs_attention": report.needs_attention},
    )
    db.flush()
    return report


def report_detail(db: Session, user: User, report: Report):
    versions = []
    for version in db.scalars(
        select(ReportVersion)
        .where(ReportVersion.report_id == report.id)
        .order_by(ReportVersion.number.desc())
    ):
        item = record_dict(version)
        item["evidence"] = [
            record_dict(asset)
            for asset in db.scalars(
                select(FileAsset)
                .join(ReportEvidence, ReportEvidence.asset_id == FileAsset.id)
                .where(ReportEvidence.version_id == version.id)
            )
        ]
        item["transcript"] = (
            retained_record(db, db.get(Transcript, version.transcript_id)) if version.transcript_id else None
        )
        item["extraction"] = (
            retained_record(db, db.get(AIExtraction, version.extraction_id))
            if version.extraction_id
            else None
        )
        versions.append(item)
    clarifications = select(Clarification).where(Clarification.report_id == report.id)
    from ..models import ReportConversation, ConversationTurn
    from .retention import expired
    conversations = []
    for conversation in db.scalars(select(ReportConversation).where(ReportConversation.report_id == report.id)):
        if not expired(db, conversation):
            conversations.append({"id": conversation.id, "status": conversation.status,
                "turns": [record_dict(turn, {"details"}) for turn in db.scalars(select(ConversationTurn).where(
                    ConversationTurn.conversation_id == conversation.id).order_by(ConversationTurn.created_at))]})
    return {
        **record_dict(report),
        "versions": versions,
        "conversations": conversations,
        "reviews": [
            record_dict(item)
            for item in db.scalars(
                select(ReportReview)
                .where(ReportReview.report_id == report.id)
                .order_by(ReportReview.created_at)
            )
        ],
        "clarifications": [
            record_dict(item) for item in db.scalars(clarifications.order_by(Clarification.created_at))
        ],
        "task_links": [
            record_dict(item)
            for item in db.scalars(select(ReportTaskLink).where(ReportTaskLink.report_id == report.id))
        ],
        "conflict_ids": list(
            db.scalars(select(ConflictReport.conflict_id).where(ConflictReport.report_id == report.id))
        ),
    }
