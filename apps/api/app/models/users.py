import enum
from uuid import UUID, uuid4
from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class UserRole(str, enum.Enum):
    admin = "admin"
    compliance_officer = "compliance_officer"
    developer = "developer"
    legal_counsel = "legal_counsel"
    auditor = "auditor"

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    clerk_user_id: Mapped[str] = mapped_column(String, unique=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    email: Mapped[str] = mapped_column(String)
