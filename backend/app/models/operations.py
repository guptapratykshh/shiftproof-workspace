from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, UTCDateTime
from .common import Entity, Mutable, Tenant


class TaskTemplate(Entity, Mutable, Tenant, Base):
    __tablename__ = "task_templates"
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    definition: Mapped[dict] = mapped_column(JSON)
    recurrence_minutes: Mapped[int | None]
    next_run: Mapped[datetime | None] = mapped_column(UTCDateTime)
    active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Task(Entity, Mutable, Tenant, Base):
    __tablename__ = "tasks"
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    shift_id: Mapped[str | None] = mapped_column(ForeignKey("shifts.id"), index=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("task_templates.id"))
    source_report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="general")
    assignment_type: Mapped[str] = mapped_column(String(20), default="individual")
    priority: Mapped[str | None] = mapped_column(String(20), index=True)
    critical: Mapped[bool] = mapped_column(default=False)
    verification_required: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(30), default="assigned", index=True)
    deadline: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    blocked_reason: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    __mapper_args__ = {"version_id_col": version}


class TaskAssignment(Entity, Tenant, Base):
    __tablename__ = "task_assignments"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    assigned_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text, default="Initial assignment")
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class TaskDependency(Entity, Tenant, Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_id"),)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))


class TaskEvidence(Entity, Tenant, Base):
    __tablename__ = "task_evidence"
    __table_args__ = (UniqueConstraint("task_id", "asset_id"),)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id"), index=True)
    linked_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class TaskHistory(Entity, Tenant, Base):
    __tablename__ = "task_history"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class TaskComment(Entity, Tenant, Base):
    __tablename__ = "task_comments"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(default=False)


class TaskVerification(Entity, Tenant, Base):
    __tablename__ = "task_verifications"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved: Mapped[bool]
    reason: Mapped[str] = mapped_column(Text)


class Alert(Entity, Mutable, Tenant, Base):
    __tablename__ = "alerts"
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20), default="critical")
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    immediate: Mapped[bool] = mapped_column(default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolution: Mapped[str] = mapped_column(Text, default="")
    escalation_level: Mapped[int] = mapped_column(default=0)
    next_escalation: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class AlertHistory(Entity, Tenant, Base):
    __tablename__ = "alert_history"
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class EscalationRule(Entity, Mutable, Tenant, Base):
    __tablename__ = "escalation_rules"
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), unique=True)
    acknowledge_minutes: Mapped[int] = mapped_column(default=10)
    backup_minutes: Mapped[int] = mapped_column(default=10)
    escalation_recipient_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    channels: Mapped[list] = mapped_column(JSON, default=lambda: ["in_app"])
    active: Mapped[bool] = mapped_column(default=True)


class ResponsibilityMapping(Entity, Mutable, Tenant, Base):
    __tablename__ = "responsibility_mappings"
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    machine: Mapped[str] = mapped_column(String(160), default="")
    area: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(60), default="")
    shift_id: Mapped[str | None] = mapped_column(ForeignKey("shifts.id"))
    supervisor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    backup_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Handover(Entity, Mutable, Tenant, Base):
    __tablename__ = "handovers"
    __table_args__ = (UniqueConstraint("department_id", "shift_id", "shift_date"),)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"))
    incoming_shift_id: Mapped[str | None] = mapped_column(ForeignKey("shifts.id"))
    shift_date: Mapped[str] = mapped_column(String(10))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    latest_version: Mapped[int] = mapped_column(default=0)
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class HandoverVersion(Entity, Tenant, Base):
    __tablename__ = "handover_versions"
    __table_args__ = (UniqueConstraint("handover_id", "number"),)
    handover_id: Mapped[str] = mapped_column(ForeignKey("handovers.id"), index=True)
    number: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)
    provisional: Mapped[bool] = mapped_column(default=False)
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    changes: Mapped[str] = mapped_column(Text, default="Initial publication")


class HandoverItem(Entity, Tenant, Base):
    __tablename__ = "handover_items"
    version_id: Mapped[str] = mapped_column(ForeignKey("handover_versions.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200))
    critical: Mapped[bool] = mapped_column(default=False)
    detail: Mapped[dict] = mapped_column(JSON)


class HandoverRecipient(Entity, Tenant, Base):
    __tablename__ = "handover_recipients"
    __table_args__ = (UniqueConstraint("version_id", "user_id"),)
    version_id: Mapped[str] = mapped_column(ForeignKey("handover_versions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    required: Mapped[bool] = mapped_column(default=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class HandoverItemAcknowledgement(Entity, Tenant, Base):
    __tablename__ = "handover_item_acknowledgements"
    __table_args__ = (UniqueConstraint("item_id", "user_id"),)
    item_id: Mapped[str] = mapped_column(ForeignKey("handover_items.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
