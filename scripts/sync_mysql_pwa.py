"""
Script de carga inicial para sincronizar pedidos, imagens (miniaturas) e usuários
para um MySQL remoto (PWA).

Requisitos:
- Variáveis no .env: DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME
- Dependências: pymysql, pillow

Uso:
  uv run python scripts/sync_mysql_pwa.py --passwords-file scripts/usuarios_plain.json
  (se não informar, será enviado o password_hash existente)
"""

from __future__ import annotations

import argparse
import base64
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from PIL import Image
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlmodel import Session, select
from sqlalchemy.engine import URL

from config import settings
from database.database import engine as local_engine
from pedidos.images import absolute_media_path
from pedidos.schema import Pedido, PedidoImagem
from auth.models import User


LOGGER = logging.getLogger("mysql_sync")
THUMBNAIL_SIZE = (300, 300)
JPEG_QUALITY = 60


def _build_mysql_url() -> str:
    if not all([settings.DB_USER, settings.DB_PASS, settings.DB_HOST, settings.DB_NAME]):
        raise ValueError("DB_USER/DB_PASS/DB_HOST/DB_NAME precisam estar configurados no .env")
    return URL.create(
        drivername="mysql+pymysql",
        username=settings.DB_USER,
        password=settings.DB_PASS,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    ).render_as_string(hide_password=False)


def _load_passwords_map(path: Optional[str]) -> Dict[str, str]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    import json

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return {str(k): str(v) for k, v in payload.items()}
    if isinstance(payload, list):
        result = {}
        for entry in payload:
            if isinstance(entry, dict) and "username" in entry and "password" in entry:
                result[str(entry["username"])] = str(entry["password"])
        return result
    raise ValueError("Formato inválido. Use dict {user: pass} ou lista de {username, password}.")


def _thumbnail_to_base64(image_path: str) -> Optional[str]:
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail(THUMBNAIL_SIZE)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:
        LOGGER.warning("Falha ao gerar miniatura (%s): %s", image_path, exc)
        return None


def _define_tables(metadata: MetaData) -> dict[str, Table]:
    pwa_pedidos = Table(
        "pwa_pedidos",
        metadata,
        Column("pedido_id", Integer, primary_key=True),
        Column("numero", String(50)),
        Column("data_entrada", String(20)),
        Column("data_entrega", String(20)),
        Column("observacao", Text),
        Column("prioridade", String(20)),
        Column("status", String(50)),
        Column("cliente", String(255)),
        Column("telefone_cliente", String(50)),
        Column("cidade_cliente", String(255)),
        Column("valor_total", String(50)),
        Column("valor_frete", String(50)),
        Column("valor_itens", String(50)),
        Column("tipo_pagamento", String(100)),
        Column("obs_pagamento", Text),
        Column("forma_envio", String(100)),
        Column("forma_envio_id", Integer),
        Column("financeiro", Boolean),
        Column("conferencia", Boolean),
        Column("sublimacao", Boolean),
        Column("costura", Boolean),
        Column("expedicao", Boolean),
        Column("pronto", Boolean),
        Column("sublimacao_maquina", String(100)),
        Column("sublimacao_data_impressao", String(50)),
        Column("items_json", Text),
        Column("data_criacao", DateTime),
        Column("ultima_atualizacao", DateTime),
    )

    pwa_pedido_imagens = Table(
        "pwa_pedido_imagens",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("pedido_id", Integer, index=True),
        Column("item_index", Integer),
        Column("item_identificador", String(100)),
        Column("mime_type", String(50)),
        Column("filename", String(255)),
        Column("image_base64", Text),
        Column("criado_em", DateTime),
    )

    pwa_users = Table(
        "pwa_users",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("username", String(150), unique=True, index=True),
        Column("password", String(255)),
        Column("is_admin", Boolean),
        Column("is_active", Boolean),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    return {
        "pwa_pedidos": pwa_pedidos,
        "pwa_pedido_imagens": pwa_pedido_imagens,
        "pwa_users": pwa_users,
    }


def _upsert_rows(conn, table: Table, rows: Iterable[dict], pk_fields: Optional[List[str]] = None) -> None:
    pk_fields = pk_fields or []
    for row in rows:
        stmt = mysql_insert(table).values(**row)
        update_data = {k: v for k, v in row.items() if k not in pk_fields}
        if not update_data:
            update_data = row
        stmt = stmt.on_duplicate_key_update(**update_data)
        conn.execute(stmt)


def _sync_users(conn, table: Table, passwords_map: Dict[str, str]) -> None:
    with Session(local_engine.sync_engine) as session:
        users = session.exec(select(User)).all()

    rows = []
    for user in users:
        plain = passwords_map.get(user.username)
        if not plain:
            # Sem senha em texto disponível -> usa hash existente
            plain = user.password_hash
        rows.append(
            {
                "username": user.username,
                "password": plain,
                "is_admin": bool(user.is_admin),
                "is_active": bool(user.is_active),
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }
        )

    if rows:
        _upsert_rows(conn, table, rows, pk_fields=["id"])
        LOGGER.info("Usuarios sincronizados: %s", len(rows))
    else:
        LOGGER.info("Nenhum usuario sincronizado.")


def _sync_pedidos(conn, table: Table) -> None:
    with Session(local_engine.sync_engine) as session:
        pedidos = session.exec(select(Pedido)).all()

    rows = []
    for pedido in pedidos:
        rows.append(
            {
                "pedido_id": pedido.id,
                "numero": pedido.numero,
                "data_entrada": pedido.data_entrada,
                "data_entrega": pedido.data_entrega,
                "observacao": pedido.observacao,
                "prioridade": str(pedido.prioridade) if pedido.prioridade else None,
                "status": pedido.status.value if hasattr(pedido.status, "value") else str(pedido.status),
                "cliente": pedido.cliente,
                "telefone_cliente": pedido.telefone_cliente,
                "cidade_cliente": pedido.cidade_cliente,
                "valor_total": pedido.valor_total,
                "valor_frete": pedido.valor_frete,
                "valor_itens": pedido.valor_itens,
                "tipo_pagamento": pedido.tipo_pagamento,
                "obs_pagamento": pedido.obs_pagamento,
                "forma_envio": pedido.forma_envio,
                "forma_envio_id": pedido.forma_envio_id,
                "financeiro": bool(pedido.financeiro),
                "conferencia": bool(pedido.conferencia),
                "sublimacao": bool(pedido.sublimacao),
                "costura": bool(pedido.costura),
                "expedicao": bool(pedido.expedicao),
                "pronto": bool(pedido.pronto),
                "sublimacao_maquina": pedido.sublimacao_maquina,
                "sublimacao_data_impressao": pedido.sublimacao_data_impressao,
                "items_json": pedido.items,
                "data_criacao": pedido.data_criacao,
                "ultima_atualizacao": pedido.ultima_atualizacao,
            }
        )

    _upsert_rows(conn, table, rows, pk_fields=["pedido_id"])
    LOGGER.info("Pedidos sincronizados: %s", len(rows))


def _sync_imagens(conn, table: Table) -> None:
    with Session(local_engine.sync_engine) as session:
        imagens = session.exec(select(PedidoImagem)).all()

    # Recriar imagens por pedido para evitar duplicatas
    pedidos_ids = {img.pedido_id for img in imagens}
    for pedido_id in pedidos_ids:
        conn.execute(delete(table).where(table.c.pedido_id == pedido_id))

    rows = []
    for image_row in imagens:
        try:
            abs_path = absolute_media_path(image_row.path)
        except Exception as exc:
            LOGGER.warning("Imagem com path invalido (%s): %s", image_row.path, exc)
            continue
        if not abs_path.exists():
            LOGGER.warning("Arquivo nao encontrado: %s", abs_path)
            continue

        b64 = _thumbnail_to_base64(str(abs_path))
        if not b64:
            continue

        rows.append(
            {
                "pedido_id": image_row.pedido_id,
                "item_index": image_row.item_index,
                "item_identificador": image_row.item_identificador,
                "mime_type": "image/jpeg",
                "filename": image_row.filename,
                "image_base64": b64,
                "criado_em": image_row.criado_em or datetime.utcnow(),
            }
        )

    if rows:
        _upsert_rows(conn, table, rows, pk_fields=["id"])
    LOGGER.info("Imagens sincronizadas: %s", len(rows))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--passwords-file",
        dest="passwords_file",
        help="JSON com senhas em texto: {\"user\":\"senha\"} ou [{\"username\":...,\"password\":...}]",
    )
    args = parser.parse_args()

    passwords_map = _load_passwords_map(args.passwords_file)

    mysql_url = _build_mysql_url()
    remote_engine = create_engine(mysql_url, pool_pre_ping=True)

    metadata = MetaData()
    tables = _define_tables(metadata)
    metadata.create_all(remote_engine)

    with remote_engine.begin() as conn:
        _sync_users(conn, tables["pwa_users"], passwords_map)
        _sync_pedidos(conn, tables["pwa_pedidos"])
        _sync_imagens(conn, tables["pwa_pedido_imagens"])

    LOGGER.info("Carga inicial concluida.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
