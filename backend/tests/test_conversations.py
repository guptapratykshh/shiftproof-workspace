from uuid import uuid4

import pytest
from conftest import expect, login
from sqlalchemy import select
from test_voice import execute, wav_bytes

from app.config import get_settings
from app.db import now
from app.models import BackgroundJob, Clarification, Conflict, DepartmentMembership, Notification, Report


def body(s, count=85, **fields):
    return {
        "client_request_id": str(uuid4()),
        "department_id": s.dept.id,
        "shift_id": s.shift.id,
        "occurred_at": now().isoformat(),
        "confirmed": True,
        "text": f"Batch B12: {count} pieces.",
        "fields": {"category": "progress", "batch": "B12", "quantity": count, "unit": "pieces", **fields},
    }


def create(s, draft):
    return expect(
        s.client.post(
            "/api/v1/report-conversations",
            json={"client_request_id": str(uuid4()), "draft": draft, "language": "en-IN"},
        ),
        201,
    )


def turn(s, c, text, kind="edit", draft=None):
    value = expect(
        s.client.post(
            f"/api/v1/report-conversations/{c['id']}/turns",
            json={
                "client_turn_id": str(uuid4()),
                "revision": c["revision"],
                "kind": kind,
                "text": text,
                "draft": draft,
            },
        ),
        202,
    )
    execute(s, value["state"]["job_id"])
    return expect(s.client.get(f"/api/v1/report-conversations/{c['id']}"))


def test_confirmed_gap_prompts_before_submission_and_notifies_once(setup):
    s = setup
    login(s.client, "worker")
    a = expect(s.client.post("/api/v1/reports", json=body(s, 100)), 201)["report"]
    login(s.client, "worker", employee="W-02")
    draft = body(s)
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert c["status"] == "awaiting_answer"
    assert "100" in c["state"]["question"] and "85" in c["state"]["question"]
    assert "Earlier you" not in c["state"]["question"]
    with s.db() as db:
        assert len(list(db.scalars(select(Report)))) == 1
        assert len(list(db.scalars(select(Conflict)))) == 0
    c = turn(s, c, "yes", "reply")
    assert c["status"] == "ready"
    submit = {**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]}
    result = expect(s.client.post("/api/v1/reports", json=submit), 201)
    assert (
        expect(s.client.post("/api/v1/reports", json=submit), 201)["report"]["id"] == result["report"]["id"]
    )
    with s.db() as db:
        assert len(list(db.scalars(select(Conflict)))) == 1
        questions = list(db.scalars(select(Clarification)))
        assert next(q for q in questions if q.report_id == a["id"]).responded_at is None
        assert next(q for q in questions if q.report_id == result["report"]["id"]).response == "yes"
        assert list(db.scalars(select(Notification).where(Notification.user_id == s.worker.id)))


def test_same_worker_correction_removes_gap_without_changing_original(setup, monkeypatch):
    from app.integrations.gemini import dialogue

    s = setup
    login(s.client, "worker")
    original = expect(s.client.post("/api/v1/reports", json=body(s, 100)), 201)["report"]
    draft = body(s)
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert "Earlier you reported 100" in c["state"]["question"]
    monkeypatch.setattr(
        dialogue, "interpret_reply", lambda *_: {"response_type": "correct", "fields": {"quantity": 100}}
    )
    c = turn(s, c, "Correction, I counted 100.", "reply")
    assert c["status"] == "ready" and not c["state"]["findings"]
    expect(
        s.client.post(
            "/api/v1/reports",
            json={**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]},
        ),
        201,
    )
    original_after = expect(s.client.get("/api/v1/reports/" + original["id"]))
    assert original_after["latest_version"] == 1
    with s.db() as db:
        assert not list(db.scalars(select(Conflict)))


def test_cross_department_transfer_is_scoped_and_receiving_supervisor_owns_it(setup):
    s = setup
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
    draft = {**body(s, quantity_stage="received", transfer_reference="MOVE-1"), "department_id": s.other.id}
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert c["state"]["findings"][0]["finding"]["category"] == "transfer_gap"
    assert "report_id" not in c["state"]["findings"][0]
    c = turn(s, c, "yes", "reply")
    expect(
        s.client.post(
            "/api/v1/reports",
            json={**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]},
        ),
        201,
    )
    with s.db() as db:
        assert db.scalar(select(Conflict)).department_id == s.other.id
    login(s.client, "supervisor", "supervisor@example.com")
    conflict = expect(s.client.get("/api/v1/conflicts"))[0]
    detail = expect(s.client.get("/api/v1/conflicts/" + conflict["id"]))
    assert detail["can_resolve"] is False
    assert len(detail["reports"]) == 1 and len(detail["shared_sources"]) == 1
    assert "text" not in detail["shared_sources"][0]


def test_stale_revision_changed_draft_and_new_source_are_rejected(setup):
    s = setup
    login(s.client, "worker")
    draft = body(s)
    c = create(s, draft)
    c = turn(s, c, draft["text"], draft=draft)
    assert c["status"] == "ready"
    assert (
        s.client.post(
            f"/api/v1/report-conversations/{c['id']}/turns",
            json={"client_turn_id": str(uuid4()), "revision": 0, "text": "Changed"},
        ).status_code
        == 409
    )
    submit = {**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]}
    assert (
        s.client.post("/api/v1/reports", json={**submit, "text": "Edited after checking"}).status_code == 409
    )
    login(s.client, "worker", employee="W-02")
    expect(s.client.post("/api/v1/reports", json=body(s, 100)), 201)
    assert s.client.get(f"/api/v1/report-conversations/{c['id']}").status_code == 403
    login(s.client, "worker")
    assert s.client.post("/api/v1/reports", json=submit).status_code == 409


def test_three_questions_or_uncertainty_never_traps_worker(setup):
    s = setup
    login(s.client, "worker")
    draft = body(s)
    draft["fields"].pop("batch")
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    for _ in range(3):
        c = turn(s, c, "yes", "reply")
    assert c["status"] == "ready" and c["state"]["unresolved"]
    draft2 = body(s)
    draft2["fields"].pop("batch")
    c = turn(s, create(s, draft2), draft2["text"], draft=draft2)
    c = turn(s, c, "I am not sure", "uncertain")
    assert c["status"] == "ready"


def test_failed_provider_is_visible_and_edit_can_continue(setup):
    s = setup
    login(s.client, "worker")
    draft = body(s)
    c = turn(s, create(s, draft), draft["text"], kind="update", draft=draft)
    assert c["status"] == "unavailable" and c["state"]["check_error"]
    c = turn(s, c, draft["text"], kind="edit", draft=draft)
    assert c["status"] == "ready"


@pytest.mark.parametrize("answer", ["Yes, confirmed.", "हाँ।", "yes!", "haan"])
def test_simple_spoken_confirmation_needs_no_language_model(answer):
    from app.integrations.gemini.dialogue import interpret_reply

    assert interpret_reply(answer, "Please confirm", {}) == {"response_type": "confirm", "fields": {}}


def test_recorded_update_chains_speech_extraction_comparison_and_question(setup, monkeypatch):
    from app.integrations.gemini import client as extraction
    from app.integrations.gnani import client as speech
    from app.schemas import ReportFields

    s = setup
    monkeypatch.setattr(get_settings(), "gnani_api_key", "test-only")
    monkeypatch.setattr(
        speech,
        "transcribe",
        lambda *_args, **_kw: {
            "text": "Received 85 pieces for B12.",
            "language": "en-IN",
            "model": "test",
            "metadata": {},
        },
    )
    monkeypatch.setattr(speech, "speak", lambda *_args: wav_bytes())
    monkeypatch.setattr(
        extraction,
        "extract",
        lambda _text: ReportFields(category="progress", batch="B12", quantity=85, unit="pieces").model_dump(),
    )
    login(s.client, "worker")
    expect(s.client.post("/api/v1/reports", json=body(s, 100)), 201)
    login(s.client, "worker", employee="W-02")
    draft = body(s)
    asset = expect(
        s.client.post(
            "/api/v1/files",
            data={"kind": "audio", "consent": "true", "department_id": s.dept.id},
            files={"file": ("update.wav", wav_bytes(), "audio/wav")},
        ),
        201,
    )
    c = create(s, draft)
    request = {
        "client_turn_id": str(uuid4()),
        "revision": c["revision"],
        "asset_id": asset["id"],
        "draft": draft,
    }
    c = expect(s.client.post(f"/api/v1/report-conversations/{c['id']}/turns", json=request), 202)
    assert (
        expect(s.client.post(f"/api/v1/report-conversations/{c['id']}/turns", json=request), 202)["revision"]
        == c["revision"]
    )
    assert execute(s, c["state"]["job_id"])["status"] == "succeeded"
    c = expect(s.client.get(f"/api/v1/report-conversations/{c['id']}"))
    execute(s, c["state"]["job_id"])
    c = expect(s.client.get(f"/api/v1/report-conversations/{c['id']}"))
    assert c["status"] == "awaiting_answer" and "15" in c["state"]["question"]
    job = execute(s, c["state"]["speech_job_id"])
    assert job["status"] == "succeeded"
    assert s.client.get("/api/v1/files/" + job["result"]["asset_id"]).content.startswith(b"RIFF")


def test_partial_delivery_preserves_received_count_and_history(setup, monkeypatch):
    from app.integrations.gemini import dialogue

    s = setup
    login(s.client, "worker")
    expect(s.client.post("/api/v1/reports", json=body(s, 100, quantity_stage="manufactured")), 201)
    login(s.client, "worker", employee="W-02")
    draft = body(s, quantity_stage="received")
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    monkeypatch.setattr(
        dialogue,
        "interpret_reply",
        lambda *_: {
            "response_type": "context",
            "fields": {"transfer_complete": False, "action_taken": "15 remain in manufacturing"},
        },
    )
    c = turn(s, c, "15 remain in manufacturing", "reply")
    assert c["status"] == "ready"
    assert c["state"]["draft"]["fields"]["quantity"] == 85
    assert c["state"]["draft"]["fields"]["transfer_complete"] is False
    assert c["state"]["findings"]
    assert any(t["text"] == "15 remain in manufacturing" for t in c["turns"])


def test_revoked_access_does_not_call_a_provider(setup, monkeypatch):
    from app.integrations.gemini import client
    from app.models import User

    s = setup
    login(s.client, "worker")
    draft = body(s)
    c = create(s, draft)
    c = expect(
        s.client.post(
            f"/api/v1/report-conversations/{c['id']}/turns",
            json={"client_turn_id": str(uuid4()), "revision": 0, "text": draft["text"]},
        ),
        202,
    )
    calls = []
    monkeypatch.setattr(client, "extract", lambda *_: calls.append(True))
    lease = str(uuid4())
    with s.db.begin() as db:
        db.get(User, s.worker.id).active = False
        job = db.get(BackgroundJob, c["state"]["job_id"])
        job.status, job.lease_token, job.attempts = "processing", lease, job.max_attempts
    s.jobs.execute(c["state"]["job_id"], lease)
    assert not calls
    with s.db() as db:
        assert db.get(BackgroundJob, c["state"]["job_id"]).status == "failed"


def test_question_keeps_each_sources_actual_unit(setup):
    s = setup
    login(s.client, "worker")
    expect(s.client.post("/api/v1/reports", json=body(s, 100, unit="kg")), 201)
    draft = body(s, 85000, unit="g")
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert "100 kg" in c["state"]["question"] and "85000 g" in c["state"]["question"]


def test_uncertain_context_requires_supervisor_attention(setup):
    s = setup
    login(s.client, "worker")
    draft = body(s)
    draft["fields"].pop("batch")
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    c = turn(s, c, "I am not sure", "uncertain")
    submitted = expect(
        s.client.post(
            "/api/v1/reports",
            json={**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]},
        ),
        201,
    )
    assert submitted["report"]["needs_attention"]


def test_superseded_job_does_not_overwrite_newer_turn(setup, monkeypatch):
    s = setup
    login(s.client, "worker")
    draft = body(s)
    c = create(s, draft)

    def enqueue_turn(revision, text):
        return expect(
            s.client.post(
                f"/api/v1/report-conversations/{c['id']}/turns",
                json={
                    "client_turn_id": str(uuid4()),
                    "revision": revision,
                    "kind": "edit",
                    "text": text,
                    "draft": draft,
                },
            ),
            202,
        )

    first = enqueue_turn(0, "Earlier words")
    latest = enqueue_turn(1, "New corrected words")
    assert execute(s, first["state"]["job_id"])["result"] == {"superseded": True}
    execute(s, latest["state"]["job_id"])
    result = expect(s.client.get(f"/api/v1/report-conversations/{c['id']}"))
    assert result["state"]["draft"]["text"] == "New corrected words"
    assert not any(t["text"] == "Earlier words" for t in result["turns"])


def test_cross_department_locations_do_not_hide_matching_transfers():
    from types import SimpleNamespace

    from app.services.contradictions import compare

    a = {
        "category": "progress",
        "batch": "B12",
        "quantity": 100,
        "unit": "pieces",
        "quantity_stage": "manufactured",
        "machine": "CNC-1",
        "work_area": "Manufacturing",
    }
    b = {**a, "quantity": 85, "quantity_stage": "received", "machine": "Sorter-2", "work_area": "Receiving"}
    report = SimpleNamespace(occurred_at=now(), shift_id="same-shift")
    assert not compare(a, b, report, report)
    assert compare(a, b, report, report, cross_department=True)[0]["category"] == "transfer_gap"


def test_inactive_links_and_unrelated_departments_cannot_compare(setup):
    s = setup
    login(s.client, "worker")
    expect(s.client.post("/api/v1/reports", json=body(s, 100, quantity_stage="manufactured")), 201)
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
    draft = {**body(s, quantity_stage="received"), "department_id": s.other.id}
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert c["status"] == "ready" and not c["state"]["findings"]
    assert (
        s.client.post(
            "/api/v1/department-links",
            json={"source_department_id": s.dept.id, "receiving_department_id": s.other.id},
        ).status_code
        == 403
    )
    login(s.client, "organization", "admin@example.com")
    expect(
        s.client.post(
            "/api/v1/department-links",
            json={"source_department_id": s.dept.id, "receiving_department_id": s.other.id},
        ),
        201,
    )
    login(s.client, "worker", employee="W-02")
    c = turn(s, c, draft["text"], draft=draft)
    assert c["state"]["findings"]
    c = turn(s, c, "yes", "reply")
    login(s.client, "organization", "admin@example.com")
    expect(
        s.client.post(
            "/api/v1/department-links",
            json={"source_department_id": s.dept.id, "receiving_department_id": s.other.id, "active": False},
        ),
        201,
    )
    login(s.client, "worker", employee="W-02")
    assert (
        s.client.post(
            "/api/v1/reports",
            json={**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]},
        ).status_code
        == 409
    )


def test_spoken_transfer_prefix_and_number_match_the_same_reference():
    from types import SimpleNamespace

    from app.services.contradictions import compare

    report = SimpleNamespace(occurred_at=now(), shift_id="one")
    source = {
        "category": "progress",
        "batch": "B12",
        "quantity": 100,
        "unit": "pieces",
        "quantity_stage": "manufactured",
        "transfer_reference": "MOVE-1",
    }
    received = {
        "category": "materials",
        "batch": "B twelve",
        "quantity": 85,
        "unit": "pieces",
        "quantity_stage": "received",
        "transfer_reference": "transfer move one",
    }
    assert compare(received, source, report, report, cross_department=True)[0]["difference"] == 15
