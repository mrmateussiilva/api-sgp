# Processo de Update Profissional - API SGP

## Visão Geral

Este documento descreve o processo completo de update da API em produção, incluindo migrations, rollback e validações.

## Pré-requisitos

1. **PowerShell 5.1+** (Windows Server 2012)
2. **NSSM instalado** (para serviço Windows)
3. **Executar como Administrador**
4. **Backup do banco** (automático no script)

## Estrutura de Diretórios

```
C:\api\
├── releases\
│   ├── v1.0.5\
│   ├── v1.0.6\
│   └── current -> v1.0.6 (link simbólico)
├── shared\
│   ├── db\
│   │   └── banco.db
│   ├── media\
│   ├── logs\
│   └── backups\
│       ├── banco-pre-1.0.6-2026-01-10-143022.db
│       └── ...
└── ...
```

## Processo de Update

### 1. Preparar Release

1. **Desenvolver e testar** código localmente
2. **Criar ZIP da release** (ex: `api-sgp-1.0.6.zip`)
3. **Incluir no ZIP**:
   - Todo o código Python
   - `requirements.txt`
   - `database/migrations/` (novas migrations)
   - `scripts/` (scripts PowerShell)
   - **NÃO incluir**: `db/`, `media/`, `logs/`, `venv/`, `shared/`

### 2. Executar Update

```powershell
# Executar como Administrador
.\scripts\update.ps1 `
  -Version "1.0.6" `
  -ReleaseZip "C:\Downloads\api-sgp-1.0.6.zip" `
  -ApiRoot "C:\api" `
  -ServiceName "SGP-API" `
  -Port 8000
```

### 3. Processo Automatizado

O script executa automaticamente os seguintes passos:

1. ✅ **Backup** do banco de dados (`shared/backups/banco-pre-{version}-{timestamp}.db`)
2. ✅ **Para serviço** (NSSM)
3. ✅ **Extrai release** em `releases/v{version}/`
4. ✅ **Atualiza link** `current` → `v{version}`
5. ✅ **Executa migrations** pendentes (`database/run_migrations.py`)
6. ✅ **Reinicia serviço**
7. ✅ **Valida healthcheck** (API + banco)

### 4. Em Caso de Erro

O script **aborta automaticamente** se:
- Backup falhar
- Migrations falharem
- Serviço não iniciar
- Healthcheck falhar

**Serviço volta automaticamente** para estado anterior (se estava rodando).

## Rollback

### Rollback Rápido (sem reverter migrations)

```powershell
.\scripts\rollback.ps1 `
  -TargetVersion "1.0.5" `
  -ServiceName "SGP-API" `
  -Port 8000
```

Este tipo de rollback:
- ✅ Reverte código para versão anterior
- ✅ Reinicia serviço
- ✅ **NÃO reverte migrations** (banco pode ter mudanças incompatíveis)

**Uso**: Quando código tem bug, mas banco está OK.

### Rollback com Reversão de Migrations

⚠️ **CUIDADO**: Reverter migrations pode causar perda de dados!

```powershell
.\scripts\rollback.ps1 `
  -TargetVersion "1.0.5" `
  -RevertMigrations `
  -ServiceName "SGP-API" `
  -Port 8000
```

**NOTA**: Reversão automática de migrations ainda não está implementada.

**Uso**: Quando banco precisa ser revertido também.

### Rollback Manual Completo

Se rollback automático falhar:

1. **Parar serviço**:
   ```powershell
   Stop-Service -Name "SGP-API"
   ```

2. **Reverter link current**:
   ```powershell
   cd C:\api\releases
   Remove-Item current -Force
   New-Item -ItemType SymbolicLink -Path current -Target v1.0.5
   ```

3. **Restaurar backup do banco** (se necessário):
   ```powershell
   Stop-Service -Name "SGP-API"
   Copy-Item "C:\api\shared\backups\banco-pre-1.0.6-2026-01-10-143022.db" `
     "C:\api\shared\db\banco.db" -Force
   Start-Service -Name "SGP-API"
   ```

4. **Reiniciar serviço**:
   ```powershell
   Start-Service -Name "SGP-API"
   ```

5. **Validar**:
   ```powershell
   Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
   ```

## Checklist de Segurança

Antes de cada update em produção:

- [ ] ✅ Código testado em desenvolvimento
- [ ] ✅ Migrations testadas localmente
- [ ] ✅ Backup manual do banco (além do automático)
- [ ] ✅ Versão da release confirmada
- [ ] ✅ Janela de manutenção agendada (se necessário)
- [ ] ✅ Logs monitorados após update
- [ ] ✅ Healthcheck validado manualmente
- [ ] ✅ Testes manuais básicos (criar pedido, listar, etc.)
- [ ] ✅ Plano de rollback definido

## Troubleshooting

### Migrations falharam

**Sintomas**:
- Script aborta com erro "Migrations falharam"
- Logs mostram erro específico da migration

**Solução**:
1. Verificar logs: `shared/logs/api.log`
2. Verificar estado: `python database/run_migrations.py --dry-run`
3. Testar migration manualmente:
   ```powershell
   cd C:\api\releases\current
   .\venv\Scripts\python.exe database\run_migrations.py --dry-run
   ```
4. Se migration está errada:
   - **NÃO modificar migration já aplicada**
   - Criar nova migration para corrigir
   - Ou fazer rollback se migration ainda não foi aplicada

### Healthcheck falhou

**Sintomas**:
- Script aborta com erro "Healthcheck falhou"
- API não responde ou banco está inacessível

**Solução**:
1. Verificar logs do serviço: `shared/logs/service_stderr.log`
2. Testar API manualmente:
   ```powershell
   Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
   ```
3. Verificar banco de dados:
   ```powershell
   Test-Path "C:\api\shared\db\banco.db"
   ```
4. Verificar permissões do diretório `shared/`
5. Fazer rollback se necessário

### Serviço não inicia

**Sintomas**:
- Script aborta com erro "Serviço não iniciou"
- Status do serviço não é "Running"

**Solução**:
1. Verificar logs: `shared/logs/service_stderr.log`
2. Testar manualmente:
   ```powershell
   cd C:\api\releases\current
   .\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```
3. Verificar dependências:
   ```powershell
   cd C:\api\releases\current
   .\venv\Scripts\python.exe -m pip list
   ```
4. Verificar variáveis de ambiente no NSSM:
   ```powershell
   nssm get SGP-API AppEnvironmentExtra
   ```
5. Verificar caminhos no NSSM:
   ```powershell
   nssm get SGP-API AppDirectory
   nssm get SGP-API AppParameters
   ```

### Erro "Release não encontrada"

**Sintomas**:
- Script aborta imediatamente
- Diretório da release não existe

**Solução**:
1. Verificar se ZIP foi extraído corretamente
2. Verificar se diretório `releases/v{version}/` existe
3. Verificar permissões de escrita em `releases/`
4. Tentar extrair ZIP manualmente

### Link simbólico quebrado

**Sintomas**:
- Serviço não encontra código
- Erros de importação

**Solução**:
```powershell
cd C:\api\releases
Remove-Item current -Force
New-Item -ItemType SymbolicLink -Path current -Target v1.0.6
```

## Manutenção

### Limpar backups antigos

Manter apenas últimos 10 backups:

```powershell
Get-ChildItem "C:\api\shared\backups\*.db" | 
  Sort-Object LastWriteTime -Descending | 
  Select-Object -Skip 10 | 
  Remove-Item
```

### Listar migrations aplicadas

```powershell
cd C:\api\releases\current
.\venv\Scripts\python.exe database\run_migrations.py --dry-run
```

### Verificar versão ativa

```powershell
(Get-Item "C:\api\releases\current").Target
```

### Verificar status do serviço

```powershell
Get-Service -Name "SGP-API"
```

### Ver logs em tempo real

```powershell
Get-Content "C:\api\shared\logs\api.log" -Wait -Tail 50
```

## Exemplo Completo de Update

```powershell
# 1. Preparar release (em desenvolvimento)
# ... desenvolver código ...
# ... testar migrations ...
# ... criar ZIP: api-sgp-1.0.6.zip ...

# 2. Copiar ZIP para servidor
# (copiar para C:\Downloads\api-sgp-1.0.6.zip)

# 3. Executar update (como Administrador)
cd C:\api
.\releases\current\scripts\update.ps1 `
  -Version "1.0.6" `
  -ReleaseZip "C:\Downloads\api-sgp-1.0.6.zip" `
  -ApiRoot "C:\api" `
  -ServiceName "SGP-API" `
  -Port 8000

# 4. Validar
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# 5. Verificar logs
Get-Content "C:\api\shared\logs\api.log" -Tail 50
```

## Próximos Passos (Melhorias Futuras)

- [ ] Implementar reversão automática de migrations no rollback
- [ ] Adicionar notificações (email/Slack) em caso de erro
- [ ] Criar dashboard de status de migrations
- [ ] Automatizar testes antes de deploy
- [ ] Adicionar suporte a rollback automático em caso de falha
- [ ] Criar script de verificação de integridade pós-update
- [ ] Adicionar métricas de tempo de update

## Referências

- [MIGRATIONS.md](./MIGRATIONS.md) - Documentação do sistema de migrations
- [DEPLOY_RELEASES.md](./DEPLOY_RELEASES.md) - Arquitetura de releases versionadas
- [NSSM Documentation](https://nssm.cc/usage)
