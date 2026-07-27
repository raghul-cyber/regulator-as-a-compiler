from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
import sqlalchemy.dialects.postgresql as pg

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(pg.TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )

class ImmutableTimestampMixin:
    created_at: Mapped[datetime] = mapped_column(pg.TIMESTAMP(timezone=True), server_default=func.now())
