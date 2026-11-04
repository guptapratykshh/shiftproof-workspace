from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, now
from ..models import BackgroundJob, FileAsset, HandoverVersion, TaskEvidence, Transcript, User
from ..schemas import Input
from ..security import admin, current_user, fail, policy_value, require_department, scoped
from ..services.common import audit, enqueue, record_dict
from ..services.reports import check_sensitive_access
from ..services.storage import read_bytes, store_asset, validate_bytes
from ..services.retention import expired, retained_job

router = APIRouter(tags=["Evidence and processing"])


@router.post("/files", status_code=201)
async def upload(
    file: UploadFile = File(...),
    department_id: str | None = Form(None),
    kind: str = Form("photo"),
    consent: bool = Form(False),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
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
    item = store_asset(db, user, content, file.filename or "evidence", mime, kind, department_id, consent)
    audit(
        db,
        user,
        user.organization_id,
        "evidence.uploaded",
        "file_asset",
        item.id,
        after={"kind": kind, "bytes": len(content)},
    )
    return record_dict(item)


@router.get("/files/{record_id}")
def download(
    record_id: str, purpose: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)
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


@router.post("/transcriptions", status_code=202)
def transcribe(values: TranscriptionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
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
    job = enqueue(
        db,
        "transcribe",
        f"transcribe:{asset.id}:{values.language}",
        values.model_dump(),
        user.organization_id,
        user.id,
    )
    return record_dict(job, {"payload", "lease_token"})


class ExtractionInput(Input):
    text: str = Field(min_length=1, max_length=20000)
    transcript_id: str | None = None


@router.post("/extractions", status_code=202)
def extract(values: ExtractionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
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
def job_status(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = scoped(db, BackgroundJob, record_id, user)
    if job.actor_id != user.id:
        fail(403, "This processing request belongs to another account.")
    return retained_job(db, job)


@router.post("/jobs/{record_id}/retry")
def retry(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = scoped(db, BackgroundJob, record_id, user)
    if job.actor_id != user.id or job.kind not in {"transcribe", "extract", "speak"}:
        fail(403, "This job cannot be retried from this account.")
    if job.status != "failed":
        fail(409, "Only failed processing requests can be retried.")
    if expired(db, job):
        fail(410, "The original processing source is no longer retained. Create a new report.")
    job.status, job.attempts, job.error, job.available_at = "queued", 0, "", now()
    return record_dict(job, {"payload", "lease_token"})


@router.post("/handover-audio/{version_id}", status_code=202)
def handover_audio(version_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..services.handovers import visible_handover

    version = scoped(db, HandoverVersion, version_id, user)
    handover = visible_handover(db, user, version.handover_id)
    if not get_settings().gnani_api_key:
        fail(503, "Handover audio is not configured. The written handover is available.")
    text = (
        ("Pending supervisor review. " if version.provisional else "Published handover. ")
        + version.snapshot.get("notes", "")
        + ". "
        + ". ".join(
            f"{item['title']}. Status: {item['detail'].get('status', 'pending')}"
            for item in version.snapshot.get("items", [])
        )
    )
    job = enqueue(
        db,
        "speak",
        f"speak:{version.id}:{user.id}",
        {"text": text, "department_id": handover.department_id},
        user.organization_id,
        user.id,
    )
    return record_dict(job, {"payload", "lease_token"})
