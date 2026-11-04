"""Apply retention at read time as well as in scheduled deletion jobs."""

from datetime import timedelta

from ..db import now
from ..security import policy_value
from .common import record_dict


def expired(db, item):
    days = policy_value(db, item.organization_id, "privacy").get("transcript_retention_days", 365)
    return item.created_at + timedelta(days=days) <= now()


def retained_record(db, item):
    if item is None:
        return None
    result = record_dict(item)
    if expired(db, item):
        for field in ("original", "input_text"):
            if field in result:
                result[field] = "[Original source removed under retention policy]"
    return result


def retained_job(db, job):
    result = record_dict(job, {"payload", "lease_token"})
    if job.kind in {"transcribe", "extract", "speak"} and expired(db, job):
        result["result"] = {"retention_expired": True}
    return result
