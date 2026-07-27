import enum
from uuid import UUID, uuid4
from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class PlanType(str, enum.Enum):
    trial = "trial"
    standard = "standard"
    enterprise = "enterprise"

class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String)
    plan: Mapped[PlanType] = mapped_column(Enum(PlanType))
