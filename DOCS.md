# API SGP — Documentação Funcional

Este documento descreve os principais módulos, fluxos e endpoints expostos pela API do Sistema de Gestão de Produção (SGP). Use-o como guia para entender como os componentes se relacionam e como integrar o frontend ou serviços externos.

## Visão Geral

- **Stack**: FastAPI + SQLModel (SQLite por padrão) com respostas `ORJSON`.
- **Domain focus**: gestão de pedidos gráficos, controle de produção, cadastros auxiliares e fichas técnicas.
- **Recursos transversais**: autenticação JWT, canais WebSocket para atualizações em tempo real, salvamento de mídias (imagens de pedidos/fichas) e logging centralizado.
- **Documentação automática**: `/docs` (Swagger UI) e `/redoc`.

## Endpoints Básicos

| Rota | Descrição |
| --- | --- |
| `GET /` | Informações gerais com mensagem e versão. |
| `GET /health` | Verificação de saúde da API para load balancers e monitoramento. |

> Todas as rotas de domínio (pedidos, cadastros, fichas etc.) são expostas com o prefixo configurado em `settings.API_V1_STR` (por padrão `/api/v1`). Já `notificacoes` mantém o prefixo `/api/notificacoes`.

## Autenticação e Sessão (`auth/router.py`)

- **POST `/auth/login`**: valida credenciais persistidas, verifica se o usuário está ativo e retorna JWT (`session_token`) + flag `is_admin`.
- **POST `/auth/logout`**: revoga o token atual (lista de revogação in-memory) para impedir reuso.
- **GET `/auth/me`**: retorna `user_id` e `username` do token válido, garantindo que o usuário permaneça ativo.

Detalhes:
- Tokens expiram após `ACCESS_TOKEN_EXPIRE_MINUTES`.
- O helper `auth/security.py` centraliza leitura de tokens, busca de usuário e parsing de headers `Authorization`.
- Rotas que exigem admin reusam dependências auxiliares (`require_admin`, `get_current_user_admin` em `pedidos/router.py`).

## Pedidos (`pedidos/router.py`)

Funcionalidades principais:

1. **Criação completa de pedido** (`POST /pedidos/`):
   - Aceita `PedidoCreate` com itens ricos, clientes, valores, status de produção etc.
   - Gera número incremental com padding de 10 dígitos quando não informado.
   - Converte itens para JSON persistido e processa imagens base64 para armazenamento em disco.
   - Atualiza `ULTIMO_PEDIDO_ID` para sinalizar novos registros e publica eventos WebSocket (`order_created`).

2. **Listagem e filtros** (`GET /pedidos/`):
   - Suporta `skip`, `limit`, `status`, busca textual por cliente e intervalo `data_inicio`/`data_fim`.
   - `date_mode` define qual data filtrar: `entrada` (padrao), `entrega` ou `qualquer`.
   - Ao retornar, converte itens JSON novamente para objetos, separando `cidade_cliente` e `estado_cliente`.

3. **Consulta individual** (`GET /pedidos/{id}`):
   - Retorna pedido com itens decodificados e campos normalizados.

4. **Atualizações parciais** (`PATCH /pedidos/{id}`):
   - Aceita qualquer subconjunto de campos; somente o status `financeiro` exige usuário admin.
   - Mantém/gera número incremental conforme necessário.
   - Controla upload/remoção de imagens de itens.
   - Detecta mudanças reais de status/etapas e envia eventos `order_updated` + `order_status_updated` quando aplicável.

5. **Exclusão**:
   - `DELETE /pedidos/{id}` remove pedido, mídias associadas e envia `order_deleted`.
   - `DELETE /pedidos/all` remove todos os pedidos (admin obrigatório) e limpa as imagens.

6. **Listagem por status** (`GET /pedidos/status/{status}`):
   - Valida enums de status e devolve somente pedidos naquele estágio.

7. **Arquivamento em JSON** (`POST /pedidos/save-json/{pedido_id}`):
   - Recebe payload livre do frontend, acrescenta metadados (`savedAt`, `savedBy`, versão) e salva um arquivo `.json` por pedido dentro de `media/pedidos/{id}/`.

8. **Imagens de itens** (`GET /pedidos/imagens/{imagem_id}`):
   - Realiza streaming do arquivo físico com MIME original. O armazenamento e validação ficam em `pedidos/images.py`.

Suporte adicional:
- Normalização de cidade/estado para facilitar buscas.
- Utilitário `apply_image_changes` garante sincronização entre banco, arquivos e itens retornados.
- Scripts auxiliares (`scripts/delete_all_pedidos.py`) usam as mesmas funções para limpeza de mídias.

## Fluxo em Tempo Real e Notificações

- **WebSocket `/ws/orders`**:
  - Exige token JWT via query (`?token=`) ou header `Authorization`.
  - Usa `OrdersNotifier` (`pedidos/realtime.py`) para manter conexões e fazer broadcast.
  - Eventos emitidos: `order_created`, `order_updated`, `order_status_updated`, `order_deleted`. Cada payload inclui `order_id`, dados do pedido e, quando disponível, informações do usuário que gerou a ação.

- **Long polling `/api/notificacoes/ultimos`**:
  - Retorna `ultimo_id` (contador global incrementado em cada criação) e timestamp atual.
  - Serve como fallback simples para frontends que ainda não consomem WebSocket, possibilitando detectar novos pedidos ao comparar IDs.

### Guia “bem simples” — Como pedidos são gravados e como o frontend recebe atualizações (REST + WebSocket)

Se você só quer entender “o que acontece quando eu crio/edito/apago um pedido” e “como isso chega no frontend”, é aqui.

#### 1) Onde o pedido é gravado?

##### 1.1 Criar pedido (grava no banco)

- **Endpoint**: `POST /pedidos/`
- **Função**: `criar_pedido(...)` (em `pedidos/router.py`)
- **O que ela faz (ordem real)**:
  - Recebe o JSON do frontend (`PedidoCreate`).
  - Prepara os `items`:
    - Converte para um formato interno e salva como **string JSON** no campo `Pedido.items`.
    - Também prepara uploads/remoções pendentes de imagens.
  - Gera `numero` automaticamente se não vier no payload (`get_next_order_number`).
  - Cria o objeto `Pedido` e faz:
    - `session.add(db_pedido)`
    - `await session.flush()`
    - aplica imagens (`apply_image_changes(...)`)
    - `await session.commit()`
    - `await session.refresh(db_pedido)`
  - Monta o `PedidoResponse` (o que volta pro frontend no REST).
  - **Salva um JSON do pedido em disco** (muito importante):
    - `_save_pedido_json_internal(pedido_id, jsonable_encoder(response))`
    - Isso cria um arquivo em:
      - `MEDIA_ROOT/pedidos/{pedido_id}/pedido-{pedido_id}-{timestamp}.json`
  - **Envia evento WebSocket pro frontend**:
    - `broadcast_order_event("order_created", response, None, user_info)`

##### 1.2 Atualizar pedido (grava no banco)

- **Endpoint**: `PATCH /pedidos/{pedido_id}`
- **Função**: `atualizar_pedido(...)` (em `pedidos/router.py`)
- **O que ela faz (ordem real)**:
  - Busca o pedido no banco.
  - Captura um “ANTES” dos campos de status (`status_fields_before`).
  - Aplica atualização (`setattr(...)` + tratamento de itens/imagens).
  - `commit()` e `refresh()`
  - Captura um “DEPOIS” (`status_fields_after`) e calcula se mudou algo de status/etapas (`status_changed`).
  - Monta o `PedidoResponse`.
  - **Salva JSON em disco antes do broadcast**:
    - `_save_pedido_json_internal(pedido_id, jsonable_encoder(response))`
  - **Sempre** dispara:
    - `broadcast_order_event("order_updated", response, None, user_info)`
  - **Só se mudou status/etapas**, dispara também:
    - `broadcast_order_event("order_status_updated", response, None, user_info)`

##### 1.3 Deletar pedido (remove do banco)

- **Endpoint**: `DELETE /pedidos/{pedido_id}`
- **Função**: `deletar_pedido(...)`
- **O que ela faz**:
  - Remove imagens do disco ligadas ao pedido.
  - Deleta imagens no banco (tabela de imagens).
  - Deleta o pedido.
  - `commit()`
  - Dispara WebSocket:
    - `broadcast_order_event("order_deleted", order_id=pedido_id)`

#### 2) Por que existe `GET /pedidos/{id}/json`?

- Esse endpoint **não vai no banco**.
- Ele lê o **arquivo JSON mais recente** do pedido em disco:
  - procura `MEDIA_ROOT/pedidos/{id}/pedido-*.json`
  - pega o mais novo (por `mtime`)
  - remove metadados (`savedAt`, `savedBy`, `version`)
  - retorna o JSON

**Motivo prático**:
- Quando o servidor envia um evento WebSocket, o frontend pode chamar `/pedidos/{id}/json` pra pegar “o pedido completo mais recente”.
- Por isso o código faz “salvar JSON ANTES do broadcast” (pra evitar o frontend buscar e pegar arquivo velho).

#### 3) Como o WebSocket funciona (o “tempo real”)

##### 3.1 Onde está o WebSocket

- **Endpoint**: `GET ws://.../ws/orders?token=SEU_JWT`
- **Função**: `orders_websocket(websocket: WebSocket)` em `main.py`

##### 3.2 Autenticação do WebSocket

- O servidor aceita conexão e depois valida o token:
  - `token` pode vir na querystring `?token=...`
  - ou no header `Authorization: Bearer ...`

Se token inválido:
- o servidor fecha com:
  - code `1008` e reason `"Token inválido ou ausente"`

##### 3.3 Lista de conexões (quem recebe broadcast)

- A classe é `OrdersNotifier` em `pedidos/realtime.py`.
- Ela guarda:
  - `self._connections`: **todas as conexões ativas**
  - `self._connections_by_user`: conexões por usuário (pra debug/controle)
  - `heartbeat`: a cada 30s manda `{"type":"ping"}` pra detectar conexão morta

##### 3.4 Broadcast “servidor → todos os clientes”

Isso é usado quando você cria/atualiza/deleta pedido via REST.

O caminho é:
- `broadcast_order_event(...)` (em `pedidos/router.py`)
- monta `message` e chama `schedule_broadcast(message)` (em `pedidos/realtime.py`)
- `schedule_broadcast` cria uma task e executa `orders_notifier.broadcast(message)`
- `orders_notifier.broadcast` envia o JSON para todas as conexões ativas via `send_text(...)`

##### 3.5 Broadcast “cliente → servidor → outros clientes”

Isso é usado quando o **frontend manda um JSON pelo WebSocket** e quer que o servidor repasse pros outros clientes.

- O servidor fica num loop:
  - `data = await websocket.receive_text()`

Regras:
- Se `data` for ping (`"ping"` ou `{"type":"ping"}`), o servidor responde pong e **não faz broadcast**.
- Se `data` for JSON e tiver `"broadcast": true`, o servidor repassa para os **outros** clientes (não manda de volta pra quem enviou), usando `orders_notifier.broadcast_except(...)`.

#### 4) Funções importantes (nome por nome)

##### Em `pedidos/router.py`

- `criar_pedido(...)`: cria pedido no banco + salva JSON + emite `order_created`
- `atualizar_pedido(...)`: atualiza pedido + salva JSON + emite `order_updated` e `order_status_updated` (se mudou)
- `deletar_pedido(...)`: apaga + emite `order_deleted`
- `_save_pedido_json_internal(pedido_id, pedido_data)`: grava arquivo JSON em `MEDIA_ROOT/pedidos/...`
- `broadcast_order_event(event_type, pedido=None, order_id=None, user_info=None)`: monta payload e chama `schedule_broadcast`

##### Em `pedidos/realtime.py`

- `schedule_broadcast(message)`: agenda `broadcast(...)` no event loop
- `OrdersNotifier.broadcast(message)`: manda para TODO MUNDO conectado
- `OrdersNotifier.broadcast_except(message, exclude_websocket)`: manda para TODO MUNDO exceto o remetente
- `OrdersNotifier.connect/disconnect`: registra/remove conexões
- Heartbeat: manda `{"type":"ping"}` periodicamente

##### Em `main.py`

- `orders_websocket(...)`: endpoint `/ws/orders` que lê mensagens e dispara broadcast quando `broadcast: true`

#### 5) Exemplos reais (payloads) que o frontend recebe

##### 5.1 Exemplo real de `order_updated` / `order_status_updated`

Quando alguém atualiza um pedido, a mensagem enviada ao frontend segue este formato (resumo):

```json
{
  "type": "order_updated",
  "order_id": 2,
  "user_id": 6,
  "username": "mateus",
  "order": {
    "id": 2,
    "numero": "0000000002",
    "status": "pendente",
    "financeiro": true,
    "conferencia": true,
    "sublimacao": true,
    "costura": true,
    "expedicao": false,
    "pronto": false,
    "ultima_atualizacao": "2026-01-07T06:02:13.219293",
    "items": [
      {
        "tipo_producao": "painel",
        "descricao": "TETETE",
        "imagem": "pedidos/tmp/7674dd9fa3194dc68c9d12a27c5c3ff1.jpg",
        "acabamento": { "overloque": true, "elastico": true, "ilhos": false }
      }
    ]
  }
}
```

Às vezes também chega:

```json
{
  "type": "order_status_updated",
  "order_id": 2,
  "user_id": 6,
  "username": "mateus",
  "order": { "...mesma estrutura do pedido..." }
}
```

##### 5.2 Exemplo do que o frontend envia pelo WebSocket (cliente → servidor)

Formato esperado:

```json
{
  "type": "order_status_updated",
  "order_id": 2,
  "order": { "id": 2, "status": "pendente" },
  "timestamp": 1768456922,
  "broadcast": true
}
```

O servidor vai:
- ignorar se for ping/pong
- se `broadcast: true`, repassar para todos os outros clientes conectados

#### 6) Checklist rápido: se algo não estiver chegando no frontend

1. O frontend abriu WebSocket em `/ws/orders` com token válido?
2. O servidor aceitou e autenticou? (procure log `Cliente conectado`)
3. Ao criar/atualizar pedido via REST, aparece log `[Broadcast] Preparando broadcast...`?
4. Tem pelo menos 1 conexão ativa no momento do broadcast?
5. Se for broadcast enviado pelo cliente:
   - o JSON tem `broadcast: true`?
   - não é `ping/pong`?
   - o servidor não está descartando por JSON inválido?

## Cadastros Auxiliares

Todos os módulos expõem CRUD completo (listar, obter, criar, atualizar parcialmente, remover) usando `AsyncSession`. Campos `ativo` permitem filtros específicos.

| Módulo | Prefixo | Particularidades |
| --- | --- | --- |
| **Clientes** (`/clientes`) | `/clientes` | Estrutura básica do cliente usada nos pedidos. |
| **Vendedores** (`/vendedores`) | `/vendedores`, `/vendedores/ativos` | Permite filtrar apenas ativos. |
| **Designers** (`/designers`) | `/designers` | Cadastro simples para atribuição nos itens. |
| **Materiais** (`/materiais`) | `/materiais` | Mantém o catálogo de tecidos/materiais disponíveis. |
| **Tipos de envio** (`/tipos-envios`) | `/tipos-envios`, `/tipos-envios/ativos` | Define métodos de entrega e IDs usados em pedidos. |
| **Tipos de pagamento** (`/tipos-pagamentos`) | `/tipos-pagamentos`, `/tipos-pagamentos/ativos` | Base para seleção da forma de pagamento. |

Cada router usa schemas dedicados (`schema.py` em cada módulo) para validação e conversão.

## Gestão de Usuários

- **Admin Router (`/admin/users/…`)**:
  - Criar, listar, detalhar, atualizar e excluir usuários com atributos `is_admin` e `is_active`.
  - Usa hashing `bcrypt` para senha e aplica validações básicas de segurança (mínimo de caracteres, unicidade).

- **Users Router (`/users/…`)**:
  - API pública (para painéis internos) que expõe leitura/criação/edição/remoção similar, retornando `UserRead`.

> Ambos reutilizam `auth.models.User` e `base.get_session`. O router admin foi pensado para ferramentas internas mais restritas; o router geral suporta telas de gerenciamento.

## Fichas Técnicas (`fichas/router.py`)

Funcionalidades:
- **POST `/fichas/`**: salva ficha com dados do produto, timestamps automáticos e, opcionalmente, imagem em base64 (armazenada em `media/fichas/{id}/` via `image_storage.py`).
- **PATCH `/fichas/{id}`**: atualiza qualquer campo e troca a imagem se um novo base64 for enviado.
- **GET `/fichas/{id}` / `GET /fichas/`**: recupera ficha única ou lista paginada (ordenada por `data_criacao` desc).
- **GET `/fichas/imagens/{id}`**: retorna a imagem original ligada à ficha, validando a existência no disco.

## Logging e Observabilidade

- `logging_config.py` define formato único (`"%(asctime)s %(levelname)s [%(name)s] %(message)s"`) e é carregado em `main.py`.
- Eventos internos relevantes usam `print` protegido por `__debug__` para facilitar diagnóstico em desenvolvimento (ex.: uploads, broadcasts).

## Armazenamento de Mídia

- **Pedidos** (`pedidos/images.py`):
  - Suporta validação de data URLs base64, limite de tamanho (`settings.MAX_IMAGE_SIZE_MB`), inferência de extensão e gravação física por pedido.
  - Expõe utilitários para recuperar caminhos absolutos e apagar arquivos (evitando path traversal).

- **Fichas** (`fichas/image_storage.py`):
  - Implementação similar, com diretório próprio e exceções específicas (`ImageStorageError`).

Ambos usam `settings.MEDIA_ROOT` (relativo ao projeto ou absoluto) e criam diretórios conforme necessário.

## Configuração

Principais variáveis (definidas em `config.py` ou `.env`):

- `DATABASE_URL` — conexão do SQLModel (SQLite default).
- `MEDIA_ROOT`, `MAX_IMAGE_SIZE_MB` — diretórios e limites de upload.
- `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` — autenticação.
- `BACKEND_CORS_ORIGINS` / `BACKEND_CORS_ALLOW_ORIGIN_REGEX` — controle de CORS.
- `API_V1_STR`, `PROJECT_NAME`, `VERSION`, `LOG_LEVEL` — metadados gerais.

## Testes e Scripts

- **Pytest**: suites em `tests/` cobrem pedidos, notificações e validações.
- **Scripts utilitários**:
  - `scripts/delete_all_pedidos.py`: apaga registros e mídias direto via CLI.
  - (Conforme README) `scripts/seed_pedidos.py` pode ser usado para dados fictícios.

---

Com este panorama você pode navegar rapidamente pelos módulos, entender como as rotas se alinham com as regras de negócio e integrar novos consumidores (frontend, automações ou serviços externos) mantendo compatibilidade com o comportamento da API.
