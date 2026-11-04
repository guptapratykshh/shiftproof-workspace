from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, UTCDateTime
from .common import Entity, Mutable, Tenant


class FileAsset(Entity, Tenant, Base):
    __tablename__ = "file_assets"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))
    byte_size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    consent: Mapped[bool] = mapped_column(default=False)
    retention_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Report(Entity, Mutable, Tenant, Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("organization_id", "author_id", "client_request_id"),)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    shift_id: Mapped[str | None] = mapped_column(ForeignKey("shifts.id"), index=True)
    client_request_id: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    category: Mapped[str] = mapped_column(String(40), default="general", index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    immediate_safety: Mapped[bool] = mapped_column(default=False)
    needs_attention: Mapped[bool] = mapped_column(default=False)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    latest_version: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class Transcript(Entity, Tenant, Base):
    __tablename__ = "transcripts"
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("file_assets.id"))
    original: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(40), default="hi-IN,en-IN")
    provider: Mapped[str] = mapped_column(String(30), default="worker")
    model: Mapped[str] = mapped_column(String(80), default="manual")
    metadata_values: Mapped[dict] = mapped_column(JSON, default=dict)


class AIExtraction(Entity, Tenant, Base):
    __tablename__ = "ai_extractions"
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"))
    input_text: Mapped[str] = mapped_column(Text)
    output: Mapped[dict] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(30), default="gemini")
    model: Mapped[str] = mapped_column(String(80))


class ReportVersion(Entity, Tenant, Base):
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("report_id", "number"),)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    number: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    fields: Mapped[dict] = mapped_column(JSON)
    transcript_id: Mapped[str | None] = mapped_column(ForeignKey("transcripts.id"))
    extraction_id: Mapped[str | None] = mapped_column(ForeignKey("ai_extractions.id"))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    correction_reason: Mapped[str] = mapped_column(Text, default="")
    confirmed: Mapped[bool] = mapped_column(default=True)


class ReportTaskLink(Entity, Tenant, Base):
    __tablename__ = "report_task_links"
    __table_args__ = (UniqueConstraint("report_id", "task_id"),)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    linked_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    follow_up: Mapped[bool] = mapped_column(default=False)


class ReportEvidence(Entity, Tenant, Base):
    __tablename__ = "report_evidence"
    __table_args__ = (UniqueConstraint("version_id", "asset_id"),)
    version_id: Mapped[str] = mapped_column(ForeignKey("report_versions.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id"))


class ReportReview(Entity, Tenant, Base):
    __tablename__ = "report_reviews"
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text)
    version_number: Mapped[int]


class Clarification(Entity, Mutable, Tenant, Base):
    __tablename__ = "clarifications"
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    conflict_id: Mapped[str | None] = mapped_column(ForeignKey("conflicts.id"))
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)
    response_type: Mapped[str | None] = mapped_column(String(30))
    responded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Conflict(Entity, Mutable, Tenant, Base):
    __tablename__ = "conflicts"
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    discrepancy: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolution: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class ConflictReport(Entity, Tenant, Base):
    __tablename__ = "conflict_reports"
    __table_args__ = (UniqueConstraint("conflict_id", "report_id"),)
    conflict_id: Mapped[str] = mapped_column(ForeignKey("conflicts.id"), index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    version_number: Mapped[int]
