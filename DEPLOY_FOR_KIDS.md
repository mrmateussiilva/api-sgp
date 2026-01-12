# 📚 GUIA COMPLETO DE INSTALAÇÃO - API SGP
## Para Iniciantes - Com Suporte a Múltiplas Versões

---

## 🎯 IMPORTANTE: Sobre Múltiplas Versões

Esta aplicação usa um **sistema de releases versionadas**, o que significa:

✅ **Você pode ter várias versões instaladas ao mesmo tempo**  
✅ **Dados são compartilhados entre todas as versões** (banco, imagens, logs)  
✅ **Fácil fazer rollback** (voltar para versão anterior)  
✅ **Cada versão é isolada** (código e ambiente virtual separados)  

**Estrutura de Versões:**
```
C:\api\                           # Diretório raiz
├── releases\                     # TODAS as versões ficam aqui
│   ├── v1.0.4\                  # Versão antiga (pode manter)
│   ├── v1.0.5\                  # Versão atual
│   └── current -> v1.0.5        # Link aponta para versão ativa
├── shared\                      # DADOS COMPARTILHADOS
│   ├── db\banco.db              # Banco de dados (ÚNICO para todas)
│   ├── media\                   # Imagens e arquivos (COMPARTILHADOS)
│   └── logs\                    # Logs (COMPARTILHADOS)
└── backups\                     # Backups do banco
```

---

## 📋 PRÉ-REQUISITOS

### O que você precisa ter instalado:

1. ✅ **Python 3.12 ou superior**
   - Verificar: `python --version`
   - Download: https://www.python.org/downloads/

2. ✅ **Git** (opcional, se você clonou do repositório)
   - Verificar: `git --version`

3. ✅ **PowerShell 5.1+** (Windows) ou **Bash** (Linux/Mac)

---

## 🚀 INSTALAÇÃO INICIAL (Primeira Vez)

### Passo 1: Escolher onde instalar

Decida onde você quer instalar a API. Recomendado:

**Windows:**
```
C:\api
```

**Linux/Mac:**
```
/opt/api
```

Você pode usar qualquer caminho, mas use um caminho absoluto (ex: `C:\api`, não `.\api`).

### Passo 2: Criar estrutura de diretórios

Crie a estrutura básica:

**Windows (PowerShell como Administrador):**
```powershell
# Criar diretório raiz
New-Item -ItemType Directory -Path "C:\api" -Force

# Criar estrutura compartilhada
$sharedDir = "C:\api\shared"
New-Item -ItemType Directory -Path "$sharedDir\db" -Force
New-Item -ItemType Directory -Path "$sharedDir\media\pedidos" -Force
New-Item -ItemType Directory -Path "$sharedDir\media\fichas" -Force
New-Item -ItemType Directory -Path "$sharedDir\media\templates" -Force
New-Item -ItemType Directory -Path "$sharedDir\logs" -Force
New-Item -ItemType Directory -Path "$sharedDir\backups" -Force
New-Item -ItemType Directory -Path "C:\api\releases" -Force
```

**Linux/Mac:**
```bash
# Criar diretório raiz (pode precisar de sudo)
sudo mkdir -p /opt/api/shared/{db,media/{pedidos,fichas,templates},logs,backups}
sudo mkdir -p /opt/api/releases
sudo chown -R $USER:$USER /opt/api  # Dar permissão ao seu usuário
```

### Passo 3: Copiar código da primeira versão

Copie todo o código da API para a pasta de releases:

**Windows:**
```powershell
# Navegar até onde está o código da API
cd C:\SeuProjeto\api-sgp

# Copiar para release v1.0.5 (ou versão atual)
Copy-Item -Path "." -Destination "C:\api\releases\v1.0.5" -Recurse -Exclude ".git","__pycache__","*.pyc","db","media","logs","venv",".venv"
```

**Linux/Mac:**
```bash
# Navegar até onde está o código
cd /caminho/do/projeto/api-sgp

# Copiar para release
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='db' --exclude='media' --exclude='logs' --exclude='venv' \
  ./ /opt/api/releases/v1.0.5/
```

### Passo 4: Criar ambiente virtual

**Windows:**
```powershell
cd C:\api\releases\v1.0.5
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
cd /opt/api/releases/v1.0.5
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Passo 5: Criar arquivo .env

Crie o arquivo `.env` na pasta da release (`C:\api\releases\v1.0.5\.env`):

```env
# Configurações do Ambiente
ENVIRONMENT=production

# Chave secreta (IMPORTANTE: gere uma única!)
# Para gerar: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=sua-chave-secreta-aqui-GERE-UMA-NOVA

# Configurações do Banco de Dados
# O banco será criado automaticamente em shared/db/banco.db
DATABASE_URL=sqlite:///C:/api/shared/db/banco.db

# Configurações de Diretórios (usando caminho absoluto)
MEDIA_ROOT=C:/api/shared/media
LOG_DIR=C:/api/shared/logs

# Configurações da API
LOG_LEVEL=INFO
MAX_IMAGE_SIZE_MB=10
```

**IMPORTANTE:**
- Em Windows, use barras `/` ou `\\` no caminho: `C:/api` ou `C:\\api`
- Em Linux/Mac: `/opt/api/shared/db/banco.db`
- Gere uma `SECRET_KEY` única e segura!

**Como gerar SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Cole o resultado no lugar de `sua-chave-secreta-aqui-GERE-UMA-NOVA`.

### Passo 6: Executar migrations

Execute as migrations para criar o banco de dados:

**Windows:**
```powershell
cd C:\api\releases\v1.0.5
$env:API_ROOT = "C:\api"
.\venv\Scripts\python.exe database\run_migrations.py
```

**Linux/Mac:**
```bash
cd /opt/api/releases/v1.0.5
export API_ROOT=/opt/api
./venv/bin/python database/run_migrations.py
```

Você verá:
```
INFO:__main__:Migrations aplicadas: []
INFO:__main__:📋 1 migration(s) pendente(s)
INFO:__main__:✅ Todas as migrations foram aplicadas com sucesso
```

O banco será criado em: `C:\api\shared\db\banco.db` (ou `/opt/api/shared/db/banco.db`)

### Passo 7: Criar link simbólico "current"

Crie um link simbólico apontando para a versão ativa:

**Windows (PowerShell como Administrador):**
```powershell
cd C:\api\releases
New-Item -ItemType SymbolicLink -Path "current" -Target "v1.0.5"
```

**Linux/Mac:**
```bash
cd /opt/api/releases
ln -s v1.0.5 current
```

### Passo 8: Testar a aplicação

Teste se tudo está funcionando:

**Windows:**
```powershell
cd C:\api\releases\current
$env:API_ROOT = "C:\api"
.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Linux/Mac:**
```bash
cd /opt/api/releases/current
export API_ROOT=/opt/api
./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Abra no navegador:
- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs

---

## 🔄 INSTALAR NOVA VERSÃO (Manter Versões Antigas)

Quando você quiser instalar uma nova versão (ex: v1.0.6), siga estes passos:

### Opção A: Usando Script Automatizado (Recomendado)

**Windows:**
```powershell
# Execute como Administrador
cd C:\api
.\releases\current\scripts\update.ps1 `
  -Version "1.0.6" `
  -ReleaseZip "C:\Downloads\api-sgp-1.0.6.zip" `
  -ApiRoot "C:\api" `
  -ServiceName "SGP-API" `
  -Port 8000
```

O script automaticamente:
1. ✅ Faz backup do banco
2. ✅ Para o serviço
3. ✅ Extrai a nova versão em `releases/v1.0.6/`
4. ✅ Atualiza o link `current` → `v1.0.6`
5. ✅ Executa migrations
6. ✅ Reinicia o serviço
7. ✅ Valida healthcheck

### Opção B: Manual (Passo a Passo)

#### 1. Copiar código da nova versão

```powershell
# Copiar nova versão (mantendo versão antiga)
Copy-Item -Path "." -Destination "C:\api\releases\v1.0.6" -Recurse -Exclude ".git","__pycache__","*.pyc","db","media","logs","venv"
```

#### 2. Criar ambiente virtual para nova versão

```powershell
cd C:\api\releases\v1.0.6
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```

#### 3. Criar arquivo .env (copiar da versão anterior)

```powershell
# Copiar .env da versão anterior
Copy-Item "C:\api\releases\v1.0.5\.env" "C:\api\releases\v1.0.6\.env"
```

#### 4. Executar migrations (se houver novas)

```powershell
cd C:\api\releases\v1.0.6
$env:API_ROOT = "C:\api"
.\venv\Scripts\python.exe database\run_migrations.py
```

#### 5. Atualizar link "current"

```powershell
cd C:\api\releases
Remove-Item current -Force
New-Item -ItemType SymbolicLink -Path "current" -Target "v1.0.6"
```

#### 6. Reiniciar serviço (se estiver rodando como serviço)

```powershell
Restart-Service -Name "SGP-API"
```

**Resultado:**
```
C:\api\
├── releases\
│   ├── v1.0.5\          ← Versão antiga (mantida!)
│   ├── v1.0.6\          ← Nova versão
│   └── current -> v1.0.6 ← Agora aponta para v1.0.6
├── shared\              ← Dados compartilhados (não mudam)
│   └── db\banco.db
```

---

## 🔙 ROLLBACK (Voltar para Versão Anterior)

Se a nova versão tiver problemas, volte para a anterior:

### Opção A: Usando Script

**Windows:**
```powershell
.\releases\current\scripts\rollback.ps1 `
  -TargetVersion "1.0.5" `
  -ApiRoot "C:\api" `
  -ServiceName "SGP-API" `
  -Port 8000
```

### Opção B: Manual

```powershell
# Parar serviço
Stop-Service -Name "SGP-API"

# Atualizar link current
cd C:\api\releases
Remove-Item current -Force
New-Item -ItemType SymbolicLink -Path "current" -Target "v1.0.5"

# Reiniciar serviço
Start-Service -Name "SGP-API"
```

**Resultado:**
- `current` agora aponta para `v1.0.5`
- Versão `v1.0.6` ainda existe (pode manter para referência)
- Dados em `shared/` não mudam (são compartilhados)

---

## 📁 ESTRUTURA COMPLETA EXPLICADA

```
C:\api\                           # Diretório raiz da API
│
├── releases\                     # TODAS as versões da API
│   ├── v1.0.4\                  # Versão antiga (pode remover depois)
│   │   ├── venv\                # Ambiente virtual isolado
│   │   ├── main.py              # Código da versão 1.0.4
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   └── .env                 # Config desta versão
│   │
│   ├── v1.0.5\                  # Versão atual (antes)
│   │   ├── venv\
│   │   ├── main.py
│   │   └── ...
│   │
│   ├── v1.0.6\                  # Nova versão (atual)
│   │   ├── venv\
│   │   ├── main.py
│   │   └── ...
│   │
│   └── current -> v1.0.6        # Link aponta para versão ativa
│
├── shared\                       # DADOS COMPARTILHADOS (não muda entre versões)
│   ├── db\
│   │   └── banco.db             # Banco SQLite (ÚNICO para todas)
│   ├── media\
│   │   ├── pedidos\             # Imagens e JSONs dos pedidos
│   │   ├── fichas\              # Imagens das fichas
│   │   └── templates\           # Templates HTML
│   ├── logs\
│   │   └── api.log              # Logs da aplicação
│   └── backups\                 # Backups automáticos
│
└── backups\                      # Backups manuais (opcional)
```

**Por que esta estrutura?**

✅ **Isolamento**: Cada versão tem seu próprio código e ambiente  
✅ **Dados Compartilhados**: Todas as versões usam o mesmo banco  
✅ **Rollback Fácil**: Apenas muda o link `current`  
✅ **Histórico**: Mantém versões antigas para referência  
✅ **Sem Perda de Dados**: Dados sempre em `shared/`  

---

## 🔐 CONFIGURAÇÃO DO ARQUIVO .env

### Onde criar?

Crie o arquivo `.env` em cada versão:
- `C:\api\releases\v1.0.5\.env`
- `C:\api\releases\v1.0.6\.env`
- etc.

### Conteúdo básico:

```env
# Ambiente
ENVIRONMENT=production

# Chave secreta (GERE UMA NOVA PARA CADA INSTALAÇÃO!)
SECRET_KEY=sua-chave-secreta-aqui-GERE-UMA-NOVA

# Banco de dados (caminho absoluto)
DATABASE_URL=sqlite:///C:/api/shared/db/banco.db

# Diretórios (caminhos absolutos)
MEDIA_ROOT=C:/api/shared/media
LOG_DIR=C:/api/shared/logs

# Configurações
LOG_LEVEL=INFO
MAX_IMAGE_SIZE_MB=10
```

### Gerar SECRET_KEY segura:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Cole o resultado no lugar de `sua-chave-secreta-aqui-GERE-UMA-NOVA`.

---

## 🗄️ ONDE ESTÁ O BANCO DE DADOS?

### Localização:

**SEMPRE em:**
- Windows: `C:\api\shared\db\banco.db`
- Linux/Mac: `/opt/api/shared/db/banco.db`

### Importante:

✅ **ÚNICO banco para todas as versões**  
✅ **Criado automaticamente** quando você roda migrations  
✅ **NÃO fica dentro das versões** (fica em `shared/`)  
✅ **Backups em:** `shared/backups/`  

### Migrations:

Execute migrations na versão ativa (a que `current` aponta):

```powershell
cd C:\api\releases\current
$env:API_ROOT = "C:\api"
.\venv\Scripts\python.exe database\run_migrations.py
```

---

## 📝 CHECKLIST DE INSTALAÇÃO INICIAL

- [ ] Python 3.12+ instalado
- [ ] Criar diretório raiz (ex: `C:\api`)
- [ ] Criar estrutura `shared/` (db, media, logs, backups)
- [ ] Criar estrutura `releases/`
- [ ] Copiar código para `releases/v1.0.5/`
- [ ] Criar ambiente virtual (`venv`)
- [ ] Instalar dependências (`pip install -r requirements.txt`)
- [ ] Criar arquivo `.env` com configurações
- [ ] Executar migrations (`python database/run_migrations.py`)
- [ ] Criar link simbólico `current` → `v1.0.5`
- [ ] Testar aplicação (`uvicorn main:app`)
- [ ] Verificar healthcheck (http://localhost:8000/health)

---

## 🔄 CHECKLIST PARA NOVA VERSÃO

- [ ] Fazer backup do banco (automático no script)
- [ ] Copiar código para `releases/v1.0.6/`
- [ ] Criar ambiente virtual para nova versão
- [ ] Instalar dependências
- [ ] Copiar/criar `.env` (ajustar se necessário)
- [ ] Executar migrations (se houver novas)
- [ ] Atualizar link `current` → `v1.0.6`
- [ ] Reiniciar serviço (se aplicável)
- [ ] Testar nova versão
- [ ] Manter versão antiga (para rollback se necessário)

---

## ❓ PROBLEMAS COMUNS

### Erro: "Banco de dados não encontrado"

**Solução:**
1. Verifique se `API_ROOT` está configurado
2. Execute migrations: `python database/run_migrations.py`
3. Verifique caminho em `.env`: `DATABASE_URL=sqlite:///C:/api/shared/db/banco.db`

### Erro: "ModuleNotFoundError"

**Solução:**
```powershell
cd C:\api\releases\current
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### Link "current" quebrado

**Solução:**
```powershell
cd C:\api\releases
Remove-Item current -Force
New-Item -ItemType SymbolicLink -Path "current" -Target "v1.0.5"
```

### Versão antiga não funciona mais

**Solução:**
- Versões antigas não precisam funcionar (só a atual)
- Mantenha apenas para rollback se necessário
- Você pode remover versões antigas depois de validar a nova

---

## 📚 PRÓXIMOS PASSOS

1. **Configurar como serviço Windows** (veja `docs_deploy.md`)
2. **Aprender sobre migrations** (veja `MIGRATIONS.md`)
3. **Aprender sobre updates** (veja `UPDATE_PROCESS.md`)
4. **Aprender sobre releases** (veja `DEPLOY_RELEASES.md`)

---

## 🔗 DOCUMENTAÇÃO RELACIONADA

- `README.md` - Visão geral do projeto
- `DEPLOY_RELEASES.md` - Sistema de releases versionadas
- `UPDATE_PROCESS.md` - Processo de update profissional
- `MIGRATIONS.md` - Sistema de migrations do banco
- `docs_deploy.md` - Deploy com NSSM (serviço Windows)

---

**Última atualização:** 2026-01-10
