import argparse
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List

import orjson
from sqlmodel import select

from database.database import async_session_maker, create_db_and_tables
from pedidos.schema import Pedido, Prioridade, Status

STATE_SEPARATOR = "||"

STATUS_SEQUENCE = [
    Status.PENDENTE,
    Status.EM_PRODUCAO,
    Status.PRONTO,
    Status.ENTREGUE,
    Status.CANCELADO,
]


def encode_city_state(cidade: str, estado: str) -> str:
    cidade = (cidade or "").strip()
    estado = (estado or "").strip()
    return f"{cidade}{STATE_SEPARATOR}{estado}" if estado else cidade


def serialize_items(items: List[dict]) -> str:
    return orjson.dumps(items).decode("utf-8")


def build_dataset() -> List[Dict]:
    now = datetime.utcnow()
    base_date = now.date()

    dataset = [
        {
            "numero": "SAMPLE-001",
            "cliente": "Agência Horizonte",
            "telefone_cliente": "(11) 91234-0001",
            "cidade": "São Paulo",
            "estado": "SP",
            "prioridade": Prioridade.ALTA,
            "status": Status.PENDENTE,
            "financeiro": False,
            "conferencia": False,
            "sublimacao": False,
            "costura": False,
            "expedicao": False,
            "pronto": False,
            "observacao": "Feira de negócios internacional",
            "tipo_pagamento": "PIX",
            "obs_pagamento": "Aguardando confirmação",
            "valor_total": "450.00",
            "valor_frete": "20.00",
            "valor_itens": "430.00",
            "forma_envio": "Motoboy",
            "forma_envio_id": 2,
            "sublimacao_maquina": None,
            "sublimacao_data_impressao": None,
            "items": [
                {
                    "id": 1,
                    "tipo_producao": "painel",
                    "descricao": "Painel backdrop 3x2",
                    "largura": "3.00",
                    "altura": "2.00",
                    "metro_quadrado": "6.00",
                    "vendedor": "Marina Sales",
                    "designer": "Carlos Lima",
                    "tecido": "Lona fosca",
                    "acabamento": {"overloque": True, "ilhos": True, "elastico": False},
                    "valor_unitario": "380.00",
                    "observacao": "Aplicar cores corporativas",
                }
            ],
        },
        {
            "numero": "SAMPLE-002",
            "cliente": "Studio Estamparia",
            "telefone_cliente": "(31) 98877-2002",
            "cidade": "Belo Horizonte",
            "estado": "MG",
            "prioridade": Prioridade.NORMAL,
            "status": Status.EM_PRODUCAO,
            "financeiro": True,
            "conferencia": True,
            "sublimacao": True,
            "costura": False,
            "expedicao": False,
            "pronto": False,
            "observacao": "Entrega parcial permitida",
            "tipo_pagamento": "Cartão",
            "obs_pagamento": "2x sem juros",
            "valor_total": "620.00",
            "valor_frete": "0.00",
            "valor_itens": "620.00",
            "forma_envio": "Retirada",
            "forma_envio_id": 5,
            "sublimacao_maquina": "Epson F6370",
            "sublimacao_data_impressao": now.isoformat(),
            "items": [
                {
                    "id": 2,
                    "tipo_producao": "toalha",
                    "descricao": "Toalhas personalizadas 1,5x1,5",
                    "largura": "1.50",
                    "altura": "1.50",
                    "metro_quadrado": "2.25",
                    "vendedor": "Ricardo Prado",
                    "designer": "Fernanda Reis",
                    "tecido": "Oxford",
                    "acabamento": {"overloque": True, "ilhos": False, "elastico": False},
                    "valor_unitario": "155.00",
                    "observacao": "Arte aprovada pelo cliente",
                },
                {
                    "id": 3,
                    "tipo_producao": "banderola",
                    "descricao": "Banderolas promocionais",
                    "largura": "0.80",
                    "altura": "1.80",
                    "metro_quadrado": "1.44",
                    "vendedor": "Ricardo Prado",
                    "designer": "Fernanda Reis",
                    "tecido": "Helanca",
                    "acabamento": {"overloque": False, "ilhos": True, "elastico": True},
                    "valor_unitario": "90.00",
                    "observacao": "Aplicar reforço superior",
                },
            ],
        },
        {
            "numero": "SAMPLE-003",
            "cliente": "Coletivo Criativo",
            "telefone_cliente": "(21) 97766-3003",
            "cidade": "Rio de Janeiro",
            "estado": "RJ",
            "prioridade": Prioridade.ALTA,
            "status": Status.PRONTO,
            "financeiro": True,
            "conferencia": True,
            "sublimacao": True,
            "costura": True,
            "expedicao": True,
            "pronto": True,
            "observacao": "Pedido revisado e embalado",
            "tipo_pagamento": "PIX",
            "obs_pagamento": "Pago integral",
            "valor_total": "780.00",
            "valor_frete": "50.00",
            "valor_itens": "730.00",
            "forma_envio": "Sedex",
            "forma_envio_id": 1,
            "sublimacao_maquina": "Roland XT-640",
            "sublimacao_data_impressao": (now - timedelta(days=1)).isoformat(),
            "items": [
                {
                    "id": 4,
                    "tipo_producao": "painel",
                    "descricao": "Painel dupla face 2x2",
                    "largura": "2.00",
                    "altura": "2.00",
                    "metro_quadrado": "4.00",
                    "vendedor": "Lívia Rocha",
                    "designer": "Arthur Peixoto",
                    "tecido": "Lona blackout",
                    "acabamento": {"overloque": True, "ilhos": True, "elastico": False},
                    "valor_unitario": "420.00",
                    "observacao": "Aplicar zíper inferior",
                }
            ],
        },
        {
            "numero": "SAMPLE-004",
            "cliente": "Eventos Boreal",
            "telefone_cliente": "(41) 98900-4004",
            "cidade": "Curitiba",
            "estado": "PR",
            "prioridade": Prioridade.NORMAL,
            "status": Status.ENTREGUE,
            "financeiro": True,
            "conferencia": True,
            "sublimacao": True,
            "costura": True,
            "expedicao": True,
            "pronto": True,
            "observacao": "Cliente recebeu no dia anterior",
            "tipo_pagamento": "Boleto",
            "obs_pagamento": "Quitado",
            "valor_total": "980.00",
            "valor_frete": "80.00",
            "valor_itens": "900.00",
            "forma_envio": "Transportadora",
            "forma_envio_id": 3,
            "sublimacao_maquina": "Epson F9470",
            "sublimacao_data_impressao": (now - timedelta(days=2)).isoformat(),
            "items": [
                {
                    "id": 5,
                    "tipo_producao": "totem",
                    "descricao": "Totem 0,9x2,1 com base",
                    "largura": "0.90",
                    "altura": "2.10",
                    "metro_quadrado": "1.89",
                    "vendedor": "Bruno Matos",
                    "designer": "Helena Prado",
                    "tecido": "Tecido display",
                    "acabamento": {"overloque": False, "ilhos": False, "elastico": False},
                    "valor_unitario": "320.00",
                    "observacao": "Incluir base metálica",
                }
            ],
        },
        {
            "numero": "SAMPLE-005",
            "cliente": "Promo Nordeste",
            "telefone_cliente": "(81) 98811-5005",
            "cidade": "Recife",
            "estado": "PE",
            "prioridade": Prioridade.NORMAL,
            "status": Status.CANCELADO,
            "financeiro": False,
            "conferencia": True,
            "sublimacao": False,
            "costura": False,
            "expedicao": False,
            "pronto": False,
            "observacao": "Cancelado pelo cliente - evento adiado",
            "tipo_pagamento": "Cartão",
            "obs_pagamento": "Chargeback solicitado",
            "valor_total": "0.00",
            "valor_frete": "0.00",
            "valor_itens": "0.00",
            "forma_envio": "A definir",
            "forma_envio_id": 0,
            "sublimacao_maquina": None,
            "sublimacao_data_impressao": None,
            "items": [
                {
                    "id": 6,
                    "tipo_producao": "lona",
                    "descricao": "Lona frontlight 5x2",
                    "largura": "5.00",
                    "altura": "2.00",
                    "metro_quadrado": "10.00",
                    "vendedor": "Bruno Matos",
                    "designer": "Helena Prado",
                    "tecido": "Lona front",
                    "acabamento": {"overloque": False, "ilhos": True, "elastico": False},
                    "valor_unitario": "0.00",
                    "observacao": "Produção interrompida",
                }
            ],
        },
    ]

    orders: List[Dict] = []
    for offset, data in enumerate(dataset):
        data_entrada = (base_date - timedelta(days=offset)).isoformat()
        data_entrega = (base_date + timedelta(days=7 - offset)).isoformat()
        cidade_encoded = encode_city_state(data.pop("cidade"), data.pop("estado"))
        items_json = serialize_items(data.pop("items"))
        pedido = {
            "data_entrada": data_entrada,
            "data_entrega": data_entrega,
            "cidade_cliente": cidade_encoded,
            "items": items_json,
            "data_criacao": now - timedelta(hours=offset),
            "ultima_atualizacao": now - timedelta(hours=offset),
        }
        pedido.update(data)
        orders.append(pedido)
    return orders


def expand_dataset(target_amount: int) -> List[Pedido]:
    base = build_dataset()
    if target_amount <= len(base):
        selected = base[:target_amount]
    else:
        selected = base.copy()
        counter = len(base) + 1
        while len(selected) < target_amount:
            template = random.choice(base)
            clone = template.copy()
            status = STATUS_SEQUENCE[len(selected) % len(STATUS_SEQUENCE)]
            clone["status"] = status
            clone["numero"] = f"SAMPLE-{counter:03d}"
            clone["cliente"] = f"{template['cliente']} #{counter}"
            entrada_dt = datetime.fromisoformat(template["data_entrada"]) + timedelta(days=counter)
            entrega_dt = datetime.fromisoformat(template["data_entrega"]) + timedelta(days=counter)
            clone["data_entrada"] = entrada_dt.isoformat()
            clone["data_entrega"] = entrega_dt.isoformat()
            clone["data_criacao"] = template["data_criacao"] + timedelta(days=counter)
            clone["ultima_atualizacao"] = template["ultima_atualizacao"] + timedelta(days=counter)
            selected.append(clone)
            counter += 1

    pedidos: List[Pedido] = []
    for payload in selected:
        pedidos.append(Pedido(**payload))
    return pedidos


async def seed_orders(amount: int) -> None:
    await create_db_and_tables()
    orders = expand_dataset(amount)

    async with async_session_maker() as session:
        result = await session.exec(select(Pedido.numero))
        existing_numbers = set(result.all())
        created = 0

        for pedido in orders:
            if pedido.numero in existing_numbers:
                continue
            session.add(pedido)
            created += 1

        if created:
            await session.commit()

        print(f"✅ {created} pedidos de exemplo criados." if created else "ℹ️ Nenhum novo pedido criado (já existentes).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed de pedidos de exemplo.")
    parser.add_argument(
        "--amount",
        "-n",
        type=int,
        default=5,
        help="Quantidade de pedidos a criar (default: 5)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_orders(max(1, args.amount)))
