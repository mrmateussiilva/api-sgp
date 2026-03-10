from __future__ import annotations

import orjson
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .schema import SyncOutboxEvent, SyncStatus


MAX_ERROR_LENGTH = 4000


async def enqueue_sync_event(
    session: AsyncSession,
    *,
    entity: str,
    event_type: str,
    entity_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
) -> SyncOutboxEvent:
    payload_json = orjson.dumps(payload or {}).decode("utf-8")
    event = SyncOutboxEvent(
        entity=entity,
        entity_id=entity_id,
        event_type=event_type,
        payload_json=payload_json,
        status=SyncStatus.PENDING.value,
        next_retry_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(event)
    return event


async def fetch_due_events(session: AsyncSession, batch_size: int) -> list[SyncOutboxEvent]:
    now = datetime.utcnow()
    stmt = (
        select(SyncOutboxEvent)
        .where(SyncOutboxEvent.status.in_([SyncStatus.PENDING.value, SyncStatus.RETRY.value]))
        .where(SyncOutboxEvent.next_retry_at <= now)
        .order_by(SyncOutboxEvent.created_at.asc(), SyncOutboxEvent.id.asc())
        .limit(batch_size)
    )
    result = await session.exec(stmt)
    return list(result.all())


async def mark_event_sent(session: AsyncSession, event_id: int) -> None:
    event = await session.get(SyncOutboxEvent, event_id)
    if not event:
        return
    now = datetime.utcnow()
    event.status = SyncStatus.SENT.value
    event.processed_at = now
    event.updated_at = now
    event.last_error = None
    session.add(event)
    await session.commit()


async def mark_event_failed(
    session: AsyncSession,
    event_id: int,
    *,
    error: str,
    max_attempts: int,
    next_retry_at: datetime,
) -> None:
    event = await session.get(SyncOutboxEvent, event_id)
    if not event:
        return

    event.attempts += 1
    event.updated_at = datetime.utcnow()
    event.last_error = error[:MAX_ERROR_LENGTH]

    if event.attempts >= max_attempts:
        event.status = SyncStatus.DEAD_LETTER.value
        event.processed_at = event.updated_at
    else:
        event.status = SyncStatus.RETRY.value
        event.next_retry_at = next_retry_at

    session.add(event)
    await session.commit()


async def get_outbox_stats(session: AsyncSession) -> dict[str, Any]:
    counts_stmt = select(SyncOutboxEvent.status, func.count()).group_by(SyncOutboxEvent.status)
    counts_res = await session.exec(counts_stmt)

    counts = {
        SyncStatus.PENDING.value: 0,
        SyncStatus.RETRY.value: 0,
        SyncStatus.SENT.value: 0,
        SyncStatus.DEAD_LETTER.value: 0,
    }
    for status, total in counts_res.all():
        counts[str(status)] = int(total)

    now = datetime.utcnow()
    oldest_stmt = (
        select(SyncOutboxEvent.created_at)
        .where(SyncOutboxEvent.status.in_([SyncStatus.PENDING.value, SyncStatus.RETRY.value]))
        .order_by(SyncOutboxEvent.created_at.asc())
        .limit(1)
    )
    oldest_res = await session.exec(oldest_stmt)
    oldest = oldest_res.first()

    pending_total = counts[SyncStatus.PENDING.value] + counts[SyncStatus.RETRY.value]
    oldest_age_seconds: Optional[int] = None
    if oldest:
        oldest_age_seconds = int((now - oldest).total_seconds())

    return {
        "queue": counts,
        "pending_total": pending_total,
        "oldest_pending_age_seconds": oldest_age_seconds,
        "generated_at": now.isoformat(),
    }


async def retry_dead_letter_event(session: AsyncSession, event_id: int) -> bool:
    event = await session.get(SyncOutboxEvent, event_id)
    if not event or event.status != SyncStatus.DEAD_LETTER.value:
        return False

    now = datetime.utcnow()
    event.status = SyncStatus.RETRY.value
    event.next_retry_at = now
    event.updated_at = now
    event.processed_at = None
    session.add(event)
    await session.commit()
    return True
