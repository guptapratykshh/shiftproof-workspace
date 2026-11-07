import io
import re
from datetime import timedelta
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select

from app.db import now
from app.models import Alert, BackgroundJob, HandoverVersion, Organization, Task
from conftest import PASSWORD, PIN, expect, login


def task_payload(s, **overrides):
    return {"title": "Check packing line", "department_id": s.dept.id, "worker_id": s.worker.id, **overrides}


def report_payload(s, **overrides):
    return {
        "client_request_id": str(uuid4()),
        "department_id": s.dept.id,
        "occurred_at": now().isoformat(),
        "text": "Packing complete. Quality inspection pending.",
        "fields": {
            "category": "quality",
            "description": "Inspection remains pending",
            "machine": "M-1",
            "batch": "B-1",
            "quantity": 10,
        },
        "confirmed": True,
        **overrides,
    }


def as_super(s):
    login(s.client, "supervisor", "supervisor@example.com")


def as_worker(s, employee="W-01"):
    login(s.client, "worker", employee=employee)


def perform(s, task, action, **kw):
    return expect(
        s.client.post(
            f"/api/v1/tasks/{task['id']}/actions", json={"action": action, "version": task["version"], **kw}
        )
    )


def test_registration_verification_onboarding_and_invite(environment):
    s = environment
    payload = {
        "fullName": "Administrator",
        "organizationName": "New Factory",
        "organizationType": "manufacturing",
        "email": "new@example.com",
        "password": PASSWORD,
    }
    expect(s.client.post("/api/v1/auth/register", json=payload), 202)
    with s.db() as db:
        assert db.scalar(select(func.count()).select_from(Organization)) == 0
        job = db.scalar(select(BackgroundJob).where(BackgroundJob.kind == "email"))
        token = re.search(r"token=([\w-]+)", job.payload["text"])[1]
    verified = expect(s.client.post("/api/v1/auth/verify", json={"token": token}))
    assert s.client.post("/api/v1/auth/verify", json={"token": token}).status_code == 400
    login(s.client, "organization", "new@example.com")
    assert s.client.post("/api/v1/organization/activate").status_code == 409
    expect(
        s.client.put(
            "/api/v1/organization",
            json={
                "name": "New Factory",
                "industry": "manufacturing",
                "contact_email": "new@example.com",
                "timezone": "Asia/Kolkata",
            },
        )
    )
    dept = expect(s.client.post("/api/v1/departments", json={"name": "Production"}), 201)
    expect(s.client.post("/api/v1/teams", json={"name": "Line A", "department_id": dept["id"]}), 201)
    expect(
        s.client.post(
            "/api/v1/shifts",
            json={"name": "Night", "starts_at": "22:00", "ends_at": "06:00", "days": [0, 1, 2, 3, 4]},
        ),
        201,
    )
    expect(
        s.client.post(
            "/api/v1/supervisors/invite",
            json={
                "name": "Responsible Supervisor",
                "email": "responsible@example.com",
                "departments": [
                    {
                        "department_id": dept["id"],
                        "primary": True,
                        "permissions": ["view", "manage", "review", "publish"],
                    }
                ],
            },
        ),
        201,
    )
    assert expect(s.client.get("/api/v1/organization/onboarding"))["can_activate"] is False
    with s.db() as db:
        jobs = db.scalars(select(BackgroundJob).where(BackgroundJob.kind == "email")).all()
        token = re.search(r"token=([\w-]+)", jobs[-1].payload["text"])[1]
    expect(
        s.client.post(
            "/api/v1/auth/activate", json={"token": token, "password": PASSWORD, "confirm": PASSWORD}
        )
    )
    expect(s.client.post("/api/v1/organization/activate"))
    assert expect(s.client.get("/api/v1/organization/onboarding"))["active"]
    assert verified["organizationId"].startswith("ORG-")


def test_csrf_last_admin_revocation_and_tenant_scope(setup):
    s = setup
    login(s.client, "organization", "admin@example.com")
    assert (
        s.client.put(
            f"/api/v1/users/{s.admin.id}/state",
            json={"active": False, "reason": "Testing last administrator protection"},
        ).status_code
        == 409
    )
    assert s.client.put(f"/api/v1/departments/{s.foreign.id}", json={"name": "Illegal"}).status_code == 404
    csrf = s.client.headers.pop("X-CSRF-Token")
    assert s.client.post("/api/v1/departments", json={"name": "Denied"}).status_code == 403
    s.client.headers["X-CSRF-Token"] = csrf
    expect(s.client.post("/api/v1/auth/logout"))
    assert s.client.get("/api/v1/auth/me").status_code == 401


def test_task_lifecycle_critical_review_and_rejection(setup):
    s = setup
    as_super(s)
    task = expect(s.client.post("/api/v1/tasks", json=task_payload(s, critical=True)), 201)
    assert task["verification_required"]
    as_worker(s)
    task = perform(s, task, "accept")
    task = perform(s, task, "start")
    task = perform(s, task, "complete")
    assert task["status"] == "completed"
    assert (
        s.client.post(
            f"/api/v1/tasks/{task['id']}/actions", json={"action": "verify", "version": task["version"]}
        ).status_code
        == 403
    )
    as_super(s)
    assert (
        s.client.post(
            f"/api/v1/tasks/{task['id']}/actions", json={"action": "reject", "version": task["version"]}
        ).status_code
        == 422
    )
    task = perform(s, task, "reject", reason="The inspection evidence is incomplete")
    assert task["status"] == "in_progress"
    as_worker(s)
    task = perform(s, task, "complete")
    as_super(s)
    task = perform(s, task, "verify")
    task = perform(s, task, "close")
    assert task["closed_at"] and len(task["verifications"]) == 2


def test_routine_team_task_one_record_and_internal_comments(setup):
    s = setup
    as_super(s)
    task = expect(
        s.client.post(
            "/api/v1/tasks", json=task_payload(s, assignment_type="team", worker_id=None, team_id=s.team.id)
        ),
        201,
    )
    expect(
        s.client.post(
            f"/api/v1/tasks/{task['id']}/comments", json={"text": "Private supervisor note", "internal": True}
        ),
        201,
    )
    as_worker(s)
    task = perform(s, task, "accept")
    assert task["comments"] == []
    as_worker(s, "W-02")
    shared = expect(s.client.get(f"/api/v1/tasks/{task['id']}"))
    assert shared["status"] == "accepted"
    shared = perform(s, shared, "start")
    shared = perform(s, shared, "complete")
    assert shared["status"] == "closed"
    with s.db() as db:
        assert db.scalar(select(func.count()).select_from(Task)) == 1


def test_department_boundary_qualifications_and_absence(setup):
    s = setup
    as_super(s)
    assert s.client.post("/api/v1/tasks", json=task_payload(s, department_id=s.other.id)).status_code == 403
    assert (
        s.client.post("/api/v1/tasks", json=task_payload(s, required_skills=["electrical"])).status_code
        == 422
    )
    task = expect(s.client.post("/api/v1/tasks", json=task_payload(s)), 201)
    expect(
        s.client.post(
            f"/api/v1/workers/{s.worker.id}/availability",
            json={
                "starts_at": now().isoformat(),
                "ends_at": (now() + timedelta(hours=8)).isoformat(),
                "status": "absent",
                "reason": "Reported absence",
            },
        ),
        201,
    )
    assert s.client.post("/api/v1/tasks", json=task_payload(s)).status_code == 422
    changed = expect(
        s.client.post(
            f"/api/v1/tasks/{task['id']}/reassign",
            json={"worker_id": s.worker2.id, "reason": "Covering absent worker", "version": task["version"]},
        )
    )
    detail = expect(s.client.get(f"/api/v1/tasks/{task['id']}"))
    assert len(detail["assignments"]) == 2 and detail["assignments"][0]["ended_at"]
    assert changed["status"] == "assigned"


def test_report_retry_correction_conflict_and_privacy(setup):
    s = setup
    as_worker(s)
    values = report_payload(s)
    # Quantity conflicts require comparable units, not two unspecified units.
    values["fields"]["unit"] = "pieces"
    report = expect(s.client.post("/api/v1/reports", json=values), 201)["report"]
    assert expect(s.client.post("/api/v1/reports", json=values), 201)["report"]["id"] == report["id"]
    assert s.client.post("/api/v1/reports", json={**values, "text": "Different"}).status_code == 409
    corrected = {**values, "text": "Ten packed; inspection is still pending."}
    detail = expect(
        s.client.post(
            f"/api/v1/reports/{report['id']}/corrections",
            json={
                "report": corrected,
                "reason": "Clarified the inspection condition",
                "version": report["version"],
            },
        ),
        201,
    )
    assert len(detail["versions"]) == 2 and detail["versions"][-1]["text"] == values["text"]
    as_worker(s, "W-02")
    expect(
        s.client.post(
            "/api/v1/reports",
            json=report_payload(
                s, fields={"category": "quality", "machine": "M-1", "batch": "B-1", "quantity": 12, "unit": "pieces"}
            ),
        ),
        201,
    )
    assert s.client.get(f"/api/v1/reports/{report['id']}").status_code == 404
    as_super(s)
    conflicts = expect(s.client.get("/api/v1/conflicts"))
    assert len(conflicts) == 1
    conflict = expect(s.client.get(f"/api/v1/conflicts/{conflicts[0]['id']}"))
    assert len(conflict["reports"]) == 2
    report = expect(s.client.get(f"/api/v1/reports/{report['id']}"))
    verified = expect(
        s.client.post(
            f"/api/v1/reports/{report['id']}/review",
            json={
                "action": "verify",
                "note": "Checked source against the batch record",
                "version": report["version"],
            },
        )
    )
    assert verified["verified_at"] and not verified["resolved_at"]
    login(s.client, "organization", "admin@example.com")
    assert s.client.get(f"/api/v1/reports/{report['id']}?purpose=Operational+review").status_code == 403
    expect(
        s.client.post(
            "/api/v1/takeovers",
            json={
                "department_id": s.dept.id,
                "reason": "Supervisor unavailable during investigation",
                "hours": 1,
            },
        ),
        201,
    )
    expect(s.client.get(f"/api/v1/reports/{report['id']}?purpose=Operational+review"))


def test_immediate_alert_escalation_and_receipt_not_resolution(setup):
    s = setup
    as_worker(s)
    report = expect(s.client.post("/api/v1/reports", json=report_payload(s, immediate_safety=True)), 201)[
        "report"
    ]
    with s.db.begin() as db:
        alert = db.scalar(select(Alert).where(Alert.report_id == report["id"]))
        assert alert.assigned_to == s.supervisor.id
        alert.next_escalation = now() - timedelta(minutes=1)
    from app.services.alerts import escalate_due

    with s.db.begin() as db:
        escalate_due(db)
    as_super(s)
    alert = expect(s.client.get("/api/v1/alerts"))[0]
    assert alert["escalation_level"] == 1
    alert = expect(
        s.client.post(
            f"/api/v1/alerts/{alert['id']}/actions",
            json={"action": "acknowledge", "version": alert["version"]},
        )
    )
    assert alert["status"] == "acknowledged" and not alert["resolved_at"]
    assert (
        s.client.post(
            f"/api/v1/alerts/{alert['id']}/actions", json={"action": "resolve", "version": alert["version"]}
        ).status_code
        == 409
    )


def test_handover_immutable_snapshots_and_separate_acknowledgements(setup):
    s = setup
    as_super(s)
    expect(
        s.client.post(
            "/api/v1/shift-assignments",
            json={
                "user_id": s.worker.id,
                "shift_id": s.shift.id,
                "department_id": s.dept.id,
                "starts_on": now().date().isoformat(),
            },
        ),
        201,
    )
    expect(s.client.post("/api/v1/tasks", json=task_payload(s, critical=True)), 201)
    handover = expect(
        s.client.post(
            "/api/v1/handovers",
            json={"department_id": s.dept.id, "shift_id": s.shift.id, "shift_date": now().date().isoformat()},
        ),
        201,
    )
    version = expect(
        s.client.post(
            f"/api/v1/handovers/{handover['id']}/publish",
            json={
                "notes": "Check outstanding inspection",
                "changes": "Initial publication",
                "version": handover["version"],
            },
        ),
        201,
    )
    as_worker(s)
    detail = expect(s.client.get(f"/api/v1/handovers/{handover['id']}"))
    critical = detail["versions"][0]["items"][0]
    expect(
        s.client.post(f"/api/v1/handovers/{handover['id']}/acknowledge", json={"version_id": version["id"]})
    )
    detail = expect(s.client.get(f"/api/v1/handovers/{handover['id']}"))
    assert detail["versions"][0]["items"][0]["acknowledgements"] == []
    expect(
        s.client.post(
            f"/api/v1/handovers/{handover['id']}/acknowledge",
            json={"version_id": version["id"], "item_id": critical["id"]},
        )
    )
    as_super(s)
    detail = expect(s.client.get(f"/api/v1/handovers/{handover['id']}"))
    second = expect(
        s.client.post(
            f"/api/v1/handovers/{handover['id']}/publish",
            json={
                "notes": "Added updated context",
                "changes": "Additional inspection context",
                "version": detail["version"],
            },
        ),
        201,
    )
    assert second["number"] == 2
    with s.db() as db:
        assert db.get(HandoverVersion, version["id"]).snapshot["notes"] == "Check outstanding inspection"
    detail = expect(s.client.get(f"/api/v1/handovers/{handover['id']}"))
    assert all(not receipt["acknowledged_at"] for receipt in detail["versions"][0]["recipients"])


def test_worker_import_preview_confirmation_and_private_pin(setup):
    s = setup
    as_super(s)
    content = b"full_name,employee_id,primary_department,teams\nNew Worker,W-03,Production,Line A\nDuplicate Worker,W-01,Production,Line A\n"
    preview = expect(
        s.client.post("/api/v1/worker-imports/preview", files={"file": ("workers.csv", content, "text/csv")}),
        201,
    )
    assert preview["valid"] == 1 and preview["invalid"] == 1
    assert s.client.post(f"/api/v1/worker-imports/{preview['id']}/confirm", json={}).status_code == 422
    result = expect(
        s.client.post(
            f"/api/v1/worker-imports/{preview['id']}/confirm", json={"confirm_valid_rows_only": True}
        )
    )
    assert result["created"] == 1
    assert (
        expect(
            s.client.post(
                f"/api/v1/worker-imports/{preview['id']}/confirm", json={"confirm_valid_rows_only": True}
            )
        )["created"]
        == 1
    )
    token = result["workers"][0]["activation_url"].split("token=")[1]
    expect(s.client.post("/api/v1/auth/activate", json={"token": token, "pin": PIN, "confirm": PIN}))
    as_worker(s, "W-03")
    person = expect(s.client.get("/api/v1/auth/me"))["user"]
    assert "pin_hash" not in person and "password_hash" not in person


def test_evidence_authorization_and_provider_failure_preserves_source(setup):
    s = setup
    as_worker(s)
    png = io.BytesIO()
    Image.new("RGB", (8, 8)).save(png, "PNG")
    asset = expect(
        s.client.post(
            "/api/v1/files",
            data={"department_id": s.dept.id, "kind": "photo"},
            files={"file": ("evidence.png", png.getvalue(), "image/png")},
        ),
        201,
    )
    assert "storage_key" not in asset
    as_worker(s, "W-02")
    assert s.client.get(f"/api/v1/files/{asset['id']}").status_code == 403
    as_worker(s)
    assert s.client.get(f"/api/v1/files/{asset['id']}").status_code == 200
    failed = s.client.post("/api/v1/extractions", json={"text": "Inspection pending"})
    assert failed.status_code == 503
    expect(s.client.post("/api/v1/reports", json=report_payload(s, evidence_ids=[asset["id"]])), 201)


def test_real_analytics_counts_corrections_once_and_null_empty_rates(setup):
    s = setup
    as_super(s)
    empty = expect(s.client.get("/api/v1/analytics"))
    assert empty["metrics"]["task_completion_rate"] is None
    as_worker(s)
    values = report_payload(s)
    report = expect(s.client.post("/api/v1/reports", json=values), 201)["report"]
    expect(
        s.client.post(
            f"/api/v1/reports/{report['id']}/corrections",
            json={
                "report": {**values, "text": "Updated wording"},
                "reason": "Clarify observation",
                "version": report["version"],
            },
        ),
        201,
    )
    as_super(s)
    data = expect(s.client.get("/api/v1/analytics"))
    assert data["metrics"]["submitted_reports"] == 1
    assert data["metrics"]["quality_issues"] == 1
    assert data["metrics"]["active_workers"] == 2
    assert s.client.get(f"/api/v1/analytics?department_id={s.foreign.id}").status_code == 403


def test_durable_job_lease_recovery_and_failure_isolation(environment):
    s = environment
    from app.services.common import enqueue

    with s.db.begin() as db:
        job = enqueue(db, "unknown", "test:job", {})
        job_id = job.id
    claimed = s.worker.claim()
    assert claimed and s.worker.claim() is None
    s.worker.execute(*claimed)
    with s.db.begin() as db:
        job = db.get(BackgroundJob, job_id)
        assert job.status == "queued" and job.attempts == 1
        job.status, job.leased_until = "processing", now() - timedelta(seconds=1)
    recovered = s.worker.claim()
    assert recovered and recovered[1] != claimed[1]
    s.worker.execute(*claimed)
    with s.db() as db:
        assert db.get(BackgroundJob, job_id).status == "processing"
