#!/usr/bin/env python3
"""
Enfileira dados já existentes na tabela sync_outbox para sincronização remota.

Uso:
  uv run python scripts/backfill_sync_outbox.py
  uv run python scripts/backfill_sync_outbox.py --no-users
  uv run python scripts/backfill_sync_outbox.py --no-pedidos
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from sqlmodel import select

from auth.models import User
from database.database import async_session_maker
from pedidos.schema import Pedido
from sync.schema import SyncEntity, SyncEventType, SyncOutboxEvent, SyncStatus


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill de sync_outbox")
    parser.add_argument("--no-pedidos", action="store_true", help="Não enfileirar pedidos")
    parser.add_argument("--no-users", action="store_true", help="Não enfileirar usuários")
    return parser.parse_args()


async def _enqueue_pedidos() -> int:
    now = datetime.utcnow()
    async with async_session_maker() as session:
        result = await session.exec(select(Pedido.id))
        pedido_ids = [pid for pid in result.all() if pid is not None]
        existing_res = await session.exec(
            select(SyncOutboxEvent.entity_id).where(
                SyncOutboxEvent.entity == SyncEntity.PEDIDO.value,
                SyncOutboxEvent.event_type == SyncEventType.UPSERT.value,
            )
        )
        existing_ids = {int(v) for v in existing_res.all() if v is not None}
        pending_ids = [int(pid) for pid in pedido_ids if int(pid) not in existing_ids]

        if not pending_ids:
            return 0

        for pedido_id in pending_ids:
            session.add(
                SyncOutboxEvent(
                    entity=SyncEntity.PEDIDO.value,
                    entity_id=int(pedido_id),
                    event_type=SyncEventType.UPSERT.value,
                    payload_json=f'{{"pedido_id": {int(pedido_id)}}}',
                    status=SyncStatus.PENDING.value,
                    attempts=0,
                    next_retry_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )

        await session.commit()
        return len(pending_ids)


async def _enqueue_users() -> int:
    now = datetime.utcnow()
    async with async_session_maker() as session:
        result = await session.exec(select(User.id))
        user_ids = [uid for uid in result.all() if uid is not None]
        existing_res = await session.exec(
            select(SyncOutboxEvent.entity_id).where(
                SyncOutboxEvent.entity == SyncEntity.USER.value,
                SyncOutboxEvent.event_type == SyncEventType.UPSERT.value,
            )
        )
        existing_ids = {int(v) for v in existing_res.all() if v is not None}
        pending_ids = [int(uid) for uid in user_ids if int(uid) not in existing_ids]

        if not pending_ids:
            return 0

        for user_id in pending_ids:
            session.add(
                SyncOutboxEvent(
                    entity=SyncEntity.USER.value,
                    entity_id=int(user_id),
                    event_type=SyncEventType.UPSERT.value,
                    payload_json=f'{{"user_id": {int(user_id)}}}',
                    status=SyncStatus.PENDING.value,
                    attempts=0,
                    next_retry_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )

        await session.commit()
        return len(pending_ids)


async def main() -> None:
    args = _parse_args()

    pedidos_count = 0
    users_count = 0

    if not args.no_pedidos:
        pedidos_count = await _enqueue_pedidos()

    if not args.no_users:
        users_count = await _enqueue_users()

    print(
        "Backfill concluído: "
        f"pedidos_enfileirados={pedidos_count}, "
        f"users_enfileirados={users_count}"
    )


if __name__ == "__main__":
    asyncio.run(main())
