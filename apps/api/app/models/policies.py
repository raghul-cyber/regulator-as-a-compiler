import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class PolicyStatus(str, enum.Enum):
    draft = "draft"
    deployed = "deployed"

class ComplianceResult(str, enum.Enum):
    pass_ = "pass"  # "pass" is a reserved keyword in Python
    fail = "fail"
    partial = "partial"

class Policy(Base, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)
    regulation_version_id: Mapped[UUID] = mapped_column(ForeignKey("regulation_versions.id"), index=True)
    requirement_ids: Mapped[list[UUID]] = mapped_column(pg.ARRAY(pg.UUID(as_uuid=True)))
    status: Mapped[PolicyStatus] = mapped_column(Enum(PolicyStatus))
    deployed_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True), nullable=True)

class SystemMapping(Base, TimestampMixin):
    __tablename__ = "system_mappings"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    system_name: Mapped[str] = mapped_column(String)
    mapped_requirement_ids: Mapped[list[UUID]] = mapped_column(pg.ARRAY(pg.UUID(as_uuid=True)))

class ComplianceCheck(Base, TimestampMixin):
    __tablename__ = "compliance_checks"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("policies.id"), index=True)
    input_payload_ref: Mapped[str] = mapped_column(String)
    result: Mapped[ComplianceResult] = mapped_column(Enum(ComplianceResult))
    violations: Mapped[dict] = mapped_column(pg.JSONB)
