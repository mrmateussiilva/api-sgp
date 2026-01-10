<#
.SYNOPSIS
    Script de atualização segura da API SGP que preserva dados de produção.

.DESCRIPTION
    Este script automatiza o processo de atualização da API preservando:
    - Banco de dados (db/banco.db)
    - Arquivos de mídia (media/)
    - Configurações (.env)
    - Backups existentes
    
    O script para o serviço, faz backup, atualiza código e reinicia.

.PARAMETER ProjectPath
    Caminho do projeto (default: diretório atual)

.PARAMETER NewCodePath
    Caminho para o código novo baixado (opcional, se não fornecido, usa Git pull)

.PARAMETER ServiceName
    Nome do serviço Windows (default: SGP-API)

.PARAMETER UseGit
    Usar Git para atualizar ao invés de copiar arquivos (default: $false)

.PARAMETER SkipBackup
    Pular backup (NÃO RECOMENDADO, default: $false)

.PARAMETER Force
    Não pedir confirmação (útil para automação, default: $false)

.EXAMPLE
    .\update_safe.ps1

.EXAMPLE
    .\update_safe.ps1 -NewCodePath "C:\Downloads\api-sgp-new" -Force

.EXAMPLE
    .\update_safe.ps1 -UseGit -Force
#>
param(
    [Parameter()][string]$ProjectPath = (Get-Location).Path,
    [Parameter()][string]$NewCodePath = "",
    [Parameter()][string]$ServiceName = "SGP-API",
    [Parameter()][bool]$UseGit = $false,
    [Parameter()][bool]$SkipBackup = $false,
    [Parameter()][switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Cores para output
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }
function Write-Step { Write-Host "`n=== $args ===" -ForegroundColor Magenta }

# Verificar se está executando como administrador
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Verificar pré-requisitos
function Test-Prerequisites {
    Write-Info "Verificando pré-requisitos..."
    
    # Verificar se Python está disponível
    try {
        $pythonVersion = & python --version 2>&1
        Write-Success "Python encontrado: $pythonVersion"
    } catch {
        Write-Error "Python não encontrado. Instale Python e adicione ao PATH."
        exit 1
    }
    
    # Verificar se o projeto existe
    if (-not (Test-Path $ProjectPath)) {
        Write-Error "Diretório do projeto não encontrado: $ProjectPath"
        exit 1
    }
    
    # Verificar se é um repositório Git (se usar Git)
    if ($UseGit) {
        $gitPath = Join-Path $ProjectPath ".git"
        if (-not (Test-Path $gitPath)) {
            Write-Error "Diretório não é um repositório Git. Use -NewCodePath ou configure Git."
            exit 1
        }
    }
    
    Write-Success "Pré-requisitos OK"
}

# Fazer backup do banco
function Backup-Database {
    if ($SkipBackup) {
        Write-Warning "Backup pulado (--SkipBackup)"
        return
    }
    
    Write-Step "Fazendo backup do banco de dados"
    
    $backupScript = Join-Path $ProjectPath "scripts\backup_database.py"
    if (Test-Path $backupScript) {
        try {
            & python $backupScript --dest "backups\db" --retention 10
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Backup criado com sucesso"
            } else {
                Write-Error "Falha ao criar backup. Código de saída: $LASTEXITCODE"
                if (-not $Force) {
                    $continue = Read-Host "Continuar mesmo assim? (S/N)"
                    if ($continue -ne "S") {
                        exit 1
                    }
                }
            }
        } catch {
            Write-Error "Erro ao executar script de backup: $_"
            if (-not $Force) {
                $continue = Read-Host "Continuar mesmo assim? (S/N)"
                if ($continue -ne "S") {
                    exit 1
                }
            }
        }
    } else {
        Write-Warning "Script de backup não encontrado. Fazendo backup manual..."
        $dbPath = Join-Path $ProjectPath "db\banco.db"
        if (Test-Path $dbPath) {
            $backupDir = Join-Path $ProjectPath "backups"
            New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
            $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
            $backupFile = Join-Path $backupDir "banco_backup_$timestamp.db"
            Copy-Item -Path $dbPath -Destination $backupFile
            Write-Success "Backup manual criado: $backupFile"
        } else {
            Write-Warning "Banco de dados não encontrado (pode ser primeira instalação)"
        }
    }
}

# Criar backup temporário dos dados
function Backup-DataFiles {
    Write-Step "Criando backup temporário dos dados"
    
    $tempBackup = Join-Path $ProjectPath "backup_temp_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    New-Item -ItemType Directory -Path $tempBackup -Force | Out-Null
    
    $dataDirs = @("db", "media")
    $dataFiles = @(".env")
    
    foreach ($dir in $dataDirs) {
        $sourcePath = Join-Path $ProjectPath $dir
        if (Test-Path $sourcePath) {
            $destPath = Join-Path $tempBackup $dir
            Write-Info "Copiando $dir..."
            Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
            Write-Success "$dir copiado"
        }
    }
    
    foreach ($file in $dataFiles) {
        $sourcePath = Join-Path $ProjectPath $file
        if (Test-Path $sourcePath) {
            $destPath = Join-Path $tempBackup $file
            Write-Info "Copiando $file..."
            Copy-Item -Path $sourcePath -Destination $destPath -Force
            Write-Success "$file copiado"
        }
    }
    
    return $tempBackup
}

# Parar serviço
function Stop-Service {
    Write-Step "Parando serviço: $ServiceName"
    
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        if ($service.Status -eq "Running") {
            Write-Info "Parando serviço..."
            Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 3
            
            $service = Get-Service -Name $ServiceName
            if ($service.Status -eq "Stopped") {
                Write-Success "Serviço parado"
            } else {
                Write-Warning "Serviço pode não ter parado completamente. Status: $($service.Status)"
            }
        } else {
            Write-Info "Serviço já estava parado"
        }
    } else {
        Write-Warning "Serviço $ServiceName não encontrado (pode estar rodando manualmente)"
    }
}

# Atualizar código via Git
function Update-WithGit {
    Write-Step "Atualizando código via Git"
    
    Push-Location $ProjectPath
    
    try {
        # Verificar se há mudanças locais
        $status = & git status --porcelain 2>&1
        if ($status) {
            Write-Warning "Há mudanças locais não commitadas:"
            Write-Host $status -ForegroundColor Yellow
            
            if (-not $Force) {
                $stash = Read-Host "Fazer stash das mudanças? (S/N)"
                if ($stash -eq "S") {
                    & git stash
                    Write-Success "Mudanças guardadas em stash"
                }
            } else {
                & git stash
                Write-Info "Mudanças guardadas automaticamente"
            }
        }
        
        # Fazer pull
        Write-Info "Fazendo git pull..."
        & git pull
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Código atualizado via Git"
        } else {
            Write-Error "Erro ao fazer git pull"
            exit 1
        }
    } finally {
        Pop-Location
    }
}

# Atualizar código copiando arquivos
function Update-WithCopy {
    param([string]$SourcePath)
    
    Write-Step "Atualizando código copiando arquivos"
    
    if (-not (Test-Path $SourcePath)) {
        Write-Error "Caminho do código novo não encontrado: $SourcePath"
        exit 1
    }
    
    # Lista de extensões de código (não dados)
    $codeExtensions = @('.py', '.txt', '.md', '.toml', '.ps1', '.json', '.html', '.css', '.js', '.ts')
    
    # Lista de arquivos/pastas a preservar
    $preservePaths = @('db', 'media', '.env', 'backups', 'logs', '__pycache__', '.git')
    
    Write-Info "Copiando arquivos de código (preservando dados)..."
    
    $filesCopied = 0
    $filesSkipped = 0
    
    Get-ChildItem -Path $SourcePath -Recurse -File | ForEach-Object {
        $relativePath = $_.FullName.Substring($SourcePath.Length + 1)
        $targetPath = Join-Path $ProjectPath $relativePath
        
        # Verificar se deve preservar
        $shouldPreserve = $false
        foreach ($preserve in $preservePaths) {
            if ($relativePath -like "$preserve*") {
                $shouldPreserve = $true
                break
            }
        }
        
        if ($shouldPreserve) {
            $filesSkipped++
            Write-Host "  ⏭️  Preservando: $relativePath" -ForegroundColor Gray
            return
        }
        
        # Verificar se é arquivo de código
        $extension = [System.IO.Path]::GetExtension($relativePath)
        if ($codeExtensions -contains $extension -or $relativePath -like ".*") {
            # Criar diretório se necessário
            $targetDir = Split-Path $targetPath -Parent
            if ($targetDir) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            
            # Copiar arquivo
            Copy-Item -Path $_.FullName -Destination $targetPath -Force
            $filesCopied++
            Write-Host "  ✅ $relativePath" -ForegroundColor Green
        } else {
            $filesSkipped++
        }
    }
    
    Write-Success "Arquivos copiados: $filesCopied, Preservados: $filesSkipped"
}

# Verificar integridade dos dados
function Test-DataIntegrity {
    param([string]$TempBackup)
    
    Write-Step "Verificando integridade dos dados"
    
    $errors = @()
    
    # Verificar banco de dados
    $dbPath = Join-Path $ProjectPath "db\banco.db"
    if (Test-Path $dbPath) {
        $size = (Get-Item $dbPath).Length / 1MB
        Write-Success "Banco de dados encontrado ($([math]::Round($size, 2)) MB)"
        
        # Verificar integridade básica
        try {
            $pythonCheck = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
result = conn.execute('PRAGMA integrity_check').fetchone()
conn.close()
print('OK' if result[0] == 'ok' else 'ERRO')
"@
            $checkResult = $pythonCheck | python
            if ($checkResult -eq "OK") {
                Write-Success "Integridade do banco verificada"
            } else {
                Write-Error "Banco de dados corrompido!"
                $errors += "Banco de dados corrompido"
            }
        } catch {
            Write-Warning "Não foi possível verificar integridade do banco: $_"
        }
    } else {
        Write-Warning "Banco de dados não encontrado"
        if (Test-Path (Join-Path $TempBackup "db\banco.db")) {
            Write-Info "Restaurando banco do backup temporário..."
            Copy-Item -Path (Join-Path $TempBackup "db\*") -Destination (Join-Path $ProjectPath "db\") -Recurse -Force
            Write-Success "Banco restaurado"
        } else {
            Write-Info "Banco será criado na primeira execução"
        }
    }
    
    # Verificar media
    $mediaPath = Join-Path $ProjectPath "media"
    if (Test-Path $mediaPath) {
        $fileCount = (Get-ChildItem -Path $mediaPath -Recurse -File).Count
        Write-Success "Media encontrada ($fileCount arquivos)"
    } else {
        Write-Warning "Pasta media não encontrada (será criada automaticamente)"
    }
    
    # Verificar .env
    $envPath = Join-Path $ProjectPath ".env"
    if (Test-Path $envPath) {
        Write-Success ".env encontrado"
    } else {
        Write-Warning ".env não encontrado (será criado com defaults se necessário)"
    }
    
    if ($errors.Count -gt 0) {
        Write-Error "Erros encontrados na verificação de integridade"
        return $false
    }
    
    return $true
}

# Instalar dependências
function Install-Dependencies {
    Write-Step "Atualizando dependências Python"
    
    $requirementsPath = Join-Path $ProjectPath "requirements.txt"
    if (Test-Path $requirementsPath) {
        try {
            & python -m pip install --upgrade pip
            & python -m pip install -r $requirementsPath --upgrade
            Write-Success "Dependências atualizadas"
        } catch {
            Write-Warning "Erro ao atualizar dependências: $_"
            Write-Info "Tente atualizar manualmente depois"
        }
    } else {
        Write-Warning "requirements.txt não encontrado"
    }
}

# Reiniciar serviço
function Start-Service {
    Write-Step "Reiniciando serviço: $ServiceName"
    
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        try {
            Start-Service -Name $ServiceName
            Start-Sleep -Seconds 5
            
            $service = Get-Service -Name $ServiceName
            if ($service.Status -eq "Running") {
                Write-Success "Serviço iniciado com sucesso"
                
                # Testar endpoint de saúde
                Start-Sleep -Seconds 3
                try {
                    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                    Write-Success "API respondendo corretamente"
                } catch {
                    Write-Warning "API não respondeu no teste inicial. Verifique os logs."
                }
            } else {
                Write-Error "Serviço não iniciou. Status: $($service.Status)"
                Write-Info "Verifique os logs em: $ProjectPath\logs\"
                return $false
            }
        } catch {
            Write-Error "Erro ao iniciar serviço: $_"
            return $false
        }
    } else {
        Write-Warning "Serviço $ServiceName não encontrado"
        Write-Info "Inicie manualmente ou use o script deploy.ps1"
    }
    
    return $true
}

# Função principal
function Main {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Atualização Segura - API SGP" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Verificar privilégios
    if (-not (Test-Administrator)) {
        Write-Warning "Este script precisa ser executado como Administrador para gerenciar serviços."
        Write-Info "Execute: Start-Process powershell -Verb RunAs"
        if (-not $Force) {
            $continue = Read-Host "Continuar mesmo assim? (S/N)"
            if ($continue -ne "S") {
                exit 1
            }
        }
    }
    
    # Normalizar caminho
    $ProjectPath = (Resolve-Path $ProjectPath).Path
    Write-Info "Diretório do projeto: $ProjectPath"
    
    # Verificar pré-requisitos
    Test-Prerequisites
    
    # Confirmar ação
    if (-not $Force) {
        Write-Host ""
        Write-Warning "Este script irá:"
        Write-Host "  1. Parar o serviço $ServiceName"
        Write-Host "  2. Fazer backup do banco de dados"
        Write-Host "  3. Atualizar código (preservando dados)"
        Write-Host "  4. Reiniciar o serviço"
        Write-Host ""
        $confirm = Read-Host "Continuar? (S/N)"
        if ($confirm -ne "S") {
            Write-Info "Cancelado pelo usuário"
            exit 0
        }
    }
    
    $tempBackup = $null
    
    try {
        # 1. Parar serviço
        Stop-Service
        
        # 2. Backup
        Backup-Database
        $tempBackup = Backup-DataFiles
        
        # 3. Atualizar código
        if ($UseGit) {
            Update-WithGit
        } elseif ($NewCodePath) {
            Update-WithCopy -SourcePath $NewCodePath
        } else {
            Write-Error "Forneça -NewCodePath ou use -UseGit"
            exit 1
        }
        
        # 4. Verificar integridade
        $integrityOk = Test-DataIntegrity -TempBackup $tempBackup
        if (-not $integrityOk) {
            Write-Error "Falha na verificação de integridade. Restaurando backup..."
            if ($tempBackup) {
                Copy-Item -Path (Join-Path $tempBackup "db\*") -Destination (Join-Path $ProjectPath "db\") -Recurse -Force
                Copy-Item -Path (Join-Path $tempBackup "media\*") -Destination (Join-Path $ProjectPath "media\") -Recurse -Force
            }
            exit 1
        }
        
        # 5. Atualizar dependências
        Install-Dependencies
        
        # 6. Reiniciar serviço
        $serviceOk = Start-Service
        if (-not $serviceOk) {
            Write-Warning "Serviço não iniciou corretamente. Verifique manualmente."
        }
        
        Write-Host ""
        Write-Success "Atualização concluída com sucesso!"
        Write-Host ""
        Write-Info "Próximos passos:"
        Write-Info "1. Verifique os logs em: $ProjectPath\logs\"
        Write-Info "2. Teste a API em: http://localhost:8000/health"
        Write-Info "3. Acesse a documentação: http://localhost:8000/docs"
        
        if ($tempBackup) {
            Write-Host ""
            Write-Warning "Backup temporário em: $tempBackup"
            Write-Info "Você pode apagar após confirmar que está tudo funcionando."
            if (-not $Force) {
                $delete = Read-Host "Apagar backup temporário agora? (S/N)"
                if ($delete -eq "S") {
                    Remove-Item -Path $tempBackup -Recurse -Force
                    Write-Success "Backup temporário removido"
                }
            }
        }
        
    } catch {
        Write-Error "Erro durante atualização: $_"
        Write-Error $_.ScriptStackTrace
        
        # Tentar restaurar se houver backup
        if ($tempBackup -and (Test-Path $tempBackup)) {
            Write-Warning "Tentando restaurar dados do backup temporário..."
            try {
                Copy-Item -Path (Join-Path $tempBackup "db\*") -Destination (Join-Path $ProjectPath "db\") -Recurse -Force
                Copy-Item -Path (Join-Path $tempBackup "media\*") -Destination (Join-Path $ProjectPath "media\") -Recurse -Force
                Write-Success "Dados restaurados do backup temporário"
            } catch {
                Write-Error "Erro ao restaurar backup: $_"
            }
        }
        
        exit 1
    }
}

# Executar
try {
    Main
} catch {
    Write-Error "Erro fatal: $_"
    exit 1
}

