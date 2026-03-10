# CONTEXT

## Repository role

This repository contains the backend API for the SGP system.

It is not the Tauri frontend.

Primary client:

- desktop application built with Tauri + React

## Primary purpose

This codebase provides:

- REST API endpoints
- WebSocket real-time communication
- authentication and authorization
- order and production management logic
- reporting endpoints
- media/file handling
- maintenance and synchronization scripts

## Core technical assumptions

- Language: Python 3.12+
- Framework: FastAPI
- ORM/model layer: SQLModel
- Database access: async SQLAlchemy
- Default database: SQLite
- Environment/dependency manager: `uv`
- Tests: `pytest`

## Execution defaults

Preferred local commands:

```bash
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
uv run pytest
```

Alternative server:

```bash
uv run hypercorn main:app --bind 0.0.0.0:8000
```

## Application entrypoint

Main file:

- `main.py`

Important behavior on startup:

- loads `.env`
- requires `DATABASE_URL`
- configures shared persistent directories
- initializes logging
- creates or validates database tables
- registers middlewares and routers

## Persistence model

Default persistence:

- SQLite

Persistent shared directories:

- `shared/db`
- `shared/media`
- `shared/logs`
- `shared/backups`

Rule:

- when changing file persistence behavior, prefer the `shared/` structure

## API behavior assumptions

- default response class is optimized (`ORJSONResponse`)
- API supports gzip compression
- API exposes health and docs endpoints
- API includes a JWT-protected WebSocket at `/ws/orders`
- CORS is already configured for local Tauri development

## Architectural conventions

The project is organized by business domain.

Typical module structure:

- `<domain>/router.py`
- `<domain>/schema.py`

Examples:

- `auth`
- `pedidos`
- `clientes`
- `pagamentos`
- `envios`
- `fichas`
- `maquinas`

Rule:

- keep new code inside the correct domain module whenever possible

## Configuration conventions

Central settings file:

- `config.py`

Important environment variables:

- `DATABASE_URL`
- `API_ROOT`
- `MEDIA_ROOT`
- `LOG_DIR`
- `SECRET_KEY`
- `ENVIRONMENT`

Rules:

- prefer environment variables over hardcoded config
- do not rely on default `SECRET_KEY` in production-oriented changes

## Frontend integration assumptions

The backend must remain compatible with a desktop client.

Keep in mind:

- Tauri + React consumes this API
- local dev origins include port `1420`
- changes to auth, payload shape, CORS, media URLs, or WebSocket behavior may affect the client immediately

## Agent instructions

When working in this repository:

- respond to the user in PT-BR
- prefer `uv` for Python execution
- prefer minimal, targeted changes
- preserve existing modular structure
- avoid introducing new global patterns unless necessary
- consider backward compatibility with the desktop client

When adding features:

- place routes in the correct domain router
- place schemas near the same domain
- use centralized settings for configurable values
- treat SQLite as the default production-relevant baseline unless the task explicitly targets another database

When reviewing or debugging:

- inspect `main.py`, `config.py`, and `database/database.py` first for app-wide behavior
- check domain routers/schemas next
- check `scripts/` for operational or migration helpers before reinventing tooling

## What this file is for

This file is intended to give an LLM or coding agent fast operational context before making changes.

Use it as a working-context summary, not as full project documentation.
