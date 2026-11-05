"""Durable database worker. Run separately: python -m app.worker."""

import logging
import os
import smtplib
import ssl
import time
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from .config import get_settings
from .db import SessionLocal, new_id, now
from .models import (
    AIExtraction,
    BackgroundJob,
    FileAsset,
    HandoverItem,
    HandoverItemAcknowledgement,
    HandoverRecipient,
    HandoverVersion,
    Task,
    TaskTemplate,
    Transcript,
    User,
)
from .services.common import audit, enqueue, notify
from .security import policy_value

log = logging.getLogger("shiftproof.worker")


def claim():
    with SessionLocal.begin() as db:
        eligible = or_(
            (BackgroundJob.status == "queued") & (BackgroundJob.available_at <= now()),
            (BackgroundJob.status == "processing") & (BackgroundJob.leased_until <= now()),
        )
        item = db.scalar(
            select(BackgroundJob)
            .where(eligible, BackgroundJob.attempts < BackgroundJob.max_attempts)
            .order_by(BackgroundJob.available_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not item:
            # A crashed final attempt must not remain processing forever.
            db.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.status == "processing",
                    BackgroundJob.leased_until <= now(),
                    BackgroundJob.attempts >= BackgroundJob.max_attempts,
                )
                .values(status="failed", error="Processing stopped before confirmation. Please retry.")
            )
            return None
        lease = new_id()
        changed = db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == item.id, eligible)
            .values(
                status="processing",
                lease_token=lease,
                leased_until=now() + timedelta(minutes=3),
                attempts=BackgroundJob.attempts + 1,
            )
        )
        return (item.id, lease) if changed.rowcount == 1 else None


def email(job: BackgroundJob):
    settings = get_settings()
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = (
        settings.mail_from,
        job.payload["to"],
        job.payload["subject"],
    )
    message["Message-ID"] = f"<{job.id}@shiftproof.local>"
    message["Date"] = format_datetime(now())
    message.set_content(job.payload["text"])
    if settings.mail_mode == "file":
        if settings.app_env == "production":
            raise ValueError("Production email requires SMTP.")
        folder = Path("data/outbox")
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = folder / f"{job.id}.eml"
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as output:
            output.write(message.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    return {"delivery": "local_outbox" if settings.mail_mode == "file" else "smtp_accepted"}


def scheduled(db):
    from .services.alerts import escalate_due
    from .services.handovers import provisional_due
    from .services.tasks import create_task, recipients, template_values
    from .services.storage import delete_bytes

    escalate_due(db)
    provisional_due(db)
    for task in db.scalars(select(Task).where(Task.status != "closed", Task.deadline.is_not(None))):
        reminder = policy_value(db, task.organization_id, "operations").get("deadline_reminder_minutes", 30)
        if task.deadline <= now() + timedelta(minutes=reminder):
            overdue = task.deadline < now()
            from .services.reports import reviewers

            for recipient in set(
                recipients(db, task) + (reviewers(db, task.department_id) if overdue else [])
            ):
                notify(
                    db,
                    task.organization_id,
                    recipient,
                    f"task:{task.id}:{'overdue' if overdue else 'due'}:{task.deadline.isoformat()}",
                    "Task is overdue" if overdue else "Task deadline approaching",
                    task.title,
                    f"/workspace/tasks/{task.id}",
                )
    for template in db.scalars(
        select(TaskTemplate)
        .where(
            TaskTemplate.active.is_(True),
            TaskTemplate.recurrence_minutes.is_not(None),
            TaskTemplate.next_run <= now(),
        )
        .with_for_update(skip_locked=True)
    ):
        actor = db.get(User, template.created_by)
        try:
            scope = db.independent() if db.bind.dialect.name == "mongodb" else db.begin_nested()
            with scope:
                if not actor.active:
                    raise ValueError("Template owner is inactive")
                task = create_task(db, actor, template_values(db, actor, template))
                task.template_id = template.id
                template.next_run = now() + timedelta(minutes=template.recurrence_minutes)
        except (SQLAlchemyError, StaleDataError):
            raise
        except Exception:
            template.active = False
            notify(
                db,
                template.organization_id,
                actor.id,
                f"template:{template.id}:paused:{template.next_run.isoformat()}",
                "Recurring task needs review",
                "Assignment or permissions are no longer valid. Review and restart the template.",
                "/workspace/tasks",
                "administrative",
            )
            template.next_run = now() + timedelta(minutes=template.recurrence_minutes)
    for recipient in db.scalars(
        select(HandoverRecipient).join(HandoverVersion, HandoverVersion.id == HandoverRecipient.version_id)
    ):
        version = db.get(HandoverVersion, recipient.version_id)
        reminder = policy_value(db, recipient.organization_id, "operations").get(
            "handover_reminder_minutes", 15
        )
        if version.created_at > now() - timedelta(minutes=reminder):
            continue
        if not recipient.acknowledged_at:
            notify(
                db,
                recipient.organization_id,
                recipient.user_id,
                f"handover:{version.id}:pending",
                "Handover receipt is pending",
                f"Acknowledge version {version.number} after reading it. Critical items need separate acknowledgement.",
                f"/workspace/handovers/{version.handover_id}",
                "handover",
            )
        for item in db.scalars(
            select(HandoverItem).where(HandoverItem.version_id == version.id, HandoverItem.critical.is_(True))
        ):
            if not db.scalar(
                select(HandoverItemAcknowledgement.id).where(
                    HandoverItemAcknowledgement.item_id == item.id,
                    HandoverItemAcknowledgement.user_id == recipient.user_id,
                )
            ):
                notify(
                    db,
                    recipient.organization_id,
                    recipient.user_id,
                    f"handover:{version.id}:critical:{item.id}:pending",
                    "Critical item receipt is pending",
                    item.title,
                    f"/workspace/handovers/{version.handover_id}",
                    "critical",
                )
    for asset in db.scalars(
        select(FileAsset).where(FileAsset.deleted_at.is_(None), FileAsset.retention_until <= now())
    ):
        delete_bytes(asset)
        asset.deleted_at = now()
        audit(db, None, asset.organization_id, "evidence.retention.expired", "file_asset", asset.id)
    from .security import digest

    for transcript in db.scalars(select(Transcript)):
        days = policy_value(db, transcript.organization_id, "privacy").get("transcript_retention_days", 365)
        if transcript.created_at + timedelta(days=days) <= now() and not transcript.metadata_values.get(
            "retention_expired_at"
        ):
            transcript.metadata_values = {
                **transcript.metadata_values,
                "retention_expired_at": now().isoformat(),
                "original_sha256": digest(transcript.original),
            }
            transcript.original = "[Original transcript removed under retention policy]"
            for extraction in db.scalars(
                select(AIExtraction).where(AIExtraction.transcript_id == transcript.id)
            ):
                extraction.input_text = "[Original input removed under retention policy]"
            audit(
                db,
                None,
                transcript.organization_id,
                "transcript.retention.expired",
                "transcript",
                transcript.id,
            )
    from .services.retention import expired

    for extraction in db.scalars(select(AIExtraction)):
        if expired(db, extraction):
            extraction.input_text = "[Original input removed under retention policy]"
    for job in db.scalars(
        select(BackgroundJob).where(BackgroundJob.kind.in_(["transcribe", "extract", "speak"]))
    ):
        if expired(db, job):
            job.payload, job.result = {}, {"retention_expired": True}
            if job.status in {"queued", "processing"}:
                job.status, job.error = "failed", "The original processing source is no longer retained."
    return {"checked_at": now().isoformat()}


def execute(job_id: str, lease: str):
    try:
        with SessionLocal.begin() as db:
            job = db.scalar(
                select(BackgroundJob)
                .where(
                    BackgroundJob.id == job_id,
                    BackgroundJob.lease_token == lease,
                    BackgroundJob.status == "processing",
                )
                .with_for_update()
            )
            if not job:
                return
            user = db.get(User, job.actor_id) if job.actor_id else None
            if job.kind in {"extract", "transcribe", "speak"} and (not user or not user.active):
                raise ValueError("This account is no longer active. Processing stopped.")
            if job.kind in {"extract", "transcribe", "speak"}:
                from .services.retention import expired

                if expired(db, job):
                    raise ValueError("The original processing source is no longer retained.")
            if job.kind == "email":
                if db.bind.dialect.name == "mongodb":
                    db.commit()
                result = email(job)
            elif job.kind == "schedule":
                result = scheduled(db)
            elif job.kind == "transcribe":
                from .services.storage import read_bytes, wav_for_transcription
                from .integrations.gnani.client import transcribe

                asset = db.get(FileAsset, job.payload["asset_id"])
                if not asset or asset.deleted_at or asset.retention_until <= now():
                    raise ValueError("The recording is no longer retained.")
                if db.bind.dialect.name == "mongodb":
                    db.commit()
                data = transcribe(wav_for_transcription(read_bytes(asset)), job.payload["language"], job.id)
                transcript = Transcript(
                    organization_id=job.organization_id,
                    author_id=job.actor_id,
                    asset_id=asset.id,
                    original=data["text"],
                    language=data["language"],
                    provider="gnani",
                    model=data["model"],
                    metadata_values=data["metadata"],
                )
                db.add(transcript)
                db.flush()
                result = {
                    "transcript_id": transcript.id,
                    "text": transcript.original,
                    "provider": "gnani",
                    "model": transcript.model,
                }
            elif job.kind == "extract":
                from .integrations.gemini.client import extract

                if db.bind.dialect.name == "mongodb":
                    db.commit()
                output = extract(job.payload["text"])
                extraction = AIExtraction(
                    organization_id=job.organization_id,
                    author_id=job.actor_id,
                    transcript_id=job.payload["transcript_id"],
                    input_text=job.payload["text"],
                    output=output,
                    model=get_settings().gemini_model,
                )
                db.add(extraction)
                db.flush()
                result = {
                    "extraction_id": extraction.id,
                    "transcript_id": extraction.transcript_id,
                    "fields": output,
                    "requires_confirmation": True,
                }
            elif job.kind == "speak":
                from .integrations.gnani.client import speak
                from .services.storage import store_asset

                if db.bind.dialect.name == "mongodb":
                    db.commit()
                audio = speak(job.payload["text"])
                asset = store_asset(
                    db, user, audio, "handover.wav", "audio/wav", "audio", job.payload["department_id"], True
                )
                result = {"asset_id": asset.id}
            else:
                raise ValueError("Unsupported processing request.")
            job.status, job.result, job.completed_at, job.error = "succeeded", result, now(), ""
            job.leased_until = None
            # Do not retain raw delivery links after successful delivery.
            if job.kind == "email":
                job.payload = {"delivered": True}
        log.info("job_completed id=%s", job_id)
    except Exception as error:
        from .integrations.gnani.client import ProviderUnavailable

        safe = (
            str(error)
            if isinstance(error, (ProviderUnavailable, ValueError))
            else "Processing failed. Your source is saved; retry after the service recovers."
        )
        with SessionLocal.begin() as db:
            job = db.scalar(
                select(BackgroundJob)
                .where(BackgroundJob.id == job_id, BackgroundJob.lease_token == lease)
                .with_for_update()
            )
            if job:
                job.status = "failed" if job.attempts >= job.max_attempts else "queued"
                job.available_at = now() + timedelta(seconds=15 * 2**job.attempts)
                job.leased_until, job.error = None, safe[:1000]
        log.warning("job_failed id=%s error_type=%s", job_id, type(error).__name__)


def tick():
    try:
        with SessionLocal.begin() as db:
            enqueue(db, "schedule", f"schedule:{now().strftime('%Y-%m-%dT%H:%M')}", {})
    except IntegrityError:
        pass
    claimed = claim()
    if claimed:
        execute(*claimed)
    return bool(claimed)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            worked = tick()
            time.sleep(0.2 if worked else 2)
        except KeyboardInterrupt:
            break
        except Exception as error:
            log.error("worker_loop_failed error_type=%s", type(error).__name__)
            time.sleep(5)
