# API Sistema de Gestão de Produção (SGP)

API para gerenciamento de pedidos de produção gráfica, desenvolvida com FastAPI e SQLModel.

## 🚀 Características

- **FastAPI**: Framework moderno e rápido para APIs
- **SQLModel**: ORM moderno baseado em Pydantic e SQLAlchemy
- **SQLite**: Banco de dados simples e eficiente
- **Validação automática**: Schemas Pydantic para validação de dados
- **Documentação automática**: Swagger UI em `/docs`

## 📋 Estrutura do Projeto

```
api-sgp/
├── pedidos/           # Módulo de pedidos
│   ├── schema.py      # Schemas SQLModel
│   └── router.py      # Rotas da API
├── database/          # Configuração do banco
│   └── database.py    # Engine e sessões SQLModel
├── main.py            # Aplicação principal
├── base.py            # Configurações base
└── config.py          # Configurações da aplicação
```

## 🛠️ Instalação

### Instalação Manual

1. **Clone o repositório**
```bash
git clone <url-do-repositorio>
cd api-sgp
```

2. **Instale as dependências**
```bash
pip install -r requirements.txt
```

3. **Execute a aplicação**

**Opção 1: Hypercorn (com múltiplos workers - Recomendado para produção no Windows)**
```bash
hypercorn main:app --bind 0.0.0.0:8000 --workers 4
```

**Opção 2: Uvicorn (desenvolvimento ou sem workers)**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Nota:** No Windows, o Uvicorn não suporta múltiplos workers. Use Hypercorn para melhor performance em produção.

### 🚀 Deploy Automatizado no Windows Server

Para facilitar o deploy no Windows Server, use o script automatizado:

```powershell
# Deploy básico (Hypercorn com 4 workers, porta 8000)
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1

# Deploy com configurações customizadas
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 `
  -Port 8080 `
  -Workers 2 `
  -ProjectPath "C:\SGP\api-sgp" `
  -CreateEnvFile

# Deploy apenas dependências (sem instalar serviço)
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -SkipServiceInstall

# Deploy com Uvicorn (sem workers)
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -UseHypercorn $false -Workers 0
```

**O script automatiza:**
- ✅ Verificação de pré-requisitos (Python, pip, NSSM)
- ✅ Instalação de dependências Python
- ✅ Criação de diretórios necessários (db, media, backups)
- ✅ Criação de arquivo .env (opcional)
- ✅ Instalação como serviço Windows usando NSSM
- ✅ Configuração automática de logs
- ✅ Inicialização do serviço

**Requisitos:**
- Executar como Administrador (para instalar serviço)
- Python 3.12+ instalado e no PATH
- PowerShell com permissão de execução de scripts

**Nota:** O script baixa e instala o NSSM automaticamente se não estiver instalado.

## 📚 Endpoints da API

## 🔄 Sincronização Robusta (Outbox)

A sincronização com o banco remoto MySQL agora usa uma fila local resiliente (`sync_outbox`) + worker com retry.

Documentação completa em: `docs/SYNC_OUTBOX.md`

### Pedidos

#### POST `/api/v1/pedidos/`
Cria um novo pedido.

**Exemplo de JSON:**
```json
{
  "numero": "1",
  "data_entrada": "2024-01-15",
  "data_entrega": "2024-01-20",
  "observacao": "Pedido urgente para evento",
  "prioridade": "ALTA",
  "status": "pendente",
  
  "cliente": "João Silva",
  "telefone_cliente": "(11) 99999-9999",
  "cidade_cliente": "São Paulo",
  
  "valor_total": "450.00",
  "valor_frete": "25.00",
  "valor_itens": "425.00",
  "tipo_pagamento": "1",
  "obs_pagamento": "2x sem juros",
  
  "forma_envio": "Sedex",
  "forma_envio_id": 1,
  
  "items": [
    {
      "id": 1,
      "tipo_producao": "painel",
      "descricao": "Painel de Fundo para Evento",
      "largura": "3.00",
      "altura": "2.50",
      "metro_quadrado": "7.50",
      "vendedor": "Maria Santos",
      "designer": "Carlos Lima",
      "tecido": "Banner",
      "acabamento": {
        "overloque": true,
        "elastico": false,
        "ilhos": true
      },
      "emenda": "sem-emenda",
      "observacao": "Impressão em alta resolução",
      "valor_unitario": "250.00",
      "imagem": "data:image/jpeg;base64,..."
    }
  ],
  
  "financeiro": false,
  "sublimacao": false,
  "costura": false,
  "expedicao": false
}
```

#### GET `/api/v1/pedidos/`
Lista todos os pedidos.
Suporta filtros `data_inicio`, `data_fim` e `date_mode` (padrao `entrada`, ou `entrega`/`qualquer`).

#### GET `/api/v1/pedidos/{pedido_id}`
Obtém um pedido específico por ID.

#### PATCH `/api/v1/pedidos/{pedido_id}`
Atualiza um pedido existente (aceita atualizações parciais).

#### DELETE `/api/v1/pedidos/{pedido_id}`
Deleta um pedido.

#### GET `/api/v1/pedidos/status/{status}`
Lista pedidos por status específico.

#### GET `/api/v1/pedidos/imagens/{imagem_id}`
Retorna o arquivo físico associado a um item de pedido.  
Envie o campo `imagem` dos itens como `data:image/<tipo>;base64,...` (mesmo formato já aceito) e a API armazenará o arquivo dentro de `MEDIA_ROOT`, retornando apenas uma URL para download quando o pedido for listado.

## 📊 Relatórios de Fechamentos

Base path: `/api/v1/relatorios-fechamentos`

- `GET /pedidos/relatorio`
- Filtro de data considera apenas `data_entrega` e `data_entrada` (sem `data_criacao`).
- `GET /pedidos/relatorio-semanal`
- `GET /pedidos/quantidade`
- `GET /pedidos/por-status`
- `GET /pedidos/por-cliente`
- `GET /pedidos/por-vendedor`
- `GET /pedidos/por-designer`
- `GET /pedidos/por-tipo-producao`
- `GET /pedidos/tendencia`
- `GET /pedidos/valor-total`

## 🗄️ Estrutura do Banco

### Tabela `pedidos`
- **id**: Chave primária
- **numero**: Número do pedido
- **data_entrada**: Data de entrada
- **data_entrega**: Data de entrega
- **observacao**: Observações do pedido
- **prioridade**: NORMAL ou ALTA
- **status**: pendente, em_producao, pronto, entregue, cancelado
- **cliente**: Nome do cliente
- **telefone_cliente**: Telefone do cliente
- **cidade_cliente**: Cidade do cliente
- **valor_total**: Valor total do pedido
- **valor_frete**: Valor do frete
- **valor_itens**: Valor dos itens
- **tipo_pagamento**: Tipo de pagamento
- **obs_pagamento**: Observações do pagamento
- **forma_envio**: Forma de envio
- **forma_envio_id**: ID da forma de envio
- **financeiro**: Status financeiro
- **sublimacao**: Status de sublimação
- **costura**: Status de costura
- **expedicao**: Status de expedição
- **items**: JSON com os itens do pedido
- **data_criacao**: Data de criação
- **ultima_atualizacao**: Data da última atualização

### Tabela `pedido_imagens`
- **id**: Chave primária
- **pedido_id**: Referência ao pedido
- **item_index/item_identificador**: Relação com o item correspondente
- **filename / mime_type**: Metadados do arquivo original
- **path**: Caminho relativo dentro de `MEDIA_ROOT`
- **tamanho / criado_em**: Informações de auditoria

## 🧪 Testes

Execute o script de teste para verificar se a API está funcionando:

```bash
python test_pedido.py
```

## 🧪 Dados de Exemplo

Para popular o banco com pedidos de diferentes status e validar o comportamento do frontend/API, execute:

```bash
python scripts/seed_pedidos.py --amount 10
```

Use `--amount` (`-n`) para informar quantos pedidos deseja inserir. O script gera registros distribuídos entre os status (pendente, em produção, pronto, entregue e cancelado) e é idempotente, ou seja, não duplica números já existentes.

### 🌱 Seed do banco (dados fake)

O projeto inclui scripts para popular o banco com dados fictícios de forma rápida.

Pedidos de exemplo:
```bash
uv run python scripts/seed_pedidos.py --amount 10
```

Com intervalo de data de entrega e imagem aplicada a todos os itens:
```bash
uv run python scripts/seed_pedidos.py --amount 10 --start-date 2026-01-10 --end-date 2026-01-20 --image-path ./caminho/para/imagem.jpg
```

Para criar uma nova leva sem colidir com numeros antigos, use outro prefixo:
```bash
uv run python scripts/seed_pedidos.py --amount 70 --start-date 2026-01-18 --end-date 2026-01-20 --prefix DEV --image-path ./caminho/para/imagem.jpg
```

Tipos de produção:
```bash
uv run python scripts/seed_producoes.py
```

Se preferir rodar sem `uv`, use `python` diretamente. Os scripts criam registros de teste respeitando a estrutura atual do banco.
Por padrao, o script usa o `DATABASE_URL` do ambiente/.env (ex.: `sqlite:///db/dev.db`). Para apontar para outro banco, exporte `DATABASE_URL` antes de rodar.

## 💾 Backups e manutenção do banco

Scripts utilitários foram adicionados em `scripts/` para operações rotineiras com o SQLite:

- **Backup**  
  ```bash
  python scripts/backup_database.py --dest backups/db --retention 10
  ```  
  Cria um backup consistente usando a API nativa do SQLite. O diretório de destino é criado automaticamente e a opção `--retention` limita quantos arquivos manter (0 desativa a limpeza).

- **Manutenção**  
  ```bash
  python scripts/db_maintenance.py --analyze --optimize
  ```  
  Executa `PRAGMA integrity_check` e, por padrão, um `VACUUM`. Flags opcionais permitem rodar `ANALYZE` e `PRAGMA optimize`. Use `--no-vacuum` para pular a compactação.

- **Remover Duplicatas**  
  ```bash
  # Verificar duplicatas sem remover (recomendado primeiro)
  python scripts/remove_duplicates.py --dry-run
  
  # Remover duplicatas de uma tabela específica
  python scripts/remove_duplicates.py --table clientes --confirm
  
  # Remover todas as duplicatas
  python scripts/remove_duplicates.py --confirm
  ```  
  Identifica e remove registros duplicados em todas as tabelas principais. Mantém apenas o registro mais antigo (menor ID) e remove as duplicatas. O script verifica duplicatas em:
  - **Clientes**: mesmo nome + telefone
  - **Vendedores**: mesmo nome
  - **Designers**: mesmo nome
  - **Materiais**: mesmo nome
  - **Pagamentos**: mesmo nome
  - **Envios**: mesmo nome
  - **Pedidos**: mesmo número
  - **Usuários**: mesmo username
  
  **⚠️ Importante:** Sempre execute primeiro com `--dry-run` para ver o que será removido antes de confirmar a remoção.

## 🔄 Atualizador automático no Windows

O script PowerShell `scripts/update.ps1` consulta um manifesto JSON, compara a versão local e instala automaticamente o MSI quando existe build nova para Windows:

```jsonc
{
  "version": "1.0.1",
  "notes": "Correções gerais.",
  "pub_date": "2025-01-01T00:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "url": "https://sgp.finderbit.com.br/update/releases/windows/SGP_1.0.1_x64.msi"
    }
  }
}
```

Execução manual:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update.ps1 `
  -ManifestUrl https://sgp.finderbit.com.br/update/releases/latest.json `
  -MsiArgs "/qn"
```

- O arquivo `C:\ProgramData\SGP\version.json` guarda a versão instalada; delete-o ou use `-Force` para reinstalar.
- Ajuste `-DownloadDir` se quiser armazenar os instaladores em outro local.
- Para rodar automaticamente, cadastre esse comando no **Task Scheduler** com privilégios elevados e monitore o histórico da tarefa.

### Atualizacao automatica via ZIP (pasta compartilhada)

Se voce distribui o backend em ZIP, use o script `scripts/update_from_share.ps1`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update_from_share.ps1 `
  -WatchPath "\\SERVIDOR\share\api" `
  -ApiRoot "C:\api" `
  -ServiceName "SGP-API" `
  -Force
```

O ZIP precisa conter a versao no nome (ex.: `api-sgp-1.0.8.zip`). O script
aplica a versao mais recente e grava o ultimo ZIP aplicado em `shared\update\last_zip.txt`.

## 📖 Documentação da API

Acesse a documentação interativa da API em:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🔧 Configuração

As configurações podem ser alteradas no arquivo `config.py` ou através de variáveis de ambiente:

- `DATABASE_URL`: URL do banco de dados
- `MEDIA_ROOT`: Diretório onde as imagens dos pedidos serão persistidas
- `MAX_IMAGE_SIZE_MB`: Tamanho máximo aceito para upload via base64
- `API_V1_STR`: Prefixo da API
- `PROJECT_NAME`: Nome do projeto
- `VERSION`: Versão da API
- `BACKEND_CORS_ORIGINS`: Origens permitidas para CORS
- `BACKEND_CORS_ALLOW_ORIGIN_REGEX`: Regex para origens dinâmicas, como `tauri.localhost`, rede local e URLs HTTPS do `ngrok`

## 🚀 Múltiplos Workers no Windows

Para melhor performance em produção no Windows Server, use **Hypercorn** que suporta múltiplos workers:

### Instalação
```bash
pip install hypercorn
```

### Execução com múltiplos workers
```powershell
hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio
```

### Número de workers recomendado
- **CPU com 2-4 cores**: 2-3 workers
- **CPU com 4-8 cores**: 4-6 workers  
- **CPU com 8+ cores**: 6-8 workers

### Configurar como serviço Windows (NSSM)
```powershell
nssm install SGP-API "C:\Python\python.exe" "-m hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio"
```

**Nota:** Cada worker consome ~50-100MB de memória adicional. Monitore o uso de recursos ao aumentar o número de workers.

**Importante:** Com múltiplos workers e SQLite, pode haver contenção no banco de dados. Para alta concorrência, considere migrar para PostgreSQL.

## 🚀 Melhorias Implementadas

- ✅ **SQLModel apenas**: Removida dependência do SQLAlchemy
- ✅ **Schemas modernos**: Estrutura Pydantic atualizada
- ✅ **Validação robusta**: Enums para status e prioridade
- ✅ **JSON nativo**: Items armazenados como JSON no banco
- ✅ **Tratamento de erros**: Try/catch com rollback
- ✅ **Documentação**: Docstrings em todas as funções
- ✅ **Testes**: Script de teste completo

## 📝 Notas

- A API agora usa apenas SQLModel para ORM
- Os items são armazenados como JSON no banco de dados
- Validação automática de todos os campos
- Suporte a diferentes tipos de produção (painel, totem, lona)
- Timestamps automáticos de criação e atualização
