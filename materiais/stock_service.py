from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .schema import Material


def normalize_material_name(nome: str) -> str:
    return " ".join(nome.strip().casefold().split())


def parse_decimal_value(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if not raw:
        return 0.0

    filtered = "".join(ch for ch in raw if ch.isdigit() or ch in ",.-")
    if not filtered:
        return 0.0

    if "," in filtered and "." in filtered:
        if filtered.rfind(",") > filtered.rfind("."):
            filtered = filtered.replace(".", "").replace(",", ".")
        else:
            filtered = filtered.replace(",", "")
    elif "," in filtered:
        filtered = filtered.replace(",", ".")

    try:
        return float(filtered)
    except ValueError:
        return 0.0


def extract_item_material_name(item: Any) -> str | None:
    value = getattr(item, "tecido", None)
    if value is None and isinstance(item, dict):
        value = item.get("tecido")
    if value is None:
        return None

    nome = str(value).strip()
    return nome or None


def calculate_item_consumption_meters(item: Any) -> float:
    metro_quadrado = getattr(item, "metro_quadrado", None)
    if metro_quadrado is None and isinstance(item, dict):
        metro_quadrado = item.get("metro_quadrado")

    consumo = parse_decimal_value(metro_quadrado)
    if consumo > 0:
        return consumo

    largura = getattr(item, "largura", None)
    altura = getattr(item, "altura", None)
    if isinstance(item, dict):
        largura = item.get("largura", largura)
        altura = item.get("altura", altura)

    largura_num = parse_decimal_value(largura)
    altura_num = parse_decimal_value(altura)
    fallback = largura_num * altura_num
    if fallback > 0:
        return fallback

    return 1.0


def summarize_material_consumption(items: list[Any]) -> dict[str, float]:
    resumo: dict[str, float] = defaultdict(float)
    for item in items or []:
        nome = extract_item_material_name(item)
        if not nome:
            continue

        nome_normalizado = normalize_material_name(nome)
        if not nome_normalizado:
            continue

        resumo[nome_normalizado] += calculate_item_consumption_meters(item)

    return dict(resumo)


def is_stock_eligible_status(status: Any) -> bool:
    if status is None:
        return True
    valor = getattr(status, "value", status)
    return str(valor).strip().lower() != "cancelado"


def build_material_stock_delta(
    consumo_anterior: dict[str, float],
    consumo_novo: dict[str, float],
) -> dict[str, float]:
    chaves = set(consumo_anterior.keys()) | set(consumo_novo.keys())
    delta: dict[str, float] = {}
    for nome in chaves:
        valor = float(consumo_novo.get(nome, 0.0)) - float(consumo_anterior.get(nome, 0.0))
        if abs(valor) > 1e-9:
            delta[nome] = valor
    return delta


async def apply_material_stock_delta(session: AsyncSession, delta: dict[str, float]) -> None:
    if not delta:
        return

    materiais_result = await session.exec(select(Material))
    materiais = materiais_result.all()

    catalogo: dict[str, Material] = {}
    for material in materiais:
        chave = normalize_material_name(material.nome)
        existente = catalogo.get(chave)
        if not existente:
            catalogo[chave] = material
            continue

        if bool(material.ativo) and not bool(existente.ativo):
            catalogo[chave] = material
            continue

        if material.id is not None and existente.id is not None and material.id < existente.id:
            catalogo[chave] = material

    for nome_normalizado, variacao in delta.items():
        material = catalogo.get(nome_normalizado)
        if not material:
            continue

        estoque_atual = float(material.estoque_metros or 0.0)
        novo_estoque = estoque_atual - float(variacao)
        if novo_estoque < -1e-9:
            nome = material.nome
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Estoque insuficiente para o material '{nome}'. "
                    f"Disponível: {estoque_atual:.2f}m, necessário: {variacao:.2f}m."
                ),
            )

        material.estoque_metros = round(max(novo_estoque, 0.0), 4)
        session.add(material)
