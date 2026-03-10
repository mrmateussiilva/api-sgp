from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class SyncStatus(str, Enum):
    PENDING = "pending"
    RETRY = "retry"
    SENT = "sent"
    DEAD_LETTER = "dead_letter"


class SyncEntity(str, Enum):
    PEDIDO = "pedido"
    USER = "user"


class SyncEventType(str, Enum):
    UPSERT = "upsert"
    DELETE = "delete"


class SyncOutboxEvent(SQLModel, table=True):
    __tablename__ = "sync_outbox"

    id: Optional[int] = Field(default=None, primary_key=True)
    entity: str = Field(index=True, max_length=50)
    entity_id: Optional[int] = Field(default=None, index=True)
    event_type: str = Field(index=True, max_length=50)
    payload_json: str = Field(default="{}")

    status: str = Field(default=SyncStatus.PENDING.value, index=True, max_length=20)
    attempts: int = Field(default=0)
    next_retry_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_error: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
