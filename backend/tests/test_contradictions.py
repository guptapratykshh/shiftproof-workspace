"""Adversarial acceptance cases shared with the real Chrome/API suite."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import now
from app.models import Conflict, Report, ReportVersion
from app.schemas import ReportFields
from app.services.contradictions import compare
from conftest import expect, login

CASES = json.loads((Path(__file__).parents[2] / "fixtures/contradiction-cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"] + " " + case["title"])
def test_confirmed_claim_matrix(case):
    time = datetime(2026, 11, 6, 6, tzinfo=UTC)
    a = SimpleNamespace(shift_id="morning", occurred_at=time)
    b = SimpleNamespace(shift_id="evening" if case.get("different_shifts") else "morning",
                        occurred_at=time + timedelta(seconds=case.get("offset_seconds", 0)))
    fa, fb = [ReportFields.model_validate(case[key]["fields"]).model_dump() for key in ("a", "b")]
    findings = compare(fa, fb, a, b)
    assert [finding["category"] for finding in findings] == case["expected"]
    assert [finding["category"] for finding in compare(fb, fa, b, a)] == case["expected"]
    for finding in findings:
        assert len(finding["values"]) == 2
        assert "verif" in finding["recommended_action"].lower()
        assert finding["severity"] == ("high" if finding["category"] in {"quantity_mismatch", "task_completion"} else "critical")
    if case["id"] == "TC-01":
        assert findings[0]["difference"] == 15


def payload(s, claim, **overrides):
    return dict(client_request_id=str(uuid4()), department_id=s.dept.id, shift_id=s.shift.id,
                occurred_at=(now() - timedelta(minutes=2)).isoformat(), confirmed=True,
                text=claim["text"], fields=claim["fields"], **overrides)


@pytest.mark.parametrize("case", CASES[:6], ids=lambda case: case["id"])
def test_original_cases_through_authenticated_api(setup, case):
    s = setup
    ids = []
    for employee, claim in zip(("W-01", "W-02"), (case["a"], case["b"])):
        login(s.client, "worker", employee=employee)
        body = payload(s, claim)
        report = expect(s.client.post("/api/v1/reports", json=body), 201)["report"]
        assert expect(s.client.post("/api/v1/reports", json=body), 201)["report"]["id"] == report["id"]
        ids.append(report["id"])
    login(s.client, "supervisor", "supervisor@example.com")
    conflicts = expect(s.client.get("/api/v1/conflicts"))
    assert len(conflicts) == bool(case["expected"])
    if not conflicts:
        return
    detail = expect(s.client.get("/api/v1/conflicts/" + conflicts[0]["id"]))
    assert [f["category"] for f in detail["findings"]] == case["expected"]
    assert {r["id"] for r in detail["reports"]} == set(ids)
    assert {r["versions"][0]["text"] for r in detail["reports"]} == {case["a"]["text"], case["b"]["text"]}
    assert all(r["clarifications"] and r["needs_attention"] for r in detail["reports"])
    login(s.client, "worker")
    own_list = expect(s.client.get("/api/v1/conflicts"))
    assert own_list[0]["discrepancy"] == "A supervisor is reviewing related reports. Respond to your own clarification request."
    assert s.client.get("/api/v1/conflicts/" + detail["id"]).status_code == 403
    assert s.client.post("/api/v1/conflicts/" + detail["id"] + "/resolve", json={"version": detail["version"], "resolution": "I choose my own statement"}).status_code == 403
    login(s.client, "supervisor", "foreign@example.com", code="ORG-OTHER")
    assert s.client.get("/api/v1/conflicts/" + detail["id"]).status_code == 404
    login(s.client, "supervisor", "supervisor@example.com")
    resolution = {"version": detail["version"], "resolution": "Verified both sources against the register and testing evidence."}
    resolved = expect(s.client.post("/api/v1/conflicts/" + detail["id"] + "/resolve", json=resolution))
    assert resolved["status"] == "resolved"
    assert s.client.post("/api/v1/conflicts/" + detail["id"] + "/resolve", json=resolution).status_code == 409
    after = expect(s.client.get("/api/v1/conflicts/" + detail["id"]))
    assert {r["versions"][0]["text"] for r in after["reports"]} == {case["a"]["text"], case["b"]["text"]}


def test_correction_rechecks_resolved_pair_and_preserves_source_version(setup):
    s = setup
    original = CASES[0]
    login(s.client, "worker")
    body = payload(s, original["a"])
    first = expect(s.client.post("/api/v1/reports", json=body), 201)["report"]
    login(s.client, "worker", employee="W-02")
    second = expect(s.client.post("/api/v1/reports", json=payload(s, original["b"])), 201)["report"]
    login(s.client, "supervisor", "supervisor@example.com")
    conflict = expect(s.client.get("/api/v1/conflicts"))[0]
    expect(s.client.post(f"/api/v1/conflicts/{conflict['id']}/resolve", json={"version": conflict["version"], "resolution": "Compared production ledger and confirmed the recorded count."}))
    login(s.client, "worker")
    first = expect(s.client.get(f"/api/v1/reports/{first['id']}"))
    corrected = {**body, "text": "Correction: CNC-01 produced 70 pieces", "fields": {**body["fields"], "quantity": 70}}
    expect(s.client.post(f"/api/v1/reports/{first['id']}/corrections", json={"report": corrected, "reason": "Recounted the same batch", "version": first["version"]}), 201)
    login(s.client, "supervisor", "supervisor@example.com")
    conflicts = expect(s.client.get("/api/v1/conflicts"))
    assert len(conflicts) == 2 and {c["status"] for c in conflicts} == {"open", "resolved"}
    old = expect(s.client.get(f"/api/v1/conflicts/{conflict['id']}"))
    assert old["findings"][0]["difference"] == 15
    new = expect(s.client.get("/api/v1/conflicts/" + next(c["id"] for c in conflicts if c["status"] == "open")))
    assert new["findings"][0]["difference"] == 15
    assert any(r["linked_version"] == 2 for r in new["reports"])
    assert all(r["linked_version"] == 1 for r in old["reports"])


def test_conflict_not_lost_after_100_unrelated_updates(setup):
    s = setup
    login(s.client, "worker")
    expect(s.client.post("/api/v1/reports", json=payload(s, CASES[0]["a"])), 201)
    with s.db.begin() as db:
        for index in range(105):
            report = Report(organization_id=s.org.id, author_id=s.worker.id, department_id=s.dept.id,
                            shift_id=s.shift.id, client_request_id=str(uuid4()), request_hash="test",
                            occurred_at=now() - timedelta(minutes=2), submitted_at=now(),
                            category="progress", status="submitted", latest_version=1)
            db.add(report)
            db.flush()
            db.add(ReportVersion(organization_id=s.org.id, report_id=report.id, number=1,
                                 text="Unrelated report", fields={"machine": f"OTHER-{index}", "quantity": 1}, author_id=s.worker.id))
    login(s.client, "worker", employee="W-02")
    expect(s.client.post("/api/v1/reports", json=payload(s, CASES[0]["b"])), 201)
    with s.db() as db:
        assert len(list(db.scalars(select(Conflict)))) == 1


def test_reporting_day_uses_organization_timezone():
    a = SimpleNamespace(shift_id=None, occurred_at=datetime(2026, 11, 5, 23, 59, tzinfo=UTC))
    b = SimpleNamespace(shift_id=None, occurred_at=datetime(2026, 11, 6, 0, 1, tzinfo=UTC))
    assert len(compare(CASES[0]['a']['fields'], CASES[0]['b']['fields'], a, b, 'Asia/Kolkata')) == 1
    a.occurred_at = datetime(2026, 11, 6, 18, 29, tzinfo=UTC)
    b.occurred_at = datetime(2026, 11, 6, 18, 31, tzinfo=UTC)
    assert compare(CASES[0]['a']['fields'], CASES[0]['b']['fields'], a, b, 'Asia/Kolkata') == []


@pytest.mark.parametrize('quantity', [float('inf'), float('nan'), -1])
def test_invalid_quantity_rejected(quantity):
    with pytest.raises(ValueError):
        ReportFields(quantity=quantity)


def test_model_cannot_silently_drop_second_machine(monkeypatch):
    from app.integrations.gemini import client
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), 'gemini_api_key', 'test-key')
    class FakeClient:
        def __init__(self, **_): self.models = self
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def generate_content(self, **_):
            return SimpleNamespace(text='{"machine":"CNC-01","quantity":100,"unit":"pieces","description":"100 pieces on CNC-01"}')
    monkeypatch.setattr(client.genai, 'Client', FakeClient)
    text = 'CNC-01 produced 100 pieces. CNC-02 produced 85 pieces.'
    result = client.extract(text)
    assert result['quantity'] is None and result['machine'] is None
    assert 'CNC-02' in result['description'] and result['uncertainty']


def test_two_workers_submit_simultaneously(setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import app
    s = setup
    clients = [TestClient(app), TestClient(app)]
    try:
        for client, employee in zip(clients, ('W-01', 'W-02')):
            login(client, 'worker', employee=employee)
        for index in range(6):
            start = Barrier(2)
            def send(side):
                claim = CASES[0]['a' if side == 0 else 'b']
                body = payload(s, {**claim, 'fields': {**claim['fields'], 'machine': f'RACE-{index}'}})
                start.wait(timeout=10)
                return clients[side].post('/api/v1/reports', json=body)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(send, (0, 1)))
            for response in results:
                expect(response, 201)
        login(s.client, 'supervisor', 'supervisor@example.com')
        assert len(expect(s.client.get('/api/v1/conflicts'))) == 6
    finally:
        for client in clients:
            client.close()


@pytest.mark.parametrize('source', ['Batch 204 is rejected.', 'CNC-204 is running.', 'Target 204 pieces; actual count is unknown.', 'At 02:04 work started.'])
def test_entity_time_or_target_number_cannot_become_quantity(monkeypatch, source):
    from app.integrations.gemini import client
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), 'gemini_api_key', 'test-key')
    class FakeClient:
        def __init__(self, **_): self.models = self
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def generate_content(self, **_): return SimpleNamespace(text='{"quantity":204}')
    monkeypatch.setattr(client.genai, 'Client', FakeClient)
    result = client.extract(source)
    assert result['quantity'] is None and result['uncertainty']


def test_mongo_login_retries_aborted_session_without_leaking_cookies(monkeypatch):
    from fastapi import Response
    from sqlalchemy.orm.exc import StaleDataError
    from app.api import auth
    from app.schemas import Login
    attempts = []
    class DB:
        bind = SimpleNamespace(dialect=SimpleNamespace(name='mongodb'))
        def commit(self): pass
        def rollback(self): attempts.append('rollback')
    def login_once(db, role, values, request, response):
        if not attempts:
            response.set_cookie('shiftproof_session', 'aborted')
            response.set_cookie('shiftproof_csrf', 'aborted')
            raise StaleDataError()
        response.set_cookie('shiftproof_session', 'committed')
        response.set_cookie('shiftproof_csrf', 'committed')
        return {'status':'authenticated'}
    monkeypatch.setattr(auth.service, 'login', login_once)
    monkeypatch.setattr(auth.time, 'sleep', lambda *_: None)
    response=Response()
    result=auth.login('worker',Login(),None,response,DB())
    assert result['status']=='authenticated' and attempts==['rollback']
    cookies=[value for key,value in response.raw_headers if key==b'set-cookie']
    assert len(cookies)==2 and all(b'committed' in c and b'aborted' not in c for c in cookies)


def test_progressive_counts_at_different_explicit_times_are_updates():
    report = SimpleNamespace(shift_id=None, occurred_at=datetime(2026,11,6,6,tzinfo=UTC))
    a = {**CASES[0]['a']['fields'], 'observation_time':'10:00'}
    b = {**CASES[0]['b']['fields'], 'observation_time':'14:00', 'quantity':150}
    assert compare(a,b,report,report) == []


def test_produced_and_quality_counts_are_different_measurements():
    report = SimpleNamespace(shift_id=None, occurred_at=datetime(2026,11,6,6,tzinfo=UTC))
    a = {**CASES[0]['a']['fields'], 'category':'progress'}
    b = {**CASES[0]['b']['fields'], 'category':'quality'}
    assert compare(a,b,report,report) == []


def test_repeating_relative_period_on_different_days_does_not_match():
    a = SimpleNamespace(shift_id=None, occurred_at=datetime(2026,11,5,6,tzinfo=UTC))
    b = SimpleNamespace(shift_id=None, occurred_at=datetime(2026,11,6,6,tzinfo=UTC))
    assert compare({**CASES[0]['a']['fields'],'reference_period':'aaj'},
                   {**CASES[0]['b']['fields'],'reference_period':'aaj'},a,b) == []


@pytest.mark.parametrize('text,expected', [('पचास', '50'), ('दो सौ चार', '204'), ('पचासी', '85'), ('eighty five', '85'), ('two hundred four', '204'), ('one two', 'one two'), ('CNC-01', 'CNC-01')])
def test_spoken_number_normalization_is_bounded(text,expected):
    from app.claim_numbers import spoken_numbers
    assert spoken_numbers(text) == expected


def test_spoken_quantity_is_separate_from_spoken_entity_id():
    from app.integrations.gemini.client import source_quantities
    from app.services.contradictions import identifier
    assert source_quantities('batch दो सौ चार के पचास piece पास हैं') == {50}
    assert identifier('batch दो सौ चार', 'batch') == identifier('Batch 204','batch')


def test_large_counts_still_detect_one_missing_piece():
    report = SimpleNamespace(shift_id=None, occurred_at=datetime(2026,11,6,6,tzinfo=UTC))
    a = {**CASES[0]['a']['fields'], 'quantity':1000000000}
    b = {**CASES[0]['b']['fields'], 'quantity':1000000001}
    assert compare(a,b,report,report)[0]['difference'] == 1


def test_english_instruction_do_is_not_a_hinglish_quantity():
    from app.integrations.gemini.client import source_quantities
    assert source_quantities('Do not guess an unknown count.') == set()


def test_batch_label_translation_keeps_only_exact_grounded_id():
    from app.integrations.gemini.client import grounded_identifier
    text='बैच दो सौ चार के पचास पीस में दरारें मिली हैं'
    assert grounded_identifier('Batch 204',text,'batch')
    assert not grounded_identifier('Batch 205',text,'batch')
    assert not grounded_identifier('Batch 0204',text,'batch')
    assert not grounded_identifier('Order 204',text,'order')


def test_failed_asset_insert_cleans_up_private_audio(tmp_path,monkeypatch):
    from app.services import storage
    from app.config import get_settings
    from sqlalchemy.orm.exc import StaleDataError
    monkeypatch.setattr(get_settings(),'storage_directory',tmp_path)
    monkeypatch.setattr(get_settings(),'storage_mode','local')
    monkeypatch.setattr(storage,'policy_value',lambda *_: {})
    class DB:
        def add(self,item): pass
        def flush(self): raise StaleDataError()
    with pytest.raises(StaleDataError):
        storage.store_asset(DB(),SimpleNamespace(id='worker',organization_id='org'),b'audio','test.wav','audio/wav','audio','dept',True)
    assert not [p for p in tmp_path.rglob('*') if p.is_file()]


def test_spoken_review_includes_confirmed_comparison_facts():
    from app.services.voice import report_script
    fields=ReportFields(order='ORD-501',dispatch_status='pending',quality_status='rejected',task_reference='TASK-108',task_status='pending',reference_period='Morning shift',quantity_basis='additional')
    script=report_script('Check the current status.',fields,'en-IN')
    for expected in ['Order: ORD-501','Dispatch status: pending','Quality status: rejected','Task: TASK-108','Task status: pending','Reporting period: Morning shift','Counting basis: additional']:
        assert expected in script
