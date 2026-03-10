# Sync Robusto com Outbox Local

## Objetivo

A sincronizacao com MySQL remoto agora usa uma camada robusta baseada em outbox local, evitando perda de eventos quando o remoto fica indisponivel.

## Visao Geral

1. Operacao de negocio (pedido/usuario) grava no banco local.
2. Na mesma transacao/sessao, a API enfileira um evento em `sync_outbox`.
3. Um worker em background processa a fila e envia para o MySQL remoto.
4. Em falha, aplica retry com backoff exponencial + jitter.
5. Apos limite de tentativas, evento vai para `dead_letter`.

## Tabela `sync_outbox`

Campos principais:

- `id`
- `entity` (`pedido` ou `user`)
- `entity_id`
- `event_type` (`upsert` ou `delete`)
- `payload_json`
- `status` (`pending`, `retry`, `sent`, `dead_letter`)
- `attempts`
- `next_retry_at`
- `last_error`
- `created_at`, `updated_at`, `processed_at`

## Worker

Arquivo: `sync/worker.py`

Comportamento:

- Polling em lote (`batch_size` padrao: 20)
- Intervalo de polling (`poll_interval_seconds` padrao: 2s)
- `max_attempts` padrao: 8
- `base_retry_seconds` padrao: 5
- `max_retry_seconds` padrao: 600
- Em `ENVIRONMENT=test`, o worker nao inicia.

## Endpoints de monitoramento

Com prefixo `API_V1_STR`:

- `GET /sync/health`
  - `ok` ou `degraded`
  - degrada se existir `dead_letter` ou fila antiga (>300s)
- `GET /sync/stats`
  - total por status e idade do item mais antigo pendente
- `POST /sync/retry-dead-letter?event_id={id}`
  - reenfileira um evento morto para nova tentativa

## Eventos gerados

### Pedidos

- Criacao: `upsert`
- Atualizacao: `upsert`
- Atualizacao em lote de status: `upsert`
- Delecao: `delete`
- Delecao em massa: `delete` por pedido

### Usuarios

- Criacao: `upsert`
- Atualizacao: `upsert`
- Delecao: `delete`

## Observacoes operacionais

- O sync da VPS permaneceu como antes (`BackgroundTasks`).
- O sync MySQL deixou de ser chamado diretamente pelos endpoints; agora passa pela outbox.
- Falhas de configuracao/conexao MySQL agora geram logs explicitos em `shared/mysql_pwa_sync_service.py`.
