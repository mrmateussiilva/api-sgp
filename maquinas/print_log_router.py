from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional

from base import get_session
from .print_log_schema import PrintLog, PrintLogCreate, PrintLogResponse, PrintLogStatus
from .schema import Machine
from pedidos.schema import Pedido

router = APIRouter(prefix="/print-logs", tags=["Print Logs"])


@router.get("/printers/{printer_id}", response_model=list[PrintLogResponse])
async def get_printer_logs(
    printer_id: int,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[PrintLogStatus] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna logs de impressão de uma impressora específica.
    Ordenados por data (mais recente primeiro).
    """
    machine = await session.get(Machine, printer_id)
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Impressora não encontrada"
        )

    query = select(PrintLog).where(PrintLog.printer_id == printer_id)
    
    if status_filter:
        query = query.where(PrintLog.status == status_filter)
    
    query = query.order_by(PrintLog.created_at.desc()).offset(offset).limit(limit)
    
    result = await session.exec(query)
    logs = result.all()

    response_logs = []
    for log in logs:
        pedido = await session.get(Pedido, log.pedido_id)
        
        response_logs.append(
            PrintLogResponse(
                id=log.id,
                printer_id=log.printer_id,
                printer_name=machine.name,
                pedido_id=log.pedido_id,
                pedido_numero=pedido.numero if pedido else None,
                item_id=log.item_id,
                status=log.status,
                error_message=log.error_message,
                created_at=log.created_at,
            )
        )

    return response_logs


@router.post("/", response_model=PrintLogResponse, status_code=status.HTTP_201_CREATED)
async def create_print_log(
    log_data: PrintLogCreate,
    session: AsyncSession = Depends(get_session),
):
    """
    Cria um novo log de impressão.
    Usado internamente pelo sistema de impressão.
    """
    machine = await session.get(Machine, log_data.printer_id)
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Impressora não encontrada"
        )

    pedido = await session.get(Pedido, log_data.pedido_id)
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido não encontrado"
        )

    db_log = PrintLog(**log_data.model_dump())
    session.add(db_log)
    await session.commit()
    await session.refresh(db_log)

    return PrintLogResponse(
        id=db_log.id,
        printer_id=db_log.printer_id,
        printer_name=machine.name,
        pedido_id=db_log.pedido_id,
        pedido_numero=pedido.numero,
        item_id=db_log.item_id,
        status=db_log.status,
        error_message=db_log.error_message,
        created_at=db_log.created_at,
    )


@router.get("/stats/{printer_id}")
async def get_printer_stats(
    printer_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna estatísticas de impressão de uma impressora.
    """
    machine = await session.get(Machine, printer_id)
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Impressora não encontrada"
        )

    query = select(PrintLog).where(PrintLog.printer_id == printer_id)
    result = await session.exec(query)
    all_logs = result.all()

    total = len(all_logs)
    success = sum(1 for log in all_logs if log.status == PrintLogStatus.SUCCESS)
    errors = sum(1 for log in all_logs if log.status == PrintLogStatus.ERROR)
    reprints = sum(1 for log in all_logs if log.status == PrintLogStatus.REPRINT)

    return {
        "printer_id": printer_id,
        "printer_name": machine.name,
        "total_prints": total,
        "successful": success,
        "errors": errors,
        "reprints": reprints,
        "success_rate": round((success / total * 100) if total > 0 else 0, 2),
    }
