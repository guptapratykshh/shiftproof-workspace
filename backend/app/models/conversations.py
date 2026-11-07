from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import Entity, Mutable, Tenant


class DepartmentLink(Entity, Mutable, Tenant, Base):
    __tablename__ = "department_links"
    __table_args__ = (UniqueConstraint("organization_id", "source_department_id", "receiving_department_id"),)
    source_department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    receiving_department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    active: Mapped[bool] = mapped_column(default=True)


class ReportConversation(Entity, Mutable, Tenant, Base):
    __tablename__ = "report_conversations"
    __table_args__ = (UniqueConstraint("author_id", "client_request_id"),)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    client_request_id: Mapped[str] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(30), default="hi-IN,en-IN")
    clarification_id: Mapped[str | None] = mapped_column(ForeignKey("clarifications.id"))
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), index=True)
    revision: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class ConversationTurn(Entity, Tenant, Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (UniqueConstraint("conversation_id", "revision", "role"),)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("report_conversations.id"), index=True)
    revision: Mapped[int]
    role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("file_assets.id"))
    transcript_id: Mapped[str | None] = mapped_column(ForeignKey("transcripts.id"))
    extraction_id: Mapped[str | None] = mapped_column(ForeignKey("ai_extractions.id"))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
