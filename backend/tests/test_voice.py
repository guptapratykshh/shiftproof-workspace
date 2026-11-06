import io
import wave
from uuid import uuid4

import httpx
import pytest
from conftest import expect
from sqlalchemy import func, select
from test_workflows import as_super, as_worker, task_payload

from app.config import get_settings
from app.models import BackgroundJob, DepartmentMembership, Report
from app.schemas import ReportFields
from app.services.voice import report_script, transcription_context


def wav_bytes(frames=b"\0\0" * 1600, sample_rate=16000):
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    return out.getvalue()


def execute(s, job_id):
    token = str(uuid4())
    with s.db.begin() as db:
        job = db.get(BackgroundJob, job_id)
        job.status, job.lease_token = "processing", token
        job.attempts = job.max_attempts
    s.jobs.execute(job_id, token)
    return expect(s.client.get(f"/api/v1/jobs/{job_id}"))


def test_gnani_request_contract_and_silence(monkeypatch):
    from app.integrations.gnani import client

    monkeypatch.setattr(get_settings(), "gnani_api_key", "private-test-key")
    calls = []

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if "/tts/" in url:
                return httpx.Response(200, request=httpx.Request("POST", url), content=wav_bytes())
            return httpx.Response(
                200, request=httpx.Request("POST", url), json={"success": True, "transcript": ""}
            )

    monkeypatch.setattr(client.httpx, "Client", FakeClient)
    assert (
        client.transcribe(b"audio", "hi-IN,en-IN", "request", keyterms=["मिक्सर"], topic="Packing")["text"]
        == ""
    )
    assert client.speak("Inspection is not complete.", "en-IN").startswith(b"RIFF")
    assert calls[0][1]["headers"]["X-API-Key-ID"] == calls[1][1]["headers"]["X-API-Key-ID"]
    assert calls[0][1]["data"]["format"] == "codemix"
    assert "मिक्सर" in calls[0][1]["data"]["keyterms"]
    assert calls[1][1]["json"]["voice"] == "Shivani"
    assert calls[1][1]["json"]["language"] == "en-IN"
    with pytest.raises(client.ProviderUnavailable):
        client.speak("x" * 5001)
    assert len(calls) == 2  # Never pay to synthesize a silently shortened report.


@pytest.mark.parametrize("failure", [None, "streaming", "http", "format", "truncated"])
def test_long_readback_joins_complete_audio_or_fails(monkeypatch, failure):
    from app.integrations.gnani import client

    monkeypatch.setattr(get_settings(), "gnani_api_key", "private-test-key")
    script = "Inspection is NOT complete. Batch B-012 has 120 boxes. जाँच अभी बाकी है।\n" * 35
    chunks = client.speech_chunks(script)
    assert "".join(chunks) == script
    assert all(len(chunk) <= 650 for chunk in chunks)
    calls, frames = [], []

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, **kwargs):
            calls.append(kwargs["json"]["text"])
            frame = len(calls).to_bytes(2, "little") * 160
            frames.append(frame)
            content = wav_bytes(frame)
            if failure == "streaming":
                content = bytearray(content)
                content[4:8] = (0xFFFFFFFF).to_bytes(4, "little")
                content[40:44] = (0xFFFFFFFE).to_bytes(4, "little")
                content = bytes(content)
            if len(calls) == 2:
                if failure == "http":
                    return httpx.Response(500, request=httpx.Request("POST", url))
                if failure == "format":
                    content = wav_bytes(frame, 24000)
                if failure == "truncated":
                    content = content[:-2]
            return httpx.Response(200, request=httpx.Request("POST", url), content=content)

    monkeypatch.setattr(client.httpx, "Client", FakeClient)
    if failure not in {None, "streaming"}:
        with pytest.raises(client.ProviderUnavailable, match="temporarily unavailable"):
            client.speak(script, "auto")
        assert len(calls) == 2  # No partial success or further paid calls after failure.
    else:
        result = client.speak(script, "auto")
        assert "".join(calls) == script
        with wave.open(io.BytesIO(result), "rb") as audio:
            assert audio.getframerate() == 16000
            assert audio.readframes(audio.getnframes()) == b"".join(frames)


def test_readback_preserves_negative_conditions_and_zero():
    script = report_script(
        "Inspection is NOT complete. <whispers>",
        ReportFields(
            quantity=0,
            batch="B-012",
            operational_status="blocked",
            quality_implication="Do not release",
            uncertainty=["Confirm whether the seal is intact."],
        ),
        "en-IN",
    )
    for value in ["NOT complete", "Quantity: 0", "B-012", "blocked", "Do not release", "Confirm whether"]:
        assert value in script
    assert "<whispers>" not in script


def test_handover_audio_keeps_version_and_unresolved_conditions():
    from types import SimpleNamespace

    from app.services.voice import handover_script

    version = SimpleNamespace(
        number=2,
        provisional=True,
        snapshot={
            "notes": "Do not release batch B-12.",
            "items": [
                {
                    "title": "Packing inspection",
                    "critical": True,
                    "detail": {"status": "reviewed", "unresolved": True, "needs_attention": True},
                },
                {
                    "title": "Repair M-12",
                    "detail": {
                        "status": "blocked",
                        "blocked_reason": "Seal missing",
                        "transfer_pending": True,
                    },
                },
            ],
        },
    )
    script = handover_script(version, "en-IN")
    for text in [
        "Version 2",
        "Pending supervisor review",
        "Do not release",
        "Critical",
        "still unresolved",
        "Seal missing",
        "incoming shift",
    ]:
        assert text in script


def test_readback_is_private_idempotent_and_never_submits(setup, monkeypatch):
    from app.integrations.gnani import client

    s = setup
    monkeypatch.setattr(get_settings(), "gnani_api_key", "test")
    monkeypatch.setattr(client, "speak", lambda text, language: wav_bytes())
    as_worker(s)
    payload = {
        "department_id": s.dept.id,
        "text": "Inspection is still pending.",
        "language": "en-IN",
        "fields": {"quantity": 120},
    }
    first = expect(s.client.post("/api/v1/report-readback", json=payload), 202)
    assert expect(s.client.post("/api/v1/report-readback", json=payload), 202)["id"] == first["id"]
    assert (
        s.client.post("/api/v1/report-readback", json={**payload, "department_id": s.other.id}).status_code
        == 403
    )
    result = execute(s, first["id"])
    assert result["status"] == "succeeded"
    assert "120" in result["result"]["script"]
    asset = result["result"]["asset_id"]
    assert s.client.get(f"/api/v1/files/{asset}").status_code == 200
    with s.db() as db:
        assert db.scalar(select(func.count()).select_from(Report)) == 0
    changed = expect(
        s.client.post("/api/v1/report-readback", json={**payload, "text": "Inspection is complete."}), 202
    )
    assert changed["id"] != first["id"]
    as_worker(s, "W-02")
    assert s.client.get(f"/api/v1/jobs/{first['id']}").status_code == 403
    assert s.client.get(f"/api/v1/files/{asset}").status_code == 403


def test_revoked_department_blocks_queued_readback(setup, monkeypatch):
    from app.integrations.gnani import client

    s = setup
    monkeypatch.setattr(get_settings(), "gnani_api_key", "test")

    def forbidden(*_):
        pytest.fail("Revoked users must never invoke the speech provider")

    monkeypatch.setattr(client, "speak", forbidden)
    as_worker(s)
    job = expect(
        s.client.post("/api/v1/report-readback", json={"department_id": s.dept.id, "text": "Pending."}), 202
    )
    with s.db.begin() as db:
        member = db.scalar(select(DepartmentMembership).where(DepartmentMembership.user_id == s.worker.id))
        member.active = False
    result = execute(s, job["id"])
    assert result["status"] == "failed"
    assert not result["result"].get("asset_id")


def test_transcription_vocabulary_respects_assignment(setup):
    s = setup
    as_super(s)
    own = expect(s.client.post("/api/v1/tasks", json=task_payload(s, title="Check mixer MX-12")), 201)
    private = expect(
        s.client.post("/api/v1/tasks", json=task_payload(s, title="Private machine", worker_id=s.worker2.id)),
        201,
    )
    with s.db() as db:
        assert "Check mixer MX-12" in transcription_context(db, s.worker, s.dept.id, own["id"])["keyterms"]
        with pytest.raises(Exception) as error:
            transcription_context(db, s.worker, s.dept.id, private["id"])
        assert error.value.status_code in {403, 404}


def test_readback_validates_length_and_provider_availability(setup, monkeypatch):
    s = setup
    as_worker(s)
    payload = {"department_id": s.dept.id, "text": "Inspection pending."}
    assert expect(s.client.get("/api/v1/voice/capabilities"))["playback"] is False
    assert s.client.post("/api/v1/report-readback", json=payload).status_code == 503
    monkeypatch.setattr(get_settings(), "gnani_api_key", "test")
    assert s.client.post("/api/v1/report-readback", json={**payload, "text": " "}).status_code == 422
    assert s.client.post("/api/v1/report-readback", json={**payload, "text": "x" * 6000}).status_code == 422
    assert (
        s.client.post("/api/v1/report-readback", json={**payload, "language": "unsupported"}).status_code
        == 422
    )
