from __future__ import annotations

import base64
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

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
from sqlalchemy.engine import URL
from sqlmodel import Session, select

from config import settings
from database.database import engine as local_engine
from pedidos.images import absolute_media_path
from pedidos.schema import Pedido, PedidoImagem
from auth.models import User


LOGGER = logging.getLogger(__name__)
THUMBNAIL_SIZE = (300, 300)
JPEG_QUALITY = 60

_REMOTE_ENGINE = None
_REMOTE_TABLES = None


def _build_mysql_url() -> Optional[str]:
    if not all([settings.DB_USER, settings.DB_PASS, settings.DB_HOST, settings.DB_NAME]):
        return None
    return URL.create(
        drivername="mysql+pymysql",
        username=settings.DB_USER,
        password=settings.DB_PASS,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    ).render_as_string(hide_password=False)


def _get_remote_engine():
    global _REMOTE_ENGINE
    if _REMOTE_ENGINE is not None:
        return _REMOTE_ENGINE
    mysql_url = _build_mysql_url()
    if not mysql_url:
        return None
    _REMOTE_ENGINE = create_engine(mysql_url, pool_pre_ping=True)
    return _REMOTE_ENGINE


def _get_tables():
    global _REMOTE_TABLES
    if _REMOTE_TABLES is not None:
        return _REMOTE_TABLES

    metadata = MetaData()
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

    engine = _get_remote_engine()
    if engine is None:
        return None
    metadata.create_all(engine)
    _REMOTE_TABLES = {
        "pwa_pedidos": pwa_pedidos,
        "pwa_pedido_imagens": pwa_pedido_imagens,
        "pwa_users": pwa_users,
    }
    return _REMOTE_TABLES


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


def _upsert_row(conn, table: Table, row: dict, pk_field: str) -> None:
    stmt = mysql_insert(table).values(**row)
    update_data = {k: v for k, v in row.items() if k != pk_field}
    if not update_data:
        update_data = row
    stmt = stmt.on_duplicate_key_update(**update_data)
    conn.execute(stmt)


def sync_pedido(pedido_id: int) -> None:
    engine = _get_remote_engine()
    tables = _get_tables()
    if engine is None or tables is None:
        return

    with Session(local_engine.sync_engine) as session:
        pedido = session.get(Pedido, pedido_id)
        if not pedido:
            return

        pedido_row = {
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

        imagens = session.exec(select(PedidoImagem).where(PedidoImagem.pedido_id == pedido_id)).all()

    with engine.begin() as conn:
        _upsert_row(conn, tables["pwa_pedidos"], pedido_row, "pedido_id")

        conn.execute(delete(tables["pwa_pedido_imagens"]).where(tables["pwa_pedido_imagens"].c.pedido_id == pedido_id))
        for image_row in imagens:
            try:
                abs_path = absolute_media_path(image_row.path)
            except Exception:
                continue
            if not abs_path.exists():
                continue

            b64 = _thumbnail_to_base64(str(abs_path))
            if not b64:
                continue

            img_row = {
                "pedido_id": image_row.pedido_id,
                "item_index": image_row.item_index,
                "item_identificador": image_row.item_identificador,
                "mime_type": "image/jpeg",
                "filename": image_row.filename,
                "image_base64": b64,
                "criado_em": image_row.criado_em or datetime.utcnow(),
            }
            _upsert_row(conn, tables["pwa_pedido_imagens"], img_row, "id")


def sync_deletion(pedido_id: int) -> None:
    engine = _get_remote_engine()
    tables = _get_tables()
    if engine is None or tables is None:
        return

    with engine.begin() as conn:
        conn.execute(delete(tables["pwa_pedidos"]).where(tables["pwa_pedidos"].c.pedido_id == pedido_id))
        conn.execute(delete(tables["pwa_pedido_imagens"]).where(tables["pwa_pedido_imagens"].c.pedido_id == pedido_id))


def sync_user(user_id: int, *, force_plain_password: Optional[str] = None) -> None:
    engine = _get_remote_engine()
    tables = _get_tables()
    if engine is None or tables is None:
        return

    with Session(local_engine.sync_engine) as session:
        user = session.get(User, user_id)
        if not user:
            return

    password_value = force_plain_password or user.password_hash
    row = {
        "username": user.username,
        "password": password_value,
        "is_admin": bool(user.is_admin),
        "is_active": bool(user.is_active),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }

    with engine.begin() as conn:
        _upsert_row(conn, tables["pwa_users"], row, "id")


def sync_user_deletion(username: str) -> None:
    engine = _get_remote_engine()
    tables = _get_tables()
    if engine is None or tables is None:
        return

    with engine.begin() as conn:
        conn.execute(delete(tables["pwa_users"]).where(tables["pwa_users"].c.username == username))
