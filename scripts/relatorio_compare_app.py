import asyncio
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import polars as pl
import streamlit as st
from sqlmodel import and_, func, or_, select

from database.database import async_session_maker
from pedidos.schema import Pedido, Status
from relatorios.fechamentos import (
    calculate_order_value,
    get_item_value,
    json_string_to_items,
    parse_currency,
)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        raw = value.split("T")[0].strip()
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


async def _load_pedidos(
    start: Optional[date],
    end: Optional[date],
    date_mode: str,
    status_filter: Optional[str],
) -> List[Pedido]:
    async with async_session_maker() as session:
        query = select(Pedido)

        if start and end:
            start_value = start.strftime("%Y-%m-%d")
            end_value = end.strftime("%Y-%m-%d")
            if date_mode == "entrada":
                query = query.where(
                    func.date(Pedido.data_entrada) >= start_value,
                    func.date(Pedido.data_entrada) <= end_value,
                )
            elif date_mode == "entrega":
                query = query.where(
                    Pedido.data_entrega.isnot(None),
                    func.date(Pedido.data_entrega) >= start_value,
                    func.date(Pedido.data_entrega) <= end_value,
                )
            else:
                query = query.where(
                    or_(
                        and_(
                            func.date(Pedido.data_entrada) >= start_value,
                            func.date(Pedido.data_entrada) <= end_value,
                        ),
                        and_(
                            func.date(Pedido.data_entrega) >= start_value,
                            func.date(Pedido.data_entrega) <= end_value,
                        ),
                    )
                )

        if status_filter and status_filter != "Todos":
            status_map = {s.value: s for s in Status}
            normalized = status_map.get(status_filter.lower().strip())
            if normalized:
                query = query.where(Pedido.status == normalized)

        result = await session.exec(query)
        return result.all()


def _build_frames(pedidos: List[Pedido]) -> Tuple[pl.DataFrame, pl.DataFrame]:
    pedido_rows: List[Dict[str, Any]] = []
    item_rows: List[Dict[str, Any]] = []

    for pedido in pedidos:
        items = json_string_to_items(pedido.items or "[]")
        items_sum = sum(get_item_value(item) for item in items)
        items_count = len(items)
        frete = parse_currency(pedido.valor_frete)
        valor_total = parse_currency(pedido.valor_total)
        valor_itens_campo = parse_currency(pedido.valor_itens)
        valor_itens_frete = items_sum + frete
        valor_calculado_api = calculate_order_value(pedido, items)

        data_base = pedido.data_entrada
        if pedido.data_entrega:
            data_base = pedido.data_entrega

        pedido_rows.append(
            {
                "pedido_id": pedido.id,
                "numero": pedido.numero,
                "cliente": pedido.cliente,
                "status": pedido.status.value if pedido.status else None,
                "data_entrada": _parse_date(pedido.data_entrada),
                "data_entrega": _parse_date(pedido.data_entrega),
                "data_base": _parse_date(data_base),
                "frete": frete,
                "valor_total": valor_total,
                "valor_itens_campo": valor_itens_campo,
                "valor_itens_frete": valor_itens_frete,
                "valor_calculado_api": valor_calculado_api,
                "diff_total_itens": round(valor_total - valor_itens_frete, 2),
                "diff_total_api": round(valor_total - valor_calculado_api, 2),
                "items_sum": items_sum,
                "items_count": items_count,
            }
        )

        for idx, item in enumerate(items):
            item_rows.append(
                {
                    "pedido_id": pedido.id,
                    "numero": pedido.numero,
                    "cliente": pedido.cliente,
                    "status": pedido.status.value if pedido.status else None,
                    "data_entrada": _parse_date(pedido.data_entrada),
                    "data_entrega": _parse_date(pedido.data_entrega),
                    "data_base": _parse_date(data_base),
                    "item_index": idx,
                    "tipo_producao": getattr(item, "tipo_producao", None),
                    "descricao": getattr(item, "descricao", None),
                    "vendedor": getattr(item, "vendedor", None),
                    "designer": getattr(item, "designer", None),
                    "valor_item": get_item_value(item),
                    "items_sum": items_sum,
                    "items_count": items_count,
                    "frete": frete,
                }
            )

    return pl.DataFrame(pedido_rows), pl.DataFrame(item_rows)


def _apply_frete_distribution(item_df: pl.DataFrame, mode: str) -> pl.DataFrame:
    if item_df.is_empty():
        return item_df.with_columns(
            frete_alocado=pl.lit(0.0), valor_item_com_frete=pl.lit(0.0)
        )

    if mode == "nenhum":
        frete_expr = pl.lit(0.0)
    elif mode == "por_item":
        frete_expr = (
            pl.when(pl.col("items_count") > 0)
            .then(pl.col("frete") / pl.col("items_count"))
            .otherwise(0.0)
        )
    else:
        frete_expr = (
            pl.when(pl.col("items_sum") > 0)
            .then(pl.col("frete") * pl.col("valor_item") / pl.col("items_sum"))
            .otherwise(0.0)
        )

    return item_df.with_columns(
        frete_alocado=frete_expr, valor_item_com_frete=pl.col("valor_item") + frete_expr
    )


@st.cache_data(show_spinner=False)
def load_data_cached(
    start: Optional[date],
    end: Optional[date],
    date_mode: str,
    status_filter: Optional[str],
) -> Tuple[pl.DataFrame, pl.DataFrame]:
    pedidos = _run_async(_load_pedidos(start, end, date_mode, status_filter))
    return _build_frames(pedidos)


st.set_page_config(page_title="Comparador de Relatorios de Fechamento", layout="wide")
st.title("Comparador de valores - Relatorios de fechamento")

with st.sidebar:
    st.header("Filtros")
    today = date.today()
    start_date = st.date_input("Data inicial", value=today.replace(day=1))
    end_date = st.date_input("Data final", value=today)
    date_mode = st.selectbox("Modo de data", ["entrada", "entrega", "qualquer"])
    status_filter = st.selectbox(
        "Status",
        ["Todos"] + [s.value for s in Status],
    )
    frete_mode = st.selectbox(
        "Distribuicao de frete",
        ["nenhum", "proporcional", "por_item"],
        help="Apenas para agrupamento por vendedor/designer.",
    )
    tolerancia = st.number_input(
        "Tolerancia para divergencia (R$)",
        min_value=0.0,
        value=0.01,
        step=0.01,
    )

pedido_df, item_df = load_data_cached(start_date, end_date, date_mode, status_filter)

if pedido_df.is_empty():
    st.warning("Nenhum pedido encontrado com os filtros atuais.")
    st.stop()

pedido_df = pedido_df.with_columns(
    pl.col("data_base").cast(pl.Date, strict=False),
    pl.col("data_entrada").cast(pl.Date, strict=False),
    pl.col("data_entrega").cast(pl.Date, strict=False),
)
item_df = item_df.with_columns(
    pl.col("data_base").cast(pl.Date, strict=False),
    pl.col("data_entrada").cast(pl.Date, strict=False),
    pl.col("data_entrega").cast(pl.Date, strict=False),
)

if date_mode == "entrada":
    pedido_df = pedido_df.with_columns(data_base=pl.col("data_entrada"))
    item_df = item_df.with_columns(data_base=pl.col("data_entrada"))
elif date_mode == "entrega":
    pedido_df = pedido_df.with_columns(data_base=pl.col("data_entrega"))
    item_df = item_df.with_columns(data_base=pl.col("data_entrega"))
else:
    pedido_df = pedido_df.with_columns(
        data_base=pl.coalesce([pl.col("data_entrega"), pl.col("data_entrada")])
    )
    item_df = item_df.with_columns(
        data_base=pl.coalesce([pl.col("data_entrega"), pl.col("data_entrada")])
    )

clientes = sorted(
    [c for c in pedido_df.select("cliente").unique().to_series().to_list() if c]
)
vendedores = sorted(
    [v for v in item_df.select("vendedor").unique().to_series().to_list() if v]
)
designers = sorted(
    [d for d in item_df.select("designer").unique().to_series().to_list() if d]
)

with st.sidebar:
    filtro_clientes = st.multiselect("Cliente", clientes)
    filtro_vendedores = st.multiselect("Vendedor", vendedores)
    filtro_designers = st.multiselect("Designer", designers)

if filtro_clientes:
    pedido_df = pedido_df.filter(pl.col("cliente").is_in(filtro_clientes))
    item_df = item_df.filter(pl.col("cliente").is_in(filtro_clientes))
if filtro_vendedores:
    item_df = item_df.filter(pl.col("vendedor").is_in(filtro_vendedores))
if filtro_designers:
    item_df = item_df.filter(pl.col("designer").is_in(filtro_designers))

item_df = _apply_frete_distribution(item_df, frete_mode)

st.subheader("Resumo por pedido")
pedido_resumo = pedido_df.select(
    [
        "pedido_id",
        "numero",
        "cliente",
        "status",
        "data_entrada",
        "data_entrega",
        "valor_total",
        "valor_itens_frete",
        "valor_calculado_api",
        "diff_total_itens",
        "diff_total_api",
    ]
).sort("pedido_id")

totais_pedidos = pedido_resumo.select(
    pl.sum("valor_total").alias("valor_total"),
    pl.sum("valor_itens_frete").alias("valor_itens_frete"),
    pl.sum("valor_calculado_api").alias("valor_calculado_api"),
    pl.sum("diff_total_itens").alias("diff_total_itens"),
    pl.sum("diff_total_api").alias("diff_total_api"),
).with_columns(
    pedido_id=pl.lit(None),
    numero=pl.lit("TOTAL"),
    cliente=pl.lit(None),
    status=pl.lit(None),
    data_entrada=pl.lit(None),
    data_entrega=pl.lit(None),
).select(pedido_resumo.columns)

divergentes = pedido_resumo.filter(
    (pl.col("diff_total_itens").abs() > tolerancia)
    | (pl.col("diff_total_api").abs() > tolerancia)
)

st.metric("Pedidos", pedido_df.height)
st.metric("Pedidos com divergencia", divergentes.height)
st.dataframe(
    pl.concat([divergentes, totais_pedidos], how="vertical").to_pandas(),
    use_container_width=True,
)

st.subheader("Agrupamentos")
group_mode = st.selectbox(
    "Agrupar por",
    ["periodo", "cliente", "vendedor", "designer"],
)

if group_mode == "periodo":
    period = st.selectbox("Periodo", ["dia", "semana", "mes"])
    if period == "dia":
        period_expr = pl.col("data_base")
    elif period == "semana":
        period_expr = pl.col("data_base").dt.truncate("1w")
    else:
        period_expr = pl.col("data_base").dt.truncate("1mo")

    grouped = (
        pedido_df.with_columns(periodo=period_expr)
        .group_by("periodo")
        .agg(
            pl.len().alias("pedidos"),
            pl.sum("valor_total").alias("total_valor_total"),
            pl.sum("valor_itens_frete").alias("total_itens_frete"),
            pl.sum("valor_calculado_api").alias("total_calculado_api"),
        )
        .sort("periodo")
    )
else:
    if group_mode == "cliente":
        grouped = (
            pedido_df.group_by("cliente")
            .agg(
                pl.len().alias("pedidos"),
                pl.sum("valor_total").alias("total_valor_total"),
                pl.sum("valor_itens_frete").alias("total_itens_frete"),
                pl.sum("valor_calculado_api").alias("total_calculado_api"),
            )
            .sort("total_valor_total", descending=True)
        )
    else:
        group_key = "vendedor" if group_mode == "vendedor" else "designer"
        grouped = (
            item_df.group_by(group_key)
            .agg(
                pl.len().alias("items"),
                pl.sum("valor_item").alias("total_itens"),
                pl.sum("valor_item_com_frete").alias("total_itens_com_frete"),
            )
            .sort("total_itens", descending=True)
        )

if not grouped.is_empty():
    total_cols = [col for col in grouped.columns if col != grouped.columns[0]]
    grouped_total = grouped.select([pl.sum(col).alias(col) for col in total_cols])

    key_col = grouped.columns[0]
    grouped_display = grouped.with_columns(pl.col(key_col).cast(pl.Utf8))
    grouped_total = grouped_total.with_columns(
        pl.lit("TOTAL").cast(pl.Utf8).alias(key_col)
    ).select(grouped_display.columns)
    grouped_display = pl.concat([grouped_display, grouped_total], how="vertical")
    st.dataframe(grouped_display.to_pandas(), use_container_width=True)

    chart_df = grouped.to_pandas()
    if group_mode == "periodo":
        fig = px.bar(
            chart_df,
            x="periodo",
            y="total_valor_total",
            title="Total por periodo (valor_total)",
        )
    elif group_mode == "cliente":
        fig = px.bar(
            chart_df,
            x="cliente",
            y="total_valor_total",
            title="Total por cliente (valor_total)",
        )
    else:
        value_col = "total_itens_com_frete" if frete_mode != "nenhum" else "total_itens"
        fig = px.bar(
            chart_df,
            x=group_key,
            y=value_col,
            title=f"Total por {group_key}",
        )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Detalhes por item")
item_detalhes = item_df.select(
    [
        "pedido_id",
        "numero",
        "cliente",
        "status",
        "data_entrada",
        "data_entrega",
        "tipo_producao",
        "descricao",
        "vendedor",
        "designer",
        "valor_item",
        "frete_alocado",
        "valor_item_com_frete",
    ]
)
total_itens = item_detalhes.select(
    pl.sum("valor_item").alias("valor_item"),
    pl.sum("frete_alocado").alias("frete_alocado"),
    pl.sum("valor_item_com_frete").alias("valor_item_com_frete"),
).with_columns(
    pedido_id=pl.lit(None),
    numero=pl.lit("TOTAL"),
    cliente=pl.lit(None),
    status=pl.lit(None),
    data_entrada=pl.lit(None),
    data_entrega=pl.lit(None),
    tipo_producao=pl.lit(None),
    descricao=pl.lit(None),
    vendedor=pl.lit(None),
    designer=pl.lit(None),
).select(item_detalhes.columns)

st.dataframe(
    pl.concat([item_detalhes, total_itens], how="vertical").to_pandas(),
    use_container_width=True,
)
