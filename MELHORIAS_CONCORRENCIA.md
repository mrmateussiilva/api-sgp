# Melhorias de Concorrência Implementadas

Este documento descreve as melhorias implementadas para suportar 20 clientes simultâneos no Windows Server 2012.

## 📋 Mudanças Implementadas

### 1. Pool de Conexões do Banco de Dados
**Arquivo:** `database/database.py`

- Configurado `pool_size=10` (10 conexões no pool)
- Configurado `max_overflow=20` (até 20 conexões extras)
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

### 3. Dependências Adicionadas
**Arquivo:** `requirements.txt`

- Adicionado `aiofiles==24.1.0` para I/O assíncrono de arquivos

## 🚀 Como Executar no Windows Server 2012

### Instalação de Dependências
```powershell
pip install -r requirements.txt
```

### Execução da API
```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio
```

**Nota:** No Windows, use `--loop asyncio` ao invés de `uvloop` (que não funciona no Windows).

### Executar como Serviço do Windows (Recomendado)

#### Opção 1: Usando NSSM (Non-Sucking Service Manager)

1. Baixe o NSSM: https://nssm.cc/download
2. Instale o serviço:
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
   - Argumentos: `-m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio`
   - Diretório: Caminho do projeto
4. Configure para executar na inicialização do sistema

## ⚠️ Limitações Conhecidas

### SQLite no Windows Server 2012
- SQLite tem limitações inerentes de concorrência
- Com 20 clientes simultâneos, pode haver contenção ocasional
- O sistema implementa retry logic (até 5 tentativas) para lidar com locks

### Sem Workers no Windows
- Uvicorn não suporta workers no Windows (limitação do sistema operacional)
- Toda a carga será processada em um único processo
- As melhorias de I/O assíncrono ajudam a compensar essa limitação

## 📊 Monitoramento Recomendado

### Métricas a Observar
1. **Tempo de resposta das requisições**
   - Endpoints de criação/atualização de pedidos
   - Upload de imagens

2. **Erros de banco de dados**
   - "database is locked" (deve ser raro com as melhorias)
   - Timeouts de conexão

3. **Uso de memória**
   - Pool de conexões consome memória adicional
   - Monitorar uso geral do processo

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

