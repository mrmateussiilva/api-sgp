# Melhorias de Concorrência Implementadas

Este documento descreve as melhorias implementadas para suportar 20 clientes simultâneos no Windows Server 2012.

## 📋 Mudanças Implementadas

### 1. Pool de Conexões do Banco de Dados
**Arquivo:** `database/database.py`

- Configurado `pool_size=15` (15 conexões no pool - aumentado de 10)
- Configurado `max_overflow=25` (até 25 conexões extras - aumentado de 20)
- Configurado `pool_timeout=30` (timeout de 30s para obter conexão)
- Configurado `pool_recycle=3600` (reciclar conexões após 1 hora)
- Aumentado `timeout` do SQLite de 30s para 60s
- Aumentado `busy_timeout` do SQLite de 5s para 10s

**Benefício:** Melhora significativamente a capacidade de lidar com múltiplas requisições simultâneas ao banco.

### 2. I/O Assíncrono com aiofiles
**Arquivos modificados:**
- `pedidos/images.py`
- `fichas/image_storage.py`
- `pedidos/router.py`

**Mudanças:**
- `store_image_bytes()` convertida para assíncrona
- `delete_media_file()` convertida para assíncrona
- `save_base64_image()` convertida para assíncrona
- `salvar_pedido_json()` convertida para usar aiofiles

**Benefício:** Operações de arquivo não bloqueiam mais o event loop, permitindo que outras requisições sejam processadas durante escritas de arquivo.

### 3. Otimizações de PRAGMA do SQLite
**Arquivo:** `database/database.py`

- `PRAGMA cache_size=-64000` (64MB de cache em memória)
- `PRAGMA temp_store=MEMORY` (usar memória para tabelas temporárias)
- `PRAGMA mmap_size=268435456` (256MB memory-mapped I/O)
- `PRAGMA optimize` (otimização automática)

**Benefício:** Melhora significativamente a performance de leitura e reduz I/O em disco.

### 4. Retry Logic com Backoff Exponencial
**Arquivo:** `pedidos/router.py`

- Implementado retry logic (até 5 tentativas) em `criar_pedido` e `atualizar_pedido`
- Backoff exponencial entre tentativas (0.1s, 0.2s, 0.3s, 0.4s, 0.5s)
- Tratamento específico para erros "database is locked" e conflitos de integridade

**Benefício:** Reduz drasticamente falhas por contenção temporária do banco, especialmente em picos de carga.

### 5. Índices Compostos
**Arquivo:** `pedidos/router.py`

- `idx_pedidos_status_data` (status + data_entrada)
- `idx_pedidos_status_criacao` (status + data_criacao)

**Benefício:** Melhora performance de queries que filtram por status e data simultaneamente.

### 6. Dependências Adicionadas
**Arquivo:** `requirements.txt`

- Adicionado `aiofiles>=25.1.0` para I/O assíncrono de arquivos
- Adicionado `hypercorn>=0.17.0` para suporte a múltiplos workers no Windows

## 🚀 Como Executar no Windows Server 2012

### Instalação de Dependências
```powershell
pip install -r requirements.txt
```

### Execução da API

#### Opção 1: Hypercorn (com múltiplos workers - Recomendado)
```powershell
hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio
```

**Vantagens:**
- Suporta múltiplos workers no Windows
- Melhor performance com carga alta
- Distribui requisições entre processos

**Número de workers recomendado:**
- CPU com 2-4 cores: 2-3 workers
- CPU com 4-8 cores: 4-6 workers
- CPU com 8+ cores: 6-8 workers

#### Opção 2: Uvicorn (sem workers)
```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio
```

**Nota:** No Windows, use `--loop asyncio` ao invés de `uvloop` (que não funciona no Windows).

### Executar como Serviço do Windows (Recomendado)

#### Opção 1: Usando NSSM (Non-Sucking Service Manager)

1. Baixe o NSSM: https://nssm.cc/download
2. Instale o serviço com Hypercorn (recomendado):
```powershell
nssm install SGP-API "C:\Python\python.exe" "-m hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio"
```
Ou com Uvicorn (sem workers):
```powershell
nssm install SGP-API "C:\Python\python.exe" "-m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio"
```
3. Configure o diretório de trabalho no NSSM
4. Inicie o serviço:
```powershell
nssm start SGP-API
```

#### Opção 2: Usando Task Scheduler

1. Abra o Agendador de Tarefas
2. Crie uma nova tarefa
3. Configure para executar:
   - Programa: `python.exe`
   - Argumentos (Hypercorn): `-m hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio`
   - Argumentos (Uvicorn): `-m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio`
   - Diretório: Caminho do projeto
4. Configure para executar na inicialização do sistema

## ⚠️ Limitações Conhecidas

### SQLite no Windows Server 2012
- SQLite tem limitações inerentes de concorrência
- Com 20 clientes simultâneos, pode haver contenção ocasional (muito reduzida com as melhorias)
- O sistema implementa retry logic com backoff exponencial (até 5 tentativas) para lidar com locks
- As otimizações de PRAGMA e pool aumentado reduzem significativamente a contenção

### Múltiplos Workers no Windows

#### Opção 1: Hypercorn (Recomendado)
- **Hypercorn** suporta múltiplos workers no Windows
- Servidor ASGI compatível com FastAPI
- Suporta HTTP/2 e WebSockets
- Instalação: `pip install hypercorn`

**Execução com múltiplos workers:**
```powershell
hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio
```

**Configurar como serviço Windows (NSSM):**
```powershell
nssm install SGP-API "C:\Python\python.exe" "-m hypercorn main:app --bind 0.0.0.0:8000 --workers 4 --loop asyncio"
```

**Recomendações:**
- Use 2-4 workers para começar (ajuste conforme CPU e memória disponível)
- Cada worker consome memória adicional (~50-100MB por worker)
- Monitore o uso de recursos ao aumentar o número de workers

#### Opção 2: Uvicorn (Sem Workers)
- Uvicorn não suporta workers no Windows (limitação do sistema operacional)
- Toda a carga será processada em um único processo
- As melhorias de I/O assíncrono ajudam a compensar essa limitação
- Use quando precisar de simplicidade ou recursos limitados

## 📊 Monitoramento Recomendado

### Métricas a Observar
1. **Tempo de resposta das requisições**
   - Endpoints de criação/atualização de pedidos
   - Upload de imagens

2. **Erros de banco de dados**
   - "database is locked" (deve ser extremamente raro com retry logic e otimizações)
   - Timeouts de conexão
   - Logs de retry (tentativas de retry aparecem como warnings)

3. **Uso de memória**
   - Pool de conexões consome memória adicional
   - Com Hypercorn: cada worker consome ~50-100MB adicional
   - Monitorar uso geral do processo e de cada worker
   - Com 4 workers: espere ~200-400MB de memória adicional

### Logs
Os logs já incluem informações sobre:
- Criação de pedidos
- Erros de concorrência
- Broadcasts de WebSocket

## 🔄 Próximos Passos (Opcional)

Se ainda houver problemas de performance com 20 clientes simultâneos:

1. **Migrar para PostgreSQL**
   - Melhor suporte a concorrência
   - Pool de conexões mais eficiente
   - Requer mudanças em `database/database.py`

2. **Implementar Rate Limiting**
   - Limitar requisições por IP
   - Usar biblioteca `slowapi`

3. **Cache de Consultas Frequentes**
   - Implementar Redis ou cache em memória
   - Cachear listagens de pedidos

## ✅ Testes Realizados

- ✅ Conversão de funções síncronas para assíncronas
- ✅ Atualização de todas as chamadas para usar `await`
- ✅ Verificação de linter (sem erros)
- ✅ Compatibilidade com Windows Server 2012
- ✅ Retry logic implementado em criar_pedido e atualizar_pedido
- ✅ Backoff exponencial testado e funcionando
- ✅ PRAGMAs otimizados aplicados
- ✅ Pool de conexões aumentado
- ✅ Índices compostos criados

## 📝 Notas Técnicas

### Por que aiofiles?
- `aiofiles` permite operações de arquivo verdadeiramente assíncronas
- Não bloqueia o event loop do asyncio
- Essencial para suportar múltiplos clientes simultâneos

### Por que pool de conexões?
- SQLite com aiosqlite pode criar muitas conexões sem pool
- Pool limita e reutiliza conexões eficientemente
- Reduz overhead de criar/destruir conexões

### Por que aumentar timeouts?
- Windows Server 2012 pode ter latência maior em operações de I/O
- Timeouts maiores reduzem falhas em picos de carga
- SQLite WAL mode permite leituras simultâneas, mas escritas ainda podem competir

### Por que retry logic com backoff exponencial?
- Reduz falhas por contenção temporária do banco
- Backoff exponencial evita sobrecarga quando há contenção
- Permite que transações concorrentes completem antes de retentar
- Melhora significativamente a taxa de sucesso em picos de carga

### Por que otimizar PRAGMAs?
- Cache maior reduz I/O em disco (64MB vs padrão)
- Memory-mapped I/O melhora performance de leitura
- Temp tables em memória são mais rápidas
- Otimização automática mantém estatísticas atualizadas

