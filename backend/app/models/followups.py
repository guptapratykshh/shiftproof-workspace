from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import Entity, Mutable, Tenant


class FollowUp(Entity, Mutable, Tenant, Base):
    __tablename__ = "follow_ups"
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    originating_department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    receiving_department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    accepted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))
    note: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="requested")
