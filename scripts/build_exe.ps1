<#
.SYNOPSIS
    Cria executável da API usando PyInstaller.

.DESCRIPTION
    Este script automatiza a criação de um executável .exe da API SGP.
    O executável contém toda a aplicação Python e pode ser usado diretamente
    sem necessidade de instalar Python ou dependências.

.PARAMETER Version
    Versão do executável (ex: 0.1, 0.2, etc.). Default: 0.1

.EXAMPLE
    .\build_exe.ps1 -Version 0.1

.EXAMPLE
    .\build_exe.ps1 -Version 0.2
#>
param(
    [Parameter()][string]$Version = "0.1"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Executável - API SGP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar PyInstaller
Write-Host "[INFO] Verificando PyInstaller..." -ForegroundColor Cyan
try {
    $null = pyinstaller --version 2>&1
    Write-Host "[SUCCESS] PyInstaller encontrado" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] PyInstaller não encontrado. Instalando..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Falha ao instalar PyInstaller" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "[INFO] Iniciando build do executável..." -ForegroundColor Cyan
Write-Host ""

# Executar build
python scripts/build_exe.py $Version

if ($LASTEXITCODE -eq 0) {
    $exeName = "api_sgp_$($Version.Replace('.', '_')).exe"
    $exePath = "dist\$exeName"
    
    if (Test-Path $exePath) {
        $fileSize = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
        Write-Host ""
        Write-Host "[SUCCESS] Executável criado com sucesso!" -ForegroundColor Green
        Write-Host "  Arquivo: $exePath" -ForegroundColor Green
        Write-Host "  Tamanho: $fileSize MB" -ForegroundColor Green
        Write-Host ""
        Write-Host "[INFO] Próximos passos:" -ForegroundColor Cyan
        Write-Host "  1. Copie o executável para o servidor Windows" -ForegroundColor Cyan
        Write-Host "  2. Crie os diretórios: db, media, logs, backups" -ForegroundColor Cyan
        Write-Host "  3. Configure o NSSM para usar o executável" -ForegroundColor Cyan
        Write-Host ""
    } else {
        Write-Host "[WARNING] Executável não encontrado em: $exePath" -ForegroundColor Yellow
        Write-Host "  Verifique a pasta dist/ para outros arquivos" -ForegroundColor Yellow
    }
} else {
    Write-Host "[ERROR] Falha ao criar executável" -ForegroundColor Red
    exit 1
}

