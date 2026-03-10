from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .service import get_outbox_stats, retry_dead_letter_event


router = APIRouter(prefix="/sync", tags=["Sync"])


@router.get("/health")
async def sync_health(session: AsyncSession = Depends(get_session)):
    stats = await get_outbox_stats(session)

    degraded_reasons: list[str] = []
    if stats["queue"].get("dead_letter", 0) > 0:
        degraded_reasons.append("dead_letter")
    if stats["oldest_pending_age_seconds"] is not None and stats["oldest_pending_age_seconds"] > 300:
        degraded_reasons.append("oldest_pending_age")

    status = "ok" if not degraded_reasons else "degraded"
    return {
        "status": status,
        "reasons": degraded_reasons,
        "stats": stats,
    }


@router.get("/stats")
async def sync_stats(session: AsyncSession = Depends(get_session)):
    return await get_outbox_stats(session)


@router.post("/retry-dead-letter")
async def retry_dead_letter(
    event_id: int = Query(..., ge=1),
    session: AsyncSession = Depends(get_session),
):
    changed = await retry_dead_letter_event(session, event_id)
    if not changed:
        raise HTTPException(status_code=404, detail="Evento dead_letter não encontrado")
    return {"message": "Evento reenfileirado", "event_id": event_id}
