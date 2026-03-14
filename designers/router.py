from datetime import datetime
from typing import List, Optional
from urllib.parse import unquote
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Designer, DesignerCreate, DesignerUpdate, DesignerArteItemResponse, PatchStatusArteRequest, PostComentarioRequest, ComentarioResponse
from pedidos.schema import Pedido, Status
from pedidos.service import json_string_to_items, items_to_json_string
from pedidos.utils import find_order_by_item_id

router = APIRouter(prefix="/designers", tags=["Designers"])


# ---------------------------------------------------------------------------
# CRUD padrão de Designers
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[Designer])
async def list_designers(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Designer))
    return result.all()


@router.get("/{designer_id}", response_model=Designer)
async def get_designer(designer_id: int, session: AsyncSession = Depends(get_session)):
    designer = await session.get(Designer, designer_id)
    if not designer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designer não encontrado")
    return designer


@router.post("/", response_model=Designer, status_code=status.HTTP_201_CREATED)
async def create_designer(designer: DesignerCreate, session: AsyncSession = Depends(get_session)):
    db_designer = Designer(**designer.model_dump())
    session.add(db_designer)
    await session.commit()
    await session.refresh(db_designer)
    return db_designer


@router.patch("/{designer_id}", response_model=Designer)
async def update_designer(
    designer_id: int,
    designer_update: DesignerUpdate,
    session: AsyncSession = Depends(get_session),
):
    db_designer = await session.get(Designer, designer_id)
    if not db_designer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designer não encontrado")

    update_data = designer_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_designer, field, value)

    session.add(db_designer)
    await session.commit()
    await session.refresh(db_designer)
    return db_designer


@router.delete("/{designer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_designer(designer_id: int, session: AsyncSession = Depends(get_session)):
    db_designer = await session.get(Designer, designer_id)
    if not db_designer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designer não encontrado")

    await session.delete(db_designer)
    await session.commit()
    return None


# ---------------------------------------------------------------------------
# Painel de Designers — rotas dedicadas
# ---------------------------------------------------------------------------

# Status de pedido que NÃO devem aparecer no painel
_STATUS_IGNORADOS = {Status.CANCELADO, Status.ENTREGUE}


@router.get(
    "/{nome}/itens",
    response_model=List[DesignerArteItemResponse],
    summary="Lista itens de arte de um designer",
    description=(
        "Retorna itens de pedidos ativos atribuídos ao designer informado. "
        "Suporta filtros de data e paginação para performance."
    ),
)
async def get_itens_designer(
    nome: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """
    Busca itens de arte diretamente no banco filtrando por designer e data.
    """
    nome_decoded = unquote(nome).strip()
    
    # Limites de segurança
    limit = min(max(limit, 1), 200)

    # 1. Query no banco filtrando por status e data
    stmt = select(Pedido).where(
        Pedido.status.not_in(list(_STATUS_IGNORADOS))
    )
    
    if start_date:
        stmt = stmt.where(Pedido.data_entrada >= start_date)
    if end_date:
        stmt = stmt.where(Pedido.data_entrada <= end_date)
        
    # Ordenar por data_entrada desc (mais recentes primeiro)
    stmt = stmt.order_by(Pedido.data_entrada.desc())

    result = await session.exec(stmt)
    pedidos = result.all()

    designer_items: List[DesignerArteItemResponse] = []

    # 2. Extrair itens do JSON e filtrar por designer em memória
    for pedido in pedidos:
        if not pedido.items:
            continue

        items = json_string_to_items(pedido.items)
        for i, item in enumerate(items):
            item_designer = (item.designer or "").strip().lower()
            if item_designer != nome_decoded.lower():
                continue

            item_id = item.id if item.id is not None else (pedido.id * 1000 + i)

            designer_items.append(
                DesignerArteItemResponse(
                    item_id=item_id,
                    order_id=pedido.id,
                    numero_pedido=pedido.numero or str(pedido.id),
                    cliente=pedido.cliente,
                    data_entrega=pedido.data_entrega,
                    tipo_producao=item.tipo_producao,
                    descricao=item.descricao,
                    largura=item.largura,
                    altura=item.altura,
                    metro_quadrado=item.metro_quadrado,
                    imagem=getattr(item, "imagem", None),
                    observacao=item.observacao,
                    status_pedido=pedido.status.value if hasattr(pedido.status, "value") else str(pedido.status),
                    prioridade=pedido.prioridade.value if hasattr(pedido.prioridade, "value") else str(pedido.prioridade),
                    status_arte="liberado" if getattr(item, "legenda_imagem", None) == "LIBERADO" else "aguardando",
                    tecido=item.tecido,
                    composicao_tecidos=item.composicao_tecidos,
                    acabamento=item.acabamento.model_dump() if item.acabamento else None,
                    vendedor=item.vendedor,
                    emenda=item.emenda,
                    emenda_qtd=item.emenda_qtd,
                    quantidade_paineis=item.quantidade_paineis,
                    quantidade_totem=item.quantidade_totem,
                    quantidade_lona=item.quantidade_lona,
                    quantidade_adesivo=item.quantidade_adesivo,
                    tipo_acabamento=item.tipo_acabamento,
                    quantidade_ilhos=item.quantidade_ilhos,
                    espaco_ilhos=item.espaco_ilhos,
                    quantidade_cordinha=item.quantidade_cordinha,
                    espaco_cordinha=item.espaco_cordinha,
                    tipo_adesivo=item.tipo_adesivo,
                    acabamento_lona=item.acabamento_lona,
                    acabamento_totem=item.acabamento_totem,
                    acabamento_totem_outro=item.acabamento_totem_outro,
                    terceirizado=item.terceirizado,
                    ziper=item.ziper,
                    cordinha_extra=item.cordinha_extra,
                    alcinha=item.alcinha,
                    toalha_pronta=item.toalha_pronta,
                    comentarios=[
                        ComentarioResponse(**c) for c in getattr(item, "comentarios", [])
                    ] if getattr(item, "comentarios", None) else [],
                )
            )

    # 3. Aplicar paginação (limit e offset) na lista final de itens
    return designer_items[offset : offset + limit]


@router.patch(
    "/itens/{item_id}/status-arte",
    response_model=DesignerArteItemResponse,
    summary="Atualiza status de arte de um item",
    description=(
        "Atualiza APENAS o campo legenda_imagem do item. "
        "Nunca sobrescreve outros campos (quantidade, preço, vendedor, etc.). "
        "Seguro para uso no painel de designers."
    ),
)
async def patch_status_arte(
    item_id: int,
    body: PatchStatusArteRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    PATCH cirúrgico — atualiza apenas legenda_imagem no JSON de items do pedido.
    """
    pedido, idx, item = await find_order_by_item_id(session, item_id)

    if pedido is None or item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} não encontrado em nenhum pedido ativo.",
        )

    # Atualizar APENAS a legenda_imagem — nunca toca em outros campos
    item.legenda_imagem = body.legenda_imagem

    # Reserializar a lista de items com o item atualizado
    items = json_string_to_items(pedido.items)
    items[idx] = item
    pedido.items = items_to_json_string(items)

    session.add(pedido)
    await session.commit()
    await session.refresh(pedido)

    # Retornar o item atualizado no formato do painel
    novo_status_arte = "liberado" if body.legenda_imagem == "LIBERADO" else "aguardando"
    return DesignerArteItemResponse(
        item_id=item_id,
        order_id=pedido.id,
        numero_pedido=pedido.numero or str(pedido.id),
        cliente=pedido.cliente,
        data_entrega=pedido.data_entrega,
        tipo_producao=item.tipo_producao,
        descricao=item.descricao,
        largura=item.largura,
        altura=item.altura,
        metro_quadrado=item.metro_quadrado,
        imagem=getattr(item, "imagem", None),
        observacao=item.observacao,
        status_pedido=pedido.status.value if hasattr(pedido.status, "value") else str(pedido.status),
        prioridade=pedido.prioridade.value if hasattr(pedido.prioridade, "value") else str(pedido.prioridade),
        status_arte=novo_status_arte,
        
        # Novos campos técnicos para o retorno do PATCH
        tecido=item.tecido,
        composicao_tecidos=item.composicao_tecidos,
        acabamento=item.acabamento.model_dump() if item.acabamento else None,
        vendedor=item.vendedor,
        emenda=item.emenda,
        emenda_qtd=item.emenda_qtd,
        quantidade_paineis=item.quantidade_paineis,
        quantidade_totem=item.quantidade_totem,
        quantidade_lona=item.quantidade_lona,
        quantidade_adesivo=item.quantidade_adesivo,
        tipo_acabamento=item.tipo_acabamento,
        quantidade_ilhos=item.quantidade_ilhos,
        espaco_ilhos=item.espaco_ilhos,
        quantidade_cordinha=item.quantidade_cordinha,
        espaco_cordinha=item.espaco_cordinha,
        tipo_adesivo=item.tipo_adesivo,
        acabamento_lona=item.acabamento_lona,
        acabamento_totem=item.acabamento_totem,
        acabamento_totem_outro=item.acabamento_totem_outro,
        terceirizado=item.terceirizado,
        ziper=item.ziper,
        cordinha_extra=item.cordinha_extra,
        alcinha=item.alcinha,
        toalha_pronta=item.toalha_pronta,
        comentarios=[
            ComentarioResponse(**c) for c in getattr(item, "comentarios", [])
        ] if getattr(item, "comentarios", None) else [],
    )


@router.post(
    "/itens/{item_id}/comentarios",
    response_model=DesignerArteItemResponse,
    summary="Adiciona um comentário a um item",
)
async def post_comentario_item(
    item_id: int,
    body: PostComentarioRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Adiciona um comentário ao histórico do item (estilo Trello).
    """
    pedido, idx, item = await find_order_by_item_id(session, item_id)

    if pedido is None or item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} não encontrado.",
        )

    # Inicializar lista de comentários se não existir
    if not hasattr(item, "comentarios") or item.comentarios is None:
        item.comentarios = []

    # Criar novo comentário
    novo_comentario = {
        "id": str(uuid.uuid4()),
        "autor": body.autor,
        "texto": body.texto,
        "data": datetime.now().isoformat()
    }

    item.comentarios.append(novo_comentario)

    # Reserializar
    items = json_string_to_items(pedido.items)
    items[idx] = item
    pedido.items = items_to_json_string(items)

    session.add(pedido)
    await session.commit()
    await session.refresh(pedido)

    return DesignerArteItemResponse(
        item_id=item_id,
        order_id=pedido.id,
        numero_pedido=pedido.numero or str(pedido.id),
        cliente=pedido.cliente,
        data_entrega=pedido.data_entrega,
        tipo_producao=item.tipo_producao,
        descricao=item.descricao,
        largura=item.largura,
        altura=item.altura,
        metro_quadrado=item.metro_quadrado,
        imagem=getattr(item, "imagem", None),
        observacao=item.observacao,
        status_pedido=pedido.status.value if hasattr(pedido.status, "value") else str(pedido.status),
        prioridade=pedido.prioridade.value if hasattr(pedido.prioridade, "value") else str(pedido.prioridade),
        status_arte="liberado" if getattr(item, "legenda_imagem", None) == "LIBERADO" else "aguardando",
        tecido=item.tecido,
        composicao_tecidos=item.composicao_tecidos,
        acabamento=item.acabamento.model_dump() if item.acabamento else None,
        vendedor=item.vendedor,
        emenda=item.emenda,
        emenda_qtd=item.emenda_qtd,
        quantidade_paineis=item.quantidade_paineis,
        quantidade_totem=item.quantidade_totem,
        quantidade_lona=item.quantidade_lona,
        quantidade_adesivo=item.quantidade_adesivo,
        tipo_acabamento=item.tipo_acabamento,
        quantidade_ilhos=item.quantidade_ilhos,
        espaco_ilhos=item.espaco_ilhos,
        quantidade_cordinha=item.quantidade_cordinha,
        espaco_cordinha=item.espaco_cordinha,
        tipo_adesivo=item.tipo_adesivo,
        acabamento_lona=item.acabamento_lona,
        acabamento_totem=item.acabamento_totem,
        acabamento_totem_outro=item.acabamento_totem_outro,
        terceirizado=item.terceirizado,
        ziper=item.ziper,
        cordinha_extra=item.cordinha_extra,
        alcinha=item.alcinha,
        toalha_pronta=item.toalha_pronta,
        comentarios=[ComentarioResponse(**c) for c in item.comentarios]
    )
