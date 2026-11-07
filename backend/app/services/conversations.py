"""Versioned, grounded clarification. No provider can submit or resolve work."""

import json
from copy import deepcopy
from types import SimpleNamespace

from sqlalchemy import select

from ..config import get_settings
from ..db import now
from ..models import (
    AIExtraction,
    Clarification,
    ConversationTurn,
    Department,
    FileAsset,
    ReportConversation,
    Transcript,
)
from ..schemas import ReportFields
from ..security import digest, fail, require_department, scoped
from .common import enqueue, record_dict
from .comparisons import candidates
from .retention import expired
from .voice import plain_speech


def accessible(db, user, identity):
    conversation = scoped(db, ReportConversation, identity, user)
    if conversation.author_id != user.id:
        fail(403, "This conversation belongs to another worker.")
    db.refresh(user)
    if not user.active:
        fail(403, "This account is no longer active.")
    require_department(db, user, conversation.department_id, active=True)
    if expired(db, conversation):
        fail(410, "This conversation is no longer retained. Start a new update.")
    if conversation.clarification_id:
        clarification = scoped(db, Clarification, conversation.clarification_id, user)
        if clarification.recipient_id != user.id:
            fail(403, "Only the requested worker may answer.")
    return conversation


def fingerprint(draft):
    # Consent/attachments and the submission key have their own existing checks.
    keys = (
        "department_id",
        "team_id",
        "shift_id",
        "task_id",
        "occurred_at",
        "text",
        "fields",
        "immediate_safety",
    )
    return digest(json.dumps({k: draft.get(k) for k in keys}, sort_keys=True, default=str))


def comparison(db, conversation, draft, state=None):
    from datetime import datetime

    report = SimpleNamespace(
        id=None,
        organization_id=conversation.organization_id,
        department_id=conversation.department_id,
        author_id=conversation.author_id,
        shift_id=draft.get("shift_id"),
        task_id=draft.get("task_id"),
        occurred_at=datetime.fromisoformat(draft["occurred_at"]),
    )
    result = []
    for match in candidates(db, report, draft["fields"], include_context=True,
                            context_decisions=(state or conversation.state).get("context_decisions", {})):
        source, version = match["report"], match["version"]
        if source.id == conversation.report_id:
            continue
        for finding in match["findings"]:
            key = digest(json.dumps([source.id, version.number, finding, draft["fields"]], sort_keys=True))
            result.append(
                {
                    "key": key,
                    "report_id": source.id,
                    "version_number": version.number,
                    "same_worker": source.author_id == conversation.author_id,
                    "source_department": db.get(Department, source.department_id).name,
                    "source_department_id": source.department_id,
                    "owner_department_id": match["owner_department_id"],
                    "finding": finding,
                }
            )
    return result


def question_for(conversation, state):
    hi = conversation.language != "en-IN"
    pending = [f for f in state["findings"] if f["key"] not in state.get("answered_keys", [])]
    if pending:
        pending.sort(key=lambda item: item["finding"]["severity"] != "critical")
        entry = pending[0]
        finding = entry["finding"]
        current, previous = finding["values"]
        fields = state["draft"]["fields"]
        entity = (
            fields.get("transfer_reference")
            or fields.get("batch")
            or fields.get("order")
            or fields.get("machine")
            or fields.get("task_reference")
            or fields.get("product")
            or "this work"
        )
        units = finding.get("units", ["", ""])
        unit, previous_unit = (units[0] or ""), (units[1] or "")

        def number(value):
            return f"{value:g}" if isinstance(value, (float, int)) else str(value)

        current, previous = number(current), number(previous)
        if entry["same_worker"]:
            text = (
                f"आपने पहले {entity} के लिए {previous} {previous_unit} बताया था। अब {current} {unit} बताया है। क्या यह सुधारी हुई गिनती है या अलग समय का अपडेट?"
                if hi
                else f"Earlier you reported {previous} {previous_unit} for {entity}. Now you said {current} {unit}. Is this a corrected count or a different update?"
            )
        else:
            difference = finding.get("difference")
            gap = (
                (
                    f" अंतर {number(difference)} {unit} है।"
                    if hi
                    else f" The difference is {number(difference)} {unit}."
                )
                if difference is not None
                else ""
            )
            text = (
                f"{entry['source_department']} में {entity} के लिए {previous} {previous_unit} दर्ज है। आपने {current} {unit} बताया।{gap} क्या यह वही बैच और पूरी डिलीवरी है? अपनी गिनती या संदर्भ की पुष्टि करें।"
                if hi
                else f"{entry['source_department']} reported {previous} {previous_unit} for {entity}. You reported {current} {unit}.{gap} Is this the same batch and complete delivery? Please confirm your count or explain the context."
            )
        if finding["category"] == "quantity_context":
            source = "आपने पहले" if entry["same_worker"] else entry["source_department"] + " की एक भेजी गई रिपोर्ट में"
            text = (
                f"{source} {entity} के लिए {previous} {previous_unit} बताया है। आपने अब {current} {unit} बताया। क्या दोनों गिनतियाँ उसी काम और उसी समय की कुल गिनती हैं, या अलग अपडेट हैं?"
                if hi else
                f"{'Your earlier report' if entry['same_worker'] else 'A submitted report in ' + entry['source_department']} says {previous} {previous_unit} for {entity}. You said {current} {unit}. Do both counts describe the same work and reporting period, or are they different updates?"
            )
        elif finding["category"] not in {"quantity_mismatch", "transfer_gap"}:
            text = (
                f"{entity}: पहले '{previous}', अब '{current}' दर्ज है। क्या दोनों उसी समय की स्थिति हैं? अपनी बात की पुष्टि या सुधार करें।"
                if hi
                else f"For {entity}, the earlier status was '{previous}' and your update says '{current}'. Are these observations from the same time? Please confirm or correct your observation."
            )
        return plain_speech(text), [entry["key"]]
    fields = state["draft"]["fields"]
    # Once a worker has answered a possible match, retain the scope decision;
    # do not immediately repeat the same missing-reference question.
    if state.get("context_decisions"):
        return "", []
    if fields.get("quantity") is not None and not any(
        fields.get(k) for k in ("batch", "machine", "order", "task_reference", "transfer_reference")
    ):
        return (
            "यह गिनती किस बैच, ऑर्डर या मशीन की है? पहचान और समय बताएँ, या कहें कि पता नहीं।"
            if hi
            else "Which batch, order or machine does this count describe? Tell me the reference and period, or say you are unsure."
        ), []
    if fields.get("quantity") is not None and not fields.get("unit"):
        return (
            "यह गिनती पीस, बॉक्स या किसी और इकाई में है?"
            if hi
            else "Is that count in pieces, boxes or another unit?"
        ), []
    return "", []


def speech_job(db, conversation, text):
    if not text or not get_settings().gnani_api_key:
        return None
    job = enqueue(
        db,
        "speak",
        f"dialogue-speech:{conversation.id}:{conversation.revision}",
        {
            "text": plain_speech(text),
            "department_id": conversation.department_id,
            "language": "en-IN" if conversation.language == "en-IN" else "auto",
            "source": f"conversation:{conversation.id}:{conversation.revision}",
        },
        conversation.organization_id,
        conversation.author_id,
    )
    return job.id


def finish_analysis(db, conversation, state):
    state["findings"] = comparison(db, conversation, state["draft"], state)
    for finding in state["findings"]:
        claim = (
            finding["report_id"] + ":" + str(finding["version_number"]) + ":" + finding["finding"]["category"]
        )
        if state.get("answered_claims", {}).get(claim) == finding["finding"]["values"]:
            state["answered_keys"] = list(set(state.get("answered_keys", []) + [finding["key"]]))
    question, keys = question_for(conversation, state)
    missing_context = bool(question and not keys)
    stopped_early = bool(state.get("explicit_uncertainty") or (question and state.get("question_count", 0) >= 3))
    if stopped_early:
        question, keys = "", []
    state["comparison_incomplete"] = missing_context or any(
        f["finding"].get("scope_relation") in {"unchecked", "unsure"} for f in state["findings"]
    )
    # Declining a possible match does not establish a scope for future reports.
    if not state["findings"] and state.get("context_decisions"):
        state["comparison_incomplete"] = True
    state["unresolved"] = bool(stopped_early or state["comparison_incomplete"]
                               or state["findings"])
    state["question"], state["question_keys"] = question, keys
    state["checked_fingerprint"] = fingerprint(state["draft"])
    state["check_error"] = ""
    if question:
        state["question_count"] = state.get("question_count", 0) + 1
    conversation.status = "awaiting_answer" if question else "ready"
    state["speech_job_id"] = speech_job(db, conversation, question)
    conversation.state = state
    db.add(
        ConversationTurn(
            organization_id=conversation.organization_id,
            conversation_id=conversation.id,
            revision=conversation.revision,
            role="assistant",
            text=question
            or (
                "आपका अपडेट तैयार है। जाँचें और पुष्टि करके भेजें।"
                if conversation.language != "en-IN"
                else "Your update is ready. Review it and tap Confirm and send."
            ),
            details={"kind": "question" if question else "summary", "findings": state["findings"]},
        )
    )


def public_state(db, conversation):
    db.flush()
    state = deepcopy(conversation.state)
    # References are kept server-side. Workers receive only the comparison facts.
    state["findings"] = [
        {
            "key": f["key"],
            "same_worker": f["same_worker"],
            "source_department": f["source_department"],
            "finding": f["finding"],
        }
        for f in state.get("findings", [])
    ]
    state.pop("answered_keys", None)
    state.pop("answered_claims", None)
    state.pop("answers", None)
    state.pop("context_decisions", None)
    result = record_dict(conversation, {"state", "client_request_id"})
    result["state"] = state
    result["turns"] = [
        record_dict(turn, {"details"})
        for turn in db.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.conversation_id == conversation.id)
            .order_by(ConversationTurn.created_at, ConversationTurn.role.desc())
        )
    ]
    return result


def check_recording(db, user, asset_id, department_id):
    asset = scoped(db, FileAsset, asset_id, user)
    if (
        asset.owner_id != user.id
        or asset.department_id != department_id
        or asset.kind != "audio"
        or not asset.consent
        or asset.deleted_at
        or (asset.retention_until and asset.retention_until <= now())
    ):
        fail(403, "Use your own retained recording with consent in this department.")
    return asset


def process_transcription(db, job, user):
    from ..integrations.gnani.client import transcribe
    from .storage import read_bytes, wav_for_transcription
    from .voice import transcription_context

    c = accessible(db, user, job.payload["conversation_id"])
    if c.revision != job.payload["revision"]:
        return {"superseded": True}
    asset = check_recording(db, user, job.payload["asset_id"], c.department_id)
    context = transcription_context(db, user, c.department_id, job.payload["draft"].get("task_id"))
    audio = wav_for_transcription(read_bytes(asset))
    if db.bind.dialect.name == "mongodb":
        db.commit()
    data = transcribe(audio, c.language, job.id, **context)
    db.refresh(c)
    accessible(db, user, c.id)
    if c.revision != job.payload["revision"]:
        return {"superseded": True}
    if not data["text"].strip():
        c.status = "unavailable"
        c.state = {**c.state, "check_error": "No clear speech was found. Reply again or type your answer."}
        return {"no_speech": True}
    transcript = Transcript(
        organization_id=user.organization_id,
        author_id=user.id,
        asset_id=asset.id,
        original=data["text"],
        language=data["language"],
        provider="gnani",
        model=data["model"],
        metadata_values=data["metadata"],
    )
    db.add(transcript)
    db.flush()
    following = enqueue(
        db,
        "conversation_analyze",
        f"dialogue-analysis:{c.id}:{c.revision}",
        {**job.payload, "text": data["text"], "transcript_id": transcript.id},
        user.organization_id,
        user.id,
    )
    c.state = {**c.state, "job_id": following.id}
    return {"conversation_id": c.id, "transcript_id": transcript.id, "text": data["text"]}


def process_analysis(db, job, user):
    from ..integrations.gemini.client import extract
    from ..integrations.gemini.dialogue import interpret_reply

    c = accessible(db, user, job.payload["conversation_id"])
    if c.revision != job.payload["revision"]:
        return {"superseded": True}
    if db.scalar(
        select(ConversationTurn.id).where(
            ConversationTurn.conversation_id == c.id,
            ConversationTurn.revision == c.revision,
            ConversationTurn.role == "assistant",
        )
    ):
        return {"conversation_id": c.id}
    state = deepcopy(c.state)
    text = job.payload["text"]
    kind = job.payload["kind"]
    draft = deepcopy(job.payload["draft"])
    transcript_id = job.payload.get("transcript_id")
    if not transcript_id:
        transcript = Transcript(
            organization_id=user.organization_id, author_id=user.id, original=text, language=c.language
        )
        db.add(transcript)
        db.flush()
        transcript_id = transcript.id
    turn = db.scalar(
        select(ConversationTurn).where(
            ConversationTurn.conversation_id == c.id,
            ConversationTurn.revision == c.revision,
            ConversationTurn.role == "worker",
        )
    )
    if not turn:
        turn = ConversationTurn(
            organization_id=user.organization_id,
            conversation_id=c.id,
            revision=c.revision,
            role="worker",
            text=text,
            asset_id=job.payload.get("asset_id"),
            transcript_id=transcript_id,
            details={"kind": kind, "client_turn_id": job.payload["client_turn_id"]},
        )
        db.add(turn)
        db.flush()
    if db.bind.dialect.name == "mongodb":
        db.commit()
    if kind in {"reply", "uncertain"}:
        answer = (
            {"response_type": "uncertain", "fields": {}, "explicit_uncertainty": True}
            if kind == "uncertain"
            else interpret_reply(text, state.get("question", ""), draft["fields"])
        )
        draft["fields"] = ReportFields.model_validate({**draft["fields"], **answer["fields"]}).model_dump()
        draft["text"] = draft.get("text", "") + "\nClarification: " + text
        if len(draft["text"]) > 20000:
            raise ValueError(
                "This conversation is too long for one report. Keep the saved answers and shorten the report text."
            )
        state["answer"], state["answer_type"] = text, answer["response_type"]
        state["explicit_uncertainty"] = answer.get("explicit_uncertainty", False)
        for finding in state.get("findings", []):
            if (finding["key"] in state.get("question_keys", [])
                    and finding["finding"]["category"] == "quantity_context"):
                relation = answer.get("scope_relation")
                # A plain yes answers this specific same-work question. Model
                # confirmation of a count alone must not establish its scope.
                if relation is None and answer["response_type"] == "confirm" and not answer["fields"]:
                    from ..integrations.gemini.dialogue import is_simple_confirmation
                    relation = "same" if is_simple_confirmation(text) else "unsure"
                state.setdefault("context_decisions", {})[
                    f"{finding['report_id']}:{finding['version_number']}"
                ] = relation or "unsure"
        state["answers"] = [
            *state.get("answers", []),
            {
                "text": text,
                "response_type": answer["response_type"],
                "revision": c.revision,
                "sources": [
                    {"report_id": f["report_id"], "version_number": f["version_number"]}
                    for f in state.get("findings", [])
                    if f["key"] in state.get("question_keys", [])
                ],
            },
        ]
        # The answer acknowledges this question, not every possible discrepancy.
        state["answered_keys"] = list(set(state.get("answered_keys", []) + state.get("question_keys", [])))
        state["answered_claims"] = {
            **state.get("answered_claims", {}),
            **{
                f["report_id"] + ":" + str(f["version_number"]) + ":" + f["finding"]["category"]: f[
                    "finding"
                ]["values"]
                for f in state.get("findings", [])
                if f["key"] in state.get("question_keys", [])
            },
        }
    else:
        draft["text"] = text
        draft["fields"] = (
            ReportFields.model_validate(draft["fields"]).model_dump() if kind == "edit" else extract(text)
        )
        state.update(
            answer="",
            answer_type="",
            answers=[],
            answered_keys=[],
            answered_claims={},
            question_count=0,
            unresolved=False,
            explicit_uncertainty=False,
            context_decisions={},
        )
    db.refresh(c)
    accessible(db, user, c.id)
    if c.revision != job.payload["revision"]:
        return {"superseded": True}
    draft["transcript_id"] = transcript_id
    if job.payload.get("asset_id"):
        draft["evidence_ids"] = list(dict.fromkeys([*draft.get("evidence_ids", []), job.payload["asset_id"]]))
    extraction = AIExtraction(
        organization_id=user.organization_id,
        author_id=user.id,
        transcript_id=transcript_id,
        input_text=draft["text"],
        output=draft["fields"],
        provider="worker" if kind in {"edit", "uncertain"} else "gemini",
        model="manual" if kind in {"edit", "uncertain"} else get_settings().gemini_model,
    )
    db.add(extraction)
    db.flush()
    turn.extraction_id = extraction.id
    draft["extraction_id"] = extraction.id
    if not draft["fields"].get("description"):
        draft["fields"]["description"] = draft["text"]
    state["draft"] = draft
    finish_analysis(db, c, state)
    return {"conversation_id": c.id, "revision": c.revision}


def mark_failed(db, job, message):
    c = db.get(ReportConversation, job.payload.get("conversation_id"))
    if c and c.revision == job.payload.get("revision") and c.status != "submitted":
        c.status = "unavailable"
        c.state = {**c.state, "check_error": message}


def verify_submission(db, user, values):
    if not values.conversation_id:
        return None
    c = accessible(db, user, values.conversation_id)
    if c.clarification_id or c.department_id != values.department_id:
        fail(422, "Use this report's own conversation.")
    if c.revision != values.conversation_revision or c.status != "ready":
        fail(409, "Review the latest conversation before sending.")
    if c.state.get("checked_fingerprint") != fingerprint(values.model_dump(mode="json")):
        fail(409, "This draft changed. Check the updated report before sending.")
    latest = comparison(db, c, c.state["draft"])
    if {f["key"] for f in latest} != {f["key"] for f in c.state.get("findings", [])}:
        fail(409, "Related reports changed. Check the update again before sending.")
    return c


def recorded_answer(db, report_id, counterpart_id, version):
    for c in db.scalars(
        select(ReportConversation).where(
            ReportConversation.report_id == report_id, ReportConversation.status == "submitted"
        )
    ):
        for answer in reversed(c.state.get("answers", [])):
            if {"report_id": counterpart_id, "version_number": version} in answer["sources"]:
                return answer
    return None
