import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config import settings
from relatorios.fechamentos import get_item_value, parse_currency


def _resolve_sqlite_path(url) -> Path | None:
    db_path = Path(url.database or "")
    if not str(db_path):
        return None
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    return db_path


def _build_engine():
    url = make_url(settings.DATABASE_URL)
    if url.drivername.startswith("sqlite"):
        db_path = _resolve_sqlite_path(url)
        if not db_path or not db_path.exists():
            pytest.skip(f"Banco SQLite nao encontrado: {db_path}")
    return create_engine(settings.DATABASE_URL)


def _iter_items(raw_items: str):
    if not raw_items:
        return []
    try:
        data = json.loads(raw_items)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _resolve_quantity(item: dict) -> float | None:
    tipo = (item.get("tipo_producao") or "").strip().lower()
    tipo_map = {
        "painel": item.get("quantidade_paineis"),
        "generica": item.get("quantidade_paineis"),
        "totem": item.get("quantidade_totem"),
        "lona": item.get("quantidade_lona"),
        "adesivo": item.get("quantidade_adesivo"),
    }
    if tipo in tipo_map and tipo_map[tipo] is not None:
        mapped = parse_currency(tipo_map[tipo])
        if mapped > 0:
            return mapped

    quantity_candidates = [
        item.get("quantity"),
        item.get("quantidade"),
        item.get("quantidade_paineis"),
        item.get("quantidade_totem"),
        item.get("quantidade_lona"),
        item.get("quantidade_adesivo"),
    ]
    quantity_value = 0.0
    for raw_value in quantity_candidates:
        value = parse_currency(raw_value)
        if value > quantity_value:
            quantity_value = value
    if quantity_value > 0:
        return quantity_value
    return None


def test_valor_item_quantidadexvalor_unitario_db():
    engine = _build_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, items FROM pedidos "
                "WHERE items IS NOT NULL AND items != ''"
            )
        ).fetchall()

    for pedido_id, raw_items in rows:
        for idx, item in enumerate(_iter_items(raw_items)):
            unit_price_raw = item.get("unit_price") or item.get("valor_unitario")
            if not unit_price_raw:
                continue
            unit_price = parse_currency(unit_price_raw)
            if unit_price <= 0:
                continue

            quantity_value = _resolve_quantity(item)
            if quantity_value is None:
                continue

            expected = quantity_value * unit_price
            actual = get_item_value(SimpleNamespace(**item))
            assert actual == pytest.approx(
                expected, abs=0.01
            ), f"Pedido {pedido_id} item {idx}"


def test_valor_total_igual_soma_itens_frete_db():
    engine = _build_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, valor_total, valor_frete, items FROM pedidos "
                "WHERE items IS NOT NULL AND items != ''"
            )
        ).fetchall()

    for pedido_id, valor_total_raw, valor_frete_raw, raw_items in rows:
        valor_total = parse_currency(valor_total_raw)
        if valor_total <= 0:
            continue

        items = _iter_items(raw_items)
        if not items:
            continue

        items_sum = sum(get_item_value(SimpleNamespace(**item)) for item in items)
        frete = parse_currency(valor_frete_raw)
        esperado = items_sum + frete

        assert valor_total == pytest.approx(
            esperado, abs=0.01
        ), f"Pedido {pedido_id}"
