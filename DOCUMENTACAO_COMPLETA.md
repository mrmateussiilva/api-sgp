# Documentação Completa - API Sistema de Gestão de Produção (SGP)

> **Versão:** 1.0.20  
> **Última Atualização:** Janeiro 2026  
> **Objetivo:** Sistema completo para gerenciamento de pedidos de produção gráfica

---

## 📋 Índice

1. [Visão Geral](#-visão-geral)
2. [Arquitetura do Sistema](#-arquitetura-do-sistema)
3. [Tecnologias Utilizadas](#-tecnologias-utilizadas)
4. [Estrutura do Projeto](#-estrutura-do-projeto)
5. [Módulos Principais](#-módulos-principais)
6. [Modelos de Dados](#-modelos-de-dados)
7. [API Endpoints](#-api-endpoints)
8. [Autenticação e Segurança](#-autenticação-e-segurança)
9. [Sistema de Tempo Real (WebSocket)](#-sistema-de-tempo-real-websocket)
10. [Gerenciamento de Mídia](#-gerenciamento-de-mídia)
11. [Relatórios e Análises](#-relatórios-e-análises)
12. [Configuração e Deploy](#-configuração-e-deploy)
13. [Fluxo de Trabalho](#-fluxo-de-trabalho)
14. [Manutenção e Backups](#-manutenção-e-backups)

---

## 🎯 Visão Geral

O **API-SGP** é um sistema backend completo desenvolvido em **FastAPI** para gerenciar todo o ciclo de vida de pedidos de produção gráfica, desde a entrada do pedido até a expedição final. O sistema oferece:

- ✅ Gerenciamento completo de pedidos com múltiplos itens
- ✅ Controle de produção por etapas (financeiro, sublimação, costura, expedição)
- ✅ Sistema de autenticação JWT com controle de permissões
- ✅ Notificações em tempo real via WebSocket
- ✅ Geração de fichas de produção e relatórios
- ✅ Upload e gerenciamento de imagens de produtos
- ✅ Rastreamento de máquinas e equipamentos
- ✅ Relatórios financeiros e de fechamento

---

## 🏗️ Arquitetura do Sistema

### Arquitetura em Camadas

```
┌─────────────────────────────────────────┐
│         Frontend (Tauri/React)          │
│     http://localhost:1420               │
└─────────────────────────────────────────┘
                    ↓ HTTP/WebSocket
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│         (main.py)                       │
├─────────────────────────────────────────┤
│  Middlewares:                           │
│  - CORS                                 │
│  - GZip Compression                     │
│  - Metrics (Performance)                │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Routers (Endpoints)             │
│  /auth, /pedidos, /fichas, etc.         │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Services (Business Logic)       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         SQLModel (ORM)                  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         SQLite Database                 │
│         (shared/db/banco.db)            │
└─────────────────────────────────────────┘
```

### Diretórios Compartilhados

O sistema utiliza uma estrutura de **diretórios compartilhados** para facilitar atualizações sem perder dados:

```
API_ROOT/
├── shared/              # Dados persistentes (compartilhados entre versões)
│   ├── db/             # Banco de dados SQLite
│   ├── media/          # Arquivos de mídia (imagens, PDFs)
│   ├── logs/           # Logs da aplicação
│   └── backups/        # Backups automáticos
├── releases/           # Versões da aplicação
│   ├── v1.0.19/
│   └── v1.0.20/        # Versão atual
└── .env                # Configurações de ambiente
```

---

## 🛠️ Tecnologias Utilizadas

### Backend Core
- **FastAPI** (0.115.14) - Framework web assíncrono moderno
- **SQLModel** (0.0.16) - ORM baseado em Pydantic + SQLAlchemy
- **Pydantic** (2.11.7) - Validação de dados e schemas
- **SQLite** - Banco de dados relacional leve

### Servidor ASGI
- **Uvicorn** (0.35.0) - Servidor ASGI para desenvolvimento
- **Hypercorn** (≥0.17.0) - Servidor ASGI com suporte a múltiplos workers (produção)

### Autenticação e Segurança
- **python-jose[cryptography]** (≥3.3.0) - JWT tokens
- **bcrypt** (≥5.0.0) - Hash de senhas
- **python-multipart** (0.0.20) - Upload de arquivos

### Utilitários
- **aiofiles** (≥25.1.0) - I/O assíncrono de arquivos
- **aiosqlite** (≥0.22.0) - SQLite assíncrono
- **orjson** (≥3.11.5) - JSON rápido
- **requests** (≥2.32.5) - Cliente HTTP
- **Faker** (37.4.0) - Geração de dados fake para testes

### Testes
- **pytest** (≥8.4.1)
- **pytest-asyncio** (≥0.23.0)

---

## 📁 Estrutura do Projeto

```
api-sgp/
├── main.py                      # Aplicação principal FastAPI
├── base.py                      # Criação de tabelas do banco
├── config.py                    # Configurações e settings
├── logging_config.py            # Configuração de logs
├── requirements.txt             # Dependências Python
├── .env                         # Variáveis de ambiente
│
├── database/                    # Configuração do banco de dados
│   ├── database.py             # Engine SQLModel e sessões
│   ├── init_db.py              # Inicialização do banco
│   └── migrations/             # Migrações de schema
│
├── auth/                        # Autenticação e autorização
│   ├── models.py               # User, RevokedToken
│   ├── schema.py               # UserCreate, UserResponse
│   ├── router.py               # /auth/login, /auth/logout
│   └── security.py             # JWT, hash de senhas
│
├── pedidos/                     # Módulo de pedidos
│   ├── schema.py               # Pedido, ItemPedido, Status, Prioridade
│   ├── router.py               # CRUD de pedidos
│   ├── service.py              # Lógica de negócio
│   ├── images.py               # Gerenciamento de imagens
│   ├── realtime.py             # Notificações WebSocket
│   └── utils.py                # Utilitários
│
├── fichas/                      # Fichas de produção
│   ├── schema.py               # Ficha, FichaTemplateModel
│   ├── router.py               # CRUD de fichas, geração de PDF
│   └── image_storage.py        # Upload de imagens para fichas
│
├── producoes/                   # Tipos de produção
│   ├── schema.py               # Producao (painel, totem, lona, etc.)
│   └── router.py               # CRUD de tipos de produção
│
├── maquinas/                    # Máquinas e equipamentos
│   ├── schema.py               # Machine
│   └── router.py               # CRUD de máquinas
│
├── clientes/                    # Cadastro de clientes
│   ├── schema.py               # Cliente
│   └── router.py               # CRUD de clientes
│
├── vendedores/                  # Cadastro de vendedores
│   ├── schema.py               # Vendedor
│   └── router.py               # CRUD de vendedores
│
├── designers/                   # Cadastro de designers
│   ├── schema.py               # Designer
│   └── router.py               # CRUD de designers
│
├── materiais/                   # Materiais (tecidos, etc.)
│   ├── schema.py               # Material
│   └── router.py               # CRUD de materiais
│
├── pagamentos/                  # Formas de pagamento
│   ├── schema.py               # Pagamento
│   └── router.py               # CRUD de pagamentos
│
├── envios/                      # Formas de envio
│   ├── schema.py               # Envio
│   └── router.py               # CRUD de envios
│
├── reposicoes/                  # Reposições de pedidos
│   ├── schema.py               # Reposicao
│   └── router.py               # CRUD de reposições
│
├── notificacoes/                # Sistema de notificações
│   ├── schema.py               # Notificacao
│   └── router.py               # CRUD de notificações
│
├── relatorios/                  # Relatórios gerais
│   ├── schema.py               # RelatorioTemplateModel
│   ├── router.py               # Endpoints de relatórios
│   └── fechamentos.py          # Lógica de fechamentos
│
├── relatorios_fechamentos/      # Relatórios de fechamento
│   ├── schema.py               # Schemas de relatórios
│   ├── router.py               # Endpoints específicos
│   └── fechamentos.py          # Cálculos e agregações
│
├── relatorios_envios/           # Relatórios de envios
│   ├── schema.py
│   └── router.py
│
├── users/                       # Gerenciamento de usuários
│   ├── schema.py               # UserUpdate
│   └── router.py               # CRUD de usuários (admin)
│
├── admin/                       # Funcionalidades administrativas
│   └── router.py               # Endpoints admin
│
├── middleware/                  # Middlewares customizados
│   └── metrics.py              # Métricas de performance
│
├── scripts/                     # Scripts utilitários
│   ├── seed_pedidos.py         # Popular banco com dados fake
│   ├── seed_producoes.py       # Seed de tipos de produção
│   ├── backup_database.py      # Backup do banco
│   ├── db_maintenance.py       # Manutenção do SQLite
│   ├── remove_duplicates.py    # Remover duplicatas
│   ├── deploy.ps1              # Deploy Windows (PowerShell)
│   ├── update.ps1              # Atualização automática
│   └── update_from_share.ps1   # Atualização via rede
│
├── tests/                       # Testes automatizados
│   └── ...
│
├── docs/                        # Documentação adicional
│   └── ...
│
└── shared/                      # Diretórios compartilhados (runtime)
    ├── db/                     # Banco de dados
    ├── media/                  # Arquivos de mídia
    ├── logs/                   # Logs
    └── backups/                # Backups
```

---

## 🧩 Módulos Principais

### 1. **Auth (Autenticação)**
- **Responsabilidade:** Gerenciar autenticação de usuários, geração de tokens JWT, logout
- **Modelos:** `User`, `RevokedToken`
- **Endpoints:**
  - `POST /auth/login` - Login e geração de token
  - `POST /auth/logout` - Logout e revogação de token
  - `GET /auth/me` - Obter dados do usuário autenticado

### 2. **Pedidos**
- **Responsabilidade:** CRUD completo de pedidos, gerenciamento de itens, status, imagens
- **Modelos:** `Pedido`, `ItemPedido`, `PedidoImagem`
- **Funcionalidades:**
  - Criação de pedidos com múltiplos itens
  - Upload de imagens em base64
  - Filtros por data, status, cliente
  - Atualização parcial (PATCH)
  - Notificações em tempo real via WebSocket

### 3. **Fichas de Produção**
- **Responsabilidade:** Gerar fichas de produção para impressão
- **Modelos:** `Ficha`, `FichaTemplateModel`
- **Funcionalidades:**
  - Templates customizáveis
  - Geração de PDF
  - Upload de imagens para fichas

### 4. **Produção**
- **Responsabilidade:** Gerenciar tipos de produção (painel, totem, lona, adesivo, etc.)
- **Modelos:** `Producao`
- **Funcionalidades:**
  - CRUD de tipos de produção
  - Associação com pedidos

### 5. **Máquinas**
- **Responsabilidade:** Cadastro e controle de máquinas de produção
- **Modelos:** `Machine`
- **Funcionalidades:**
  - CRUD de máquinas
  - Rastreamento de uso

### 6. **Relatórios**
- **Responsabilidade:** Gerar relatórios financeiros, de fechamento, tendências
- **Módulos:**
  - `relatorios_fechamentos` - Relatórios de fechamento por período
  - `relatorios_envios` - Relatórios de envios
- **Funcionalidades:**
  - Relatórios semanais/mensais
  - Agrupamento por cliente, vendedor, designer, tipo de produção
  - Análise de tendências
  - Cálculo de valores totais

### 7. **Notificações**
- **Responsabilidade:** Sistema de notificações para usuários
- **Modelos:** `Notificacao`
- **Funcionalidades:**
  - Notificações push
  - Histórico de notificações

### 8. **Cadastros Auxiliares**
- **Clientes:** Cadastro de clientes
- **Vendedores:** Cadastro de vendedores
- **Designers:** Cadastro de designers
- **Materiais:** Cadastro de materiais (tecidos, etc.)
- **Pagamentos:** Formas de pagamento
- **Envios:** Formas de envio

---

## 📊 Modelos de Dados

### **Pedido** (Tabela: `pedidos`)

```python
class Pedido(SQLModel, table=True):
    id: int                              # PK
    numero: str                          # Número do pedido (único)
    data_entrada: str                    # Data de entrada (YYYY-MM-DD)
    data_entrega: str                    # Data de entrega prevista
    observacao: str                      # Observações gerais
    prioridade: Prioridade               # NORMAL | ALTA
    status: Status                       # pendente | em_producao | pronto | entregue | cancelado
    
    # Cliente
    cliente: str                         # Nome do cliente
    telefone_cliente: str
    cidade_cliente: str
    estado_cliente: str
    
    # Financeiro
    valor_total: str
    valor_frete: str
    valor_itens: str
    tipo_pagamento: str
    obs_pagamento: str
    
    # Envio
    forma_envio: str
    forma_envio_id: int
    
    # Status de Produção
    financeiro: bool                     # Aprovado financeiramente?
    conferencia: bool                    # Conferido?
    sublimacao: bool                     # Sublimação concluída?
    costura: bool                        # Costura concluída?
    expedicao: bool                      # Expedido?
    pronto: bool                         # Pronto para entrega?
    sublimacao_maquina: str              # Máquina usada
    sublimacao_data_impressao: str       # Data de impressão
    
    # Items (JSON)
    items: str                           # JSON array de ItemPedido
    
    # Auditoria
    data_criacao: datetime
    ultima_atualizacao: datetime
```

### **ItemPedido** (Armazenado como JSON em `Pedido.items`)

```python
class ItemPedido(SQLModel):
    id: int                              # ID do item
    tipo_producao: str                   # painel | totem | lona | adesivo
    descricao: str                       # Descrição do produto
    largura: str                         # Largura (metros)
    altura: str                          # Altura (metros)
    metro_quadrado: str                  # Área total
    vendedor: str                        # Nome do vendedor
    designer: str                        # Nome do designer
    tecido: str                          # Tipo de tecido
    acabamento: Acabamento               # overloque, elastico, ilhos
    emenda: str                          # sem-emenda | com-emenda
    observacao: str                      # Observações do item
    valor_unitario: str                  # Valor unitário
    imagem: str                          # URL da imagem ou base64
    imagem_path: str                     # Caminho relativo da imagem
    composicao_tecidos: str              # Composição de tecidos
    machine_id: int                      # ID da máquina
    
    # Campos de produção
    rip_maquina: str                     # RIP da máquina
    data_impressao: str                  # Data de impressão
    perfil_cor: str                      # Perfil de cor
    tecido_fornecedor: str               # Fornecedor do tecido
    
    # Campos adicionais (acabamentos, quantidades, etc.)
    # ... (vários campos opcionais para diferentes tipos de produção)
```

### **User** (Tabela: `user`)

```python
class User(SQLModel, table=True):
    id: int                              # PK
    username: str                        # Único, indexado
    password_hash: str                   # Hash bcrypt
    is_admin: bool                       # Permissão de admin
    is_active: bool                      # Usuário ativo?
    created_at: datetime
    updated_at: datetime
```

### **Ficha** (Tabela: `fichas`)

```python
class Ficha(SQLModel, table=True):
    id: int                              # PK
    pedido_id: int                       # FK para pedidos
    item_index: int                      # Índice do item no pedido
    template_id: int                     # FK para template
    data_criacao: datetime
    # ... (campos customizáveis do template)
```

### **Machine** (Tabela: `machines`)

```python
class Machine(SQLModel, table=True):
    id: int                              # PK
    name: str                            # Nome da máquina
    type: str                            # Tipo (impressora, cortadora, etc.)
    status: str                          # ativa | inativa | manutencao
    # ... (outros campos de configuração)
```

### **Enums Importantes**

```python
class Status(str, Enum):
    PENDENTE = "pendente"
    EM_PRODUCAO = "em_producao"
    PRONTO = "pronto"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"

class Prioridade(str, Enum):
    NORMAL = "NORMAL"
    ALTA = "ALTA"
```

---

## 🔌 API Endpoints

### **Autenticação** (`/auth`)

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| POST | `/auth/login` | Login e geração de token JWT | ❌ |
| POST | `/auth/logout` | Logout e revogação de token | ✅ |
| GET | `/auth/me` | Dados do usuário autenticado | ✅ |

### **Pedidos** (`/pedidos`)

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| GET | `/pedidos/` | Listar todos os pedidos (com filtros) | ✅ |
| GET | `/pedidos/{id}` | Obter pedido por ID | ✅ |
| POST | `/pedidos/` | Criar novo pedido | ✅ |
| PATCH | `/pedidos/{id}` | Atualizar pedido (parcial) | ✅ |
| DELETE | `/pedidos/{id}` | Deletar pedido | ✅ |
| GET | `/pedidos/status/{status}` | Listar pedidos por status | ✅ |
| GET | `/pedidos/imagens/{imagem_id}` | Download de imagem | ✅ |

**Filtros disponíveis em GET `/pedidos/`:**
- `data_inicio` - Data inicial (YYYY-MM-DD)
- `data_fim` - Data final (YYYY-MM-DD)
- `date_mode` - Modo de filtro: `entrada` | `entrega` | `qualquer`
- `status` - Filtrar por status
- `cliente` - Filtrar por nome do cliente

### **Fichas** (`/fichas`)

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| GET | `/fichas/` | Listar fichas | ✅ |
| GET | `/fichas/{id}` | Obter ficha por ID | ✅ |
| POST | `/fichas/` | Criar ficha | ✅ |
| PATCH | `/fichas/{id}` | Atualizar ficha | ✅ |
| DELETE | `/fichas/{id}` | Deletar ficha | ✅ |
| GET | `/fichas/{id}/pdf` | Gerar PDF da ficha | ✅ |

### **Relatórios de Fechamento** (`/relatorios-fechamentos`)

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| GET | `/pedidos/relatorio` | Relatório geral de pedidos | ✅ |
| GET | `/pedidos/relatorio-semanal` | Relatório semanal | ✅ |
| GET | `/pedidos/quantidade` | Quantidade de pedidos | ✅ |
| GET | `/pedidos/por-status` | Agrupamento por status | ✅ |
| GET | `/pedidos/por-cliente` | Agrupamento por cliente | ✅ |
| GET | `/pedidos/por-vendedor` | Agrupamento por vendedor | ✅ |
| GET | `/pedidos/por-designer` | Agrupamento por designer | ✅ |
| GET | `/pedidos/por-tipo-producao` | Agrupamento por tipo | ✅ |
| GET | `/pedidos/tendencia` | Análise de tendências | ✅ |
| GET | `/pedidos/valor-total` | Valor total por período | ✅ |

### **Outros Módulos**

Cada módulo (clientes, vendedores, designers, materiais, pagamentos, envios, máquinas, produção) segue o padrão CRUD:

- `GET /{modulo}/` - Listar todos
- `GET /{modulo}/{id}` - Obter por ID
- `POST /{modulo}/` - Criar
- `PATCH /{modulo}/{id}` - Atualizar
- `DELETE /{modulo}/{id}` - Deletar

### **Health Check**

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| GET | `/` | Informações da API | ❌ |
| GET | `/health` | Status de saúde (API + DB) | ❌ |

---

## 🔐 Autenticação e Segurança

### **Fluxo de Autenticação**

1. **Login:**
   - Cliente envia `username` e `password` para `POST /auth/login`
   - API valida credenciais (bcrypt)
   - API gera token JWT com expiração de 8 dias
   - Token retornado ao cliente

2. **Requisições Autenticadas:**
   - Cliente envia token no header: `Authorization: Bearer <token>`
   - Middleware valida token e extrai dados do usuário
   - Requisição processada se token válido

3. **Logout:**
   - Cliente envia token para `POST /auth/logout`
   - Token adicionado à tabela `revoked_tokens`
   - Token não pode mais ser usado

### **Configurações de Segurança** (`config.py`)

```python
SECRET_KEY: str = "change-me"                    # ⚠️ Alterar em produção!
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 dias
```

### **CORS**

O sistema permite requisições de:
- `http://localhost:1420` (Tauri)
- `http://tauri.localhost`
- `tauri://localhost`
- IPs locais (192.168.x.x, 10.x.x.x)

---

## 🔄 Sistema de Tempo Real (WebSocket)

### **Endpoint WebSocket**

```
ws://localhost:8000/ws/orders?token=<JWT_TOKEN>
```

### **Funcionalidades**

- **Notificações de Pedidos:** Quando um pedido é criado/atualizado/deletado, todos os clientes conectados recebem notificação
- **Broadcast entre Clientes:** Clientes podem enviar mensagens broadcast (ex: "usuário X está editando pedido Y")
- **Heartbeat/Ping-Pong:** Mantém conexão ativa

### **Exemplo de Mensagem**

```json
{
  "type": "order_updated",
  "order_id": 123,
  "user_id": 1,
  "username": "admin",
  "broadcast": true
}
```

### **Implementação** (`pedidos/realtime.py`)

```python
class OrdersNotifier:
    def __init__(self):
        self.connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        # Conectar usuário
    
    async def disconnect(self, websocket: WebSocket):
        # Desconectar usuário
    
    async def broadcast(self, message: dict):
        # Enviar para todos os clientes
    
    async def broadcast_except(self, message: dict, exclude_websocket: WebSocket):
        # Enviar para todos exceto remetente
```

---

## 📁 Gerenciamento de Mídia

### **Upload de Imagens**

As imagens podem ser enviadas de duas formas:

1. **Base64 (no JSON do pedido):**
   ```json
   {
     "items": [
       {
         "imagem": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
       }
     ]
   }
   ```

2. **Arquivo físico (multipart/form-data):**
   - Endpoint específico para upload

### **Armazenamento**

- **Diretório:** `shared/media/pedidos/`
- **Estrutura:** `{pedido_id}/{item_index}_{timestamp}.{ext}`
- **Tabela:** `pedido_imagens` (metadados)

### **Configurações** (`config.py`)

```python
MEDIA_ROOT: str = "media"              # Diretório raiz
MAX_IMAGE_SIZE_MB: int = 10            # Tamanho máximo
```

---

## 📈 Relatórios e Análises

### **Relatórios Disponíveis**

1. **Relatório Geral de Pedidos**
   - Filtro por data de entrada/entrega
   - Agrupamento por status
   - Valores totais

2. **Relatório Semanal**
   - Pedidos da semana atual
   - Comparação com semana anterior

3. **Agrupamentos:**
   - Por cliente (top clientes)
   - Por vendedor (performance)
   - Por designer (carga de trabalho)
   - Por tipo de produção (produtos mais vendidos)

4. **Análise de Tendências**
   - Crescimento/decrescimento de pedidos
   - Valores médios por período

5. **Fechamento Financeiro**
   - Valores totais por período
   - Valores por forma de pagamento
   - Valores por status de produção

### **Exemplo de Endpoint**

```http
GET /relatorios-fechamentos/pedidos/por-cliente?data_inicio=2026-01-01&data_fim=2026-01-31
```

**Resposta:**
```json
{
  "total_clientes": 15,
  "clientes": [
    {
      "cliente": "João Silva",
      "total_pedidos": 10,
      "valor_total": "5000.00"
    }
  ]
}
```

---

## ⚙️ Configuração e Deploy

### **Variáveis de Ambiente** (`.env`)

```bash
# Banco de Dados
DATABASE_URL=sqlite:///shared/db/banco.db

# Diretórios
API_ROOT=.
MEDIA_ROOT=media
LOG_DIR=logs

# Segurança
SECRET_KEY=your-super-secret-key-here
ENVIRONMENT=production

# CORS (opcional)
BACKEND_CORS_ORIGINS=http://localhost:1420,http://tauri.localhost
```

### **Instalação Manual**

```bash
# 1. Clonar repositório
git clone <url-do-repositorio>
cd api-sgp

# 2. Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar .env
cp .env.example .env
# Editar .env com suas configurações

# 5. Executar
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Deploy Automatizado (Windows)**

```powershell
# Deploy básico (Hypercorn com 4 workers)
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1

# Deploy customizado
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 `
  -Port 8080 `
  -Workers 2 `
  -ProjectPath "C:\SGP\api-sgp" `
  -CreateEnvFile
```

**O script automatiza:**
- ✅ Verificação de pré-requisitos (Python, pip, NSSM)
- ✅ Instalação de dependências
- ✅ Criação de diretórios (db, media, backups)
- ✅ Instalação como serviço Windows (NSSM)
- ✅ Configuração de logs
- ✅ Inicialização automática

### **Produção com Múltiplos Workers**

```bash
# Hypercorn (recomendado para Windows)
hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio

# Uvicorn (Linux/Mac)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Número de workers recomendado:**
- 2-4 cores: 2-3 workers
- 4-8 cores: 4-6 workers
- 8+ cores: 6-8 workers

---

## 🔄 Fluxo de Trabalho

### **Ciclo de Vida de um Pedido**

```
1. CRIAÇÃO
   ├─ Cliente faz pedido
   ├─ Vendedor registra no sistema
   ├─ Status: PENDENTE
   └─ Notificação enviada via WebSocket

2. APROVAÇÃO FINANCEIRA
   ├─ Financeiro aprova pagamento
   ├─ Campo `financeiro` = true
   └─ Status: PENDENTE → EM_PRODUCAO

3. PRODUÇÃO
   ├─ Designer cria arte
   ├─ Sublimação imprime
   │  ├─ Campo `sublimacao` = true
   │  ├─ `sublimacao_maquina` = "Máquina 1"
   │  └─ `sublimacao_data_impressao` = "2026-01-31"
   ├─ Costura finaliza
   │  └─ Campo `costura` = true
   └─ Conferência valida
      └─ Campo `conferencia` = true

4. EXPEDIÇÃO
   ├─ Produto embalado
   ├─ Campo `expedicao` = true
   ├─ Status: EM_PRODUCAO → PRONTO
   └─ Notificação para cliente

5. ENTREGA
   ├─ Produto enviado/retirado
   ├─ Status: PRONTO → ENTREGUE
   └─ Pedido finalizado
```

### **Fluxo de Autenticação**

```
1. Login
   └─ POST /auth/login
      ├─ Validar credenciais
      ├─ Gerar JWT token
      └─ Retornar token + dados do usuário

2. Requisições Autenticadas
   └─ Header: Authorization: Bearer <token>
      ├─ Middleware valida token
      ├─ Verifica se não está revogado
      └─ Extrai user_id e permissões

3. Logout
   └─ POST /auth/logout
      ├─ Adicionar token à tabela revoked_tokens
      └─ Token não pode mais ser usado
```

---

## 🛠️ Manutenção e Backups

### **Backup do Banco de Dados**

```bash
# Backup manual
python scripts/backup_database.py --dest backups/db --retention 10

# Backup automático (cron/task scheduler)
0 2 * * * python /path/to/api-sgp/scripts/backup_database.py --dest /path/to/backups --retention 30
```

### **Manutenção do SQLite**

```bash
# Verificar integridade + VACUUM
python scripts/db_maintenance.py --analyze --optimize

# Apenas verificar integridade
python scripts/db_maintenance.py --no-vacuum
```

### **Remover Duplicatas**

```bash
# Verificar duplicatas (dry-run)
python scripts/remove_duplicates.py --dry-run

# Remover duplicatas de uma tabela
python scripts/remove_duplicates.py --table clientes --confirm

# Remover todas as duplicatas
python scripts/remove_duplicates.py --confirm
```

### **Popular Banco com Dados Fake**

```bash
# Criar 10 pedidos fake
python scripts/seed_pedidos.py --amount 10

# Criar pedidos com intervalo de datas e imagem
python scripts/seed_pedidos.py --amount 50 \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --image-path ./exemplo.jpg

# Criar tipos de produção
python scripts/seed_producoes.py
```

### **Atualização Automática**

#### **Via MSI (Windows)**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update.ps1 `
  -ManifestUrl https://sgp.finderbit.com.br/update/releases/latest.json `
  -MsiArgs "/qn"
```

#### **Via ZIP (Rede Compartilhada)**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update_from_share.ps1 `
  -WatchPath "\\SERVIDOR\share\api" `
  -ApiRoot "C:\api" `
  -ServiceName "SGP-API" `
  -Force
```

---

## 📝 Notas Importantes

### **Limitações do SQLite**

- ⚠️ **Concorrência:** SQLite tem limitações com múltiplos workers escrevendo simultaneamente
- ⚠️ **Produção de Alta Carga:** Para alta concorrência, considere migrar para PostgreSQL
- ✅ **Ideal para:** Pequenas/médias empresas, até ~100 usuários simultâneos

### **Segurança**

- 🔒 **Alterar SECRET_KEY em produção!** Nunca use o valor padrão
- 🔒 **HTTPS obrigatório em produção** para proteger tokens JWT
- 🔒 **Validar permissões** em endpoints sensíveis (admin)

### **Performance**

- ⚡ **GZip ativado** para comprimir respostas (threshold: 100 bytes)
- ⚡ **ORJson** para serialização rápida de JSON
- ⚡ **Índices no banco** para queries rápidas (numero, data_entrada, data_entrega, status, cliente)

### **Logs**

- 📋 Logs armazenados em `shared/logs/`
- 📋 Rotação automática de logs
- 📋 Nível configurável via `LOG_LEVEL` (DEBUG, INFO, WARNING, ERROR)

---

## 🎓 Exemplos de Uso

### **Criar Pedido**

```bash
curl -X POST http://localhost:8000/pedidos/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "numero": "001",
    "data_entrada": "2026-01-31",
    "data_entrega": "2026-02-05",
    "cliente": "João Silva",
    "telefone_cliente": "(11) 99999-9999",
    "cidade_cliente": "São Paulo",
    "valor_total": "500.00",
    "items": [
      {
        "tipo_producao": "painel",
        "descricao": "Painel de Fundo",
        "largura": "3.00",
        "altura": "2.50",
        "metro_quadrado": "7.50",
        "vendedor": "Maria",
        "designer": "Carlos",
        "tecido": "Banner",
        "valor_unitario": "500.00"
      }
    ]
  }'
```

### **Atualizar Status**

```bash
curl -X PATCH http://localhost:8000/pedidos/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "em_producao",
    "financeiro": true
  }'
```

### **Listar Pedidos por Período**

```bash
curl "http://localhost:8000/pedidos/?data_inicio=2026-01-01&data_fim=2026-01-31&date_mode=entrega" \
  -H "Authorization: Bearer <token>"
```

---

## 📞 Suporte e Contribuição

Para dúvidas, bugs ou sugestões, entre em contato com a equipe de desenvolvimento.

---

**Desenvolvido com ❤️ usando FastAPI e SQLModel**
