"""Initial migration

Revision ID: 80f2b0b88f51
Revises: 
Create Date: 2026-01-17 17:20:12.959432

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import pedidos.schema


# revision identifiers, used by Alembic.
revision: str = '80f2b0b88f51'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(connection)
    existing = inspector.get_table_names()
    # Banco vazio: criar todas as tabelas a partir dos modelos atuais
    if "designer" not in existing and "user" not in existing:
        from sqlmodel import SQLModel
        from auth import models as _auth_models
        from pedidos import schema as _pedidos_schema
        from clientes import schema as _clientes_schema
        from pagamentos import schema as _pagamentos_schema
        from envios import schema as _envios_schema
        from admin import schema as _admin_schema
        from materiais import schema as _materiais_schema
        from designers import schema as _designers_schema
        from vendedores import schema as _vendedores_schema
        from producoes import schema as _producoes_schema
        from fichas import schema as _fichas_schema
        from relatorios import schema as _relatorios_schema
        from relatorios_fechamentos import schema as _relatorios_fechamentos_schema
        from reposicoes import schema as _reposicoes_schema
        from users import schema as _users_schema
        from maquinas import schema as _maquinas_schema
        from maquinas import print_log_schema as _print_log_schema
        SQLModel.metadata.create_all(connection)
        return

    # Using batch_alter_table for SQLite compatibility

    # Designer
    with op.batch_alter_table('designer') as batch_op:
        batch_op.alter_column('observacao',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=True)
        batch_op.create_index(op.f('ix_designer_id'), ['id'], unique=False)

    # Envio
    with op.batch_alter_table('envio') as batch_op:
        batch_op.alter_column('observacao',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=True)
        batch_op.create_index(op.f('ix_envio_id'), ['id'], unique=False)

    # Payment
    with op.batch_alter_table('payment') as batch_op:
        batch_op.alter_column('taxa_percentual',
               existing_type=sa.REAL(),
               type_=sa.Float(),
               existing_nullable=False,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('observacao',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=True)
        batch_op.create_index(op.f('ix_payment_id'), ['id'], unique=False)

    # Pedidos
    with op.batch_alter_table('pedidos') as batch_op:
        batch_op.alter_column('numero',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('data_entrega',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=11),
               type_=pedidos.schema.StatusType(length=50),
               existing_nullable=False)
        batch_op.alter_column('telefone_cliente',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('cidade_cliente',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('valor_total',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('valor_frete',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('valor_itens',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('tipo_pagamento',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('forma_envio',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('conferencia',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('pronto',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('sublimacao_maquina',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=True)
        batch_op.alter_column('sublimacao_data_impressao',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=True)
        
        # Drop old indexes if they exist
        batch_op.drop_index(op.f('idx_pedidos_cliente'))
        batch_op.drop_index(op.f('idx_pedidos_data_criacao'))
        batch_op.drop_index(op.f('idx_pedidos_data_entrada'))
        batch_op.drop_index(op.f('idx_pedidos_data_entrega'))
        batch_op.drop_index(op.f('idx_pedidos_numero'))
        batch_op.drop_index(op.f('idx_pedidos_status'))
        batch_op.drop_index(op.f('idx_pedidos_status_criacao'))
        batch_op.drop_index(op.f('idx_pedidos_status_data'))
        batch_op.drop_index(op.f('uq_pedidos_numero'))
        
        # Create new indexes
        batch_op.create_index(op.f('ix_pedidos_cliente'), ['cliente'], unique=False)
        batch_op.create_index(op.f('ix_pedidos_data_entrada'), ['data_entrada'], unique=False)
        batch_op.create_index(op.f('ix_pedidos_data_entrega'), ['data_entrega'], unique=False)
        batch_op.create_index(op.f('ix_pedidos_numero'), ['numero'], unique=False)
        batch_op.create_index(op.f('ix_pedidos_status'), ['status'], unique=False)

    # Producoes
    with op.batch_alter_table('producoes') as batch_op:
        batch_op.alter_column('created_at',
               existing_type=sa.VARCHAR(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)

    # User
    with op.batch_alter_table('user') as batch_op:
        batch_op.alter_column('created_at',
               existing_type=sa.TEXT(),
               type_=sa.DateTime(),
               existing_nullable=True)
        batch_op.alter_column('updated_at',
               existing_type=sa.TEXT(),
               type_=sa.DateTime(),
               existing_nullable=True)
        batch_op.create_index(op.f('ix_user_username'), ['username'], unique=True)
        # batch_op.drop_column('email')

    # Vendedor
    with op.batch_alter_table('vendedor') as batch_op:
        batch_op.alter_column('comissao_percentual',
               existing_type=sa.REAL(),
               type_=sa.Float(),
               existing_nullable=False,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('observacao',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=True)
        batch_op.create_index(op.f('ix_vendedor_id'), ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Ignored for this fix
    pass