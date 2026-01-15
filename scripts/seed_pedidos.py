import argparse
import asyncio
import os
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles
import orjson
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_file_has_key(key: str) -> bool:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.split("=", 1)[0].strip() == key:
            return True
    return False


def _configure_shared_defaults() -> None:
    if os.environ.get("DATABASE_URL") or _env_file_has_key("DATABASE_URL"):
        return
    if not (os.environ.get("API_ROOT") or _env_file_has_key("API_ROOT")):
        return
    api_root = Path(os.environ.get("API_ROOT") or PROJECT_ROOT)
    shared_dir = api_root / "shared"
    if not shared_dir.exists():
        return
    os.environ.setdefault("API_ROOT", str(api_root))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{shared_dir / 'db' / 'banco.db'}")
    os.environ.setdefault("MEDIA_ROOT", str(shared_dir / "media"))
    os.environ.setdefault("LOG_DIR", str(shared_dir / "logs"))


_configure_shared_defaults()

from database.database import async_session_maker, create_db_and_tables
from pedidos.schema import Pedido, PedidoImagem, Prioridade, Status
from pedidos.images import store_image_bytes

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


def _parse_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{label} invalida. Use YYYY-MM-DD.") from exc


def _pick_delivery_date(start: date, end: date) -> date:
    if start > end:
        raise ValueError("data inicial deve ser menor ou igual a data final.")
    if start == end:
        return start
    delta_days = (end - start).days
    offset = random.randint(0, delta_days)
    return start + timedelta(days=offset)


def _build_date_fields(
    base_date: date,
    offset: int,
    start_date: Optional[date],
    end_date: Optional[date],
) -> Tuple[str, str, datetime, datetime]:
    if start_date and end_date:
        entrega_date = _pick_delivery_date(start_date, end_date)
        entrada_date = entrega_date - timedelta(days=random.randint(0, 5))
        created_at = datetime.combine(
            entrada_date, time(hour=random.randint(8, 18), minute=random.randint(0, 59))
        )
        updated_at = created_at + timedelta(hours=random.randint(0, 12))
        return (
            entrada_date.isoformat(),
            entrega_date.isoformat(),
            created_at,
            updated_at,
        )

    data_entrada = (base_date - timedelta(days=offset)).isoformat()
    data_entrega = (base_date + timedelta(days=7 - offset)).isoformat()
    created_at = datetime.utcnow() - timedelta(hours=offset)
    return data_entrada, data_entrega, created_at, created_at


def build_dataset(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
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
        data_entrada, data_entrega, created_at, updated_at = _build_date_fields(
            base_date,
            offset,
            start_date,
            end_date,
        )
        cidade_encoded = encode_city_state(
            data.pop("cidade"), data.pop("estado"))
        items_json = serialize_items(data.pop("items"))
        pedido = {
            "data_entrada": data_entrada,
            "data_entrega": data_entrega,
            "cidade_cliente": cidade_encoded,
            "items": items_json,
            "data_criacao": created_at,
            "ultima_atualizacao": updated_at,
        }
        pedido.update(data)
        orders.append(pedido)
    return orders


def expand_dataset(
    target_amount: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Pedido]:
    base = build_dataset(start_date, end_date)
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
            if start_date and end_date:
                data_entrada, data_entrega, created_at, updated_at = _build_date_fields(
                    date.today(),
                    counter,
                    start_date,
                    end_date,
                )
                clone["data_entrada"] = data_entrada
                clone["data_entrega"] = data_entrega
                clone["data_criacao"] = created_at
                clone["ultima_atualizacao"] = updated_at
            else:
                entrada_dt = datetime.fromisoformat(
                    template["data_entrada"]) + timedelta(days=counter)
                entrega_dt = datetime.fromisoformat(
                    template["data_entrega"]) + timedelta(days=counter)
                clone["data_entrada"] = entrada_dt.isoformat()
                clone["data_entrega"] = entrega_dt.isoformat()
                clone["data_criacao"] = template["data_criacao"] + \
                    timedelta(days=counter)
                clone["ultima_atualizacao"] = template["ultima_atualizacao"] + \
                    timedelta(days=counter)
            selected.append(clone)
            counter += 1

    pedidos: List[Pedido] = []
    for payload in selected:
        pedidos.append(Pedido(**payload))
    return pedidos


async def _attach_images_for_order(
    session: AsyncSession,
    pedido: Pedido,
    items: List[dict],
    image_data: bytes,
    mime_type: str,
    original_name: str,
) -> None:
    for index, item in enumerate(items):
        identifier = item.get("id")
        item_identificador = str(identifier) if identifier is not None else None
        relative_path, filename, size = await store_image_bytes(
            pedido.id,
            image_data,
            mime_type,
            original_filename=original_name,
        )
        session.add(
            PedidoImagem(
                pedido_id=pedido.id,
                item_index=index,
                item_identificador=item_identificador,
                filename=filename,
                mime_type=mime_type,
                path=relative_path,
                tamanho=size,
            )
        )


async def seed_orders(
    amount: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    image_path: Optional[Path] = None,
) -> None:
    await create_db_and_tables()
    orders = expand_dataset(amount, start_date, end_date)
    image_data: Optional[bytes] = None
    mime_type: Optional[str] = None
    original_name: Optional[str] = None

    if image_path:
        if not image_path.exists() or not image_path.is_file():
            raise FileNotFoundError(f"Imagem nao encontrada: {image_path}")
        original_name = image_path.name
        mime_type = "image/jpeg"
        guessed = Path(image_path).suffix.lower()
        if guessed:
            import mimetypes

            mime_type = mimetypes.guess_type(str(image_path))[0] or mime_type
        async with aiofiles.open(image_path, "rb") as file_obj:
            image_data = await file_obj.read()

    async with async_session_maker() as session:
        result = await session.exec(select(Pedido.numero))
        existing_numbers = set(result.all())
        created = 0
        created_orders: List[Pedido] = []

        for pedido in orders:
            if pedido.numero in existing_numbers:
                continue
            session.add(pedido)
            created_orders.append(pedido)
            created += 1

        if created:
            await session.commit()
            for pedido in created_orders:
                await session.refresh(pedido)

        if created_orders and image_data and mime_type and original_name:
            for pedido in created_orders:
                items_payload = orjson.loads(pedido.items or "[]")
                await _attach_images_for_order(
                    session,
                    pedido,
                    items_payload,
                    image_data,
                    mime_type,
                    original_name,
                )
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
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Data inicial para data_entrega (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Data final para data_entrega (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--image-path",
        type=str,
        default=None,
        help="Caminho para uma imagem a aplicar em todos os itens.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    start_date = _parse_date(args.start_date, "data inicial")
    end_date = _parse_date(args.end_date, "data final")
    if (start_date and not end_date) or (end_date and not start_date):
        raise ValueError("Informe data inicial e data final juntas.")
    image_path = Path(args.image_path) if args.image_path else None
    asyncio.run(seed_orders(max(1, args.amount), start_date, end_date, image_path))
