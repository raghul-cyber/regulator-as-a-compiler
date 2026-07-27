from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class Webhook(Base, TimestampMixin):
    __tablename__ = "webhooks"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    url: Mapped[str] = mapped_column(String)
    event_types: Mapped[list[str]] = mapped_column(pg.ARRAY(String))
    secret: Mapped[str] = mapped_column(String)
