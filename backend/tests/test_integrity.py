import io
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from PIL import Image
from sqlalchemy import func, select

from app.db import now
from app.models import (
    AIExtraction,
    Alert,
    BackgroundJob,
    DepartmentMembership,
    DeviceSession,
    Report,
    Shift,
    Transcript,
)
from app.services.handovers import next_shift, shift_window
from conftest import expect, login
from test_workflows import as_super, as_worker, perform, report_payload, task_payload


def test_immediate_alert_retries_link_one_owned_report(setup):
    s = setup
    as_worker(s)
    payload = {
        "department_id": s.dept.id,
        "title": "Stop the packing line safely",
        "client_request_id": str(uuid4()),
    }
    first = expect(s.client.post("/api/v1/alerts/immediate", json=payload), 201)
    assert expect(s.client.post("/api/v1/alerts/immediate", json=payload), 201)["id"] == first["id"]
    assert expect(s.client.get(f"/api/v1/alerts/{first['id']}"))["id"] == first["id"]
    report = report_payload(s, immediate_safety=True, immediate_alert_id=first["id"])
    as_worker(s, "W-02")
    assert s.client.post("/api/v1/reports", json=report).status_code == 422
    as_worker(s)
    created = expect(s.client.post("/api/v1/reports", json=report), 201)["report"]
    assert expect(s.client.post("/api/v1/reports", json=report), 201)["report"]["id"] == created["id"]
    with s.db() as db:
        assert db.scalar(select(func.count()).select_from(Alert)) == 1
        assert db.get(Alert, first["id"]).report_id == created["id"]
    as_super(s)
    metrics = expect(s.client.get("/api/v1/analytics"))["metrics"]
    assert metrics["safety_incidents"] == metrics["critical_incidents"] == 1


def test_expected_account_header_rejects_old_shared_device_queue(setup):
    s = setup
    as_worker(s, "W-02")
    s.client.headers["X-Account-ID"] = s.worker.id
    assert s.client.post("/api/v1/reports", json=report_payload(s)).status_code == 401
    s.client.headers.pop("X-Account-ID")
    with s.db() as db:
        assert db.scalar(select(func.count()).select_from(Report)) == 0


def test_simultaneous_report_retries_create_one_record(setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    s = setup
    as_worker(s)
    payload = report_payload(s)
    barrier = Barrier(2)

    def submit():
        barrier.wait()
        return expect(s.client.post("/api/v1/reports", json=payload), 201)["report"]["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _: submit(), range(2)))
    assert len(set(result)) == 1
    with s.db() as db:
        assert db.scalar(select(func.count()).select_from(Report)) == 1


def test_task_association_never_suggests_another_workers_private_task(setup):
    s = setup
    as_super(s)
    first = expect(s.client.post("/api/v1/tasks", json=task_payload(s, title="Inspect packing motor")), 201)
    expect(
        s.client.post(
            "/api/v1/tasks",
            json=task_payload(s, title="Inspect packing motor privately", worker_id=s.worker2.id),
        ),
        201,
    )
    as_worker(s)
    suggestions = expect(
        s.client.post(
            "/api/v1/task-associations",
            json={"department_id": s.dept.id, "text": "Inspect packing motor: inspection remains pending."},
        )
    )
    assert [item["id"] for item in suggestions["items"]] == [first["id"]]
    assert suggestions["confirmation_required"]


def test_cross_department_followup_preserves_origin_and_limits_source_access(setup):
    s = setup
    as_worker(s)
    report = expect(s.client.post("/api/v1/reports", json=report_payload(s)), 201)["report"]
    as_super(s)
    referral = expect(
        s.client.post(
            "/api/v1/follow-ups",
            json={
                "report_id": report["id"],
                "receiving_department_id": s.other.id,
                "note": "Inspect the equipment serving the packing line.",
            },
        ),
        201,
    )
    with s.db.begin() as db:
        source_membership = db.scalar(
            select(DepartmentMembership).where(DepartmentMembership.user_id == s.supervisor.id)
        )
        source_membership.active = False
        db.add(
            DepartmentMembership(
                organization_id=s.org.id,
                user_id=s.supervisor.id,
                department_id=s.other.id,
                permissions=["view", "manage", "review", "workforce"],
            )
        )
        db.add(
            DepartmentMembership(
                organization_id=s.org.id, user_id=s.worker2.id, department_id=s.other.id, permissions=["view"]
            )
        )
    as_super(s)
    assert s.client.get(f"/api/v1/reports/{report['id']}").status_code == 404
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    def assign_once():
        barrier.wait()
        return s.client.post(
            f"/api/v1/follow-ups/{referral['id']}/assign",
            json=task_payload(s, department_id=s.other.id, worker_id=s.worker2.id),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: assign_once(), range(2)))
    assert sorted(response.status_code for response in responses) == [201, 409]
    task = next(response.json() for response in responses if response.status_code == 201)
    assert task["source_report_id"] == report["id"]
    with s.db() as db:
        assert db.get(Report, report["id"]).department_id == s.dept.id


def test_qualification_expiry_and_removal_restrict_assignment(setup):
    s = setup
    as_super(s)
    payload = {
        "name": s.worker.name,
        "department_ids": [s.dept.id],
        "primary_department_id": s.dept.id,
        "team_ids": [s.team.id],
        "skills": ["packing"],
    }
    person = expect(s.client.put(f"/api/v1/workers/{s.worker.id}", json=payload))
    skill_id = person["skills"][0]["id"]
    expect(
        s.client.put(
            f"/api/v1/workers/{s.worker.id}/qualifications/{skill_id}",
            json={"qualification": "PACK-2026", "expires_on": (now().date() - timedelta(days=1)).isoformat()},
        )
    )
    assert (
        s.client.post("/api/v1/tasks", json=task_payload(s, required_skills=["packing"])).status_code == 422
    )
    expect(
        s.client.put(
            f"/api/v1/workers/{s.worker.id}/qualifications/{skill_id}",
            json={
                "qualification": "PACK-2027",
                "expires_on": (now().date() + timedelta(days=365)).isoformat(),
            },
        )
    )
    expect(s.client.post("/api/v1/tasks", json=task_payload(s, required_skills=["packing"])), 201)
    person = expect(s.client.put(f"/api/v1/workers/{s.worker.id}", json={**payload, "skills": []}))
    assert person["skills"] == []
    assert (
        s.client.post("/api/v1/tasks", json=task_payload(s, required_skills=["packing"])).status_code == 422
    )


def test_dependencies_and_reassignment_optimistic_version(setup):
    s = setup
    as_super(s)
    predecessor = expect(s.client.post("/api/v1/tasks", json=task_payload(s)), 201)
    dependent = expect(
        s.client.post("/api/v1/tasks", json=task_payload(s, depends_on=[predecessor["id"]])), 201
    )
    as_worker(s)
    dependent = perform(s, dependent, "accept")
    assert (
        s.client.post(
            f"/api/v1/tasks/{dependent['id']}/actions",
            json={"action": "start", "version": dependent["version"]},
        ).status_code
        == 409
    )
    predecessor = perform(s, predecessor, "accept")
    predecessor = perform(s, predecessor, "start")
    predecessor = perform(s, predecessor, "complete")
    assert predecessor["status"] == "closed"
    perform(s, dependent, "start")
    as_super(s)
    task = expect(s.client.post("/api/v1/tasks", json=task_payload(s)), 201)
    updated = expect(
        s.client.post(
            f"/api/v1/tasks/{task['id']}/reassign",
            json={
                "worker_id": s.worker2.id,
                "reason": "Balance the incoming shift",
                "version": task["version"],
            },
        )
    )
    assert updated["version"] > task["version"]
    assert (
        s.client.post(
            f"/api/v1/tasks/{task['id']}/reassign",
            json={"worker_id": s.worker.id, "reason": "Stale supervisor form", "version": task["version"]},
        ).status_code
        == 409
    )


def test_approved_routine_allocation_respects_workload_and_critical_boundary(setup):
    s = setup
    as_super(s)
    expect(s.client.post("/api/v1/tasks", json=task_payload(s)), 201)
    template = expect(
        s.client.post("/api/v1/task-templates", json={"task": task_payload(s), "auto_allocate": True}), 201
    )
    created = expect(s.client.post(f"/api/v1/task-templates/{template['id']}/apply"), 201)
    detail = expect(s.client.get(f"/api/v1/tasks/{created['id']}"))
    assert detail["assignments"][0]["user_id"] == s.worker2.id
    assert (
        s.client.post(
            "/api/v1/task-templates", json={"task": task_payload(s, critical=True), "auto_allocate": True}
        ).status_code
        == 422
    )


def test_task_evidence_shared_only_with_current_assignee(setup):
    s = setup
    as_super(s)
    task = expect(s.client.post("/api/v1/tasks", json=task_payload(s)), 201)
    image = io.BytesIO()
    Image.new("RGB", (12, 12), "purple").save(image, format="PNG")
    asset = expect(
        s.client.post(
            "/api/v1/files",
            data={"kind": "photo", "department_id": s.dept.id},
            files={"file": ("instructions.png", image.getvalue(), "image/png")},
        ),
        201,
    )
    expect(s.client.post(f"/api/v1/tasks/{task['id']}/evidence", json={"asset_id": asset["id"]}), 201)
    as_worker(s)
    assert s.client.get(f"/api/v1/files/{asset['id']}").status_code == 200
    as_worker(s, "W-02")
    assert s.client.get(f"/api/v1/files/{asset['id']}").status_code in {403, 404}


def test_transcript_retention_applies_before_scheduled_cleanup(setup):
    s = setup
    as_worker(s)
    with s.db.begin() as db:
        transcript = Transcript(
            organization_id=s.org.id,
            author_id=s.worker.id,
            original="PRIVATE OLD RECORDING",
            language="en-IN",
            created_at=now() - timedelta(days=400),
        )
        db.add(transcript)
        db.flush()
        extraction = AIExtraction(
            organization_id=s.org.id,
            author_id=s.worker.id,
            transcript_id=transcript.id,
            input_text=transcript.original,
            output={"category": "general", "description": "Old update"},
            model="test",
            created_at=transcript.created_at,
        )
        db.add(extraction)
        db.flush()
        job = BackgroundJob(
            organization_id=s.org.id,
            actor_id=s.worker.id,
            kind="transcribe",
            dedupe_key=str(uuid4()),
            status="succeeded",
            payload={"text": transcript.original},
            result={"text": transcript.original},
            created_at=transcript.created_at,
        )
        db.add(job)
        db.flush()
        transcript_id, extraction_id, job_id = transcript.id, extraction.id, job.id
    report = expect(
        s.client.post(
            "/api/v1/reports",
            json=report_payload(s, transcript_id=transcript_id, extraction_id=extraction_id),
        ),
        201,
    )["report"]
    response = s.client.get(f"/api/v1/reports/{report['id']}")
    assert response.status_code == 200 and "PRIVATE OLD RECORDING" not in response.text
    assert "PRIVATE OLD RECORDING" not in s.client.get(f"/api/v1/jobs/{job_id}").text
    with s.db.begin() as db:
        s.jobs.scheduled(db)
    with s.db() as db:
        assert "PRIVATE OLD RECORDING" not in db.get(Transcript, transcript_id).original
        assert db.get(BackgroundJob, job_id).payload == {}


def test_overnight_incoming_shift_uses_next_calendar_day(setup):
    s = setup
    with s.db.begin() as db:
        night = Shift(
            organization_id=s.org.id, name="Night", starts_at="22:00", ends_at="06:00", days=list(range(7))
        )
        db.add(night)
        db.flush()
        start, end = shift_window(s.org, night, "2026-11-01")
        assert start.date().isoformat() == "2026-11-01"
        assert end.date().isoformat() == "2026-11-02"
        incoming = next_shift(db, s.org, end)
        assert incoming[1] == s.shift.id and incoming[2] == "2026-11-02"


def test_workspace_context_orientation_and_scope(setup):
    s = setup
    as_super(s)
    expect(s.client.put("/api/v1/orientation", json={"step": 3}))
    assert expect(s.client.get("/api/v1/auth/me"))["user"]["profile"]["orientation_step"] == "3"
    assert s.client.get(f"/api/v1/workspace/context?department_id={s.other.id}").status_code == 403
    expect(s.client.get("/api/v1/workspace/context"))
    expect(s.client.get(f"/api/v1/departments/{s.dept.id}/overview"))
    login(s.client, "organization", "admin@example.com")
    expect(s.client.get("/api/v1/workspace/context"))
    as_worker(s)
    assert s.client.put("/api/v1/orientation", json={"step": 3}).status_code == 403


@pytest.mark.parametrize("mode", ["timeout", "rate_limit", "malformed", "wrong_shape"])
def test_speech_provider_failure_returns_safe_error(monkeypatch, mode):
    from app.config import get_settings
    from app.integrations.gnani import client

    monkeypatch.setattr(get_settings(), "gnani_api_key", "test-secret-never-returned")

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, **_):
            if mode == "timeout":
                raise httpx.ReadTimeout("test-secret-never-returned")
            return httpx.Response(
                429 if mode == "rate_limit" else 200,
                request=httpx.Request("POST", url),
                content=b"not JSON" if mode == "malformed" else b"[]" if mode == "wrong_shape" else b"{}",
            )

    monkeypatch.setattr(client.httpx, "Client", FakeClient)
    with pytest.raises(client.ProviderUnavailable) as error:
        client.transcribe(b"audio", "hi-IN,en-IN", str(uuid4()))
    assert "test-secret" not in str(error.value)


def test_gemini_grounding_rejects_invented_identifiers(monkeypatch):
    from app.config import get_settings
    from app.integrations.gemini import client

    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")

    class FakeClient:
        def __init__(self, **_):
            self.models = self

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def generate_content(self, **kwargs):
            # Keep JSON Schema keywords out of Gemini's older Schema format.
            config = kwargs["config"]
            assert config.response_schema is None
            assert config.response_json_schema["additionalProperties"] is False
            return SimpleNamespace(
                text='{"category":"quality","description":"Inspection pending","machine":"INVENTED-9","batch":"GUESS-5","quantity":99,"suggested_task_id":"foreign-task"}'
            )

    monkeypatch.setattr(client.genai, "Client", FakeClient)
    result = client.extract("10 units packed. Inspection is pending.")
    assert result["machine"] is None and result["batch"] is None and result["quantity"] is None
    assert result["suggested_task_id"] is None and len(result["uncertainty"]) <= 3


def test_passive_polling_does_not_extend_shared_device_idle_session(setup):
    s = setup
    as_worker(s)
    past = now() - timedelta(minutes=50)
    with s.db.begin() as db:
        session = db.scalar(select(DeviceSession).where(DeviceSession.user_id == s.worker.id))
        session_id = session.id
        session.last_seen = past
    expect(s.client.get("/api/v1/notifications"))
    expect(s.client.get("/api/v1/auth/me"))
    s.client.headers["X-User-Activity"] = "0"
    expect(s.client.get("/api/v1/tasks"))
    with s.db.begin() as db:
        assert db.get(DeviceSession, session_id).last_seen == past
        db.get(DeviceSession, session_id).last_seen = now() - timedelta(minutes=61)
    assert s.client.get("/api/v1/auth/me").status_code == 401


def test_review_and_link_existing_work_preserve_unresolved_report(setup):
    s = setup
    as_worker(s)
    report = expect(s.client.post("/api/v1/reports", json=report_payload(s)), 201)["report"]
    assert (
        s.client.post(
            f"/api/v1/reports/{report['id']}/review",
            json={
                "action": "review",
                "version": report["version"],
                "note": "Observation checked against source",
            },
        ).status_code
        == 403
    )
    as_super(s)
    task = expect(s.client.post("/api/v1/tasks", json=task_payload(s)), 201)
    report = expect(
        s.client.post(
            f"/api/v1/reports/{report['id']}/review",
            json={
                "action": "review",
                "version": report["version"],
                "note": "Observation checked against source",
            },
        )
    )
    assert report["status"] == "reviewed" and report["resolved_at"] is None and report["verified_at"] is None
    expect(
        s.client.post(
            f"/api/v1/reports/{report['id']}/tasks",
            json={
                "task_id": task["id"],
                "version": report["version"],
                "note": "This inspection checks the reported condition",
            },
        ),
        201,
    )
    detail = expect(s.client.get(f"/api/v1/reports/{report['id']}"))
    assert detail["task_links"][0]["task_id"] == task["id"]
    assert any(review["action"] == "task_linked" for review in detail["reviews"])


def test_department_and_team_names_ignore_case_and_surrounding_spaces(setup):
    s = setup
    login(s.client, "organization", "admin@example.com")
    assert s.client.post("/api/v1/departments", json={"name": " production "}).status_code == 409
    assert (
        s.client.post("/api/v1/teams", json={"name": " line a ", "department_id": s.dept.id}).status_code
        == 409
    )


def test_detail_views_and_availability_corrections_remain_scoped(setup):
    s = setup
    as_worker(s)
    assert s.client.get(f"/api/v1/teams/{s.team.id}/overview").status_code == 403
    assert s.client.get(f"/api/v1/supervisors/{s.supervisor.id}/overview").status_code == 403
    as_super(s)
    team = expect(s.client.get(f"/api/v1/teams/{s.team.id}/overview"))
    assert any(person["id"] == s.worker.id for person in team["people"])
    assert "pin_hash" not in str(team)
    absence = expect(
        s.client.post(
            f"/api/v1/workers/{s.worker.id}/availability",
            json={
                "starts_at": (now() - timedelta(hours=1)).isoformat(),
                "ends_at": (now() + timedelta(hours=1)).isoformat(),
                "status": "absent",
                "reason": "Recorded absent pending confirmation",
            },
        ),
        201,
    )
    assert s.client.post("/api/v1/tasks", json=task_payload(s)).status_code == 422
    expect(
        s.client.put(
            f"/api/v1/workers/{s.worker.id}/availability/{absence['id']}",
            json={
                "starts_at": absence["starts_at"],
                "ends_at": absence["ends_at"],
                "status": "available",
                "reason": "Worker confirmed attendance in person",
            },
        )
    )
    expect(s.client.post("/api/v1/tasks", json=task_payload(s)), 201)
    login(s.client, "organization", "admin@example.com")
    person = expect(s.client.get(f"/api/v1/supervisors/{s.supervisor.id}/overview"))
    assert person["departments"][0]["department_id"] == s.dept.id
    assert "password_hash" not in str(person) and "offline_key" not in str(person)


def test_optional_critical_email_is_queued_once_and_never_substitutes_acknowledgement(setup):
    s = setup
    login(s.client, "organization", "admin@example.com")
    expect(
        s.client.put(
            "/api/v1/escalation-rules", json={"department_id": s.dept.id, "channels": ["in_app", "email"]}
        )
    )
    as_worker(s)
    report = expect(s.client.post("/api/v1/reports", json=report_payload(s, immediate_safety=True)), 201)[
        "report"
    ]
    with s.db.begin() as db:
        alert = db.scalar(select(Alert).where(Alert.report_id == report["id"]))
        jobs = list(db.scalars(select(BackgroundJob).where(BackgroundJob.kind == "email")))
        assert len(jobs) == 1 and jobs[0].payload["to"] == s.supervisor.email
        assert "acknowledge or resolve" in jobs[0].payload["text"]
        assert alert.status == "new" and not alert.acknowledged_at
        alert.next_escalation = now() - timedelta(minutes=1)
    from app.services.alerts import escalate_due

    with s.db.begin() as db:
        escalate_due(db)
        escalate_due(db)
    with s.db() as db:
        assert (
            db.scalar(select(func.count()).select_from(BackgroundJob).where(BackgroundJob.kind == "email"))
            == 2
        )
