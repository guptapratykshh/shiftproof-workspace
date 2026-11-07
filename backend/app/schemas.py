from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

INDUSTRIES = {
    "manufacturing",
    "maintenance",
    "warehousing",
    "quality",
    "food",
    "construction",
    "healthcare",
    "facility",
}
Role = Literal["organization", "supervisor", "worker"]
Priority = Literal["normal", "important", "urgent", "critical"]
Category = Literal["general", "progress", "safety", "quality", "equipment", "maintenance", "materials"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def password_policy(value: str) -> str:
    if (
        len(value) < 12
        or len(value) > 128
        or not any(c.isalpha() for c in value)
        or not any(c.isdigit() for c in value)
    ):
        raise ValueError("Use 12–128 characters including a letter and a number")
    return value


class Registration(Input):
    fullName: str = Field(min_length=2, max_length=200)
    organizationName: str = Field(min_length=2, max_length=200)
    email: EmailStr
    organizationType: str
    phone: str = Field(default="", max_length=40)
    password: str

    _password = field_validator("password")(password_policy)

    @field_validator("organizationType")
    @classmethod
    def industry(cls, value):
        if value not in INDUSTRIES:
            raise ValueError("Choose a supported organization type")
        return value


class Login(Input):
    organizationId: str = Field(default="", max_length=64)
    email: str = Field(default="", max_length=254)
    employeeId: str = Field(default="", max_length=64)
    password: str = Field(default="", max_length=128)
    pin: str = Field(default="", max_length=6)


class TokenInput(Input):
    token: str = Field(min_length=20, max_length=200)


class ActivateInput(TokenInput):
    password: str | None = None
    pin: str | None = None
    confirm: str

    @model_validator(mode="after")
    def secret(self):
        value = self.pin if self.pin is not None else self.password
        if value != self.confirm:
            raise ValueError("Confirmation must match")
        if self.pin is not None:
            if len(self.pin) != 6 or not self.pin.isascii() or not self.pin.isdigit():
                raise ValueError("PIN must contain exactly six digits")
        elif self.password is not None:
            password_policy(self.password)
        else:
            raise ValueError("Choose a password or PIN")
        return self


class RecoverInput(Input):
    email: EmailStr
    role: Literal["organization", "supervisor"]
    organizationId: str = ""


class OrganizationInput(Input):
    name: str = Field(min_length=2, max_length=200)
    industry: str
    contact_email: EmailStr
    timezone: str = "Asia/Kolkata"
    contact: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=500)
    logo_asset_id: str | None = None

    @field_validator("industry")
    @classmethod
    def industry_value(cls, value):
        if value not in INDUSTRIES:
            raise ValueError("Choose a supported organization type")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_value(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Choose a valid IANA timezone")
        return value


class DepartmentInput(Input):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    active: bool = True


class TeamInput(DepartmentInput):
    department_id: str


class ShiftInput(Input):
    name: str = Field(min_length=2, max_length=120)
    starts_at: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    ends_at: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days: list[int] = Field(min_length=1, max_length=7)
    rotation: dict = Field(default_factory=dict)
    grace_minutes: int = Field(default=15, ge=0, le=120)
    active: bool = True

    @field_validator("days")
    @classmethod
    def valid_days(cls, value):
        if len(set(value)) != len(value) or any(day not in range(7) for day in value):
            raise ValueError("Working days must be unique values from 0 (Monday) to 6 (Sunday)")
        return value

    @model_validator(mode="after")
    def shift_length(self):
        if self.starts_at == self.ends_at:
            raise ValueError("Shift start and end must differ; overnight shifts are supported")
        return self


class MembershipInput(Input):
    department_id: str
    primary: bool = False
    backup: bool = False
    permissions: list[Literal["view", "manage", "review", "publish", "workforce", "evidence"]] = Field(
        default_factory=lambda: ["view"]
    )


class InviteInput(Input):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    role: Literal["organization", "supervisor"] = "supervisor"
    phone: str = Field(default="", max_length=40)
    departments: list[MembershipInput] = Field(default_factory=list)


class WorkerInput(Input):
    name: str = Field(min_length=2, max_length=200)
    employee_code: str | None = Field(default=None, max_length=64)
    phone: str = Field(default="", max_length=40)
    department_ids: list[str] = Field(min_length=1)
    primary_department_id: str
    team_ids: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    shift_id: str | None = None
    profile: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def primary_is_member(self):
        if self.primary_department_id not in self.department_ids:
            raise ValueError("Primary department must be a membership")
        if len(set(self.department_ids)) != len(self.department_ids):
            raise ValueError("Duplicate department memberships")
        return self


class TaskInput(Input):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10000)
    instructions: str = Field(default="", max_length=10000)
    department_id: str
    team_id: str | None = None
    shift_id: str | None = None
    assignment_type: Literal["individual", "team"] = "individual"
    worker_id: str | None = None
    lead_id: str | None = None
    priority: Priority | None = None
    critical: bool = False
    verification_required: bool = False
    category: str = Field(default="general", max_length=60)
    deadline: datetime | None = None
    required_skills: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    source_report_id: str | None = None

    @field_validator("deadline")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Deadline must include a timezone")
        return value

    @model_validator(mode="after")
    def assignment(self):
        if self.assignment_type == "individual" and not self.worker_id:
            raise ValueError("An individual task requires one responsible worker")
        if self.assignment_type == "team" and (not self.team_id or self.worker_id):
            raise ValueError("A team task requires a team instead of an individual assignee")
        if self.critical or self.priority == "critical":
            self.critical = True
            self.verification_required = True
        return self


class TaskAction(Input):
    action: Literal["accept", "start", "block", "resume", "complete", "verify", "reject", "close"]
    reason: str = Field(default="", max_length=5000)
    version: int = Field(ge=1)


class ReportFields(Input):
    category: Category = "general"
    description: str = Field(default="", max_length=10000)
    machine: str | None = Field(default=None, max_length=200)
    work_area: str | None = Field(default=None, max_length=200)
    batch: str | None = Field(default=None, max_length=200)
    order: str | None = Field(default=None, max_length=200)
    task_reference: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=200)
    reference_period: str | None = Field(default=None, max_length=200)
    observation_time: str | None = Field(default=None, max_length=200)
    quantity_basis: Literal["total", "additional"] | None = None
    quantity_stage: Literal["manufactured", "dispatched", "received"] | None = None
    transfer_reference: str | None = Field(default=None, max_length=200)
    transfer_complete: bool | None = None
    quantity: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    unit: str | None = Field(default=None, max_length=40)
    operational_status: str | None = Field(default=None, max_length=200)
    quality_status: Literal["passed", "rejected", "pending"] | None = None
    dispatch_status: Literal["dispatched", "pending"] | None = None
    machine_status: Literal["operational", "maintenance", "stopped", "failed"] | None = None
    task_status: Literal["completed", "pending"] | None = None
    action_taken: str | None = Field(default=None, max_length=2000)
    safety_implication: str | None = Field(default=None, max_length=2000)
    quality_implication: str | None = Field(default=None, max_length=2000)
    uncertainty: list[str] = Field(default_factory=list)
    suggested_task_id: str | None = None


class ReportInput(Input):
    client_request_id: str = Field(min_length=16, max_length=80)
    department_id: str
    team_id: str | None = None
    shift_id: str | None = None
    occurred_at: datetime
    text: str = Field(min_length=1, max_length=20000)
    fields: ReportFields
    task_id: str | None = None
    transcript_id: str | None = None
    extraction_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)
    immediate_safety: bool = False
    immediate_alert_id: str | None = None
    confirmed: Literal[True]
    conversation_id: str | None = None
    conversation_revision: int | None = Field(default=None, ge=0)

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Occurrence time must include a timezone")
        return value


class NoteInput(Input):
    note: str = Field(min_length=1, max_length=10000)


class StateInput(Input):
    active: bool
    reason: str = Field(min_length=1, max_length=2000)


class PreferenceInput(Input):
    theme: Literal["dark", "light", "system"] = "dark"
    language: Literal["en", "hi"] = "en"
    speech_language: Literal["hi-IN", "en-IN", "hi-IN,en-IN"] = "hi-IN,en-IN"
    notifications: dict[str, bool] = Field(default_factory=dict)
