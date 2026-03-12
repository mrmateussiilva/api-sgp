"""
tests/test_pricing.py
=====================
Testes unitários para o módulo pedidos/pricing.py.

Cobre as funções de cálculo de preço de itens e totais de pedidos,
incluindo o caso principal do bug: painel com ilhós.
"""
from decimal import Decimal
import pytest
from pedidos.pricing import (
    parse_money,
    calculate_item_unit_price,
    recalculate_items_totals,
    calculate_order_totals,
)


# ---------------------------------------------------------------------------
# parse_money
# ---------------------------------------------------------------------------

class TestParseMoney:
    def test_none_retorna_zero(self):
        assert parse_money(None) == Decimal("0.00")

    def test_string_formato_ptbr_virgula(self):
        assert parse_money("100,50") == Decimal("100.50")

    def test_string_formato_ptbr_ponto_milhar(self):
        assert parse_money("1.234,56") == Decimal("1234.56")

    def test_string_formato_enus(self):
        assert parse_money("100.00") == Decimal("100.00")

    def test_inteiro(self):
        assert parse_money(100) == Decimal("100.00")

    def test_float(self):
        assert parse_money(1.5) == Decimal("1.50")

    def test_string_com_prefixo_real(self):
        assert parse_money("R$ 100,00") == Decimal("100.00")

    def test_string_vazia_retorna_zero(self):
        assert parse_money("") == Decimal("0.00")

    def test_string_invalida_retorna_zero(self):
        assert parse_money("abc") == Decimal("0.00")


# ---------------------------------------------------------------------------
# calculate_item_unit_price
# ---------------------------------------------------------------------------

class TestCalculateItemUnitPrice:
    """Testa cálculo do preço unitário de um item."""

    def test_painel_sem_extras(self):
        """Painel simples sem ilhós ou cordinha: apenas valor_painel."""
        item = {
            "tipo_producao": "painel",
            "valor_painel": "100.00",
            "tipo_acabamento": "nenhum",
        }
        assert calculate_item_unit_price(item) == Decimal("100.00")

    def test_painel_com_valores_adicionais(self):
        """Painel com valores adicionais."""
        item = {
            "tipo_producao": "painel",
            "valor_painel": "100.00",
            "valores_adicionais": "20.00",
            "tipo_acabamento": "nenhum",
        }
        assert calculate_item_unit_price(item) == Decimal("120.00")

    def test_painel_com_ilhos(self):
        """
        CASO PRINCIPAL DO BUG:
        painel=100, 18 ilhós de R$1,00 → esperado 118,00
        """
        item = {
            "tipo_producao": "painel",
            "valor_painel": "100.00",
            "tipo_acabamento": "ilhos",
            "quantidade_ilhos": "18",
            "valor_ilhos": "1.00",
        }
        assert calculate_item_unit_price(item) == Decimal("118.00")

    def test_painel_com_cordinha(self):
        """Painel com cordinha."""
        item = {
            "tipo_producao": "painel",
            "valor_painel": "100.00",
            "tipo_acabamento": "cordinha",
            "quantidade_cordinha": "10",
            "valor_cordinha": "2.00",
        }
        assert calculate_item_unit_price(item) == Decimal("120.00")

    def test_painel_com_todos_extras(self):
        """Painel com ilhós, cordinha e valores adicionais (tipo_acabamento geral)."""
        item = {
            "tipo_producao": "painel",
            "valor_painel": "100.00",
            "valores_adicionais": "10.00",
            "tipo_acabamento": "ilhos",
            "quantidade_ilhos": "18",
            "valor_ilhos": "1.00",
            # cordinha não é somada: tipo_acabamento é 'ilhos', não 'cordinha'
        }
        assert calculate_item_unit_price(item) == Decimal("128.00")

    def test_generica_com_ilhos(self):
        """Tipo 'generica' segue a mesma regra que painel."""
        item = {
            "tipo_producao": "generica",
            "valor_painel": "50.00",
            "tipo_acabamento": "ilhos",
            "quantidade_ilhos": "10",
            "valor_ilhos": "0.50",
        }
        assert calculate_item_unit_price(item) == Decimal("55.00")

    def test_mesa_babado_com_ilhos(self):
        """Tipo 'mesa_babado' segue a mesma regra que painel."""
        item = {
            "tipo_producao": "mesa_babado",
            "valor_painel": "80.00",
            "tipo_acabamento": "ilhos",
            "quantidade_ilhos": "8",
            "valor_ilhos": "2.00",
        }
        assert calculate_item_unit_price(item) == Decimal("96.00")

    def test_tipo_formato_case_insensitive(self):
        """Tipo de produção deve ser insensível a maiúsculas."""
        item = {
            "tipo_producao": "PAINEL",
            "valor_painel": "100.00",
            "tipo_acabamento": "ilhos",
            "quantidade_ilhos": "18",
            "valor_ilhos": "1.00",
        }
        assert calculate_item_unit_price(item) == Decimal("118.00")

    def test_outro_tipo_retorna_valor_unitario_existente(self):
        """Tipos que não são painel/generica/mesa_babado devem retornar valor_unitario sem recalcular."""
        item = {
            "tipo_producao": "lona",
            "valor_unitario": "200.00",
            "valor_lona": "150.00",
        }
        assert calculate_item_unit_price(item) == Decimal("200.00")

    def test_totem_retorna_valor_unitario(self):
        """Totem não pode ser recalculado pelo backend como painel."""
        item = {
            "tipo_producao": "totem",
            "valor_unitario": "350.00",
            "valor_totem": "300.00",
        }
        assert calculate_item_unit_price(item) == Decimal("350.00")

    def test_valores_em_formato_ptbr(self):
        """Aceita valores no formato brasileiro (vírgula como separador decimal)."""
        item = {
            "tipo_producao": "painel",
            "valor_painel": "100,00",
            "tipo_acabamento": "ilhos",
            "quantidade_ilhos": "18",
            "valor_ilhos": "1,00",
        }
        assert calculate_item_unit_price(item) == Decimal("118.00")

    def test_campos_ausentes_tratados_como_zero(self):
        """Campos ausentes não devem causar erro — devem ser tratados como zero."""
        item = {
            "tipo_producao": "painel",
            "tipo_acabamento": "ilhos",
            # valor_painel, quantidade_ilhos, valor_ilhos ausentes
        }
        assert calculate_item_unit_price(item) == Decimal("0.00")


# ---------------------------------------------------------------------------
# recalculate_items_totals
# ---------------------------------------------------------------------------

class TestRecalculateItemsTotals:
    def test_recalcula_apenas_itens_painel(self):
        items = [
            {
                "tipo_producao": "painel",
                "valor_painel": "100.00",
                "tipo_acabamento": "ilhos",
                "quantidade_ilhos": "18",
                "valor_ilhos": "1.00",
            },
            {
                "tipo_producao": "totem",
                "valor_unitario": "500.00",
            },
        ]
        result = recalculate_items_totals(items)

        assert Decimal(result[0]["valor_unitario"]) == Decimal("118.00")
        assert Decimal(result[1]["valor_unitario"]) == Decimal("500.00")

    def test_nao_modifica_lista_original(self):
        """A função não deve modificar os dicts originais."""
        original_valor = "50.00"
        items = [
            {
                "tipo_producao": "painel",
                "valor_painel": original_valor,
                "tipo_acabamento": "nenhum",
            }
        ]
        recalculate_items_totals(items)
        assert items[0].get("valor_unitario") is None  # original não foi tocado


# ---------------------------------------------------------------------------
# calculate_order_totals
# ---------------------------------------------------------------------------

class TestCalculateOrderTotals:
    def test_total_sem_frete(self):
        items = [
            {
                "tipo_producao": "painel",
                "valor_unitario": "118.00",
                "quantidade_paineis": "1",
            }
        ]
        result = calculate_order_totals(items, "0.00")
        assert result["valor_itens"] == "118.00"
        assert result["valor_total"] == "118.00"

    def test_total_com_frete(self):
        items = [
            {
                "tipo_producao": "painel",
                "valor_unitario": "118.00",
                "quantidade_paineis": "1",
            }
        ]
        result = calculate_order_totals(items, "20.00")
        assert result["valor_itens"] == "118.00"
        assert result["valor_total"] == "138.00"

    def test_multiplos_itens(self):
        items = [
            {
                "tipo_producao": "painel",
                "valor_unitario": "100.00",
                "quantidade_paineis": "2",
            },
            {
                "tipo_producao": "totem",
                "valor_unitario": "50.00",
                "quantidade_totem": "3",
            },
        ]
        result = calculate_order_totals(items, "0.00")
        # 100*2 + 50*3 = 200 + 150 = 350
        assert result["valor_itens"] == "350.00"
        assert result["valor_total"] == "350.00"

    def test_frete_none_tratado_como_zero(self):
        items = [{"tipo_producao": "painel", "valor_unitario": "100.00", "quantidade_paineis": "1"}]
        result = calculate_order_totals(items, None)
        assert result["valor_total"] == "100.00"

    def test_lista_vazia(self):
        result = calculate_order_totals([], "0.00")
        assert result["valor_itens"] == "0.00"
        assert result["valor_total"] == "0.00"

    def test_caso_principal_do_bug(self):
        """
        CASO PRINCIPAL DO BUG (end-to-end):
        painel=100 + 18 ilhós de R$1 → valor_unitario=118 → total=118
        """
        items = [
            {
                "tipo_producao": "painel",
                "valor_painel": "100.00",
                "tipo_acabamento": "ilhos",
                "quantidade_ilhos": "18",
                "valor_ilhos": "1.00",
                "quantidade_paineis": "1",
            }
        ]
        # Simula o fluxo completo do backend
        items_recalculados = recalculate_items_totals(items)
        result = calculate_order_totals(items_recalculados, "0.00")

        assert Decimal(items_recalculados[0]["valor_unitario"]) == Decimal("118.00")
        assert result["valor_itens"] == "118.00"
        assert result["valor_total"] == "118.00"
