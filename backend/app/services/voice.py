"""Deterministic speech scripts and context, with no generated decisions."""

import math

from ..schemas import ReportFields
from ..security import fail, require_department


def transcription_context(db, user, department_id, task_id=None):
    department = require_department(db, user, department_id, active=True)
    terms = [department.name]
    if task_id:
        from .tasks import visible_task

        task = visible_task(db, user, task_id)
        if task.department_id != department_id:
            fail(422, "The selected task must belong to the recording department.")
        terms.extend([task.title, *task.required_skills])
    return {
        "keyterms": list(dict.fromkeys(term for term in terms if term and len(term) <= 200))[:30],
        "topic": f"Operational shift update in {department.name}. Preserve quantities and unfinished conditions.",
    }


def plain_speech(text):
    # Worker input must not activate expressive audio tags in the provider.
    return text.replace("<", " less than ").replace(">", " greater than ")


def report_script(text: str, fields: ReportFields, language: str, immediate_safety: bool = False):
    hindi = language != "en-IN"
    parts = ["आपका अपडेट।" if hindi else "Your update.", text.strip()]
    if immediate_safety:
        parts.append("तत्काल सुरक्षा का विषय।" if hindi else "Immediate safety concern.")
    labels = {
        "description": ("Report details", "रिपोर्ट का विवरण"),
        "machine": ("Equipment", "मशीन"),
        "work_area": ("Work area", "कार्य क्षेत्र"),
        "batch": ("Batch or order", "बैच या ऑर्डर"),
        "quantity": ("Quantity", "मात्रा"),
        "unit": ("Unit", "इकाई"),
        "operational_status": ("Status", "स्थिति"),
        "action_taken": ("Action already taken", "की गई कार्रवाई"),
        "safety_implication": ("Safety concern", "सुरक्षा का विषय"),
        "quality_implication": ("Quality concern", "गुणवत्ता का विषय"),
        "order": ("Order", "ऑर्डर"), "task_reference": ("Task", "कार्य"),
        "product": ("Product", "उत्पाद"), "reference_period": ("Reporting period", "रिपोर्ट की अवधि"),
        "observation_time": ("Observation time", "देखने का समय"),
        "quantity_basis": ("Counting basis", "गिनती का आधार"),
        "quality_status": ("Quality status", "गुणवत्ता की स्थिति"),
        "dispatch_status": ("Dispatch status", "डिस्पैच की स्थिति"),
        "machine_status": ("Machine status", "मशीन की स्थिति"),
        "task_status": ("Task status", "कार्य की स्थिति"),
    }
    for key, value in fields.model_dump().items():
        if key in {"category", "uncertainty", "suggested_task_id"}:
            continue
        label = labels.get(key, (key.replace("_", " "), key.replace("_", " ")))
        if value is None or value == "" or (key == "description" and value.strip() == text.strip()):
            continue
        if key == "quantity":
            if not math.isfinite(value):
                fail(422, "Use a finite quantity.")
            value = str(int(value)) if value.is_integer() else str(value)
        parts.append(f"{label[1 if hindi else 0]}: {value}.")
    for question in fields.uncertainty:
        parts.append(("कृपया जाँचें: " if hindi else "Please check: ") + question)
    parts.append(
        "सही होने पर ही पुष्टि करके भेजें।" if hindi else "Check this is correct before confirming and sending."
    )
    return checked_script("\n".join(parts))


def checked_script(text):
    text = plain_speech(text)
    if len(text) > 5000:
        fail(422, "This update is too long for spoken playback. Review it in writing; no text was omitted.")
    return text


def handover_script(version, language):
    hindi = language != "en-IN"
    label = (
        ("पर्यवेक्षक की समीक्षा बाकी है।" if version.provisional else "प्रकाशित हैंडओवर।")
        if hindi
        else ("Pending supervisor review." if version.provisional else "Published handover.")
    )
    parts = [label, f"{'संस्करण' if hindi else 'Version'} {version.number}.", version.snapshot.get("notes", "")]
    for item in version.snapshot.get("items", []):
        detail = item.get("detail", {})
        parts.append(("ज़रूरी। " if hindi else "Critical. ") if item.get("critical") else "")
        parts.append(item["title"])
        # Speak operational facts from this frozen version, never live task state.
        if detail.get("unresolved"):
            parts.append("यह विषय अभी अनसुलझा है।" if hindi else "This issue is still unresolved.")
        if detail.get("transfer_pending"):
            parts.append(
                "अगली शिफ्ट को यह काम जारी रखना है।" if hindi else "Work remains for the incoming shift."
            )
        if detail.get("needs_attention"):
            parts.append("ध्यान देना ज़रूरी है।" if hindi else "Needs attention.")
        for key in (
            "status",
            "description",
            "blocked_reason",
            "quantity",
            "unit",
            "machine",
            "work_area",
            "batch",
            "deadline",
        ):
            if detail.get(key) is not None and detail.get(key) != "":
                parts.append(f"{key.replace('_', ' ')}: {detail[key]}.")
    return checked_script("\n".join(parts))
