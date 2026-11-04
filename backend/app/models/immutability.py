from sqlalchemy import event

from .operations import AlertHistory, HandoverItem, HandoverVersion, TaskHistory, TaskVerification
from .platform import AuditLog
from .reporting import ReportReview, ReportVersion

IMMUTABLE_MODELS = (
    ReportVersion,
    HandoverVersion,
    HandoverItem,
    TaskHistory,
    TaskVerification,
    AlertHistory,
    ReportReview,
    AuditLog,
)


def immutable(_mapper, _connection, _target):
    raise ValueError("Historical records are immutable. Append a new version or event instead.")


for model in IMMUTABLE_MODELS:
    event.listen(model, "before_update", immutable)
    event.listen(model, "before_delete", immutable)
