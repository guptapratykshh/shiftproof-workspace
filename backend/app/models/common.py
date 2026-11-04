from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import UTCDateTime, new_id, now


class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)


class Tenant:
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Mutable:
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
