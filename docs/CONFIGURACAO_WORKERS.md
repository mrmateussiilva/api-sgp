# 🔧 Configuração de Múltiplos Workers - Windows Server

## 📋 Resumo

Este guia explica como configurar múltiplos workers no Windows Server para melhorar a performance da API SGP.

---

## 🎯 Por Que Múltiplos Workers?

### Problema Atual (1 Worker)
- **Todo processamento em um único processo**
- Requests bloqueiam umas às outras
- Capacidade limitada pela CPU single-core efetiva
- **Gargalo**: 1 worker não é suficiente para 20 clientes simultâneos

### Solução (2-3 Workers)
- **Requisições distribuídas entre processos**
- Um worker lento não bloqueia os demais
- Melhor uso de CPU multi-core
- **Capacidade**: 2-3x mais requisições simultâneas

---

## ✅ Pré-requisitos

- ✅ **Hypercorn instalado**: Já está nas dependências (`hypercorn>=0.17.0`)
- ✅ **Código pronto**: `main.py` já suporta múltiplos workers
- ✅ **SQLite WAL mode**: Já configurado (seguro para múltiplos workers)
- ✅ **Windows Server**: Hypercorn funciona no Windows (diferente do Uvicorn)

---

## 🚀 Como Configurar

### Opção 1: Usando NSSM (Recomendado para Produção)

#### Passo 1: Verificar serviço atual

```powershell
# PowerShell (como Administrador)
nssm status SGP-API
nssm get SGP-API AppParameters
```

#### Passo 2: Parar serviço

```powershell
nssm stop SGP-API
```

#### Passo 3: Reconfigurar com 2 workers

```powershell
# Ajustar caminhos conforme sua instalação
$pythonPath = "C:\Python\python.exe"  # OU caminho do venv
$projectPath = "C:\api\releases\current"  # Ajustar conforme necessário
$port = 8000

# Configurar serviço
nssm set SGP-API Application $pythonPath
nssm set SGP-API AppParameters "-m hypercorn main:app --bind 0.0.0.0:$port --workers 2 --loop asyncio"
nssm set SGP-API AppDirectory $projectPath
```

**Importante**: Ajuste os caminhos conforme sua instalação:
- `$pythonPath`: Caminho do `python.exe` (ou do venv)
- `$projectPath`: Diretório onde está o `main.py`
- `$port`: Porta da API (geralmente 8000)

#### Passo 4: Verificar configuração

```powershell
nssm get SGP-API AppParameters
```

Deve mostrar: `-m hypercorn main:app --bind 0.0.0.0:8000 --workers 2 --loop asyncio`

#### Passo 5: Iniciar serviço

```powershell
nssm start SGP-API
```

#### Passo 6: Verificar logs

```powershell
# Verificar logs do serviço
# Logs devem mostrar: "Workers: 2"
```

---

### Opção 2: Usando Script de Deploy

Se você usa o script `scripts/deploy.ps1`:

```powershell
# PowerShell (como Administrador)
.\scripts\deploy.ps1 -Workers 2 -Port 8000 -UseHypercorn $true
```

---

### Opção 3: Testar Manualmente (Antes de Configurar Serviço)

Para testar antes de configurar como serviço:

```powershell
# No diretório do projeto
cd C:\api\releases\current  # Ajustar caminho

# Testar com 2 workers
python -m hypercorn main:app --bind 0.0.0.0:8000 --workers 2 --loop asyncio
```

Ou usando o `main.py`:

```powershell
python main.py --bind 0.0.0.0:8000 --workers 2
```

---

## 📊 Como Verificar se Está Funcionando

### 1. Logs na Inicialização

Quando inicia com 2 workers, você verá algo assim:

```
🚀 Iniciando API SGP com Hypercorn
   Host: 0.0.0.0
   Porta: 8000
   Workers: 2
   Loop: asyncio
```

### 2. Gerenciador de Tarefas

No Gerenciador de Tarefas do Windows:
- **Deve ver 2 processos Python** rodando
- Cada um é um worker independente
- Uso de CPU e memória distribuído entre os workers

### 3. Logs do Middleware de Métricas

Com o middleware de métricas implementado, os logs devem mostrar múltiplos workers processando requisições.

### 4. Teste de Carga

Faça algumas requisições simultâneas e verifique:
- Latência reduzida
- Sem bloqueios
- Múltiplas requisições sendo processadas simultaneamente

---

## 🛡️ Segurança dos Dados

### Por Que é Seguro?

✅ **SQLite WAL mode já configurado**:
- Permite múltiplos leitores simultâneos
- Escritas serializadas pelo SQLite (thread-safe)
- Arquivo único compartilhado entre workers

✅ **Cada worker tem seu próprio pool de conexões**:
- `pool_size=15` por worker
- Total: até 30 conexões (2 workers × 15)
- SQLite gerencia locks internamente

✅ **Retry logic implementado**:
- Backoff exponencial em operações críticas
- Tratamento de "database is locked"

### Riscos Conhecidos

⚠️ **Conteção de escrita no SQLite**:
- Muitas escritas simultâneas podem causar contenção
- Mitigado por: WAL mode + retry logic + busy_timeout
- **Impacto**: Baixo para 20 clientes simultâneos

---

## 📈 Resultados Esperados

### Com 2 Workers:

- ✅ **Capacidade**: 2-3x mais requisições simultâneas (20 → 40-60)
- ✅ **Latência**: -30-50% em média (requests distribuídos)
- ✅ **CPU**: Melhor uso de múltiplos cores
- ✅ **Estabilidade**: Um worker lento não bloqueia o sistema

### Monitoramento Inicial (Primeiras 24-48h):

- ✅ Logs de erros (devem ser mínimos)
- ✅ Tempo de resposta (via middleware de métricas)
- ✅ Uso de memória (cada worker consome ~50-100MB)
- ✅ Logs de "database is locked" (devem ser raros)

---

## 🔄 Ajuste Gradual

### Começar com 2 Workers (Recomendado)

**Por quê?**
- Dobra a capacidade com baixo risco
- SQLite gerencia locks adequadamente
- Fácil reverter se necessário
- Uso de memória moderado (~100-200MB adicional)

### Quando Aumentar para 3-4 Workers?

✅ **Aumentar se:**
- Sistema estável com 2 workers por 48h+
- CPU < 50% (tem capacidade)
- Logs mostram que 2 workers não são suficientes
- Muitas requisições simultâneas (>40)

⚠️ **Não aumentar se:**
- CPU > 80% (pode causar contenção)
- Muitos erros "database is locked"
- Sistema instável
- Memória limitada

### Recomendações por CPU:

- **CPU 2-4 cores**: 2 workers (recomendado inicial)
- **CPU 4-6 cores**: 2-3 workers
- **CPU 6-8 cores**: 3-4 workers
- **CPU 8+ cores**: 3-4 workers (SQLite não se beneficia muito de mais)

---

## 🔄 Como Reverter (Voltar para 1 Worker)

Se algo der errado, é fácil reverter:

```powershell
# PowerShell (como Administrador)

# 1. Parar serviço
nssm stop SGP-API

# 2. Reconfigurar para 1 worker (Uvicorn)
nssm set SGP-API AppParameters "-m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio"

# OU com Hypercorn com 1 worker:
nssm set SGP-API AppParameters "-m hypercorn main:app --bind 0.0.0.0:8000 --workers 1 --loop asyncio"

# 3. Iniciar serviço
nssm start SGP-API
```

**Impacto da reversão**: Nenhum. Sistema volta exatamente como estava antes.

---

## ⚠️ Troubleshooting

### Erro: "Hypercorn não encontrado"

**Solução:**
```powershell
pip install hypercorn
# OU se usar venv:
.\venv\Scripts\pip install hypercorn
```

### Erro: "Module not found"

**Solução:**
- Verificar que `AppDirectory` no NSSM aponta para o diretório do projeto
- Verificar que `main.py` existe no diretório

### Workers não aparecem nos logs

**Solução:**
- Verificar que comando está sendo usado (`-m hypercorn` com `--workers 2`)
- Verificar logs do serviço (stdout/stderr)
- Verificar Gerenciador de Tarefas (deve ver 2 processos Python)

### Muitos erros "database is locked"

**Solução:**
- Reduzir para 2 workers
- Verificar se há queries muito lentas (via logs de métricas)
- Considerar otimizar queries problemáticas

### Alto uso de memória

**Solução:**
- Verificar uso por worker (deve ser ~50-100MB cada)
- Considerar reduzir `pool_size` se necessário
- Monitorar uso geral do sistema

---

## 📝 Checklist de Implementação

Antes de configurar:
- [ ] Hypercorn instalado (`pip install hypercorn`)
- [ ] Backup do banco criado
- [ ] Acesso ao Windows Server (administrador)
- [ ] NSSM instalado (se usar NSSM)
- [ ] Caminho do Python verificado
- [ ] Caminho do projeto verificado

Configuração:
- [ ] Serviço parado
- [ ] Serviço reconfigurado com 2 workers
- [ ] Configuração verificada
- [ ] Serviço iniciado
- [ ] Logs verificados (deve mostrar "Workers: 2")

Pós-configuração (24-48h):
- [ ] Logs monitorados (sem erros)
- [ ] Performance verificada (latência reduzida)
- [ ] Uso de recursos verificado (CPU, memória)
- [ ] Estabilidade confirmada

---

## 📚 Referências Técnicas

- **Hypercorn**: https://hypercorn.readthedocs.io/
- **SQLite WAL mode**: https://www.sqlite.org/wal.html
- **NSSM**: https://nssm.cc/
- **FastAPI Deployment**: https://fastapi.tiangolo.com/deployment/

---

## ✅ Exemplo Completo (Windows Server 2012)

```powershell
# PowerShell (como Administrador)

# 1. Verificar Python
python --version

# 2. Verificar Hypercorn
python -m pip list | findstr hypercorn

# 3. Ir para diretório do projeto
cd C:\api\releases\current  # Ajustar caminho

# 4. Parar serviço atual
nssm stop SGP-API

# 5. Reconfigurar com 2 workers
$pythonPath = "C:\Python\python.exe"  # Ajustar caminho
$projectPath = "C:\api\releases\current"  # Ajustar caminho
$port = 8000

nssm set SGP-API Application $pythonPath
nssm set SGP-API AppParameters "-m hypercorn main:app --bind 0.0.0.0:$port --workers 2 --loop asyncio"
nssm set SGP-API AppDirectory $projectPath

# 6. Verificar configuração
nssm get SGP-API AppParameters

# 7. Iniciar serviço
nssm start SGP-API

# 8. Verificar status
nssm status SGP-API

# 9. Verificar logs
# Verificar arquivo de log ou stdout do serviço
```

---

**Data de Criação**: 2026-01-11  
**Versão**: 1.0  
**Status**: ✅ Pronto para uso
