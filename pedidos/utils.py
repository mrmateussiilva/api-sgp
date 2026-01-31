from __future__ import annotations

from typing import Any, Iterable
import json

from sqlmodel import select

from pedidos.schema import Pedido
from pedidos.service import json_string_to_items

DEFAULT_KEY_FIELDS = ("numero", "pedido_id", "id_pedido", "id")

DEFAULT_PEDIDO_FIELDS = {
    "id",
    "pedido_id",
    "numero",
    "cliente",
    "telefone_cliente",
    "cidade_estado",
    "cidade_cliente",
    "estado_cliente",
    "data_envio",
    "data_entrega",
    "forma_envio",
    "prioridade",
    "designer",
    "vendedor",
    "rip",
    "data_rip",
    "observacao",
}

DEFAULT_PRODUTO_FIELDS = {
    "id_item",
    "item_id",
    "descricao",
    "dimensoes",
    "quantity",
    "material",
    "emenda_label",
    "emenda_qtd",
    "tipo_producao",
    "acabamentos_painel",
    "overloque",
    "elastico",
    "ilhos_resumo",
    "cordinha_resumo",
    "quantidade_paineis",
    "acabamento_totem_resumo",
    "acabamento_totem_outro",
    "quantidade_totem",
    "acabamento_lona",
    "quantidade_lona",
    "quantidade_ilhos",
    "espaco_ilhos",
    "quantidade_cordinha",
    "espaco_cordinha",
    "tipo_adesivo",
    "quantidade_adesivo",
    "observacao_item",
    "imagem",
    "legenda_imagem",
}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _first_key_value(record: dict[str, Any], key_fields: Iterable[str]) -> str | None:
    for key in key_fields:
        value = record.get(key)
        if _is_empty(value):
            continue
        return str(value).strip()
    return None


def agrupar_pedidos(
    registros: list[dict[str, Any]],
    *,
    key_fields: Iterable[str] | None = None,
    pedido_fields: Iterable[str] | None = None,
    produto_fields: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Agrupa registros "explodidos" (1 produto por linha) em pedidos únicos.

    - Deduplica pedidos pelo primeiro campo encontrado em key_fields.
    - Mescla campos de cabeçalho, mantendo o primeiro valor não vazio.
    - Deduplica produtos por conteúdo.
    """
    key_fields = tuple(key_fields or DEFAULT_KEY_FIELDS)
    pedido_fields = set(pedido_fields or DEFAULT_PEDIDO_FIELDS)
    produto_fields = set(produto_fields or DEFAULT_PRODUTO_FIELDS)

    pedidos: dict[str, dict[str, Any]] = {}

    for registro in registros or []:
        if not isinstance(registro, dict):
            continue

        pedido_key = _first_key_value(registro, key_fields)
        if not pedido_key:
            continue

        pedido = pedidos.setdefault(pedido_key, {"produtos": [], "_produtos_seen": set()})

        for field in pedido_fields:
            if field not in registro:
                continue
            value = registro.get(field)
            if _is_empty(value):
                continue
            if _is_empty(pedido.get(field)):
                pedido[field] = value

        produto: dict[str, Any] = {}
        for field in produto_fields:
            if field in registro and not _is_empty(registro.get(field)):
                produto[field] = registro[field]

        if not produto:
            produto = {
                key: value
                for key, value in registro.items()
                if key not in pedido_fields and key not in key_fields and key != "produtos"
            }

        if produto:
            assinatura = json.dumps(produto, sort_keys=True, ensure_ascii=True, default=str)
            if assinatura not in pedido["_produtos_seen"]:
                pedido["_produtos_seen"].add(assinatura)
                pedido["produtos"].append(produto)

    resultado: list[dict[str, Any]] = []
    for pedido in pedidos.values():
        pedido.pop("_produtos_seen", None)
        resultado.append(pedido)

    return resultado


async def find_order_by_item_id(session, item_id: int):
    # Buscar todos os pedidos (ou filtrar por status se performance for critica)
    # Como nao temos tabela de itens, precisamos iterar.
    # TODO: Em producao idealmente teriamos tabela de itens ou indice no JSON.
    stmt = select(Pedido)
    result = await session.exec(stmt)
    pedidos = result.all()

    for pedido in pedidos:
        if not pedido.items:
            continue

        items = json_string_to_items(pedido.items)
        for i, item in enumerate(items):
            if item.id == item_id:
                return pedido, i, item
            if item.id is None and pedido.id is not None:
                fallback_id = pedido.id * 1000 + i
                if fallback_id == item_id:
                    return pedido, i, item

    return None, None, None
