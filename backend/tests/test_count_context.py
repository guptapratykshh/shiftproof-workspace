import pytest
from conftest import expect, login
from sqlalchemy import select
from test_conversations import body, create, turn

from app.integrations.gemini.client import grounded_identifier
from app.models import Clarification, Conflict, Notification, Report, ReportVersion
from app.services.count_context import normalize_count_fields, product_key

FIRST = "seventy five packaging products की हो चुकी हैं, और वो dispatch के लिए ready है।"
SECOND = "अस्सी product kitchen products की packaging हो चुकी है और एक जगह से वो dispatch के लिए ready है। packaging हो गई है।"


@pytest.mark.parametrize("text,count", [(FIRST, 75), (SECOND, 80)])
def test_actual_spoken_product_counts_have_units_and_are_not_manufacturing(text, count):
    fields = normalize_count_fields({"quantity": count, "quantity_stage": "manufactured"}, text, stage=True)
    assert fields["unit"] == "items"
    assert fields["quantity_stage"] == "packed"
    assert fields["dispatch_status"] == "pending"


def test_product_grounding_accepts_hindi_connectors_without_fuzzy_ids():
    assert product_key("kitchen products") == product_key("किचन के प्रोडक्ट्स")
    assert grounded_identifier("kitchen products", "ये kitchen के products की गिनती है।", "product")
    assert not grounded_identifier("kitchen products", "ये दूसरे products की गिनती है।", "product")
    assert not grounded_identifier("batch 12", "batch 13", "batch")


@pytest.mark.parametrize(
    "text", ["75 boxes of products", "75 kg of products", "products की गिनती 75 boxes है"]
)
def test_containers_and_weight_are_not_inferred_as_items(text):
    assert not normalize_count_fields({"quantity": 75}, text).get("unit")


@pytest.mark.parametrize(
    "text",
    [
        "75 products are not ready for dispatch",
        "75 products will be ready for dispatch",
        "75 products की packaging नहीं हो चुकी है",
    ],
)
def test_negated_or_future_work_is_not_assigned_a_completed_stage(text):
    assert not normalize_count_fields({"quantity": 75}, text, stage=True).get("quantity_stage")


def product_draft(s, count, **fields):
    draft = body(
        s,
        count,
        batch=None,
        product="kitchen products",
        unit="items",
        quantity_basis="total",
        quantity_stage="packed",
    )
    draft["fields"].update(fields)
    draft["text"] = FIRST if count == 75 else SECOND
    return draft


def submit_conversation(s, c):
    return s.client.post(
        "/api/v1/reports",
        json={**c["state"]["draft"], "conversation_id": c["id"], "conversation_revision": c["revision"]},
    )


def test_private_draft_is_not_a_shared_report_then_submission_enables_comparison(setup):
    s = setup
    login(s.client, "worker")
    a = product_draft(s, 75)
    ca = turn(s, create(s, a), a["text"], draft=a)
    ca = turn(s, ca, "I am not sure", "uncertain")
    assert ca["state"]["comparison_incomplete"]
    login(s.client, "worker", employee="W-02")
    b = product_draft(s, 80)
    b["shift_id"] = None
    cb = turn(s, create(s, b), b["text"], draft=b)
    assert not cb["state"]["findings"]
    assert "75" not in cb["state"]["question"]
    login(s.client, "worker")
    first = expect(submit_conversation(s, ca), 201)["report"]
    login(s.client, "worker", employee="W-02")
    cb = turn(s, cb, b["text"], draft=b)
    assert cb["status"] == "awaiting_answer"
    assert "75" in cb["state"]["question"] and "80" in cb["state"]["question"]
    assert "same work and reporting period" in cb["state"]["question"]
    assert "context_decisions" not in cb["state"]
    cb = turn(s, cb, "yes", "reply")
    assert cb["status"] == "ready"
    assert cb["state"]["findings"][0]["finding"]["scope_relation"] == "same"
    second = expect(submit_conversation(s, cb), 201)["report"]
    expect(submit_conversation(s, cb), 201)
    with s.db() as db:
        assert len(list(db.scalars(select(Report)))) == 2
        conflicts = list(db.scalars(select(Conflict)))
        assert len(conflicts) == 1
        questions = list(db.scalars(select(Clarification)))
        assert next(q for q in questions if q.report_id == first["id"]).responded_at is None
        assert next(q for q in questions if q.report_id == second["id"]).response == "yes"
        assert list(db.scalars(select(Notification).where(Notification.user_id == s.supervisor.id)))
    login(s.client, "supervisor", "supervisor@example.com")
    detail = expect(s.client.get("/api/v1/conflicts/" + conflicts[0].id))
    assert detail["findings"][0]["category"] == "quantity_context"
    assert detail["findings"][0]["scope_relation"] == "same"
    assert sorted(detail["findings"][0]["values"]) == [75, 80]


@pytest.mark.parametrize(
    "relation,answer,conflict",
    [
        ("different", "Those are different updates from separate batches", False),
        ("unsure", "I only know my count is eighty", True),
        ("same", "Same work, but correction: seventy five", False),
    ],
)
def test_scope_answers_and_corrections_are_preserved(setup, monkeypatch, relation, answer, conflict):
    from app.integrations.gemini import dialogue

    s = setup
    login(s.client, "worker")
    first = expect(s.client.post("/api/v1/reports", json=product_draft(s, 75)), 201)["report"]
    login(s.client, "worker", employee="W-02")
    draft = product_draft(s, 80)
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    monkeypatch.setattr(
        dialogue,
        "interpret_reply",
        lambda *_: {
            "response_type": "context",
            "scope_relation": relation,
            "fields": {"quantity": 75} if relation == "same" else {},
        },
    )
    c = turn(s, c, answer, "reply")
    assert c["status"] == "ready"
    assert (bool(c["state"]["findings"])) == conflict
    expect(submit_conversation(s, c), 201)
    with s.db() as db:
        assert bool(list(db.scalars(select(Conflict)))) == conflict
        assert (
            db.scalar(select(ReportVersion).where(ReportVersion.report_id == first["id"])).fields["quantity"]
            == 75
        )


@pytest.mark.parametrize(
    "a,b",
    [
        ({"batch": "A"}, {"batch": "B"}),
        ({"reference_period": "morning"}, {"reference_period": "evening"}),
        ({}, {"unit": "boxes"}),
        ({}, {"quantity_basis": "additional"}),
        ({}, {"product": "other products"}),
    ],
)
def test_different_explicit_context_is_not_flagged(setup, a, b):
    s = setup
    login(s.client, "worker")
    expect(s.client.post("/api/v1/reports", json=product_draft(s, 75, **a)), 201)
    login(s.client, "worker", employee="W-02")
    draft = product_draft(s, 80, **b)
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert not c["state"]["findings"]


def test_partial_context_answer_does_not_end_conversation_as_uncertain(setup, monkeypatch):
    from app.integrations.gemini import dialogue

    s = setup
    login(s.client, "worker")
    draft = product_draft(s, 75, product="packaging products", unit=None)
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    monkeypatch.setattr(
        dialogue,
        "interpret_reply",
        lambda *_: {
            "response_type": "uncertain",
            "fields": {"product": "kitchen के products", "unit": "items"},
        },
    )
    c = turn(s, c, "ये kitchen के products की गिनती है।", "reply")
    assert c["status"] == "awaiting_answer"
    assert c["state"]["draft"]["fields"]["product"] == "kitchen के products"
    c = turn(s, c, "I am not sure", "uncertain")
    assert c["status"] == "ready" and c["state"]["comparison_incomplete"]


def test_product_fallback_does_not_cross_linked_departments(setup):
    from app.models import DepartmentMembership

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
    expect(s.client.post("/api/v1/reports", json=product_draft(s, 75)), 201)
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
    draft = {**product_draft(s, 80), "department_id": s.other.id}
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert not c["state"]["findings"]
    assert "75" not in c["state"]["question"]


def test_scope_answer_is_bound_to_exact_source_version(setup):
    s = setup
    login(s.client, "worker")
    source = expect(s.client.post("/api/v1/reports", json=product_draft(s, 75)), 201)["report"]
    login(s.client, "worker", employee="W-02")
    draft = product_draft(s, 80)
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    c = turn(s, c, "yes", "reply")
    with s.db.begin() as db:
        original = db.get(Report, source["id"])
        old = db.scalar(select(ReportVersion).where(ReportVersion.report_id == original.id))
        original.latest_version = 2
        db.add(
            ReportVersion(
                organization_id=s.org.id,
                report_id=original.id,
                number=2,
                author_id=original.author_id,
                text="Correction: 78 kitchen products.",
                fields={**old.fields, "quantity": 78},
                correction_reason="Recount",
            )
        )
    assert submit_conversation(s, c).status_code == 409


def test_unknown_units_do_not_produce_a_numeric_conflict():
    from types import SimpleNamespace

    from app.db import now
    from app.services.contradictions import compare

    report = SimpleNamespace(shift_id=None, occurred_at=now())
    fields = {"category": "progress", "batch": "A", "quantity": 75}
    assert compare(fields, {**fields, "quantity": 80}, report, report) == []


def test_count_noun_in_old_report_only_supports_a_question_not_a_silent_conflict(setup):
    s = setup
    login(s.client, "worker")
    a = product_draft(s, 75, unit=None, batch="PACK-1")
    source = expect(s.client.post("/api/v1/reports", json=a), 201)["report"]
    login(s.client, "worker", employee="W-02")
    draft = product_draft(s, 80, batch="PACK-1")
    expect(s.client.post("/api/v1/reports", json=draft), 201)
    with s.db() as db:
        assert not list(db.scalars(select(Conflict)))
        assert (
            db.scalar(select(ReportVersion).where(ReportVersion.report_id == source["id"])).fields["unit"]
            is None
        )
    c = turn(s, create(s, draft), draft["text"], draft=draft)
    assert c["status"] == "awaiting_answer"
    assert c["state"]["findings"][0]["finding"]["category"] == "quantity_context"
    assert "75" in c["state"]["question"]
