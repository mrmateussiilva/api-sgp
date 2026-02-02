from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional

from base import get_session
from .print_log_schema import PrintLog, PrintLogCreate, PrintLogResponse, PrintLogStatus
from .schema import Machine
from pedidos.schema import Pedido
from pedidos.service import json_string_to_items
from pedidos.router import populate_items_with_image_paths

router = APIRouter(prefix="/print-logs", tags=["Print Logs"])


@router.get("/", response_model=list[PrintLogResponse])
async def list_all_logs(
    limit: int = Query(default=1000, le=50000),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[PrintLogStatus] = None,
    data_inicio: Optional[str] = Query(default=None, description="Data de início (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(default=None, description="Data de fim (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
):
    """
    Lista logs de todas as impressoras.
    Ordenados por data (mais recente primeiro).
    """
    query = select(PrintLog)
    
    if status_filter:
        query = query.where(PrintLog.status == status_filter)
    
    if data_inicio:
        query = query.where(PrintLog.created_at >= data_inicio)
    if data_fim:
        # Adiciona 23:59:59 para incluir todo o dia de fim
        query = query.where(PrintLog.created_at <= f"{data_fim} 23:59:59")
    
    query = query.order_by(PrintLog.created_at.desc()).offset(offset).limit(limit)
    
    result = await session.exec(query)
    logs = result.all()

    response_logs = []
    # Cache para evitar múltiplas consultas à tabela de máquinas
    machine_cache = {}

    for log in logs:
        if log.printer_id not in machine_cache:
            machine = await session.get(Machine, log.printer_id)
            machine_cache[log.printer_id] = machine.name if machine else "Desconhecida"
        
        pedido = await session.get(Pedido, log.pedido_id)
        
        # Buscar detalhes do item
        item_details = {}
        if pedido and log.item_id:
            try:
                items = json_string_to_items(pedido.items)
                # Popular caminhos de imagem
                await populate_items_with_image_paths(session, pedido.id, items)
                
                target_item = next((i for i in items if i.id == log.item_id), None)
                if not target_item:
                    # Tenta fallback se o ID for baseado em index
                    fallback_id = pedido.id * 1000
                    target_item = next((i for idx, i in enumerate(items) if (pedido.id * 1000 + idx) == log.item_id), None)

                if target_item:
                    item_details = {
                        "item_descricao": target_item.descricao,
                        "item_imagem": target_item.imagem,
                        "item_medidas": f"{target_item.largura} x {target_item.altura} m",
                        "item_material": f"{target_item.tecido or ''} {target_item.perfil_cor or ''}".strip()
                    }
            except Exception as e:
                print(f"Erro ao extrair detalhes do item no log: {e}")

        response_logs.append(
            PrintLogResponse(
                id=log.id,
                printer_id=log.printer_id,
                printer_name=machine_cache[log.printer_id],
                pedido_id=log.pedido_id,
                pedido_numero=pedido.numero if pedido else None,
                cliente=pedido.cliente if pedido else None,
                item_id=log.item_id,
                status=log.status,
                error_message=log.error_message,
                created_at=log.created_at,
                **item_details
            )
        )

    return response_logs


@router.get("/printers/{printer_id}", response_model=list[PrintLogResponse])
async def get_printer_logs(
    printer_id: int,
    limit: int = Query(default=1000, le=50000),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[PrintLogStatus] = None,
    data_inicio: Optional[str] = Query(default=None, description="Data de início (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(default=None, description="Data de fim (YYYY-MM-DD)"),
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
    
    if data_inicio:
        query = query.where(PrintLog.created_at >= data_inicio)
    if data_fim:
        query = query.where(PrintLog.created_at <= f"{data_fim} 23:59:59")
    
    query = query.order_by(PrintLog.created_at.desc()).offset(offset).limit(limit)
    
    result = await session.exec(query)
    logs = result.all()

    response_logs = []
    for log in logs:
        pedido = await session.get(Pedido, log.pedido_id)
        
        # Buscar detalhes do item
        item_details = {}
        if pedido and log.item_id:
            try:
                items = json_string_to_items(pedido.items)
                await populate_items_with_image_paths(session, pedido.id, items)
                
                target_item = next((i for i in items if i.id == log.item_id), None)
                if not target_item:
                    target_item = next((i for idx, i in enumerate(items) if (pedido.id * 1000 + idx) == log.item_id), None)

                if target_item:
                    item_details = {
                        "item_descricao": target_item.descricao,
                        "item_imagem": target_item.imagem,
                        "item_medidas": f"{target_item.largura} x {target_item.altura} m",
                        "item_material": f"{target_item.tecido or ''} {target_item.perfil_cor or ''}".strip()
                    }
            except Exception as e:
                print(f"Erro ao extrair detalhes do item no log: {e}")

        response_logs.append(
            PrintLogResponse(
                id=log.id,
                printer_id=log.printer_id,
                printer_name=machine.name,
                pedido_id=log.pedido_id,
                pedido_numero=pedido.numero if pedido else None,
                cliente=pedido.cliente if pedido else None,
                item_id=log.item_id,
                status=log.status,
                error_message=log.error_message,
                created_at=log.created_at,
                **item_details
            )
        )

    return response_logs


@router.post("/", response_model=PrintLogResponse, status_code=status.HTTP_201_CREATED)
async def create_print_log(
    log_data: PrintLogCreate,
    session: AsyncSession = Depends(get_session),
):
    """
    Cria ou atualiza um log de impressão.
    Implementa lógica para evitar duplicidade: se um item já tiver log, atualiza para a nova máquina/status.
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

    # Lógica para evitar duplicidade de itens
    db_log = None
    if log_data.item_id:
        query = select(PrintLog).where(
            PrintLog.pedido_id == log_data.pedido_id,
            PrintLog.item_id == log_data.item_id
        )
        result = await session.exec(query)
        db_log = result.first()

    if db_log:
        # Atualiza log existente
        for key, value in log_data.model_dump().items():
            setattr(db_log, key, value)
        # Resetar data de criação para aparecer no topo se for uma "reatribuição"
        from datetime import datetime
        db_log.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        # Cria novo log
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
