from typing import Literal
import asyncio
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..config import get_settings
from ..db import get_db, new_id, now
from ..models import BackgroundJob, FileAsset, HandoverVersion, TaskEvidence, Transcript, User
from ..schemas import Input, ReportFields
from ..security import admin, current_user, digest, fail, policy_value, require_department, scoped
from ..services.common import audit, enqueue, record_dict
from ..services.reports import check_sensitive_access
from ..services.retention import expired, retained_job
from ..services.storage import asset_available, delete_bytes, read_bytes, store_asset, validate_bytes

router = APIRouter(tags=["Evidence and processing"])


@router.post("/files", status_code=201)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    department_id: str | None = Form(None),
    kind: str = Form("photo"),
    consent: bool = Form(False),
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    if kind == "logo":
        admin(user)
    elif not department_id:
        fail(422, "Choose a department for this evidence.")
    else:
        require_department(db, user, department_id, active=True)
    if kind == "audio" and not consent:
        fail(422, "Recording consent is required before uploading audio.")
    privacy = policy_value(db, user.organization_id, "privacy")
    if kind in {"photo", "video"} and not privacy.get(
        "photos_allowed" if kind == "photo" else "videos_allowed", True
    ):
        fail(403, "Organization policy does not allow this evidence type.")
    content = await file.read(get_settings().max_upload_bytes + 1)
    content, mime = validate_bytes(content, file.content_type or "", kind)
    for attempt in range(4):
        item = None
        try:
            if attempt:
                user = current_user(request, db)
                if kind == "logo":
                    admin(user)
                else:
                    require_department(db, user, department_id, active=True)
                privacy = policy_value(db, user.organization_id, "privacy")
                if kind in {"photo", "video"} and not privacy.get(
                    "photos_allowed" if kind == "photo" else "videos_allowed", True
                ):
                    fail(403, "Organization policy does not allow this evidence type.")
            item = store_asset(db, user, content, file.filename or "evidence", mime, kind, department_id, consent)
            audit(db, user, user.organization_id, "evidence.uploaded", "file_asset", item.id,
                  after={"kind": kind, "bytes": len(content)})
            if db.bind.dialect.name == "mongodb":
                db.commit()
            return record_dict(item)
        except StaleDataError:
            db.rollback()
            if item:
                delete_bytes(item)
            if db.bind.dialect.name != "mongodb" or attempt == 3:
                raise
            await asyncio.sleep(0.1 * 2**attempt)


@router.get("/files/{record_id}")
def download(
    record_id: str,
    purpose: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    asset = scoped(db, FileAsset, record_id, user)
    if asset.deleted_at or (asset.retention_until and asset.retention_until <= now()):
        fail(410, "This evidence is no longer retained.")
    if asset.owner_id != user.id and asset.kind != "logo":
        if not asset.department_id:
            fail(403, "This file is private.")
        linked_task = db.scalar(select(TaskEvidence.task_id).where(TaskEvidence.asset_id == asset.id))
        if user.role == "worker":
            if not linked_task:
                fail(403, "Only your own evidence or your assigned task instructions are accessible.")
            from ..services.tasks import visible_task

            visible_task(db, user, linked_task)
        else:
            check_sensitive_access(db, user, asset.department_id, purpose, evidence=True)
    audit(db, user, user.organization_id, "evidence.accessed", "file_asset", asset.id, purpose=purpose)
    try:
        content = read_bytes(asset)
    except Exception:
        fail(503, "Evidence storage is temporarily unavailable. Try again later.")
    disposition = "attachment" if asset.kind == "document" else "inline"
    return Response(
        content,
        media_type=asset.mime_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="evidence.{asset.mime_type.split("/")[-1]}"',
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


class TranscriptionInput(Input):
    asset_id: str
    language: Literal["hi-IN", "en-IN", "hi-IN,en-IN"] = "hi-IN,en-IN"
    task_id: str | None = None


@router.get("/voice/capabilities")
def voice_capabilities(user: User = Depends(current_user)):
    settings = get_settings()
    return {
        "transcription": bool(settings.gnani_api_key),
        "playback": bool(settings.gnani_api_key),
        "extraction": bool(settings.gemini_api_key),
        "max_recording_seconds": 29,
    }


@router.post("/transcriptions", status_code=202)
def transcribe(
    values: TranscriptionInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    asset = scoped(db, FileAsset, values.asset_id, user)
    if (
        asset.owner_id != user.id
        or asset.kind != "audio"
        or not asset.consent
        or asset.deleted_at
        or asset.retention_until <= now()
    ):
        fail(403, "Use your own retained audio recording with consent.")
    if not get_settings().gnani_api_key:
        fail(
            503,
            "Speech transcription is not configured. Your recording is saved; type your update to continue.",
        )
    from ..services.voice import transcription_context

    transcription_context(db, user, asset.department_id, values.task_id)
    job = enqueue(
        db,
        "transcribe",
        f"transcribe:{asset.id}:{values.language}:{values.task_id or ''}",
        values.model_dump(),
        user.organization_id,
        user.id,
    )
    return record_dict(job, {"payload", "lease_token"})


class PlaybackInput(Input):
    language: Literal["hi-IN", "en-IN", "auto"] = "auto"


class ReadbackInput(PlaybackInput):
    department_id: str
    text: str = Field(min_length=1, max_length=20000)
    fields: ReportFields = Field(default_factory=ReportFields)
    immediate_safety: bool = False


def validate_playback_source(db, user, job):
    if expired(db, job):
        fail(410, "The original processing source is no longer retained.")
    require_department(db, user, job.payload["department_id"], active=True)
    source = job.payload.get("source", "")
    if source.startswith("handover:"):
        from ..services.handovers import visible_handover
        version = scoped(db, HandoverVersion, source.split(":", 1)[1], user)
        visible_handover(db, user, version.handover_id)
    elif source.startswith("conversation:"):
        from ..services.conversations import accessible
        _, identity, revision = source.split(":")
        conversation = accessible(db, user, identity)
        if conversation.revision != int(revision):
            fail(409, "This question has changed. Use the current conversation.")


def reserve_local_playback(job, background_tasks):
    from ..worker import execute
    job.status, job.lease_token = "processing", new_id()
    job.leased_until = now() + timedelta(minutes=3)
    # A failed local repair requires an explicit retry here, so an unrelated
    # machine cannot take the repaired job and put its audio on another disk.
    job.attempts = job.max_attempts
    job.payload = {**job.payload, "recover_on_origin": True}
    background_tasks.add_task(execute, job.id, job.lease_token)


def recover_playback(db, user, job, background_tasks):
    """Repair derived speech only, keeping the original source and job identity.

    Local files are not shared by other machines using the same database. Reserve
    the repair's lease here and execute after the request commits, on this API's
    filesystem. Other queue workers cannot claim it while the lease is active.
    """
    validate_playback_source(db, user, job)
    if job.status != "succeeded":
        return
    asset = db.get(FileAsset, job.result.get("asset_id")) if job.result.get("asset_id") else None
    if not asset or asset.deleted_at or (asset.retention_until and asset.retention_until <= now()):
        fail(410, "This generated audio is no longer retained.")
    if asset.organization_id != user.organization_id or asset.owner_id != user.id:
        fail(403, "This audio belongs to another account.")
    try:
        available = asset_available(asset)
    except Exception:
        fail(503, "Audio storage is temporarily unavailable. Please try again later.")
    if available:
        return
    job.result, job.error, job.completed_at = {}, "", None
    job.attempts, job.available_at = 0, now()
    if get_settings().storage_mode == "local":
        reserve_local_playback(job, background_tasks)
    else:
        job.status, job.lease_token, job.leased_until = "queued", None, None
    audit(db, user, user.organization_id, "speech.regeneration_requested", "background_job", job.id)


def queue_playback(db, user, text, department_id, language, source, background_tasks):
    settings = get_settings()
    if not settings.gnani_api_key:
        fail(503, "Spoken playback is not configured. Review your update in writing.")
    fingerprint = digest(
        f"{text}:{language}:{settings.gnani_tts_model}:{settings.gnani_tts_voice}:{settings.gnani_tts_speed}"
    )
    job = enqueue(
        db,
        "speak",
        f"speak:{user.id}:{department_id}:{source}:{fingerprint}",
        {"text": text, "department_id": department_id, "language": language, "source": source},
        user.organization_id,
        user.id,
    )
    if job.status == "succeeded":
        recover_playback(db, user, job, background_tasks)
    return record_dict(job, {"payload", "lease_token"})


@router.post("/report-readback", status_code=202)
def report_readback(
    values: ReadbackInput, background_tasks: BackgroundTasks,
    user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    from ..services.voice import report_script

    require_department(db, user, values.department_id, active=True)
    if not values.text.strip():
        fail(422, "Add your update before listening.")
    script = report_script(values.text, values.fields, values.language, values.immediate_safety)
    return queue_playback(db, user, script, values.department_id, values.language, "report-readback", background_tasks)


class ExtractionInput(Input):
    text: str = Field(min_length=1, max_length=20000)
    transcript_id: str | None = None


@router.post("/extractions", status_code=202)
def extract(
    values: ExtractionInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    if not get_settings().gemini_api_key:
        fail(503, "AI extraction is not configured. Complete and review the report fields manually.")
    if values.transcript_id:
        transcript = scoped(db, Transcript, values.transcript_id, user)
        if transcript.author_id != user.id:
            fail(403, "Use your own transcript.")
    else:
        transcript = Transcript(
            organization_id=user.organization_id,
            author_id=user.id,
            original=values.text,
            language=user.preferences.get("speech_language", "hi-IN,en-IN"),
        )
        db.add(transcript)
        db.flush()
    from ..security import digest

    job = enqueue(
        db,
        "extract",
        f"extract:{transcript.id}:{digest(values.text)}",
        {"transcript_id": transcript.id, "text": values.text},
        user.organization_id,
        user.id,
    )
    return record_dict(job, {"payload", "lease_token"})


@router.get("/jobs/{record_id}")
def job_status(
    record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    job = scoped(db, BackgroundJob, record_id, user)
    if job.actor_id != user.id:
        fail(403, "This processing request belongs to another account.")
    return retained_job(db, job)


@router.post("/jobs/{record_id}/retry")
def retry(
    record_id: str, background_tasks: BackgroundTasks,
    user: User = Depends(current_user), db: Session = Depends(get_db, scope="function")
):
    job = scoped(db, BackgroundJob, record_id, user)
    if job.actor_id != user.id or job.kind not in {"transcribe", "extract", "speak", "conversation_transcribe", "conversation_analyze"}:
        fail(403, "This job cannot be retried from this account.")
    if job.kind == "speak":
        validate_playback_source(db, user, job)
        if job.status == "succeeded":
            recover_playback(db, user, job, background_tasks)
            return record_dict(job, {"payload", "lease_token"})
        if job.status in {"queued", "processing"}:
            return record_dict(job, {"payload", "lease_token"})
    if job.status != "failed":
        fail(409, "Only failed processing requests can be retried.")
    if expired(db, job):
        fail(410, "The original processing source is no longer retained. Create a new report.")
    if job.kind.startswith("conversation_"):
        from ..services.conversations import accessible
        conversation = accessible(db, user, job.payload["conversation_id"])
        if conversation.revision != job.payload["revision"] or conversation.status == "submitted":
            fail(409, "This conversation changed. Use the latest update.")
        conversation.status = "processing"
        conversation.state = {**conversation.state, "check_error": ""}
    job.status, job.attempts, job.error, job.available_at = "queued", 0, "", now()
    if job.kind == "speak" and job.payload.get("recover_on_origin") and get_settings().storage_mode == "local":
        reserve_local_playback(job, background_tasks)
    return record_dict(job, {"payload", "lease_token"})


@router.post("/handover-audio/{version_id}", status_code=202)
def handover_audio(
    version_id: str,
    background_tasks: BackgroundTasks,
    values: PlaybackInput | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db, scope="function"),
):
    from ..services.handovers import visible_handover
    from ..services.voice import handover_script

    version = scoped(db, HandoverVersion, version_id, user)
    handover = visible_handover(db, user, version.handover_id)
    language = values.language if values else "auto"
    return queue_playback(
        db,
        user,
        handover_script(version, language),
        handover.department_id,
        language,
        f"handover:{version.id}",
        background_tasks,
    )
