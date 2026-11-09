"""Compare human-confirmed facts, keeping entity, measurement and time scopes separate.

This is deliberately not a free-text truth judge. Unknown context/statuses need
human clarification; a later observation or an additional quantity is not a lie.
Findings always retain both claims and propose verification, never pick a winner.
"""

import math
import re
import unicodedata
from zoneinfo import ZoneInfo
from ..claim_numbers import spoken_numbers
from .count_context import product_key


def normalized(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in value)
    return re.sub(r"\s+", " ", value)


def identifier(value, kind=""):
    if kind == "product":
        return product_key(value)
    value = normalized(spoken_numbers(str(value or "")))
    prefixes = {"batch": r"^(?:batch|बैच)\s*[-_:]?\s*", "order": r"^(?:order|ord|ऑर्डर)\s*[-_:]?\s*",
                "task_reference": r"^(?:task|कार्य)\s*[-_:]?\s*",
                "transfer_reference": r"^(?:transfer|shipment|ट्रांसफर|ट्रांसफ़र|शिपमेंट)\s*(?:id\s*)?[-_:]?\s*"}
    if kind in prefixes:
        value = re.sub(prefixes[kind], "", value)
    return re.sub(r"[\s\-_‐‑–]+", "", value.replace(chr(0x2014), ""))


UNITS = {
    "pieces": ("pieces", 1), "piece": ("pieces", 1), "pcs": ("pieces", 1),
    "units": ("pieces", 1), "unit": ("pieces", 1), "पीस": ("pieces", 1),
    "items": ("pieces", 1), "item": ("pieces", 1), "products": ("pieces", 1),
    "product": ("pieces", 1), "उत्पाद": ("pieces", 1), "प्रोडक्ट्स": ("pieces", 1),
    "kg": ("mass", 1000), "kgs": ("mass", 1000), "kilograms": ("mass", 1000),
    "g": ("mass", 1), "grams": ("mass", 1), "gram": ("mass", 1),
    "boxes": ("boxes", 1), "box": ("boxes", 1),
}
STATUS_ALIASES = {
    "quality_status": {
        "passed": {"passed", "pass", "approved", "no defects", "पास", "पास है", "pass hai"},
        "rejected": {"rejected", "reject", "failed", "fail", "फेल", "reject kar diya"},
        "pending": {"pending", "inspection pending"},
    },
    "dispatch_status": {
        "dispatched": {"dispatched", "shipped", "departed", "dispatch complete"},
        "pending": {"pending", "not dispatched", "awaiting dispatch", "loading bay", "dispatch nahi hua"},
    },
    "machine_status": {
        "operational": {"operational", "running", "working", "चालू", "chal rahi hai"},
        "maintenance": {"maintenance", "under maintenance"},
        "stopped": {"stopped", "not running", "band hai", "बंद"},
        "failed": {"failed", "broken", "down"},
    },
    "task_status": {
        "completed": {"completed", "complete", "done", "repair complete", "पूरा"},
        "pending": {"pending", "in progress", "not complete", "not completed", "complete nahi hua", "अधूरा"},
    },
}
RULES = [
    ("quality_status", "quality_status", "Quality status conflict", "critical", ("batch",),
     "Keep the batch on quality hold until a supervisor verifies inspection results and defect evidence."),
    ("dispatch_status", "dispatch_status", "Dispatch status conflict", "critical", ("order",),
     "Verify vehicle departure, loading-bay location and dispatch documentation before confirming dispatch."),
    ("machine_status", "machine_availability", "Machine availability conflict", "critical", ("machine",),
     "Verify maintenance status and safe release before restarting production."),
    ("task_status", "task_completion", "Task completion conflict", "high", ("task_reference",),
     "Verify repair completion and testing evidence with the responsible team before marking the task complete."),
]


def status(fields, key):
    value = fields.get(key)
    # Support existing reports, but do not treat arbitrary differently-worded
    # descriptions as opposites or infer that 'not complete' means 'complete'.
    if not value:
        category = fields.get("category")
        legacy_category = {"quality_status": {"quality"}, "machine_status": {"equipment", "maintenance"},
                           "dispatch_status": {"materials", "progress"}, "task_status": {"maintenance", "progress"}}
        if category in legacy_category[key]:
            value = fields.get("operational_status")
    value = normalized(value)
    return next((state for state, aliases in STATUS_ALIASES[key].items() if value in aliases), None)


def context_matches(a, b, entities, cross_department=False):
    # Shared contradictory identifiers always separate the contexts. Missing
    # optional location/product metadata is not itself a contradiction.
    for key in ("machine", "batch", "order", "task_reference", "product", "work_area", "transfer_reference"):
        if cross_department and key in {"machine", "work_area"}:
            continue
        if a.get(key) and b.get(key) and identifier(a[key], key) != identifier(b[key], key):
            return False
    return any(a.get(key) and b.get(key) and identifier(a[key], key) == identifier(b[key], key)
               for key in entities)


def same_period(a, b, report_a, report_b, timezone):
    zone = ZoneInfo(timezone)
    same_day = report_a.occurred_at.astimezone(zone).date() == report_b.occurred_at.astimezone(zone).date()
    left, right = a.get("reference_period"), b.get("reference_period")
    if left or right:
        if not (left and right and normalized(left) == normalized(right)):
            return False
        # 'Today' and repeating shift names on different days do not identify
        # one production period. An explicit shared date can identify it.
        return same_day or bool(re.search(r"\d{4}-\d{2}-\d{2}", normalized(left)))
    # A worker on the incoming shift can explicitly reference the outgoing
    # period above. Otherwise different shift assignments are not comparable.
    if report_a.shift_id != report_b.shift_id:
        return False
    return same_day


def same_observation(a, b, report_a, report_b):
    left, right = a.get("observation_time"), b.get("observation_time")
    if left or right:
        return bool(left and right and normalized(left) == normalized(right))
    # Without an explicit shared observation, changed statuses at distinct
    # recorded times are updates. A small entry-time tolerance handles two
    # people reporting the same handover; the finding remains a review request.
    return abs((report_a.occurred_at - report_b.occurred_at).total_seconds()) <= 300


def compare(a, b, report_a, report_b, timezone="UTC", cross_department=False):
    transfer = bool(a.get("transfer_reference") and b.get("transfer_reference")
                    and identifier(a["transfer_reference"], "transfer_reference") == identifier(b["transfer_reference"], "transfer_reference"))
    if not transfer and not same_period(a, b, report_a, report_b, timezone):
        return []
    findings = []
    entities = ("batch", "order", "transfer_reference") if cross_department else ("batch", "machine", "order", "task_reference", "transfer_reference")
    stages = {a.get("quantity_stage"), b.get("quantity_stage")} - {None}
    transfer_gap = len(stages) == 2
    if (context_matches(a, b, entities, cross_department)
            and (a.get("category") == b.get("category") or transfer_gap)
            and (not (a.get("observation_time") or b.get("observation_time")) or same_observation(a, b, report_a, report_b))
            and a.get("quantity_basis") != "additional" and b.get("quantity_basis") != "additional"
            and a.get("quantity") is not None and b.get("quantity") is not None):
        ua, ub = normalized(a.get("unit")), normalized(b.get("unit"))
        unit_a, factor_a = UNITS.get(ua, (ua, 1))
        unit_b, factor_b = UNITS.get(ub, (ub, 1))
        qa, qb = a["quantity"] * factor_a, b["quantity"] * factor_b
        if unit_a and unit_a == unit_b and not math.isclose(qa, qb, rel_tol=0, abs_tol=1e-9):
            findings.append({
                "category": "transfer_gap" if transfer_gap else "quantity_mismatch",
                "title": "Transfer difference" if transfer_gap else "Quantity mismatch", "severity": "high",
                "field": "quantity", "values": [a["quantity"], b["quantity"]],
                "units": [a.get("unit"), b.get("unit")],
                "difference": abs(qa - qb) / factor_a, "difference_unit": a.get("unit"),
                "stages": [a.get("quantity_stage"), b.get("quantity_stage")],
                "recommended_action": "Supervisor verification required: check the production register, counting basis and reporting period.",
            })
    if same_observation(a, b, report_a, report_b):
        for key, category, title, severity, entities, action in RULES:
            if cross_department and not context_matches(a, b, ("batch", "order", "transfer_reference"), True):
                continue
            if not context_matches(a, b, entities, cross_department):
                continue
            left, right = status(a, key), status(b, key)
            incompatible = bool(left and right and left != right)
            if key == "quality_status":
                incompatible = {left, right} == {"passed", "rejected"}
            if key == "machine_status":
                incompatible = incompatible and "operational" in (left, right)
            if incompatible:
                findings.append({"category": category, "title": title, "severity": severity,
                                 "field": key, "values": [left, right], "recommended_action": action})
    return findings


def summary(findings):
    parts = []
    for finding in findings:
        values = " vs ".join(str(value) for value in finding["values"])
        difference = (f" Difference: {finding['difference']:g} {finding.get('difference_unit') or 'units'}."
                      if "difference" in finding else "")
        parts.append(f"{finding['title']} ({finding['severity']}): {values}.{difference} {finding['recommended_action']}")
    return " ".join(parts) + " Both claims remain unverified; confirm the observation time and context with both workers."


def possible_count_difference(a, b, report_a, report_b, relation=None):
    """Ask about a shared product/task; missing identifiers are never assumed equal.

    This is deliberately separate from compare(): it can only become a review
    request via a worker conversation, and never bridges departments.
    """
    if report_a.department_id != report_b.department_id or relation == "different":
        return []
    if a.get("quantity_basis") == "additional" or b.get("quantity_basis") == "additional":
        return []
    if a.get("quantity") is None or b.get("quantity") is None:
        return []
    # Explicitly different work/time is not a potential contradiction.
    for key in ("batch", "order", "transfer_reference", "machine", "work_area", "product",
                "task_reference", "reference_period", "observation_time"):
        if a.get(key) and b.get(key) and identifier(a[key], key) != identifier(b[key], key):
            return []
    if getattr(report_a, "task_id", None) and getattr(report_b, "task_id", None):
        if report_a.task_id != report_b.task_id:
            return []
    entities = ("batch", "order", "transfer_reference", "machine", "task_reference", "product")
    shared_task = bool(getattr(report_a, "task_id", None)
                       and report_a.task_id == getattr(report_b, "task_id", None))
    if not (shared_task or context_matches(a, b, entities)):
        return []
    ua, ub = normalized(a.get("unit")), normalized(b.get("unit"))
    dimension_a, factor_a = UNITS.get(ua, (ua, 1))
    dimension_b, factor_b = UNITS.get(ub, (ub, 1))
    if not dimension_a or dimension_a != dimension_b:
        return []
    qa, qb = a["quantity"] * factor_a, b["quantity"] * factor_b
    if math.isclose(qa, qb, rel_tol=0, abs_tol=1e-9):
        return []
    return [{
        "category": "quantity_context", "title": "Possible count difference", "severity": "high",
        "field": "quantity", "values": [a["quantity"], b["quantity"]],
        "units": [a.get("unit"), b.get("unit")],
        "difference": abs(qa - qb) / factor_a, "difference_unit": a.get("unit"),
        "stages": [a.get("quantity_stage"), b.get("quantity_stage")],
        "scope_relation": relation or "unchecked",
        "recommended_action": (
            "The worker confirmed the same work and reporting period. Verify both counts."
            if relation == "same" else
            "Confirm whether these counts describe the same work and reporting period before resolving the difference."
        ),
    }]
