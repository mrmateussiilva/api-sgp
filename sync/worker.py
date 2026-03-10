from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta

import orjson

from config import settings
from database.database import async_session_maker
from shared.mysql_pwa_sync_service import (
    sync_deletion as mysql_sync_deletion,
)
from shared.mysql_pwa_sync_service import (
    sync_pedido as mysql_sync_pedido,
)
from shared.mysql_pwa_sync_service import (
    sync_user as mysql_sync_user,
)
from shared.mysql_pwa_sync_service import (
    sync_user_deletion as mysql_sync_user_deletion,
)
from .schema import SyncEntity, SyncEventType, SyncOutboxEvent
from .service import fetch_due_events, mark_event_failed, mark_event_sent


logger = logging.getLogger(__name__)


class SyncOutboxWorker:
    def __init__(
        self,
        *,
        poll_interval_seconds: float = 2.0,
        batch_size: int = 20,
        max_attempts: int = 8,
        base_retry_seconds: int = 5,
        max_retry_seconds: int = 600,
    ) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.base_retry_seconds = base_retry_seconds
        self.max_retry_seconds = max_retry_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if settings.ENVIRONMENT == "test":
            logger.info("[SYNC] Worker não iniciado em ambiente de teste")
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop(), name="sync-outbox-worker")
        logger.info("[SYNC] Worker iniciado")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
        logger.info("[SYNC] Worker finalizado")

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                processed = await self._process_batch()
                if processed == 0:
                    await asyncio.sleep(self.poll_interval_seconds)
            except Exception as exc:
                logger.exception("[SYNC] Erro no loop do worker: %s", exc)
                await asyncio.sleep(self.poll_interval_seconds)

    async def _process_batch(self) -> int:
        async with async_session_maker() as session:
            events = await fetch_due_events(session, self.batch_size)

        if not events:
            return 0

        for event in events:
            await self._process_event(event)

        return len(events)

    async def _process_event(self, event: SyncOutboxEvent) -> None:
        try:
            await self._dispatch_event(event)
            async with async_session_maker() as session:
                await mark_event_sent(session, event.id)
        except Exception as exc:
            backoff_seconds = self._compute_backoff(event.attempts)
            next_retry = datetime.utcnow() + timedelta(seconds=backoff_seconds)
            logger.exception(
                "[SYNC] Falha ao processar evento id=%s entity=%s type=%s tentativa=%s",
                event.id,
                event.entity,
                event.event_type,
                event.attempts + 1,
            )
            async with async_session_maker() as session:
                await mark_event_failed(
                    session,
                    event.id,
                    error=str(exc),
                    max_attempts=self.max_attempts,
                    next_retry_at=next_retry,
                )

    def _compute_backoff(self, attempts: int) -> int:
        # attempts representa a quantidade atual de falhas registradas.
        exp = min(self.base_retry_seconds * (2 ** attempts), self.max_retry_seconds)
        jitter = random.randint(0, min(self.base_retry_seconds, 5))
        return min(exp + jitter, self.max_retry_seconds)

    async def _dispatch_event(self, event: SyncOutboxEvent) -> None:
        payload = orjson.loads(event.payload_json or "{}")

        if event.entity == SyncEntity.PEDIDO.value:
            pedido_id = event.entity_id or payload.get("pedido_id")
            if not pedido_id:
                raise ValueError(f"Evento de pedido sem pedido_id (event_id={event.id})")

            if event.event_type == SyncEventType.DELETE.value:
                await asyncio.to_thread(mysql_sync_deletion, int(pedido_id))
                return

            if event.event_type == SyncEventType.UPSERT.value:
                await asyncio.to_thread(mysql_sync_pedido, int(pedido_id))
                return

            raise ValueError(f"Tipo de evento de pedido inválido: {event.event_type}")

        if event.entity == SyncEntity.USER.value:
            if event.event_type == SyncEventType.DELETE.value:
                username = payload.get("username")
                if not username:
                    raise ValueError(f"Evento de user delete sem username (event_id={event.id})")
                await asyncio.to_thread(mysql_sync_user_deletion, str(username))
                return

            if event.event_type == SyncEventType.UPSERT.value:
                user_id = event.entity_id or payload.get("user_id")
                if not user_id:
                    raise ValueError(f"Evento de user upsert sem user_id (event_id={event.id})")
                await asyncio.to_thread(mysql_sync_user, int(user_id))
                return

            raise ValueError(f"Tipo de evento de user inválido: {event.event_type}")

        raise ValueError(f"Entidade de sync inválida: {event.entity}")


sync_outbox_worker = SyncOutboxWorker()
