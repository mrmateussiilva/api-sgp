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
