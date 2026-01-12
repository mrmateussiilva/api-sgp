# Sistema de Migrations - API SGP

## Visão Geral

O sistema de migrations permite gerenciar mudanças no schema do banco de dados de forma controlada e reversível.

## Como Funciona

1. **Migrations são arquivos Python** em `database/migrations/`
2. **Cada migration tem um número** (001, 002, 003...)
3. **Migrations são aplicadas em ordem** (001 → 002 → 003)
4. **Estado é rastreado** na tabela `_migrations`
5. **Migrations podem ser revertidas** (se implementarem `downgrade()`)

## Estrutura de Diretórios

```
database/
├── migrations/
│   ├── __init__.py
│   ├── base.py              # Classe base Migration
│   ├── registry.py          # Registro de todas as migrations
│   ├── m001_initial_schema.py
│   ├── m002_nova_migration.py
│   └── ...
└── run_migrations.py        # Script para executar migrations
```

## Criar Nova Migration

### 1. Criar arquivo de migration

Criar arquivo `database/migrations/m002_nome_da_migration.py`:

```python
from .base import Migration
from sqlmodel.ext.asyncio import AsyncSession
from sqlalchemy import text

class Migration002_NomeDaMigration(Migration):
    version = "002"
    name = "add_nova_tabela"
    description = "Adiciona tabela nova_tabela"
    
    async def upgrade(self, session: AsyncSession) -> None:
        # Aplicar mudanças
        statement = text("""
            CREATE TABLE nova_tabela (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL
            )
        """)
        await session.execute(statement)
        await session.commit()
    
    async def downgrade(self, session: AsyncSession) -> None:
        # Reverter mudanças
        statement = text("DROP TABLE IF EXISTS nova_tabela")
        await session.execute(statement)
        await session.commit()
```

### 2. Registrar migration

Adicionar em `database/migrations/registry.py`:

```python
from .m002_nome_da_migration import Migration002_NomeDaMigration

MIGRATIONS = [
    Migration001_InitialSchema,
    Migration002_NomeDaMigration,  # Nova migration
]
```

**IMPORTANTE**: Sempre manter migrations em ordem numérica!

## Executar Migrations

### Aplicar migrations pendentes

```bash
python database/run_migrations.py
```

### Dry run (apenas verificar)

```bash
python database/run_migrations.py --dry-run
```

### Reverter migration específica

```bash
python database/run_migrations.py --rollback 002
```

## Tabela _migrations

O sistema cria automaticamente a tabela `_migrations` para rastrear migrations aplicadas:

```sql
CREATE TABLE _migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    applied_at DATETIME NOT NULL,
    description TEXT
);
```

## Boas Práticas

1. **Sempre fazer backup** antes de aplicar migrations
2. **Testar migrations** em ambiente de desenvolvimento primeiro
3. **Migrations devem ser idempotentes** (podem rodar múltiplas vezes sem efeito colateral)
4. **Implementar downgrade** quando possível (permite rollback)
5. **Documentar mudanças** na descrição da migration
6. **Nunca modificar migrations já aplicadas** - criar nova migration
7. **Manter migrations simples** - uma mudança por migration quando possível
8. **Testar downgrade** antes de aplicar em produção

## SQLite - Limitações e Soluções

SQLite tem limitações para ALTER TABLE:

### ✅ Suportado:
- `CREATE TABLE`
- `DROP TABLE`
- `CREATE INDEX`
- `DROP INDEX`
- `ALTER TABLE ... ADD COLUMN` (apenas no final da tabela)

### ⚠️ Limitado:
- `ALTER TABLE ... RENAME COLUMN` (SQLite 3.25.0+)
- `ALTER TABLE ... RENAME TABLE`

### ❌ Não Suportado:
- `ALTER TABLE ... DROP COLUMN`
- `ALTER TABLE ... ALTER COLUMN`
- `ALTER TABLE ... MODIFY COLUMN`

### Solução para Mudanças Complexas:

Para alterações que SQLite não suporta diretamente (ex: remover coluna, alterar tipo):

1. **Criar nova tabela** com schema desejado
2. **Copiar dados** da tabela antiga para nova
3. **Dropar tabela antiga**
4. **Renomear nova tabela** para nome original
5. **Recriar índices** se necessário

Exemplo:

```python
async def upgrade(self, session: AsyncSession) -> None:
    # 1. Criar nova tabela
    await session.execute(text("""
        CREATE TABLE user_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL  -- Nova coluna obrigatória
        )
    """))
    
    # 2. Copiar dados
    await session.execute(text("""
        INSERT INTO user_new (id, username, email)
        SELECT id, username, COALESCE(email, '') FROM user
    """))
    
    # 3. Dropar tabela antiga
    await session.execute(text("DROP TABLE user"))
    
    # 4. Renomear nova tabela
    await session.execute(text("ALTER TABLE user_new RENAME TO user"))
    
    await session.commit()
```

## Exemplos de Migrations

### Exemplo 1: Adicionar Coluna

```python
class Migration002_AddEmailToUser(Migration):
    version = "002"
    name = "add_email_to_user"
    description = "Adiciona coluna email à tabela user"
    
    async def upgrade(self, session: AsyncSession) -> None:
        statement = text("ALTER TABLE user ADD COLUMN email TEXT")
        await session.execute(statement)
        await session.commit()
    
    async def downgrade(self, session: AsyncSession) -> None:
        # Remover coluna requer recriação da tabela
        raise NotImplementedError("Remover coluna requer recriação da tabela")
```

### Exemplo 2: Criar Índice

```python
class Migration003_CreateUserEmailIndex(Migration):
    version = "003"
    name = "create_user_email_index"
    description = "Cria índice em user.email"
    
    async def upgrade(self, session: AsyncSession) -> None:
        statement = text("CREATE INDEX IF NOT EXISTS idx_user_email ON user(email)")
        await session.execute(statement)
        await session.commit()
    
    async def downgrade(self, session: AsyncSession) -> None:
        statement = text("DROP INDEX IF EXISTS idx_user_email")
        await session.execute(statement)
        await session.commit()
```

### Exemplo 3: Criar Nova Tabela

```python
class Migration004_CreateAuditLog(Migration):
    version = "004"
    name = "create_audit_log"
    description = "Cria tabela de log de auditoria"
    
    async def upgrade(self, session: AsyncSession) -> None:
        statement = text("""
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user(id)
            )
        """)
        await session.execute(statement)
        await session.commit()
    
    async def downgrade(self, session: AsyncSession) -> None:
        statement = text("DROP TABLE IF EXISTS audit_log")
        await session.execute(statement)
        await session.commit()
```

## Integração com Processo de Update

As migrations são executadas automaticamente durante o processo de update:

1. Script `update.ps1` chama `database/run_migrations.py`
2. Migrations pendentes são aplicadas
3. Se migrations falharem, update é abortado
4. Serviço volta para estado anterior

Veja `UPDATE_PROCESS.md` para detalhes do processo completo.

## Troubleshooting

### Migration já aplicada mas aparece como pendente

Verificar tabela `_migrations`:

```sql
SELECT * FROM _migrations ORDER BY version;
```

Se migration não está na tabela, ela será aplicada novamente (deve ser idempotente).

### Erro ao aplicar migration

1. Verificar logs: `shared/logs/api.log`
2. Verificar estado atual: `python database/run_migrations.py --dry-run`
3. Se necessário, corrigir migration e criar nova versão
4. **NÃO modificar migration já aplicada**

### Rollback de migration não funciona

1. Verificar se migration implementa `downgrade()`
2. Verificar se `downgrade()` não levanta `NotImplementedError`
3. Testar `downgrade()` manualmente antes de usar em produção
4. Algumas migrations são irreversíveis por design (ex: remover coluna)

## Referências

- [SQLite ALTER TABLE](https://www.sqlite.org/lang_altertable.html)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Core](https://docs.sqlalchemy.org/en/20/core/)
