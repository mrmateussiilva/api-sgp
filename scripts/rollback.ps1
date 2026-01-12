<#
.SYNOPSIS
    Script de rollback para API SGP.

.DESCRIPTION
    Reverte para versão anterior e opcionalmente reverte migrations.

.PARAMETER TargetVersion
    Versão para rollback (ex: "1.0.5")

.PARAMETER RevertMigrations
    Se especificado, reverte migrations da versão atual antes de fazer rollback

.PARAMETER ApiRoot
    Diretório raiz da API (default: "C:\api")

.PARAMETER ServiceName
    Nome do serviço Windows (default: "SGP-API")

.PARAMETER Port
    Porta da API (default: 8000)

.EXAMPLE
    .\scripts\rollback.ps1 -TargetVersion "1.0.5"
#>
param(
    [Parameter(Mandatory=$true)][string]$TargetVersion,
    [Parameter(Mandatory=$false)][switch]$RevertMigrations,
    [Parameter(Mandatory=$false)][string]$ApiRoot = "C:\api",
    [Parameter(Mandatory=$false)][string]$ServiceName = "SGP-API",
    [Parameter(Mandatory=$false)][int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

$ReleasesDir = Join-Path $ApiRoot "releases"
$CurrentLink = Join-Path $ReleasesDir "current"
$TargetReleaseDir = Join-Path $ReleasesDir "v$TargetVersion"

# Validar versão de destino
if (-not (Test-Path $TargetReleaseDir)) {
    Write-Error "Versão de destino não encontrada: $TargetReleaseDir"
    exit 1
}

# Obter versão atual
$currentVersion = $null
if (Test-Path $CurrentLink) {
    $currentLinkItem = Get-Item $CurrentLink
    if ($currentLinkItem.LinkType -eq "SymbolicLink") {
        $currentVersion = $currentLinkItem.Target
    }
}

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  ROLLBACK - API SGP" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Info "Versão atual: $currentVersion"
Write-Info "Versão de destino: v$TargetVersion"
Write-Host ""

$confirm = Read-Host "Deseja continuar com o rollback? (s/N)"
if ($confirm -ne "s" -and $confirm -ne "S") {
    Write-Info "Rollback cancelado"
    exit 0
}

try {
    # 1. Parar serviço
    Write-Info "Parando serviço..."
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq "Running") {
        Stop-Service -Name $ServiceName -Force
        Start-Sleep -Seconds 3
    }
    
    # 2. Reverter migrations (se solicitado)
    if ($RevertMigrations) {
        Write-Warning "⚠️ Reverter migrations pode causar perda de dados!"
        Write-Warning "⚠️ Apenas migrations reversíveis serão revertidas"
        # TODO: Implementar reversão de migrations
        Write-Info "Reversão de migrations não implementada ainda"
    }
    
    # 3. Atualizar link current
    Write-Info "Atualizando link 'current'..."
    if (Test-Path $CurrentLink) {
        Remove-Item -Path $CurrentLink -Force
    }
    New-Item -ItemType SymbolicLink -Path $CurrentLink -Target $TargetReleaseDir | Out-Null
    
    # 4. Reiniciar serviço
    Write-Info "Reiniciando serviço..."
    Start-Service -Name $ServiceName
    Start-Sleep -Seconds 5
    
    # 5. Validar healthcheck
    $healthUrl = "http://localhost:$Port/health"
    $maxAttempts = 10
    $attempt = 0
    $healthOk = $false
    
    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
            $health = $response.Content | ConvertFrom-Json
            
            if ($health.status -eq "ok") {
                $healthOk = $true
                break
            }
        } catch {
            $attempt++
            if ($attempt -lt $maxAttempts) {
                Write-Info "Tentativa $attempt/$maxAttempts - Aguardando API iniciar..."
                Start-Sleep -Seconds 3
            }
        }
    }
    
    if ($healthOk) {
        Write-Success "✅ Rollback concluído com sucesso!"
        Write-Info "Versão ativa: v$TargetVersion"
    } else {
        Write-Warning "⚠️ Rollback concluído, mas healthcheck falhou"
        Write-Warning "⚠️ Verifique os logs manualmente"
    }
    
} catch {
    Write-Error "Erro durante rollback: $_"
    exit 1
}
