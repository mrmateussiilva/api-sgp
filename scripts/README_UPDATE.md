# 📦 Guia de Atualização Segura da API SGP

Este guia explica como usar o script `update_safe.ps1` para atualizar a API preservando todos os dados de produção.

## 🚀 Uso Rápido

### Opção 1: Atualizar via Git (Recomendado)

Se você usa Git para versionar o código:

```powershell
# Executar como Administrador
powershell -ExecutionPolicy Bypass -File .\scripts\update_safe.ps1 -UseGit
```

### Opção 2: Atualizar copiando código novo

Se você baixou o código novo em uma pasta:

```powershell
# Executar como Administrador
powershell -ExecutionPolicy Bypass -File .\scripts\update_safe.ps1 -NewCodePath "C:\Downloads\api-sgp-novo"
```

## 📋 O que o Script Faz

1. ✅ **Para o serviço** - Para a API antes de fazer mudanças
2. ✅ **Faz backup** - Cria backup automático do banco de dados
3. ✅ **Preserva dados** - Mantém `db/`, `media/`, `.env` intactos
4. ✅ **Atualiza código** - Substitui apenas arquivos de código
5. ✅ **Verifica integridade** - Testa se o banco está OK
6. ✅ **Atualiza dependências** - Instala/atualiza pacotes Python
7. ✅ **Reinicia serviço** - Volta a API ao ar

## 🔒 Arquivos Preservados

O script **NUNCA** apaga ou sobrescreve:

- ✅ `db/banco.db` - Banco de dados com todos os pedidos
- ✅ `media/` - Imagens e JSONs dos pedidos
- ✅ `.env` - Configurações sensíveis (SECRET_KEY)
- ✅ `backups/` - Backups anteriores
- ✅ `logs/` - Logs do sistema

## 📝 Exemplos de Uso

### Exemplo 1: Atualização via Git (com confirmação)

```powershell
cd C:\SGP\api-sgp
powershell -ExecutionPolicy Bypass -File .\scripts\update_safe.ps1 -UseGit
```

O script vai:
- Pedir confirmação antes de continuar
- Fazer backup automático
- Fazer `git pull`
- Preservar todos os dados
- Reiniciar o serviço

### Exemplo 2: Atualização via Git (sem confirmação - automação)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update_safe.ps1 -UseGit -Force
```

### Exemplo 3: Atualização copiando código novo

```powershell
# Você baixou o código novo em C:\Downloads\api-sgp-v2
powershell -ExecutionPolicy Bypass -File .\scripts\update_safe.ps1 -NewCodePath "C:\Downloads\api-sgp-v2"
```

### Exemplo 4: Atualização sem backup (NÃO RECOMENDADO)

```powershell
# Apenas se você já fez backup manualmente
powershell -ExecutionPolicy Bypass -File .\scripts\update_safe.ps1 -UseGit -SkipBackup -Force
```

## ⚙️ Parâmetros Disponíveis

| Parâmetro | Descrição | Padrão |
|-----------|-----------|--------|
| `-ProjectPath` | Caminho do projeto | Diretório atual |
| `-NewCodePath` | Caminho do código novo (se não usar Git) | "" |
| `-ServiceName` | Nome do serviço Windows | "SGP-API" |
| `-UseGit` | Usar Git para atualizar | `$false` |
| `-SkipBackup` | Pular backup (NÃO RECOMENDADO) | `$false` |
| `-Force` | Não pedir confirmação | `$false` |

## 🔍 Verificação Pós-Atualização

Após a atualização, o script verifica:

1. ✅ Banco de dados existe e tem tamanho > 0
2. ✅ Integridade do banco (PRAGMA integrity_check)
3. ✅ Pasta media existe com arquivos
4. ✅ Serviço iniciou corretamente
5. ✅ API responde no endpoint `/health`

## 🆘 Em Caso de Problema

### Se o banco de dados foi perdido

O script cria um backup temporário em `backup_temp_YYYYMMDD_HHMMSS/`. Para restaurar:

```powershell
# Encontrar o backup mais recente
Get-ChildItem -Path . -Directory -Filter "backup_temp_*" | Sort-Object CreationTime -Descending | Select-Object -First 1

# Restaurar banco
Copy-Item -Path "backup_temp_*\db\*" -Destination "db\" -Recurse -Force

# Restaurar media
Copy-Item -Path "backup_temp_*\media\*" -Destination "media\" -Recurse -Force
```

### Se o serviço não iniciou

```powershell
# Ver logs
Get-Content logs\service_stderr.log -Tail 50

# Tentar iniciar manualmente
Start-Service SGP-API

# Ou verificar configuração
nssm get SGP-API AppParameters
```

### Se houver erro durante atualização

O script tenta restaurar automaticamente do backup temporário. Se não conseguir:

1. Pare o serviço: `Stop-Service SGP-API`
2. Restaure do backup temporário (veja acima)
3. Verifique os logs
4. Tente novamente

## 📊 Checklist Antes de Atualizar

Antes de executar o script, verifique:

- [ ] Você tem acesso de Administrador
- [ ] Fez backup manual extra (além do automático)
- [ ] Código novo está testado
- [ ] Serviço está rodando (para poder parar)
- [ ] Tem espaço em disco para backup

## 🔄 Processo Manual (Se Precisar)

Se preferir fazer manualmente ou o script não funcionar:

```powershell
# 1. Parar serviço
Stop-Service SGP-API

# 2. Backup
python scripts\backup_database.py

# 3. Copiar dados para lugar seguro
$temp = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item -Path "db" -Destination "$temp\db" -Recurse
Copy-Item -Path "media" -Destination "$temp\media" -Recurse
Copy-Item -Path ".env" -Destination "$temp\.env"

# 4. Atualizar código (Git ou copiar arquivos)
git pull
# OU copiar código novo (exceto db/, media/, .env)

# 5. Verificar se dados estão intactos
Test-Path "db\banco.db"
Test-Path "media\pedidos"

# 6. Atualizar dependências
pip install -r requirements.txt --upgrade

# 7. Reiniciar serviço
Start-Service SGP-API
```

## 💡 Dicas

1. **Sempre use `-UseGit` se possível** - É mais seguro e rápido
2. **Faça backup extra antes** - Além do backup automático
3. **Teste em ambiente de desenvolvimento primeiro** - Se possível
4. **Monitore os logs após atualização** - Verifique se está tudo OK
5. **Mantenha backups antigos** - Não apague imediatamente

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs em `logs/`
2. Verifique o backup temporário em `backup_temp_*/`
3. Restaure do backup se necessário
4. Verifique a documentação em `docs_deploy.md`

---

**⚠️ IMPORTANTE**: Este script preserva dados, mas sempre faça backup extra antes de atualizar em produção!

