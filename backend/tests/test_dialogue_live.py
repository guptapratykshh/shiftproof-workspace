"""Opt-in synthetic provider check; never runs in the ordinary offline test suite."""

import os
from uuid import uuid4

import pytest
from conftest import expect, login
from test_conversations import body, create, turn
from test_voice import execute

from app.config import Settings, get_settings
from app.models import DepartmentMembership


@pytest.mark.skipif(
    os.environ.get("SHIFTPROOF_LIVE_DIALOGUE") != "1", reason="Requires explicit live-provider opt-in"
)
def test_synthetic_gnani_conversation_with_real_answer_interpretation(setup, monkeypatch):
    from app.integrations.gnani.client import speak

    s = setup
    private = Settings()
    assert private.gnani_api_key and private.gemini_api_key
    monkeypatch.setattr(get_settings(), "gnani_api_key", private.gnani_api_key)
    monkeypatch.setattr(get_settings(), "gemini_api_key", private.gemini_api_key)
    login(s.client, "organization", "admin@example.com")
    expect(
        s.client.post(
            "/api/v1/department-links",
            json={"source_department_id": s.dept.id, "receiving_department_id": s.other.id},
        ),
        201,
    )
    login(s.client, "worker")
    expect(
        s.client.post(
            "/api/v1/reports", json=body(s, 100, quantity_stage="manufactured", transfer_reference="MOVE-1")
        ),
        201,
    )
    with s.db.begin() as db:
        db.add(
            DepartmentMembership(
                organization_id=s.org.id,
                user_id=s.worker2.id,
                department_id=s.other.id,
                primary=True,
                active=True,
                permissions=[],
            )
        )
    login(s.client, "worker", employee="W-02")
    draft = {**body(s), "department_id": s.other.id, "text": "", "fields": {"category": "general"}}
    c = create(s, draft)

    def complete(identity):
        result = execute(s, identity)
        if result["status"] == "failed":
            # Exercise the same explicit retry a worker can use for a transient provider error.
            expect(s.client.post(f"/api/v1/jobs/{identity}/retry"))
            result = execute(s, identity)
        assert result["status"] == "succeeded", result.get("error")
        return result

    audio = speak(
        "I received eighty five pieces for batch B twelve, transfer MOVE one. This is the total received count.",
        "en-IN",
    )
    asset = expect(
        s.client.post(
            "/api/v1/files",
            data={"kind": "audio", "consent": "true", "department_id": s.other.id},
            files={"file": ("synthetic-update.wav", audio, "audio/wav")},
        ),
        201,
    )
    c = expect(
        s.client.post(
            f"/api/v1/report-conversations/{c['id']}/turns",
            json={"client_turn_id": str(uuid4()), "revision": 0, "asset_id": asset["id"], "draft": draft},
        ),
        202,
    )
    complete(c["state"]["job_id"])
    c = expect(s.client.get(f"/api/v1/report-conversations/{c['id']}"))
    complete(c["state"]["job_id"])
    c = expect(s.client.get(f"/api/v1/report-conversations/{c['id']}"))
    assert c["state"]["draft"]["fields"]["quantity"] == 85
    # ASR may space identifiers; comparison normalizes batch and transfer IDs.
    assert c["status"] == "awaiting_answer", c["state"]["draft"]["fields"]
    assert "100" in c["state"]["question"] and "85" in c["state"]["question"]
    speech = complete(c["state"]["speech_job_id"])
    assert speech["status"] == "succeeded"
    assert s.client.get("/api/v1/files/" + speech["result"]["asset_id"]).content.startswith(b"RIFF")
    c = turn(
        s, c, "I received 85 pieces. This is a partial delivery; 15 pieces remain in manufacturing.", "reply"
    )
    assert c["status"] == "ready"
    assert c["state"]["draft"]["fields"]["quantity"] == 85
    assert c["state"]["draft"]["fields"]["transfer_complete"] is False
    assert c["state"]["findings"]
    result = expect(
        s.client.post(
            "/api/v1/reports",
            json={**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]},
        ),
        201,
    )
    assert result["report"]["needs_attention"]
