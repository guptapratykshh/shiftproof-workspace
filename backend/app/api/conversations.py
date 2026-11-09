from typing import Literal
import time

from fastapi import APIRouter, Depends, Request
from pydantic import Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..db import get_db
from ..models import (
    BackgroundJob,
    Clarification,
    ConflictReport,
    ConversationTurn,
    Department,
    DepartmentLink,
    ReportConversation,
    ReportVersion,
    User,
)
from ..schemas import Input, ReportInput
from ..security import admin, current_user, department_ids, fail, scoped
from ..services import conversations as service
from ..services.common import audit, enqueue, job_key, record_dict
from ..services.reports import accessible_report, validate_sources

router = APIRouter(tags=["Report conversations"])


def retry_write(request, db, user, operation):
    # Speech jobs and turns can touch the same referenced records in MongoDB.
    # Retry the whole idempotent transaction, including fresh authorization.
    # HTTP revision conflicts are deliberately not caught here.
    for attempt in range(6):
        try:
            result = operation(user)
            if db.bind.dialect.name == "mongodb":
                db.commit()
            return result
        except StaleDataError:
            if db.bind.dialect.name != "mongodb" or attempt == 5:
                raise
            db.rollback()
            time.sleep(0.15 * 2**attempt)
            user = current_user(request, db)


class Draft(ReportInput):
    text: str = Field(default="", max_length=20000)


class Create(Input):
    client_request_id: str = Field(min_length=16, max_length=80)
    draft: Draft
    language: Literal["hi-IN", "en-IN", "hi-IN,en-IN"] = "hi-IN,en-IN"
    clarification_id: str | None = None


@router.post("/report-conversations", status_code=201)
def create(
    values: Create, request: Request,
    user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    return retry_write(request, db, user, lambda actor: create_once(values, actor, db))


def create_once(values, user, db):
    validate_sources(db, user, values.draft)
    existing = db.scalar(
        select(ReportConversation).where(
            ReportConversation.author_id == user.id,
            ReportConversation.client_request_id == values.client_request_id,
        )
    )
    if existing:
        service.accessible(db, user, existing.id)
        if (
            existing.department_id != values.draft.department_id
            or existing.clarification_id != values.clarification_id
        ):
            fail(409, "This conversation key already belongs to another context.")
        return service.public_state(db, existing)
    draft = values.draft.model_dump(mode="json")
    draft["conversation_id"], draft["conversation_revision"] = None, None
    question, report_id = "", None
    if values.clarification_id:
        clarification = scoped(db, Clarification, values.clarification_id, user)
        if clarification.recipient_id != user.id or clarification.responded_at:
            fail(409, "This clarification cannot be answered by this account.")
        report = accessible_report(db, user, clarification.report_id)
        if report.department_id != values.draft.department_id:
            fail(422, "Use the clarification's department.")
        linked = (
            db.scalar(
                select(ConflictReport).where(
                    ConflictReport.conflict_id == clarification.conflict_id,
                    ConflictReport.report_id == report.id,
                )
            )
            if clarification.conflict_id
            else None
        )
        version = db.scalar(
            select(ReportVersion).where(
                ReportVersion.report_id == report.id,
                ReportVersion.number == (linked.version_number if linked else report.latest_version),
            )
        )
        draft.update(
            text=version.text,
            fields=version.fields,
            shift_id=report.shift_id,
            occurred_at=report.occurred_at.isoformat(),
        )
        question, report_id = clarification.question, report.id
    conversation = ReportConversation(
        organization_id=user.organization_id,
        author_id=user.id,
        department_id=values.draft.department_id,
        client_request_id=values.client_request_id,
        language=values.language,
        clarification_id=values.clarification_id,
        report_id=report_id,
        status="awaiting_answer" if question else "draft",
        state={
            "draft": draft,
            "question": question,
            "question_count": 1 if question else 0,
            "findings": [],
            "answered_keys": [],
            "question_keys": [],
        },
    )
    db.add(conversation)
    db.flush()
    if question:
        findings = service.comparison(db, conversation, draft)
        conversation.state = {
            **conversation.state,
            "findings": findings,
            "question_keys": [f["key"] for f in findings],
            "speech_job_id": service.speech_job(db, conversation, question),
        }
        db.add(
            ConversationTurn(
                organization_id=user.organization_id,
                conversation_id=conversation.id,
                revision=0,
                role="assistant",
                text=question,
                details={"kind": "question"},
            )
        )
    audit(db, user, user.organization_id, "conversation.started", "report_conversation", conversation.id)
    return service.public_state(db, conversation)


@router.get("/report-conversations/{identity}")
def detail(
    identity: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    return service.public_state(db, service.accessible(db, user, identity))


class Turn(Input):
    client_turn_id: str = Field(min_length=16, max_length=80)
    revision: int = Field(ge=0)
    kind: Literal["update", "reply", "edit", "uncertain"] = "update"
    text: str = Field(default="", max_length=20000)
    asset_id: str | None = None
    draft: Draft | None = None

    @model_validator(mode="after")
    def content(self):
        if self.asset_id and self.text:
            raise ValueError("Use either a recording or text for a turn")
        if not self.asset_id and not self.text and self.kind != "uncertain":
            raise ValueError("Add your update or answer")
        return self


@router.post("/report-conversations/{identity}/turns", status_code=202)
def turn(
    identity: str,
    values: Turn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    return retry_write(request, db, user, lambda actor: turn_once(identity, values, actor, db))


def turn_once(identity, values, user, db):
    c = service.accessible(db, user, identity)
    previous = db.scalar(
        select(BackgroundJob).where(
            BackgroundJob.dedupe_key == job_key(f"dialogue-turn:{c.id}:{values.client_turn_id}")
        )
    )
    if previous:
        if previous.payload.get("request") != values.model_dump(mode="json"):
            fail(409, "This turn key already contains a different answer.")
        return service.public_state(db, c)
    if c.revision != values.revision or c.status == "submitted":
        fail(409, "This conversation changed. Refresh before replying.")
    if values.kind in {"reply", "uncertain"} and not c.state.get("question"):
        fail(409, "There is no current question. Record a new update instead.")
    draft = values.draft.model_dump(mode="json") if values.draft else c.state["draft"]
    if values.kind in {"reply", "uncertain"}:
        draft = c.state["draft"]
    validate_sources(db, user, Draft.model_validate(draft))
    if draft["department_id"] != c.department_id:
        fail(422, "Start a new conversation for a different department.")
    if values.asset_id:
        service.check_recording(db, user, values.asset_id, c.department_id)
    if c.clarification_id and db.get(Clarification, c.clarification_id).responded_at:
        fail(409, "This clarification already has a submitted answer.")
    c.revision += 1
    c.status = "processing"
    job = enqueue(
        db,
        "conversation_transcribe" if values.asset_id else "conversation_analyze",
        f"dialogue-turn:{c.id}:{values.client_turn_id}",
        {
            "conversation_id": c.id,
            "revision": c.revision,
            "kind": values.kind,
            "client_turn_id": values.client_turn_id,
            "text": values.text or "I am not sure",
            "asset_id": values.asset_id,
            "draft": draft,
            "request": values.model_dump(mode="json"),
        },
        user.organization_id,
        user.id,
    )
    c.state = {**c.state, "job_id": job.id, "speech_job_id": None, "check_error": ""}
    return service.public_state(db, c)


class LinkInput(Input):
    source_department_id: str
    receiving_department_id: str
    active: bool = True


@router.get("/department-links")
def links(user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")):
    query = select(DepartmentLink).where(DepartmentLink.organization_id == user.organization_id)
    if user.role != "organization":
        allowed = department_ids(db, user)
        query = query.where(
            DepartmentLink.active.is_(True),
            or_(
                DepartmentLink.source_department_id.in_(allowed),
                DepartmentLink.receiving_department_id.in_(allowed),
            ),
        )
    return [
        {
            **record_dict(item),
            "source_name": db.get(Department, item.source_department_id).name,
            "receiving_name": db.get(Department, item.receiving_department_id).name,
        }
        for item in db.scalars(query)
    ]


@router.post("/department-links", status_code=201)
def save_link(
    values: LinkInput, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    admin(user)
    if values.source_department_id == values.receiving_department_id:
        fail(422, "Choose two different departments.")
    for identity in (values.source_department_id, values.receiving_department_id):
        if not scoped(db, Department, identity, user).active:
            fail(422, "Both linked departments must be active.")
    item = db.scalar(
        select(DepartmentLink).where(
            DepartmentLink.organization_id == user.organization_id,
            DepartmentLink.source_department_id == values.source_department_id,
            DepartmentLink.receiving_department_id == values.receiving_department_id,
        )
    )
    reverse = db.scalar(
        select(DepartmentLink).where(
            DepartmentLink.organization_id == user.organization_id,
            DepartmentLink.source_department_id == values.receiving_department_id,
            DepartmentLink.receiving_department_id == values.source_department_id,
            DepartmentLink.active.is_(True),
        )
    )
    if values.active and reverse:
        fail(409, "A reverse link is active. Disable it before changing the transfer direction.")
    if not item:
        item = DepartmentLink(organization_id=user.organization_id, **values.model_dump())
        db.add(item)
    else:
        item.active = values.active
    db.flush()
    audit(
        db,
        user,
        user.organization_id,
        "department_link.updated",
        "department_link",
        item.id,
        after=record_dict(item),
    )
    return record_dict(item)
