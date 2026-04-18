<#
.SYNOPSIS
    Gera um ZIP de release limpo da API para deploy na intranet.

.DESCRIPTION
    O script copia apenas os arquivos necessários da aplicação para um diretório temporário,
    exclui dados locais e empacota o resultado em dist/api-sgp-<versao>.zip.

.EXAMPLE
    .\scripts\build-release.ps1

.EXAMPLE
    .\scripts\build-release.ps1 -Version 1.0.21 -OutputDir C:\deploy
#>
param(
    [Parameter()][string]$ProjectRoot = "",
    [Parameter()][string]$Version = "",
    [Parameter()][string]$OutputDir = "",
    [Parameter()][switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }

function Get-VersionFromPyProject {
    param([string]$Root)

    $pyprojectPath = Join-Path $Root "pyproject.toml"
    if (-not (Test-Path $pyprojectPath)) {
        throw "pyproject.toml não encontrado em $Root"
    }

    $match = Select-String -Path $pyprojectPath -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $match) {
        throw "Versão não encontrada em pyproject.toml"
    }

    return $match.Matches[0].Groups[1].Value
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Get-VersionFromPyProject -Root $ProjectRoot
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ProjectRoot "dist"
}

if (-not (Test-Path (Join-Path $ProjectRoot "main.py"))) {
    throw "main.py não encontrado em $ProjectRoot"
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$releaseName = "api-sgp-$Version"
$zipPath = Join-Path $OutputDir "$releaseName.zip"
$stagingDir = Join-Path ([System.IO.Path]::GetTempPath()) "$releaseName-$([guid]::NewGuid().ToString('N'))"

$excludeDirs = @("db", "media", "logs", "backups", "venv", ".venv", "__pycache__", ".git", "releases", "shared", "dist")
$excludeFiles = @("*.pyc", "*.pyo", "*.db", "*.db-shm", "*.db-wal", ".env")

if ((Test-Path $zipPath) -and (-not $Force)) {
    throw "Arquivo já existe: $zipPath. Use -Force para sobrescrever."
}

New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

try {
    Write-Info "Montando release $releaseName"

    Get-ChildItem -Path $ProjectRoot -Recurse -Force | ForEach-Object {
        $relativePath = $_.FullName.Substring($ProjectRoot.Length).TrimStart("\")
        if ([string]::IsNullOrWhiteSpace($relativePath)) {
            return
        }

        foreach ($excludeDir in $excludeDirs) {
            if ($relativePath.StartsWith("$excludeDir\") -or $relativePath -like "*\$excludeDir\*") {
                return
            }
        }

        foreach ($excludePattern in $excludeFiles) {
            if ($_.Name -like $excludePattern) {
                return
            }
        }

        $destination = Join-Path $stagingDir $relativePath
        if ($_.PSIsContainer) {
            if (-not (Test-Path $destination)) {
                New-Item -ItemType Directory -Path $destination -Force | Out-Null
            }
            return
        }

        $parent = Split-Path -Path $destination -Parent
        if (-not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }

        Copy-Item -Path $_.FullName -Destination $destination -Force
    }

    $manifest = @{
        name = "api-sgp"
        version = $Version
        built_at = (Get-Date).ToString("s")
        source = $ProjectRoot
    } | ConvertTo-Json -Depth 4

    Set-Content -Path (Join-Path $stagingDir "release-manifest.json") -Value $manifest -Encoding UTF8

    if (Test-Path $zipPath) {
        Remove-Item -Path $zipPath -Force
    }

    Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
    Write-Success "Release gerada: $zipPath"
} finally {
    if (Test-Path $stagingDir) {
        Remove-Item -Path $stagingDir -Recurse -Force
    }
}
