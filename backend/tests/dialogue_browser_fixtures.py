"""Deterministic providers, only inside the isolated browser-test server."""

import io
import os
import re
import threading
import time
import wave
from datetime import timedelta
from uuid import uuid4


def install():
    if os.environ.get("SHIFTPROOF_BROWSER_TEST") != "1":
        raise RuntimeError("Browser fixtures are test-only")
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import SessionLocal, now
    from app.integrations.gemini import client as gemini
    from app.integrations.gemini import dialogue
    from app.integrations.gnani import client as gnani
    from app.models import BackgroundJob
    from app.schemas import ReportFields
    from app.worker import execute

    get_settings().gnani_api_key = "isolated-test-only"
    get_settings().gemini_api_key = "isolated-test-only"

    def transcribe(_audio, language, request_id, **_):
        with SessionLocal() as db:
            job = db.get(BackgroundJob, request_id)
            reply = job.payload.get("kind") == "reply"
        return {
            "text": "Yes, confirmed" if reply else "I received 85 pieces for Batch B12, transfer MOVE-1.",
            "language": language,
            "model": "test-fixture",
            "metadata": {},
        }

    def speak(*_):
        output = io.BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 1600)
        return output.getvalue()

    def extract(text):
        if "kitchen products" in text:
            match = re.search(r"(\d+) kitchen products", text)
            return ReportFields(category="progress", description=text, product="kitchen products",
                                quantity=int(match[1]), unit="items", quantity_stage="packed",
                                quantity_basis="total", dispatch_status="pending").model_dump()
        match = re.search(r"(\d+) pieces", text)
        return ReportFields(
            category="progress",
            description=text,
            batch="B12",
            quantity=int(match[1]) if match else 85,
            unit="pieces",
            quantity_stage="received",
            transfer_reference="MOVE-1",
        ).model_dump()

    original_reply = dialogue.interpret_reply

    def reply(text, question, fields):
        if "100" in text:
            return {"response_type": "correct", "fields": {"quantity": 100}}
        return original_reply(text, question, fields)

    gnani.transcribe, gnani.speak, gemini.extract, dialogue.interpret_reply = (
        transcribe,
        speak,
        extract,
        reply,
    )

    def work():
        while True:
            try:
                identity = lease = None
                with SessionLocal.begin() as db:
                    job = db.scalar(
                        select(BackgroundJob)
                        .where(
                            BackgroundJob.status == "queued",
                            BackgroundJob.kind.in_(
                                ["conversation_transcribe", "conversation_analyze", "speak"]
                            ),
                        )
                        .order_by(BackgroundJob.created_at)
                    )
                    if job:
                        identity, lease = job.id, str(uuid4())
                        job.status, job.lease_token, job.attempts, job.max_attempts = (
                            "processing",
                            lease,
                            1,
                            1,
                        )
                        job.leased_until = now() + timedelta(minutes=3)
                if identity:
                    execute(identity, lease)
            except Exception:
                pass  # Startup races are retried; assertions inspect API job results.
            time.sleep(0.1)

    threading.Thread(target=work, daemon=True).start()
