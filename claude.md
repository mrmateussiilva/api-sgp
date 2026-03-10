# CLAUDE

## Objetivo

Backend em Python para um sistema de gestão de produção.

Consumidores principais:

- cliente desktop em Tauri + React
- scripts internos de manutenção, seed, backup e sincronização

Protocolos expostos:

- HTTP REST
- WebSocket

## Stack

- Linguagem: Python 3.12+
- Framework API: FastAPI
- Servidores ASGI: Uvicorn, Hypercorn
- Modelagem/ORM: SQLModel
- Engine SQL assíncrona: SQLAlchemy async
- Validação/configuração: Pydantic v2, pydantic-settings
- Banco padrão: SQLite
- Banco auxiliar em integrações: MySQL remoto
- Migrações: Alembic
- Testes: Pytest
- Gerenciamento de ambiente: `uv`

Dependências importantes:

- API: `fastapi`, `uvicorn`, `hypercorn`
- Banco: `sqlmodel`, `aiosqlite`, `alembic`, `pymysql`
- Auth: `python-jose[cryptography]`, `bcrypt`
- Performance/serialização: `orjson`
- Arquivos: `aiofiles`, `pillow`
- Relatórios/exportação: `polars`, `pandas`, `openpyxl`, `xlsxwriter`
- Integração HTTP: `httpx`, `requests`

## Entrada da aplicação

Arquivo principal:

- [`main.py`](/home/mateus/Documentos/Projetcts/FinderBit/api-sgp/main.py)

Fluxo de inicialização:

- lê `.env`
- resolve `API_ROOT`
- cria diretórios persistentes em `shared/`
- exige `DATABASE_URL`
- define `MEDIA_ROOT` e `LOG_DIR` se ausentes
- configura logging
- executa criação/verificação de tabelas no lifespan
- registra middlewares
- registra routers por domínio

## Middlewares e resposta

- Resposta padrão: `ORJSONResponse`
- Métricas: `MetricsMiddleware`
- Compressão: `GZipMiddleware`
- CORS: `CORSMiddleware`

## Integração com Tauri + React

O backend já está preparado para uso por app desktop.

Sinais disso:

- CORS inclui `http://localhost:1420`
- CORS inclui `http://127.0.0.1:1420`
- CORS inclui `tauri://localhost`
- CORS inclui `http://tauri.localhost`
- WebSocket em `/ws/orders`
- autenticação JWT no WebSocket
- suporte a upload e entrega de mídia para pedidos e fichas

## Banco e persistência

Arquivo principal:

- [`database/database.py`](/home/mateus/Documentos/Projetcts/FinderBit/api-sgp/database/database.py)

Características:

- engine assíncrona
- conversão automática para `sqlite+aiosqlite`
- pool de conexões configurado
- otimizações SQLite com:
- `PRAGMA journal_mode=WAL`
- `PRAGMA synchronous=NORMAL`
- `PRAGMA busy_timeout`
- `PRAGMA cache_size`
- `PRAGMA temp_store=MEMORY`
- `PRAGMA mmap_size`

Pastas persistentes:

- `shared/db`
- `shared/media`
- `shared/logs`
- `shared/backups`

## Configuração

Arquivo principal:

- [`config.py`](/home/mateus/Documentos/Projetcts/FinderBit/api-sgp/config.py)

Variáveis críticas:

- `DATABASE_URL`
- `API_ROOT`
- `MEDIA_ROOT`
- `LOG_DIR`
- `SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `ENVIRONMENT`
- `PORT`
- `VPS_SYNC_URL`
- `VPS_SYNC_API_KEY`

Regra importante:

- em produção, `SECRET_KEY` não pode usar valor padrão

## Endpoints base

- `GET /`
- `GET /health`
- `GET /docs`
- `GET /redoc`
- `WS /ws/orders`

## Organização por domínio

Cada domínio costuma ter `router.py` e `schema.py`.

Módulos principais:

- `auth`
- `pedidos`
- `clientes`
- `pagamentos`
- `envios`
- `admin`
- `materiais`
- `designers`
- `vendedores`
- `producoes`
- `users`
- `notificacoes`
- `fichas`
- `relatorios_fechamentos`
- `relatorios_envios`
- `reposicoes`
- `maquinas`

## Execução local

Com `uv`:

```bash
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Alternativa:

```bash
uv run hypercorn main:app --bind 0.0.0.0:8000
```

## Testes

```bash
uv run pytest
```

Local dos testes:

- `tests/`

## Convenções para agentes e LLMs

Idioma:

- responder em PT-BR ao interagir neste repositório

Premissas operacionais:

- este repositório é o backend
- o frontend Tauri + React está em outro projeto/cliente
- `uv` é a ferramenta preferencial para instalar dependências e executar comandos Python
- a API é assíncrona e usa FastAPI + SQLModel
- o banco principal padrão é SQLite

Ao modificar código:

- preservar a arquitetura modular por domínio
- manter novas rotas dentro do módulo de negócio correto
- manter schemas e rotas próximos ao domínio correspondente
- respeitar configurações centralizadas em `config.py`
- evitar hardcode de paths fora da estrutura `shared/` quando houver persistência
- considerar compatibilidade com o cliente desktop Tauri

Ao adicionar integrações:

- preferir configuração via variáveis de ambiente
- considerar impacto em CORS, JWT e WebSocket quando houver comunicação com frontend
- tratar SQLite como banco padrão e MySQL como integração auxiliar

Ao executar localmente:

- preferir `uv run ...`
- usar `uv run pytest` para testes

## Resumo rápido

Este projeto é uma API FastAPI assíncrona, modular, com SQLite por padrão, JWT, WebSocket, suporte a mídia e foco em servir um cliente desktop Tauri + React.
