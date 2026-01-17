# Guia de Migrations com Alembic

Este projeto utiliza o **Alembic** para gerenciamento de versões do banco de dados (migrations). Isso substitui a antiga abordagem de alterar o banco manualmente via código no startup da aplicação.

## Comandos Principais

Todos os comandos devem ser executados via `uv run` para garantir que estão usando o ambiente virtual correto.

### 1. Criar uma Nova Migration

Sempre que você alterar um modelo (arquivos `schema.py` ou `models.py`), você precisa gerar uma nova migration.

```bash
uv run alembic revision --autogenerate -m "descricao_da_mudanca"
```

*   **--autogenerate**: O Alembic compara seus modelos Python com o banco de dados atual e tenta gerar o script automaticamente.
*   **-m "..."**: Uma mensagem curta descrevendo a alteração (ex: "add_telefone_cliente", "create_table_produtos").

**IMPORTANTE**: Sempre revise o arquivo gerado em `alembic/versions/` antes de aplicar! O autogenerate não é perfeito.

### 2. Aplicar Migrations (Upgrade)

Para atualizar o banco de dados para a versão mais recente:

```bash
uv run alembic upgrade head
```

### 3. Reverter Migrations (Downgrade)

Para desfazer a última migration aplicada (voltar uma versão):

```bash
uv run alembic downgrade -1
```

Para voltar para uma revisão específica:

```bash
uv run alembic downgrade <revision_id>
```

### 4. Verificar Status

Para ver qual a revisão atual do banco e se há migrations pendentes:

```bash
uv run alembic current
```

Para ver o histórico de migrations:

```bash
uv run alembic history
```

## Estrutura

*   **alembic.ini**: Arquivo de configuração principal.
*   **alembic/env.py**: Script Python que define como o Alembic se conecta ao banco e acessa os modelos.
*   **alembic/versions/**: Diretório onde ficam os scripts de migration (.py).

## Boas Práticas

1.  **Nunca altere o banco manualmente** (via SQL direto ou ferramenta visual) em produção. Use sempre migrations.
2.  **Revise o código gerado**: O `--autogenerate` pode não detectar mudanças de nome de tabela (ele pode achar que você deletou uma e criou outra) ou tipos de colunas complexos.
3.  **Commit**: Os arquivos gerados em `alembic/versions/` devem ser commitados no Git.
4.  **Batch Mode (SQLite)**: Como o SQLite tem limitações com `ALTER TABLE`, o `env.py` foi configurado para usar `render_as_batch=True`. Isso recria a tabela com a nova estrutura e copia os dados, permitindo operações que o SQLite nativamente não suportaria.

## Solução de Problemas

### "Target database is not up to date"
Significa que existem migrations na pasta `versions/` que ainda não foram aplicadas no banco. Rode `uv run alembic upgrade head`.

### Tabela não detectada
Se você criou um novo modelo (arquivo `schema.py`), certifique-se de que ele foi importado no `alembic/env.py` para que o Alembic "enxergue" a nova classe.
