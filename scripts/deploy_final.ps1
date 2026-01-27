<#
.SYNOPSIS
    Deploy final para Windows Server com diretório compartilhado acima da API.

.DESCRIPTION
    - Cria/garante a estrutura compartilhada em C:\api\shared
    - (Opcional) Cria .env com API_ROOT e SECRET_KEY
    - Instala e configura serviço Windows via NSSM
    - Inicia o serviço
#>
param(
    [Parameter()][string]$ProjectPath = (Get-Location).Path,
    [Parameter()][string]$ApiRoot = "C:\\api",
    [Parameter()][string]$DeployPath = "",
    [Parameter()][string]$PythonPath = "python.exe",
    [Parameter()][string]$ServiceName = "SGP-API",
    [Parameter()][int]$Port = 8000,
    [Parameter()][int]$Workers = 4,
    [Parameter()][bool]$UseHypercorn = $true,
    [Parameter()][string]$NSSMPath = "nssm.exe",
    [Parameter()][bool]$InstallNSSM = $true,
    [Parameter()][bool]$CreateEnvFile = $false,
    [Parameter()][string]$SecretKey = "",
    [Parameter()][bool]$UseVenv = $true,
    [Parameter()][switch]$SkipServiceInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-NSSM {
    Write-Info "Baixando NSSM..."
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $tempDir = Join-Path $env:TEMP "nssm_install"
    $zipPath = Join-Path $tempDir "nssm.zip"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    try {
        Invoke-WebRequest -Uri $nssmUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
        $nssmExe = Get-ChildItem -Path $tempDir -Recurse -Filter "nssm.exe" | Select-Object -First 1
        if (-not $nssmExe) { throw "nssm.exe não encontrado no arquivo baixado" }
        $nssmTarget = Join-Path $env:ProgramFiles "NSSM\\nssm.exe"
        New-Item -ItemType Directory -Path (Split-Path $nssmTarget) -Force | Out-Null
        Copy-Item $nssmExe.FullName $nssmTarget -Force
        $script:NSSMPath = $nssmTarget
        Write-Success "NSSM instalado em: $nssmTarget"
    } catch {
        Write-Error "Falha ao baixar/instalar NSSM: $_"
        exit 1
    } finally {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Test-Prerequisites {
    Write-Info "Verificando pré-requisitos..."
    try {
        $pythonVersion = & $PythonPath --version 2>&1
        Write-Success "Python encontrado: $pythonVersion"
    } catch {
        Write-Error "Python não encontrado. Instale Python 3.12+ e adicione ao PATH."
        exit 1
    }
    try {
        $pipVersion = & $PythonPath -m pip --version 2>&1
        Write-Success "pip encontrado: $pipVersion"
    } catch {
        Write-Error "pip não encontrado. Instale pip e tente novamente."
        exit 1
    }
    if (-not $SkipServiceInstall) {
        try {
            $null = & $NSSMPath version 2>&1
            Write-Success "NSSM encontrado: $NSSMPath"
        } catch {
            if ($InstallNSSM) {
                Write-Warning "NSSM não encontrado. Tentando baixar e instalar..."
                Install-NSSM
            } else {
                Write-Error "NSSM não encontrado. Instale NSSM ou use -InstallNSSM para instalação automática."
                exit 1
            }
        }
    }
}

function Install-Dependencies {
    Write-Info "Instalando dependências Python..."
    $requirementsPath = Join-Path $ProjectPath "requirements.txt"
    if (-not (Test-Path $requirementsPath)) {
        Write-Error "Arquivo requirements.txt não encontrado em: $ProjectPath"
        exit 1
    }
    try {
        $installPython = $PythonPath
        if ($UseVenv) {
            $venvDir = Join-Path $ProjectPath ".venv"
            if (-not (Test-Path $venvDir)) {
                Write-Info "Criando venv em: $venvDir"
                & $PythonPath -m venv $venvDir
            }
            $installPython = Join-Path $venvDir "Scripts\\python.exe"
            if (-not (Test-Path $installPython)) {
                Write-Error "Python do venv não encontrado em: $installPython"
                exit 1
            }
        }
        & $installPython -m pip install --upgrade pip
        & $installPython -m pip install -r $requirementsPath
        Write-Success "Dependências instaladas com sucesso"
        $script:RuntimePython = $installPython
    } catch {
        Write-Error "Falha ao instalar dependências: $_"
        exit 1
    }
}

function Sync-CurrentRelease {
    if ([string]::IsNullOrEmpty($DeployPath)) {
        $script:DeployPath = Join-Path $ApiRoot "current"
    }
    Write-Info "Sincronizando código para: $DeployPath"
    New-Item -ItemType Directory -Path $DeployPath -Force | Out-Null
    $excludeDirs = @(
        ".git", ".venv", "__pycache__", "logs", "media", "db", "backups", "shared"
    )
    $excludeFiles = @("*.pyc", "*.pyo")
    $robocopyArgs = @(
        "`"$SourcePath`"",
        "`"$DeployPath`"",
        "/MIR",
        "/XJ",
        "/R:2",
        "/W:2",
        "/NFL",
        "/NDL"
    )
    foreach ($dir in $excludeDirs) {
        $robocopyArgs += "/XD"
        $robocopyArgs += "`"$dir`""
    }
    foreach ($file in $excludeFiles) {
        $robocopyArgs += "/XF"
        $robocopyArgs += "`"$file`""
    }
    & robocopy @robocopyArgs | Out-Null
    if ($LASTEXITCODE -gt 7) {
        Write-Error "Falha ao copiar arquivos com robocopy. ExitCode=$LASTEXITCODE"
        exit 1
    }
    Write-Success "Código sincronizado para $DeployPath"
}

function Initialize-SharedDirectories {
    Write-Info "Criando diretórios compartilhados em $ApiRoot\\shared..."
    $sharedRoot = Join-Path $ApiRoot "shared"
    $directories = @(
        "db",
        "media",
        "media\\pedidos",
        "media\\fichas",
        "media\\templates",
        "logs",
        "backups"
    )
    foreach ($dir in $directories) {
        $fullPath = Join-Path $sharedRoot $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
            Write-Success "Diretório criado: $fullPath"
        } else {
            Write-Info "Diretório já existe: $fullPath"
        }
    }
}

function Initialize-EnvFile {
    if (-not $CreateEnvFile) { return }
    Write-Info "Criando arquivo .env..."
    $envPath = Join-Path $ProjectPath ".env"
    if (Test-Path $envPath) {
        Write-Warning "Arquivo .env já existe. Pulando criação."
        return
    }
    if ([string]::IsNullOrEmpty($SecretKey)) {
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        $SecretKey = [Convert]::ToBase64String($bytes)
    }
    $envContent = @"
# Configurações da API SGP
API_ROOT=$ApiRoot
ENVIRONMENT=production
SECRET_KEY=$SecretKey
LOG_LEVEL=INFO
# Ajuste para o seu frontend:
# BACKEND_CORS_ORIGINS=http://seu-front,https://seu-front
"@
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
    Write-Success "Arquivo .env criado em: $envPath"
}

function Install-WindowsService {
    if ($SkipServiceInstall) {
        Write-Info "Pulando instalação do serviço (--SkipServiceInstall)"
        return
    }
    Write-Info "Instalando serviço Windows: $ServiceName"
    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Warning "Serviço $ServiceName já existe. Parando e removendo..."
        Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue
        & $NSSMPath remove $ServiceName confirm
        Start-Sleep -Seconds 2
    }
    if ($UseHypercorn) {
        if ($Workers -gt 0) {
            $appArgs = "-m hypercorn main:app --bind 0.0.0.0:$Port --workers $Workers --loop asyncio"
        } else {
            Write-Warning "Workers=0 mas UseHypercorn=true. Usando 1 worker."
            $appArgs = "-m hypercorn main:app --bind 0.0.0.0:$Port --workers 1 --loop asyncio"
        }
    } else {
        $appArgs = "-m uvicorn main:app --host 0.0.0.0 --port $Port --loop asyncio"
    }
    $servicePython = $PythonPath
    if ($UseVenv) {
        $servicePython = Join-Path $ProjectPath ".venv\\Scripts\\python.exe"
        if (-not (Test-Path $servicePython)) {
            Write-Error "Python do venv não encontrado em: $servicePython"
            exit 1
        }
    }
    try {
        & $NSSMPath install $ServiceName $servicePython $appArgs
        & $NSSMPath set $ServiceName AppDirectory $ProjectPath
        & $NSSMPath set $ServiceName DisplayName "SGP API Server"
        & $NSSMPath set $ServiceName Description "API Sistema de Gestão de Produção (SGP)"
        & $NSSMPath set $ServiceName Start SERVICE_AUTO_START
        & $NSSMPath set $ServiceName AppEnvironmentExtra "API_ROOT=$ApiRoot" "ENVIRONMENT=production"
        $sharedLogs = Join-Path (Join-Path $ApiRoot "shared") "logs"
        New-Item -ItemType Directory -Path $sharedLogs -Force | Out-Null
        & $NSSMPath set $ServiceName AppStdout (Join-Path $sharedLogs "service_stdout.log")
        & $NSSMPath set $ServiceName AppStderr (Join-Path $sharedLogs "service_stderr.log")
        Write-Success "Serviço instalado com sucesso"
        Write-Info "Comando: $servicePython $appArgs"
    } catch {
        Write-Error "Falha ao instalar serviço: $_"
        exit 1
    }
}

function Start-WindowsService {
    if ($SkipServiceInstall) { return }
    Write-Info "Iniciando serviço: $ServiceName"
    try {
        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 3
        $service = Get-Service -Name $ServiceName
        if ($service.Status -eq "Running") {
            Write-Success "Serviço iniciado com sucesso"
            Write-Info "API disponível em: http://0.0.0.0:$Port"
            Write-Info "Documentação: http://localhost:$Port/docs"
        } else {
            Write-Warning "Serviço não está rodando. Status: $($service.Status)"
            Write-Info "Verifique os logs em: $ApiRoot\\shared\\logs\\"
        }
    } catch {
        Write-Error "Falha ao iniciar serviço: $_"
    }
}

function Main {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Deploy Final - API SGP (Windows)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    if (-not $SkipServiceInstall -and -not (Test-Administrator)) {
        Write-Error "Este script precisa ser executado como Administrador para instalar serviços."
        Write-Info "Execute: Start-Process powershell -Verb RunAs"
        exit 1
    }
    $SourcePath = (Resolve-Path $ProjectPath).Path
    Write-Info "Diretório de origem: $SourcePath"
    $mainPySource = Join-Path $SourcePath "main.py"
    if (-not (Test-Path $mainPySource)) {
        Write-Error "Arquivo main.py não encontrado em: $SourcePath"
        exit 1
    }
    Test-Prerequisites
    Sync-CurrentRelease
    $ProjectPath = $DeployPath
    Install-Dependencies
    Initialize-SharedDirectories
    Initialize-EnvFile
    Install-WindowsService
    Start-WindowsService
    Write-Host ""
    Write-Success "Deploy concluído com sucesso!"
}

try {
    Main
} catch {
    Write-Error "Erro durante o deploy: $_"
    Write-Error $_.ScriptStackTrace
    exit 1
}
