from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, UTCDateTime
from .common import Entity, Mutable, Tenant


class Organization(Entity, Mutable, Base):
    __tablename__ = "organizations"
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(40))
    contact: Mapped[str] = mapped_column(String(40), default="")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Kolkata")
    active: Mapped[bool] = mapped_column(default=False)
    onboarding_step: Mapped[int] = mapped_column(default=1)
    onboarding_skipped: Mapped[list] = mapped_column(JSON, default=list)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Entity, Mutable, Tenant, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "email"),
        UniqueConstraint("organization_id", "employee_code"),
    )
    role: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254), index=True)
    employee_code: Mapped[str | None] = mapped_column(String(64), index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    password_hash: Mapped[str | None] = mapped_column(Text)
    pin_hash: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=False)
    verified: Mapped[bool] = mapped_column(default=False)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    offline_key: Mapped[str | None] = mapped_column(String(64))


class Department(Entity, Mutable, Tenant, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)


class Team(Entity, Mutable, Tenant, Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("department_id", "name"),)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)


class DepartmentMembership(Entity, Tenant, Base):
    __tablename__ = "department_memberships"
    __table_args__ = (UniqueConstraint("user_id", "department_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    primary: Mapped[bool] = mapped_column(default=False)
    backup: Mapped[bool] = mapped_column(default=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True)


class TeamMembership(Entity, Tenant, Base):
    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("user_id", "team_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    active: Mapped[bool] = mapped_column(default=True)


class Shift(Entity, Mutable, Tenant, Base):
    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    name: Mapped[str] = mapped_column(String(120))
    starts_at: Mapped[str] = mapped_column(String(5))
    ends_at: Mapped[str] = mapped_column(String(5))
    days: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4, 5])
    rotation: Mapped[dict] = mapped_column(JSON, default=dict)
    grace_minutes: Mapped[int] = mapped_column(default=15)
    active: Mapped[bool] = mapped_column(default=True)


class ShiftAssignment(Entity, Tenant, Base):
    __tablename__ = "shift_assignments"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"), index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    starts_on: Mapped[str] = mapped_column(String(10))
    ends_on: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(default=True)


class WorkerAvailability(Entity, Tenant, Base):
    __tablename__ = "worker_availability"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text, default="")
    recorded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Skill(Entity, Tenant, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    name: Mapped[str] = mapped_column(String(160))


class WorkerSkill(Entity, Tenant, Base):
    __tablename__ = "worker_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    qualification: Mapped[str] = mapped_column(String(200), default="")
    expires_on: Mapped[str | None] = mapped_column(String(10))


class Invitation(Entity, Tenant, Base):
    __tablename__ = "invitations"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PendingRegistration(Entity, Base):
    __tablename__ = "pending_registrations"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    organization_name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(40))
    phone: Mapped[str] = mapped_column(String(40), default="")
    password_hash: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class DeviceSession(Entity, Tenant, Base):
    __tablename__ = "device_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime)
    device: Mapped[str] = mapped_column(String(200), default="")
    revoked: Mapped[bool] = mapped_column(default=False)


class AuthThrottle(Base):
    __tablename__ = "auth_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    reset_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Takeover(Entity, Tenant, Base):
    __tablename__ = "takeovers"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class OrganizationPolicy(Entity, Mutable, Tenant, Base):
    __tablename__ = "organization_policies"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class ImportBatch(Entity, Tenant, Base):
    __tablename__ = "import_batches"
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    rows: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="preview")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
