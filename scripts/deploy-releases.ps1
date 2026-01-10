<#
.SYNOPSIS
    Script de deploy com arquitetura de releases versionadas para API SGP.

.DESCRIPTION
    Este script implementa uma arquitetura de releases versionadas:
    - Cada versão é isolada em seu próprio diretório (releases/v1.0.5/)
    - Cada release tem seu próprio ambiente virtual (venv)
    - Diretórios compartilhados: db, media, logs (shared/)
    - Link simbólico "current" aponta para a versão ativa
    - Gerenciamento de serviço Windows via NSSM

.PARAMETER Version
    Versão a ser deployada (ex: "1.0.5")

.PARAMETER ApiRoot
    Diretório raiz da API (default: "C:\api")

.PARAMETER ServiceName
    Nome do serviço Windows (default: "SGP-API")

.PARAMETER Port
    Porta para o servidor (default: 8000)

.PARAMETER Action
    Ação a executar: "deploy", "rollback", "list", "status" (default: "deploy")

.PARAMETER RollbackVersion
    Versão para rollback (obrigatório se Action="rollback")

.EXAMPLE
    .\deploy-releases.ps1 -Version "1.0.5" -Action "deploy"

.EXAMPLE
    .\deploy-releases.ps1 -Action "rollback" -RollbackVersion "1.0.4"

.EXAMPLE
    .\deploy-releases.ps1 -Action "list"
#>
param(
    [Parameter(Mandatory=$false)][string]$Version = "1.0.5",
    [Parameter(Mandatory=$false)][string]$ApiRoot = "C:\api",
    [Parameter(Mandatory=$false)][string]$ServiceName = "SGP-API",
    [Parameter(Mandatory=$false)][int]$Port = 8000,
    [Parameter(Mandatory=$false)][ValidateSet("deploy", "rollback", "list", "status")]
    [string]$Action = "deploy",
    [Parameter(Mandatory=$false)][string]$RollbackVersion = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Cores para output
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

# Diretórios
$ReleasesDir = Join-Path $ApiRoot "releases"
$SharedDir = Join-Path $ApiRoot "shared"
$CurrentLink = Join-Path $ReleasesDir "current"
$ReleaseDir = Join-Path $ReleasesDir "v$Version"

# Verificar se está executando como administrador
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Inicializar estrutura de diretórios compartilhados
function Initialize-SharedDirectories {
    Write-Info "Inicializando diretórios compartilhados..."
    
    $sharedDirs = @(
        "db",
        "media\pedidos",
        "media\fichas",
        "media\templates",
        "logs",
        "backups"
    )
    
    foreach ($dir in $sharedDirs) {
        $fullPath = Join-Path $SharedDir $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
            Write-Success "Diretório compartilhado criado: $dir"
        }
    }
    
    # Criar diretório de releases se não existir
    if (-not (Test-Path $ReleasesDir)) {
        New-Item -ItemType Directory -Path $ReleasesDir -Force | Out-Null
        Write-Success "Diretório de releases criado: $ReleasesDir"
    }
}

# Verificar se uv está instalado
function Test-UV {
    try {
        $uvVersion = uv --version 2>&1
        Write-Success "uv encontrado: $uvVersion"
        return $true
    } catch {
        Write-Error "uv não encontrado. Instale com: cargo install uv"
        return $false
    }
}

# Criar ambiente virtual para a release
function New-ReleaseVenv {
    param([string]$ReleasePath)
    
    Write-Info "Criando ambiente virtual para release v$Version..."
    
    $venvPath = Join-Path $ReleasePath "venv"
    
    if (Test-Path $venvPath) {
        Write-Warning "Ambiente virtual já existe. Removendo..."
        Remove-Item -Path $venvPath -Recurse -Force
    }
    
    # Usar uv para criar venv
    Push-Location $ReleasePath
    try {
        uv venv venv
        Write-Success "Ambiente virtual criado: $venvPath"
    } finally {
        Pop-Location
    }
    
    return $venvPath
}

# Instalar dependências na release
function Install-Dependencies {
    param([string]$ReleasePath, [string]$VenvPath)
    
    Write-Info "Instalando dependências para release v$Version..."
    
    $pythonPath = Join-Path $VenvPath "Scripts\python.exe"
    $pipPath = Join-Path $VenvPath "Scripts\pip.exe"
    
    Push-Location $ReleasePath
    try {
        # Ativar venv e instalar dependências com uv
        & $pythonPath -m pip install --upgrade pip
        uv pip install -r requirements.txt
        
        Write-Success "Dependências instaladas com sucesso"
    } finally {
        Pop-Location
    }
}

# Copiar arquivos da API para a release
function Copy-ReleaseFiles {
    param([string]$SourcePath, [string]$TargetPath)
    
    Write-Info "Copiando arquivos para release v$Version..."
    
    # Diretórios e arquivos a copiar (excluir db, media, logs, venv, __pycache__, etc)
    $excludeDirs = @("db", "media", "logs", "backups", "venv", "__pycache__", ".git", "releases", "shared", ".venv")
    $excludeFiles = @("*.pyc", "*.pyo", "*.db", "*.db-shm", "*.db-wal", ".env")
    
    Get-ChildItem -Path $SourcePath -Recurse | ForEach-Object {
        $relativePath = $_.FullName.Substring($SourcePath.Length + 1)
        $targetItem = Join-Path $TargetPath $relativePath
        
        # Pular diretórios excluídos
        $shouldExclude = $false
        foreach ($excludeDir in $excludeDirs) {
            if ($relativePath -like "*\$excludeDir\*" -or $relativePath.StartsWith("$excludeDir\")) {
                $shouldExclude = $true
                break
            }
        }
        
        if ($shouldExclude) {
            return
        }
        
        # Pular arquivos excluídos
        foreach ($excludePattern in $excludeFiles) {
            if ($_.Name -like $excludePattern) {
                return
            }
        }
        
        if ($_.PSIsContainer) {
            if (-not (Test-Path $targetItem)) {
                New-Item -ItemType Directory -Path $targetItem -Force | Out-Null
            }
        } else {
            Copy-Item -Path $_.FullName -Destination $targetItem -Force
        }
    }
    
    Write-Success "Arquivos copiados com sucesso"
}

# Criar arquivo .env para a release
function New-ReleaseEnvFile {
    param([string]$ReleasePath)
    
    Write-Info "Criando arquivo .env para release v$Version..."
    
    $envPath = Join-Path $ReleasePath ".env"
    $dbPath = Join-Path $SharedDir "db\banco.db"
    $mediaPath = Join-Path $SharedDir "media"
    $logPath = Join-Path $SharedDir "logs"
    
    $envContent = @"
# Configurações de Diretórios Compartilhados
API_ROOT=$ApiRoot
DATABASE_URL=sqlite:///$($dbPath.Replace('\', '/'))
MEDIA_ROOT=$mediaPath
LOG_DIR=$logPath

# Configurações da API
ENVIRONMENT=production
VERSION=$Version
PORT=$Port

# Configurações de Segurança
# IMPORTANTE: Gere uma SECRET_KEY única para produção!
# SECRET_KEY=$(New-Guid)
SECRET_KEY=change-me-$(New-Guid)
"@
    
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
    Write-Success "Arquivo .env criado: $envPath"
}

# Criar/atualizar link simbólico "current"
function Update-CurrentLink {
    param([string]$TargetPath)
    
    Write-Info "Atualizando link simbólico 'current'..."
    
    if (Test-Path $CurrentLink) {
        # Remover link existente
        if ((Get-Item $CurrentLink).LinkType -eq "SymbolicLink") {
            Remove-Item -Path $CurrentLink -Force
        } else {
            Write-Warning "Arquivo 'current' existe mas não é um link simbólico. Removendo..."
            Remove-Item -Path $CurrentLink -Recurse -Force
        }
    }
    
    # Criar novo link simbólico
    New-Item -ItemType SymbolicLink -Path $CurrentLink -Target $TargetPath | Out-Null
    Write-Success "Link simbólico 'current' atualizado: $CurrentLink -> $TargetPath"
}

# Instalar/atualizar serviço Windows via NSSM
function Install-Service {
    param([string]$ReleasePath, [string]$ServiceName, [int]$Port)
    
    if (-not (Test-Administrator)) {
        Write-Error "Elevação de privilégios necessária para instalar serviço"
        Write-Info "Execute o script como Administrador"
        return $false
    }
    
    Write-Info "Instalando/atualizando serviço Windows '$ServiceName'..."
    
    # Verificar NSSM
    $nssmPath = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if (-not $nssmPath) {
        Write-Error "NSSM não encontrado. Instale NSSM primeiro."
        Write-Info "Download: https://nssm.cc/download"
        return $false
    }
    
    $nssmExe = $nssmPath.Source
    $venvPath = Join-Path $ReleasePath "venv"
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    $mainPath = Join-Path $ReleasePath "main.py"
    $appDir = $ReleasePath
    
    # Configurar variáveis de ambiente
    $envVars = @(
        "API_ROOT=$ApiRoot",
        "PYTHONPATH=$appDir",
        "PORT=$Port"
    )
    
    # Verificar se serviço já existe
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Info "Serviço '$ServiceName' já existe. Parando..."
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    
    # Instalar/atualizar serviço
    & $nssmExe install $ServiceName $pythonPath "-m uvicorn main:app --host 0.0.0.0 --port $Port" 2>&1 | Out-Null
    & $nssmExe set $ServiceName AppDirectory $appDir 2>&1 | Out-Null
    
    # Configurar variáveis de ambiente
    foreach ($envVar in $envVars) {
        $key, $value = $envVar.Split('=', 2)
        & $nssmExe set $ServiceName AppEnvironmentExtra "$key=$value" 2>&1 | Out-Null
    }
    
    # Configurações adicionais do NSSM
    & $nssmExe set $ServiceName DisplayName "SGP API v$Version" 2>&1 | Out-Null
    & $nssmExe set $ServiceName Description "API Sistema de Gestão de Produção - Versão $Version" 2>&1 | Out-Null
    & $nssmExe set $ServiceName Start SERVICE_AUTO_START 2>&1 | Out-Null
    
    # Diretórios de log
    $stdoutLog = Join-Path $SharedDir "logs\service_stdout.log"
    $stderrLog = Join-Path $SharedDir "logs\service_stderr.log"
    & $nssmExe set $ServiceName AppStdout $stdoutLog 2>&1 | Out-Null
    & $nssmExe set $ServiceName AppStderr $stderrLog 2>&1 | Out-Null
    & $nssmExe set $ServiceName AppStdoutCreationDisposition 4 2>&1 | Out-Null
    & $nssmExe set $ServiceName AppStderrCreationDisposition 4 2>&1 | Out-Null
    
    Write-Success "Serviço '$ServiceName' instalado/atualizado com sucesso"
    
    # Iniciar serviço
    Write-Info "Iniciando serviço '$ServiceName'..."
    Start-Service -Name $ServiceName
    Start-Sleep -Seconds 3
    
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq "Running") {
        Write-Success "Serviço '$ServiceName' iniciado com sucesso"
        return $true
    } else {
        Write-Error "Falha ao iniciar serviço '$ServiceName'"
        Write-Info "Verifique os logs em: $stdoutLog e $stderrLog"
        return $false
    }
}

# Deploy de nova release
function Deploy-Release {
    param([string]$SourcePath)
    
    Write-Info "Iniciando deploy da release v$Version..."
    
    # Inicializar estrutura
    Initialize-SharedDirectories
    
    # Verificar uv
    if (-not (Test-UV)) {
        return $false
    }
    
    # Criar diretório da release
    if (Test-Path $ReleaseDir) {
        Write-Warning "Release v$Version já existe. Removendo..."
        Remove-Item -Path $ReleaseDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    Write-Success "Diretório de release criado: $ReleaseDir"
    
    # Copiar arquivos
    Copy-ReleaseFiles -SourcePath $SourcePath -TargetPath $ReleaseDir
    
    # Criar venv
    $venvPath = New-ReleaseVenv -ReleasePath $ReleaseDir
    
    # Instalar dependências
    Install-Dependencies -ReleasePath $ReleaseDir -VenvPath $venvPath
    
    # Criar .env
    New-ReleaseEnvFile -ReleasePath $ReleaseDir
    
    # Atualizar link simbólico
    Update-CurrentLink -TargetPath $ReleaseDir
    
    # Instalar serviço
    $serviceInstalled = Install-Service -ReleasePath $ReleaseDir -ServiceName $ServiceName -Port $Port
    
    if ($serviceInstalled) {
        Write-Success "✅ Deploy da release v$Version concluído com sucesso!"
        Write-Info "Release ativa: $CurrentLink -> $ReleaseDir"
        Write-Info "Diretórios compartilhados: $SharedDir"
        return $true
    } else {
        Write-Error "Deploy concluído, mas falha ao iniciar serviço"
        return $false
    }
}

# Rollback para versão anterior
function Rollback-Release {
    param([string]$TargetVersion)
    
    Write-Info "Iniciando rollback para versão v$TargetVersion..."
    
    $targetReleaseDir = Join-Path $ReleasesDir "v$TargetVersion"
    
    if (-not (Test-Path $targetReleaseDir)) {
        Write-Error "Release v$TargetVersion não encontrada: $targetReleaseDir"
        return $false
    }
    
    # Atualizar link simbólico
    Update-CurrentLink -TargetPath $targetReleaseDir
    
    # Reiniciar serviço
    Write-Info "Reiniciando serviço '$ServiceName'..."
    Restart-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 3
    
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq "Running") {
        Write-Success "✅ Rollback para versão v$TargetVersion concluído com sucesso!"
        Write-Info "Release ativa: $CurrentLink -> $targetReleaseDir"
        return $true
    } else {
        Write-Error "Falha ao reiniciar serviço após rollback"
        return $false
    }
}

# Listar releases disponíveis
function List-Releases {
    Write-Info "Releases disponíveis:"
    
    if (-not (Test-Path $ReleasesDir)) {
        Write-Warning "Diretório de releases não existe: $ReleasesDir"
        return
    }
    
    $releases = Get-ChildItem -Path $ReleasesDir -Directory | Where-Object { $_.Name -like "v*" } | Sort-Object Name -Descending
    
    if ($releases.Count -eq 0) {
        Write-Warning "Nenhuma release encontrada"
        return
    }
    
    # Determinar release ativa
    $currentRelease = $null
    if (Test-Path $CurrentLink) {
        try {
            $currentTarget = (Get-Item $CurrentLink).Target
            $currentRelease = Split-Path -Leaf $currentTarget
        } catch {
            # Link pode estar quebrado
        }
    }
    
    foreach ($release in $releases) {
        $version = $release.Name
        $isActive = ($version -eq $currentRelease)
        $status = if ($isActive) { "[ATIVA]" } else { "[      ]" }
        $color = if ($isActive) { "Green" } else { "Gray" }
        
        Write-Host "$status $version" -ForegroundColor $color
    }
    
    if ($currentRelease) {
        Write-Info "Release ativa: $currentRelease"
    } else {
        Write-Warning "Nenhuma release ativa (link 'current' não encontrado ou quebrado)"
    }
}

# Mostrar status atual
function Show-Status {
    Write-Info "Status do sistema de releases:"
    Write-Host ""
    
    Write-Host "📁 API Root: $ApiRoot" -ForegroundColor Cyan
    Write-Host "📁 Releases: $ReleasesDir" -ForegroundColor Cyan
    Write-Host "📁 Shared: $SharedDir" -ForegroundColor Cyan
    Write-Host ""
    
    # Listar releases
    List-Releases
    
    Write-Host ""
    
    # Status do serviço
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        $statusColor = if ($service.Status -eq "Running") { "Green" } else { "Red" }
        Write-Host "🔧 Serviço '$ServiceName': " -NoNewline
        Write-Host $service.Status -ForegroundColor $statusColor
    } else {
        Write-Warning "Serviço '$ServiceName' não encontrado"
    }
}

# Main
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API SGP - Deploy de Releases" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

switch ($Action) {
    "deploy" {
        $sourcePath = (Get-Location).Path
        if (-not (Test-Path (Join-Path $sourcePath "main.py"))) {
            Write-Error "Arquivo main.py não encontrado no diretório atual: $sourcePath"
            Write-Info "Execute o script a partir do diretório raiz da API"
            exit 1
        }
        Deploy-Release -SourcePath $sourcePath
    }
    
    "rollback" {
        if ([string]::IsNullOrEmpty($RollbackVersion)) {
            Write-Error "Parâmetro -RollbackVersion é obrigatório para rollback"
            exit 1
        }
        Rollback-Release -TargetVersion $RollbackVersion
    }
    
    "list" {
        List-Releases
    }
    
    "status" {
        Show-Status
    }
    
    default {
        Write-Error "Ação inválida: $Action"
        Write-Info "Ações válidas: deploy, rollback, list, status"
        exit 1
    }
}

