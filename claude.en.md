# CLAUDE

## Purpose

Python backend for a production management system.

Primary consumers:

- desktop client built with Tauri + React
- internal scripts for maintenance, seeding, backup, and synchronization

Exposed protocols:

- HTTP REST
- WebSocket

## Stack

- Language: Python 3.12+
- API framework: FastAPI
- ASGI servers: Uvicorn, Hypercorn
- ORM/modeling: SQLModel
- Async SQL engine: SQLAlchemy async
- Validation/settings: Pydantic v2, pydantic-settings
- Default database: SQLite
- Auxiliary integration database: remote MySQL
- Migrations: Alembic
- Tests: Pytest
- Environment management: `uv`

Important dependencies:

- API: `fastapi`, `uvicorn`, `hypercorn`
- Database: `sqlmodel`, `aiosqlite`, `alembic`, `pymysql`
- Auth: `python-jose[cryptography]`, `bcrypt`
- Performance/serialization: `orjson`
- Files: `aiofiles`, `pillow`
- Reporting/export: `polars`, `pandas`, `openpyxl`, `xlsxwriter`
- HTTP integration: `httpx`, `requests`

## Application entry point

Main file:

- [`main.py`](/home/mateus/Documentos/Projetcts/FinderBit/api-sgp/main.py)

Startup flow:

- reads `.env`
- resolves `API_ROOT`
- creates persistent directories under `shared/`
- requires `DATABASE_URL`
- sets `MEDIA_ROOT` and `LOG_DIR` if missing
- configures logging
- creates/verifies database tables during lifespan
- registers middlewares
- registers domain routers

## Middleware and response defaults

- Default response: `ORJSONResponse`
- Metrics: `MetricsMiddleware`
- Compression: `GZipMiddleware`
- CORS: `CORSMiddleware`

## Tauri + React integration

The backend is already prepared for desktop app usage.

Indicators:

- CORS includes `http://localhost:1420`
- CORS includes `http://127.0.0.1:1420`
- CORS includes `tauri://localhost`
- CORS includes `http://tauri.localhost`
- WebSocket endpoint at `/ws/orders`
- JWT authentication on the WebSocket
- support for upload and serving media for orders and templates

## Database and persistence

Main file:

- [`database/database.py`](/home/mateus/Documentos/Projetcts/FinderBit/api-sgp/database/database.py)

Characteristics:

- async engine
- automatic conversion to `sqlite+aiosqlite`
- configured connection pool
- SQLite optimizations with:
- `PRAGMA journal_mode=WAL`
- `PRAGMA synchronous=NORMAL`
- `PRAGMA busy_timeout`
- `PRAGMA cache_size`
- `PRAGMA temp_store=MEMORY`
- `PRAGMA mmap_size`

Persistent directories:

- `shared/db`
- `shared/media`
- `shared/logs`
- `shared/backups`

## Configuration

Main file:

- [`config.py`](/home/mateus/Documentos/Projetcts/FinderBit/api-sgp/config.py)

Critical variables:

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

Important rule:

- in production, `SECRET_KEY` must not use the default value

## Base endpoints

- `GET /`
- `GET /health`
- `GET /docs`
- `GET /redoc`
- `WS /ws/orders`

## Domain organization

Each domain typically contains `router.py` and `schema.py`.

Main modules:

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

## Local execution

With `uv`:

```bash
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Alternative:

```bash
uv run hypercorn main:app --bind 0.0.0.0:8000
```

## Tests

```bash
uv run pytest
```

Test location:

- `tests/`

## Repository conventions for agents and LLMs

Language:

- respond in PT-BR when interacting in this repository

Operational assumptions:

- this repository is the backend
- the Tauri + React frontend lives in a separate client project
- `uv` is the preferred tool for installing dependencies and running Python commands
- the API is asynchronous and uses FastAPI + SQLModel
- the default primary database is SQLite

When changing code:

- preserve the modular architecture by domain
- keep new routes inside the correct business module
- keep schemas and routes close to the corresponding domain
- respect centralized settings in `config.py`
- avoid hardcoded paths outside the `shared/` structure when persistence is involved
- consider compatibility with the Tauri desktop client

When adding integrations:

- prefer configuration through environment variables
- consider CORS, JWT, and WebSocket impact when frontend communication is involved
- treat SQLite as the default database and MySQL as an auxiliary integration

When running locally:

- prefer `uv run ...`
- use `uv run pytest` for tests

## Quick summary

This project is a modular asynchronous FastAPI API, using SQLite by default, JWT, WebSocket, media handling, and built to serve a Tauri + React desktop client.
