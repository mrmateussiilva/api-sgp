<#
.SYNOPSIS
    Script de update profissional para API SGP com migrations.

.DESCRIPTION
    Este script implementa um processo de update completo:
    1. Para o serviço NSSM
    2. Cria backup versionado do banco
    3. Baixa/extrai nova release
    4. Atualiza ponteiro current
    5. Executa migrations
    6. Reinicia serviço
    7. Valida healthcheck
    8. Aborta em caso de erro (com rollback opcional)

.PARAMETER Version
    Versão a ser deployada (ex: "1.0.6")

.PARAMETER ReleaseZip
    Caminho do arquivo ZIP da nova release (opcional)

.PARAMETER ApiRoot
    Diretório raiz da API (default: "C:\api")

.PARAMETER ServiceName
    Nome do serviço Windows (default: "SGP-API")

.PARAMETER Port
    Porta da API (default: 8000)

.PARAMETER SkipBackup
    Pular backup (NÃO RECOMENDADO em produção)

.PARAMETER Force
    Não pedir confirmação (útil para automação)

.EXAMPLE
    .\scripts\update.ps1 -Version "1.0.6" -ReleaseZip "C:\Downloads\api-sgp-1.0.6.zip"
#>
param(
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$false)][string]$ReleaseZip = "",
    [Parameter(Mandatory=$false)][string]$ApiRoot = "C:\api",
    [Parameter(Mandatory=$false)][string]$ServiceName = "SGP-API",
    [Parameter(Mandatory=$false)][int]$Port = 8000,
    [Parameter(Mandatory=$false)][switch]$SkipBackup,
    [Parameter(Mandatory=$false)][switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Cores
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }
function Write-Step { Write-Host "[STEP] $args" -ForegroundColor Magenta }

# Diretórios
$ReleasesDir = Join-Path $ApiRoot "releases"
$SharedDir = Join-Path $ApiRoot "shared"
$BackupsDir = Join-Path $SharedDir "backups"
$CurrentLink = Join-Path $ReleasesDir "current"
$ReleaseDir = Join-Path $ReleasesDir "v$Version"
$DbPath = Join-Path $SharedDir "db\banco.db"

# Variáveis de estado
$serviceWasRunning = $false
$backupCreated = $false
$backupPath = $null

# Função de cleanup em caso de erro
function Cleanup-OnError {
    param([string]$Message)
    
    Write-Error "❌ ERRO: $Message"
    Write-Warning "Executando cleanup..."
    
    # Se serviço estava rodando, tentar reiniciar
    if ($serviceWasRunning) {
        Write-Info "Tentando reiniciar serviço..."
        try {
            $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
            if ($service -and $service.Status -ne "Running") {
                Start-Service -Name $ServiceName
                Start-Sleep -Seconds 3
            }
        } catch {
            Write-Warning "Não foi possível reiniciar serviço automaticamente"
        }
    }
    
    exit 1
}

# Função para criar backup
function Backup-Database {
    Write-Step "1/7: Criando backup do banco de dados..."
    
    if (-not (Test-Path $DbPath)) {
        Write-Warning "Banco de dados não encontrado: $DbPath"
        return
    }
    
    $timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
    $backupFile = Join-Path $BackupsDir "banco-pre-$Version-$timestamp.db"
    
    New-Item -ItemType Directory -Path $BackupsDir -Force | Out-Null
    
    try {
        Copy-Item -Path $DbPath -Destination $backupFile -Force
        $script:backupCreated = $true
        $script:backupPath = $backupFile
        Write-Success "Backup criado: $backupFile"
    } catch {
        Cleanup-OnError "Falha ao criar backup: $_"
    }
}

# Função para parar serviço
function Stop-Service {
    Write-Step "2/7: Parando serviço '$ServiceName'..."
    
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        if ($service.Status -eq "Running") {
            $script:serviceWasRunning = $true
            try {
                Stop-Service -Name $ServiceName -Force
                Start-Sleep -Seconds 3
                Write-Success "Serviço parado"
            } catch {
                Cleanup-OnError "Falha ao parar serviço: $_"
            }
        } else {
            Write-Info "Serviço já estava parado"
        }
    } else {
        Write-Warning "Serviço '$ServiceName' não encontrado"
    }
}

# Função para extrair release
function Extract-Release {
    Write-Step "3/7: Preparando release v$Version..."
    
    if ($ReleaseZip -and (Test-Path $ReleaseZip)) {
        # Extrair de ZIP
        Write-Info "Extraindo ZIP: $ReleaseZip"
        
        if (Test-Path $ReleaseDir) {
            Remove-Item -Path $ReleaseDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
        
        # Extrair ZIP (PowerShell 5.1+)
        Expand-Archive -Path $ReleaseZip -DestinationPath $ReleaseDir -Force
        
        Write-Success "Release extraída: $ReleaseDir"
    } else {
        # Assumir que código já está na pasta (modo desenvolvimento)
        if (-not (Test-Path $ReleaseDir)) {
            Cleanup-OnError "Release não encontrada: $ReleaseDir"
        }
        Write-Info "Usando release existente: $ReleaseDir"
    }
}

# Função para atualizar link current
function Update-CurrentLink {
    Write-Step "4/7: Atualizando link 'current'..."
    
    if (Test-Path $CurrentLink) {
        Remove-Item -Path $CurrentLink -Force
    }
    
    New-Item -ItemType SymbolicLink -Path $CurrentLink -Target $ReleaseDir | Out-Null
    Write-Success "Link 'current' atualizado: $CurrentLink -> $ReleaseDir"
}

# Função para executar migrations
function Invoke-Migrations {
    Write-Step "5/7: Executando migrations..."
    
    $venvPython = Join-Path $ReleaseDir "venv\Scripts\python.exe"
    $migrationsScript = Join-Path $ReleaseDir "database\run_migrations.py"
    
    if (-not (Test-Path $venvPython)) {
        Cleanup-OnError "Python virtual environment não encontrado: $venvPython"
    }
    
    if (-not (Test-Path $migrationsScript)) {
        Write-Warning "Script de migrations não encontrado. Pulando migrations..."
        return
    }
    
    try {
        $env:API_ROOT = $ApiRoot
        $result = & $venvPython $migrationsScript 2>&1
        $exitCode = $LASTEXITCODE
        
        if ($exitCode -ne 0) {
            Write-Error "Migrations falharam:"
            $result | ForEach-Object { Write-Host $_ }
            Cleanup-OnError "Migrations falharam com código $exitCode"
        }
        
        Write-Success "Migrations executadas com sucesso"
        $result | ForEach-Object { Write-Host $_ }
    } catch {
        Cleanup-OnError "Erro ao executar migrations: $_"
    }
}

# Função para reiniciar serviço
function Start-Service {
    Write-Step "6/7: Reiniciando serviço '$ServiceName'..."
    
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Cleanup-OnError "Serviço '$ServiceName' não encontrado"
    }
    
    try {
        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 5
        
        $service = Get-Service -Name $ServiceName
        if ($service.Status -ne "Running") {
            Cleanup-OnError "Serviço não iniciou. Status: $($service.Status)"
        }
        
        Write-Success "Serviço iniciado"
    } catch {
        Cleanup-OnError "Erro ao iniciar serviço: $_"
    }
}

# Função para validar healthcheck
function Test-HealthCheck {
    Write-Step "7/7: Validando healthcheck..."
    
    $healthUrl = "http://localhost:$Port/health"
    $maxAttempts = 10
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            $health = $response.Content | ConvertFrom-Json
            
            if ($health.status -eq "ok" -and $health.checks.database -eq "ok") {
                Write-Success "✅ Healthcheck OK - API e banco funcionando"
                Write-Info "Versão: $($health.version)"
                return $true
            } else {
                Write-Warning "Healthcheck retornou status degradado: $($health.status)"
            }
        } catch {
            $attempt++
            if ($attempt -lt $maxAttempts) {
                Write-Info "Tentativa $attempt/$maxAttempts - Aguardando API iniciar..."
                Start-Sleep -Seconds 3
            }
        }
    }
    
    Cleanup-OnError "Healthcheck falhou após $maxAttempts tentativas"
}

# Função principal
function Main {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  UPDATE PROFISSIONAL - API SGP" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Info "Versão: $Version"
    Write-Info "API Root: $ApiRoot"
    Write-Info "Serviço: $ServiceName"
    Write-Host ""
    
    # Confirmação
    if (-not $Force) {
        $confirm = Read-Host "Deseja continuar com o update? (s/N)"
        if ($confirm -ne "s" -and $confirm -ne "S") {
            Write-Info "Update cancelado pelo usuário"
            exit 0
        }
    }
    
    try {
        # 1. Backup
        if (-not $SkipBackup) {
            Backup-Database
        } else {
            Write-Warning "⚠️ Backup pulado (não recomendado)"
        }
        
        # 2. Parar serviço
        Stop-Service
        
        # 3. Extrair release
        Extract-Release
        
        # 4. Atualizar link
        Update-CurrentLink
        
        # 5. Executar migrations
        Invoke-Migrations
        
        # 6. Reiniciar serviço
        Start-Service
        
        # 7. Validar healthcheck
        Test-HealthCheck
        
        Write-Host ""
        Write-Success "========================================"
        Write-Success "✅ UPDATE CONCLUÍDO COM SUCESSO!"
        Write-Success "========================================"
        Write-Host ""
        Write-Info "Versão ativa: $Version"
        Write-Info "Backup criado: $backupPath"
        Write-Info "API: http://localhost:$Port"
        Write-Info "Health: http://localhost:$Port/health"
        Write-Info "Docs: http://localhost:$Port/docs"
        
    } catch {
        Cleanup-OnError "Erro durante update: $_"
    }
}

# Executar
Main
