<#
.SYNOPSIS
    Atualiza a API automaticamente a partir de um ZIP em uma pasta compartilhada.

.DESCRIPTION
    Procura o ZIP mais recente em uma pasta (local ou UNC), extrai a versao do nome,
    executa o update e grava o ultimo ZIP aplicado para evitar repeticao.

.PARAMETER WatchPath
    Pasta onde o ZIP sera colocado (ex: \\SERVIDOR\share\api).

.PARAMETER ApiRoot
    Diretório raiz da API (default: C:\api).

.PARAMETER ServiceName
    Nome do serviço Windows (default: SGP-API).

.PARAMETER ZipPattern
    Padrao do arquivo ZIP (default: api-sgp-*.zip).

.PARAMETER MinAgeSeconds
    Tempo minimo (segundos) desde a ultima modificacao do ZIP.

.PARAMETER StateFile
    Caminho do arquivo que guarda o ultimo ZIP aplicado.

.PARAMETER SkipBackup
    Pular backup (NÃO RECOMENDADO).

.PARAMETER Force
    Não pedir confirmação (automacao).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\update_from_share.ps1 `
      -WatchPath "\\SERVIDOR\share\api" -ApiRoot "C:\api" -Force
#>
param(
    [Parameter(Mandatory=$true)][string]$WatchPath,
    [Parameter(Mandatory=$false)][string]$ApiRoot = "C:\api",
    [Parameter(Mandatory=$false)][string]$ServiceName = "SGP-API",
    [Parameter(Mandatory=$false)][string]$ZipPattern = "api-sgp-*.zip",
    [Parameter(Mandatory=$false)][int]$MinAgeSeconds = 30,
    [Parameter(Mandatory=$false)][string]$StateFile = "",
    [Parameter(Mandatory=$false)][switch]$SkipBackup,
    [Parameter(Mandatory=$false)][switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

if (-not (Test-Path $WatchPath)) {
    Write-Error "Pasta nao encontrada: $WatchPath"
    exit 1
}

$statePath = $StateFile
if (-not $statePath) {
    $stateDir = Join-Path $ApiRoot "shared\update"
    $statePath = Join-Path $stateDir "last_zip.txt"
} else {
    $stateDir = Split-Path $statePath -Parent
}

$latest = Get-ChildItem -Path $WatchPath -Filter $ZipPattern -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $latest) {
    Write-Info "Nenhum ZIP encontrado em $WatchPath"
    exit 0
}

$ageSeconds = (Get-Date) - $latest.LastWriteTime
if ($ageSeconds.TotalSeconds -lt $MinAgeSeconds) {
    Write-Info "ZIP ainda recente (aguardando $MinAgeSeconds s): $($latest.Name)"
    exit 0
}

if (Test-Path $statePath) {
    $lastApplied = (Get-Content $statePath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($lastApplied -eq $latest.FullName) {
        Write-Info "ZIP ja aplicado: $($latest.Name)"
        exit 0
    }
}

$versionMatch = [regex]::Match($latest.BaseName, "(\d+\.\d+\.\d+)")
if (-not $versionMatch.Success) {
    Write-Error "Nao foi possivel extrair a versao do nome: $($latest.Name)"
    exit 1
}
$version = $versionMatch.Groups[1].Value

$updateScript = Join-Path $ApiRoot "scripts\update.ps1"
if (-not (Test-Path $updateScript)) {
    Write-Error "Script de update nao encontrado: $updateScript"
    exit 1
}

Write-Info "Aplicando update $version com $($latest.FullName)"
& powershell -ExecutionPolicy Bypass -File $updateScript `
    -Version $version `
    -ReleaseZip $latest.FullName `
    -ApiRoot $ApiRoot `
    -ServiceName $ServiceName `
    -SkipBackup:$SkipBackup `
    -Force:$Force

if ($LASTEXITCODE -ne 0) {
    Write-Error "Update falhou com codigo $LASTEXITCODE"
    exit $LASTEXITCODE
}

New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
Set-Content -Path $statePath -Value $latest.FullName
Write-Success "Update aplicado e registrado em $statePath"
