"""
pedidos/pricing.py
==================
Módulo centralizado de cálculo de preços de itens e pedidos.

O backend recalcula o valor_unitario a partir dos campos componentes
antes de persistir, tornando-se a fonte da verdade para cálculos financeiros.

Regra de negócio (painel / generica / mesa_babado):
    valor_unitario = valor_painel
                   + valores_adicionais
                   + (quantidade_ilhos × valor_ilhos)   [se tipo_acabamento indicar ilhós]
                   + (quantidade_cordinha × valor_cordinha) [se tipo_acabamento indicar cordinha]

    subtotal_item  = valor_unitario × quantidade
    valor_itens    = Σ subtotal_item
    valor_total    = valor_itens + valor_frete
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# Tipos de produção que têm seus extras (ilhós, cordinha, adicionais)
# somados ao valor_unitario pelo backend.
TIPOS_COM_COMPONENTES = frozenset({"painel", "generica", "mesa_babado"})

# Mapa de tipo → campo de quantidade correspondente
_TIPO_QTD_FIELD: dict[str, str] = {
    "painel": "quantidade_paineis",
    "generica": "quantidade_paineis",
    "mesa_babado": "quantidade_paineis",
    "totem": "quantidade_totem",
    "lona": "quantidade_lona",
    "adesivo": "quantidade_adesivo",
    "canga": "quantidade_canga",
    "impressao_3d": "quantidade_impressao_3d",
    "mochilinha": "quantidade_mochilinha",
    "bolsinha": "quantidade_mochilinha",
}


def _get_value(item: Any, key: str, default: Any = None) -> Any:
    """Extrai valor de um item, seja ele dict ou objeto (Pydantic/SQLModel)."""
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(key, default)
    # Tenta atributo (para objetos Pydantic/SQLModel)
    return getattr(item, key, default)


def parse_money(value: Any) -> Decimal:
    """Converte string/int/float/None → Decimal monetário com 2 casas decimais.

    Aceita formatos pt-BR (vírgula decimal, pontos de milhar) e en-US.
    Exemplos:
        parse_money("100,50") → Decimal("100.50")
        parse_money("1.234,56") → Decimal("1234.56")
        parse_money("100.00")  → Decimal("100.00")
        parse_money(None)      → Decimal("0.00")
    """
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(value, str):
        cleaned = value.strip().replace("R$", "").strip()
        # Detectar formato pt-BR (vírgula como decimal)
        if "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal("0.00")
    return Decimal("0.00")


def _parse_qty(value: Any) -> Decimal:
    """Converte uma quantidade para Decimal inteiro (mínimo 1)."""
    try:
        qty = Decimal(str(value).replace(",", ".").strip()).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return qty if qty >= 1 else Decimal("1")
    except Exception:
        return Decimal("1")


def calculate_item_unit_price(item: Any) -> Decimal:
    """Recalcula valor_unitario de um item a partir dos campos componentes.

    Para itens do tipo painel/generica/mesa_babado:
        valor_unitario = valor_painel
                       + valores_adicionais
                       + (quantidade_ilhos × valor_ilhos)     [se acabamento for ilhós]
                       + (quantidade_cordinha × valor_cordinha) [se acabamento for cordinha]

    Para todos os outros tipos, retorna o valor_unitario enviado pelo frontend
    sem modificação (o backend não impõe regra sobre esses tipos).
    """
    tipo = (_get_value(item, "tipo_producao") or "").lower().strip()

    if tipo not in TIPOS_COM_COMPONENTES:
        return parse_money(_get_value(item, "valor_unitario"))

    base = parse_money(_get_value(item, "valor_painel"))
    adicionais = parse_money(_get_value(item, "valores_adicionais"))

    tipo_acabamento = (_get_value(item, "tipo_acabamento") or "").lower().strip()

    # Ilhós
    valor_ilhos = Decimal("0.00")
    if "ilho" in tipo_acabamento:
        qtd_ilhos = _parse_qty(_get_value(item, "quantidade_ilhos") or 0)
        preco_ilho = parse_money(_get_value(item, "valor_ilhos"))
        valor_ilhos = qtd_ilhos * preco_ilho

    # Cordinha
    valor_cordinha = Decimal("0.00")
    if "cordinha" in tipo_acabamento:
        qtd_cordinha = _parse_qty(_get_value(item, "quantidade_cordinha") or 0)
        preco_cordinha = parse_money(_get_value(item, "valor_cordinha"))
        valor_cordinha = qtd_cordinha * preco_cordinha

    total = base + adicionais + valor_ilhos + valor_cordinha
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recalculate_items_totals(items: list[Any]) -> list[dict[str, Any]]:
    """Recalcula valor_unitario de todos os itens de painel/generica/mesa_babado.

    Retorna uma nova lista de DICTS com os itens corrigidos.
    Itens de outros tipos são retornados como dicts sem alteração financeira.
    """
    result: list[dict[str, Any]] = []
    for item in items:
        # Converter para dict se for objeto Pydantic/SQLModel
        if not isinstance(item, dict):
            if hasattr(item, "model_dump"):
                item_dict = item.model_dump(exclude_none=True)
            elif hasattr(item, "dict"):
                item_dict = item.dict()
            else:
                item_dict = vars(item).copy()
        else:
            item_dict = item.copy()

        tipo = (_get_value(item_dict, "tipo_producao") or "").lower().strip()
        if tipo in TIPOS_COM_COMPONENTES:
            new_unit_price = calculate_item_unit_price(item_dict)
            item_dict["valor_unitario"] = str(new_unit_price)

        result.append(item_dict)
    return result


def _derive_item_qty(item: Any) -> Decimal:
    """Determina a quantidade de um item baseado no tipo de produção."""
    tipo = (_get_value(item, "tipo_producao") or "").lower().strip()
    qty_field = _TIPO_QTD_FIELD.get(tipo, "quantidade_paineis")
    raw_qty = (
        _get_value(item, qty_field) or _get_value(item, "quantidade_paineis") or "1"
    )
    return _parse_qty(raw_qty)


def calculate_order_totals(
    items: list[dict[str, Any]], valor_frete: Any
) -> dict[str, str]:
    """Calcula valor_itens e valor_total do pedido a partir dos itens.

    Args:
        items: Lista de dicts de item (já com valor_unitario recalculado).
        valor_frete: Valor do frete (string/número/None).

    Returns:
        Dict com 'valor_itens' e 'valor_total' como strings "X.XX".
    """
    frete = parse_money(valor_frete)
    valor_itens = Decimal("0.00")

    for item in items:
        unit_price = parse_money(_get_value(item, "valor_unitario"))
        qty = _derive_item_qty(item)
        valor_itens += unit_price * qty

    valor_itens = valor_itens.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    valor_total = (valor_itens + frete).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "valor_itens": str(valor_itens),
        "valor_total": str(valor_total),
    }


# ---------------------------------------------------------------------------
# Guardrail: normalização obrigatória antes de persistir
# ---------------------------------------------------------------------------

class FinancialInconsistencyError(ValueError):
    """Levantado quando valor_total diverge da soma dos itens + frete.

    Em produção normal não deve ocorrer pois normalize_order_financials
    sempre recalcula antes de persistir. Útil como tripwire em testes.
    """


def normalize_order_financials(
    items: list[Any],
    valor_frete: Any,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Guardrail central: recalcula items e totais antes de qualquer persistência.

    Esta é a ÚNICA porta de entrada para salvar pedidos com dados financeiros.
    Qualquer endpoint (criação, atualização, sync) DEVE passar por aqui antes
    de persistir items ou valor_total.

    Fluxo:
        1. Recalcula valor_unitario de cada item do tipo painel/generica/mesa_babado
           a partir dos campos componentes (valor_painel, ilhós, cordinha, adicionais).
        2. Recalcula valor_itens = Σ (valor_unitario × quantidade).
        3. Recalcula valor_total = valor_itens + valor_frete.
        4. Retorna (items_normalizados, {valor_itens, valor_total}).

    Args:
        items: Lista de dicts de item (como vinda do frontend ou banco).
        valor_frete: Frete do pedido (string/número/None).

    Returns:
        Tupla (items_normalizados, totais) onde totais é um dict com
        'valor_itens' e 'valor_total' como strings "X.XX".
    """
    items_normalizados = recalculate_items_totals(items)
    totais = calculate_order_totals(items_normalizados, valor_frete)
    return items_normalizados, totais


def assert_order_financials_consistent(
    items: list[dict[str, Any]],
    valor_frete: Any,
    valor_total_persistido: Any,
    *,
    tolerance: Decimal = Decimal("0.02"),
) -> None:
    """Verifica que o valor_total persistido é consistente com a soma dos itens + frete.

    Uso principal: testes automatizados de regressão.

    Args:
        items: Lista de itens já normalizados e persistidos.
        valor_frete: Valor do frete persistido.
        valor_total_persistido: valor_total salvo no banco.
        tolerance: Diferença máxima tolerada (default: R$ 0,02 por arredondamento).

    Raises:
        FinancialInconsistencyError: se a diferença for maior que a tolerância.
    """
    totais = calculate_order_totals(items, valor_frete)
    esperado = parse_money(totais["valor_total"])
    real = parse_money(valor_total_persistido)

    diff = abs(esperado - real)
    if diff > tolerance:
        raise FinancialInconsistencyError(
            f"Inconsistência financeira detectada: "
            f"valor_total={real} ≠ soma(items)+frete={esperado} "
            f"(diferença={diff})"
        )
