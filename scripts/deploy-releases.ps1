<#
.SYNOPSIS
    Deploy automatizado da API SGP com releases versionadas para ambiente de intranet.

.DESCRIPTION
    Fluxo suportado:
    - Receber uma release pronta em ZIP ou usar o diretório atual como fonte
    - Extrair/copiar para releases/vX.Y.Z
    - Criar venv isolado
    - Instalar dependências com uv
    - Criar .env da release apontando para shared/
    - Fazer backup do banco antes do update
    - Rodar migrations
    - Atualizar o link current
    - Reiniciar o serviço via NSSM
    - Validar healthcheck
    - Fazer rollback automático se necessário

.EXAMPLE
    .\scripts\deploy-releases.ps1 -Action deploy -Version 1.0.20 -ReleaseZip C:\deploy\api-sgp-1.0.20.zip

.EXAMPLE
    .\scripts\deploy-releases.ps1 -Action rollback -RollbackVersion 1.0.19
#>
param(
    [Parameter()][ValidateSet("deploy", "rollback", "list", "status")]
    [string]$Action = "deploy",
    [Parameter()][string]$Version = "",
    [Parameter()][string]$ReleaseZip = "",
    [Parameter()][string]$SourcePath = "",
    [Parameter()][string]$ApiRoot = "C:\api",
    [Parameter()][string]$ServiceName = "SGP-API",
    [Parameter()][int]$Port = 8000,
    [Parameter()][string]$PythonPath = "python",
    [Parameter()][string]$RollbackVersion = "",
    [Parameter()][string]$HealthUrl = "",
    [Parameter()][switch]$SkipBackup,
    [Parameter()][switch]$SkipMigrations,
    [Parameter()][switch]$SkipHealthcheck,
    [Parameter()][switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-ErrorMessage { Write-Host "[ERROR] $args" -ForegroundColor Red }
function Write-Step { Write-Host "`n=== $args ===" -ForegroundColor Magenta }

$ReleasesDir = Join-Path $ApiRoot "releases"
$SharedDir = Join-Path $ApiRoot "shared"
$CurrentLink = Join-Path $ReleasesDir "current"
$HealthCheckUrl = if ([string]::IsNullOrWhiteSpace($HealthUrl)) { "http://127.0.0.1:$Port/health" } else { $HealthUrl }

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-Administrator {
    if (-not (Test-Administrator)) {
        throw "Execute o script como Administrador."
    }
}

function Initialize-SharedDirectories {
    Write-Step "Inicializando estrutura compartilhada"

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
            Write-Success "Diretório criado: $fullPath"
        }
    }

    if (-not (Test-Path $ReleasesDir)) {
        New-Item -ItemType Directory -Path $ReleasesDir -Force | Out-Null
        Write-Success "Diretório de releases criado: $ReleasesDir"
    }
}

function Test-Python {
    try {
        $pythonVersion = & $PythonPath --version 2>&1
        Write-Success "Python encontrado: $pythonVersion"
    } catch {
        throw "Python não encontrado em '$PythonPath'."
    }
}

function Test-NSSM {
    try {
        $command = Get-Command nssm.exe -ErrorAction Stop
        return $command.Source
    } catch {
        throw "NSSM não encontrado no PATH."
    }
}

function Get-VersionFromPyProject {
    param([string]$ProjectRoot)

    $pyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
    if (-not (Test-Path $pyprojectPath)) {
        return ""
    }

    $match = Select-String -Path $pyprojectPath -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($match) {
        return $match.Matches[0].Groups[1].Value
    }

    return ""
}

function Resolve-DeployVersion {
    if (-not [string]::IsNullOrWhiteSpace($Version)) {
        return $Version.Trim()
    }

    if (-not [string]::IsNullOrWhiteSpace($SourcePath)) {
        $projectVersion = Get-VersionFromPyProject -ProjectRoot $SourcePath
        if ($projectVersion) {
            return $projectVersion
        }
    }

    throw "Informe -Version explicitamente ou forneça uma fonte contendo pyproject.toml."
}

function Get-ReleaseDir {
    param([string]$ResolvedVersion)
    return (Join-Path $ReleasesDir "v$ResolvedVersion")
}

function Get-CurrentReleasePath {
    if (-not (Test-Path $CurrentLink)) {
        return $null
    }

    try {
        $item = Get-Item -Path $CurrentLink -Force
        return $item.Target
    } catch {
        return $null
    }
}

function Get-CurrentReleaseVersion {
    $currentPath = Get-CurrentReleasePath
    if (-not $currentPath) {
        return $null
    }

    return (Split-Path -Leaf $currentPath).TrimStart("v")
}

function Backup-Database {
    if ($SkipBackup) {
        Write-Warning "Backup ignorado por parâmetro."
        return $null
    }

    Write-Step "Criando backup do banco"

    $dbPath = Join-Path $SharedDir "db\banco.db"
    if (-not (Test-Path $dbPath)) {
        Write-Warning "Banco não encontrado em $dbPath. Seguindo sem backup."
        return $null
    }

    $backupDir = Join-Path $SharedDir "backups"
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = Join-Path $backupDir "banco-pre-deploy-$timestamp.db"
    Copy-Item -Path $dbPath -Destination $backupPath -Force
    Write-Success "Backup criado: $backupPath"
    return $backupPath
}

function Stop-ApiService {
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Warning "Serviço $ServiceName não encontrado."
        return
    }

    if ($service.Status -eq "Stopped") {
        Write-Info "Serviço $ServiceName já está parado."
        return
    }

    Write-Step "Parando serviço"
    Stop-Service -Name $ServiceName -Force
    $service.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
    Write-Success "Serviço parado."
}

function Start-ApiService {
    Write-Step "Iniciando serviço"
    Start-Service -Name $ServiceName
    $service = Get-Service -Name $ServiceName -ErrorAction Stop
    $service.WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
    Write-Success "Serviço iniciado."
}

function Expand-ReleaseArchive {
    param(
        [string]$ZipPath,
        [string]$TargetPath
    )

    Write-Step "Extraindo release ZIP"
    if (-not (Test-Path $ZipPath)) {
        throw "Release ZIP não encontrada: $ZipPath"
    }

    if (Test-Path $TargetPath) {
        Remove-Item -Path $TargetPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null

    Expand-Archive -Path $ZipPath -DestinationPath $TargetPath -Force

    $entries = @(Get-ChildItem -Path $TargetPath -Force)
    if ($entries.Count -eq 1 -and $entries[0].PSIsContainer) {
        $nested = $entries[0].FullName
        Get-ChildItem -Path $nested -Force | ForEach-Object {
            Move-Item -Path $_.FullName -Destination $TargetPath -Force
        }
        Remove-Item -Path $nested -Recurse -Force
    }

    Write-Success "Release extraída em $TargetPath"
}

function Copy-ReleaseFiles {
    param(
        [string]$ProjectRoot,
        [string]$TargetPath
    )

    Write-Step "Copiando arquivos do projeto"

    if (-not (Test-Path (Join-Path $ProjectRoot "main.py"))) {
        throw "main.py não encontrado em $ProjectRoot"
    }

    if (Test-Path $TargetPath) {
        Remove-Item -Path $TargetPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null

    $excludeDirs = @("db", "media", "logs", "backups", "venv", "__pycache__", ".git", "releases", "shared", ".venv", "dist")
    $excludeFiles = @("*.pyc", "*.pyo", "*.db", "*.db-shm", "*.db-wal", ".env")

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

        $destination = Join-Path $TargetPath $relativePath
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

    Write-Success "Arquivos copiados para $TargetPath"
}

function New-ReleaseVenv {
    param([string]$ReleasePath)

    Write-Step "Criando venv da release"
    & $PythonPath -m venv (Join-Path $ReleasePath "venv")
    Write-Success "venv criada em $(Join-Path $ReleasePath 'venv')"
}

function Install-ReleaseDependencies {
    param([string]$ReleasePath)

    Write-Step "Instalando dependências"
    $pythonPath = Join-Path $ReleasePath "venv\Scripts\python.exe"

    Push-Location $ReleasePath
    try {
        & $pythonPath -m pip install --upgrade pip
        if (Test-Path (Join-Path $ReleasePath "requirements.txt")) {
            & $pythonPath -m pip install -r requirements.txt
        } elseif (Test-Path (Join-Path $ReleasePath "pyproject.toml")) {
            & $pythonPath -m pip install .
        } else {
            throw "Nenhum arquivo de dependências encontrado na release."
        }
    } finally {
        Pop-Location
    }

    Write-Success "Dependências instaladas."
}

function Set-EnvValue {
    param(
        [string]$FilePath,
        [string]$Key,
        [string]$Value
    )

    $escapedKey = [regex]::Escape($Key)
    $line = "$Key=$Value"

    if (-not (Test-Path $FilePath)) {
        Set-Content -Path $FilePath -Value $line -Encoding UTF8
        return
    }

    $content = Get-Content -Path $FilePath -Raw -Encoding UTF8
    if ($content -match "(?m)^$escapedKey=") {
        $updated = [regex]::Replace($content, "(?m)^$escapedKey=.*$", $line)
    } else {
        $separator = if ($content.EndsWith("`n") -or [string]::IsNullOrEmpty($content)) { "" } else { "`r`n" }
        $updated = "$content$separator$line`r`n"
    }
    Set-Content -Path $FilePath -Value $updated -Encoding UTF8
}

function Initialize-ReleaseEnv {
    param(
        [string]$ReleasePath,
        [string]$ResolvedVersion
    )

    Write-Step "Preparando .env da release"

    $releaseEnvPath = Join-Path $ReleasePath ".env"
    $sharedEnvPath = Join-Path $SharedDir ".env"

    if (Test-Path $sharedEnvPath) {
        Copy-Item -Path $sharedEnvPath -Destination $releaseEnvPath -Force
        Write-Info "Baseado em $sharedEnvPath"
    } elseif (-not (Test-Path $releaseEnvPath)) {
        New-Item -ItemType File -Path $releaseEnvPath -Force | Out-Null
    }

    $databaseUrl = "sqlite:///$((Join-Path $SharedDir 'db\banco.db').Replace('\', '/'))"
    $mediaRoot = (Join-Path $SharedDir "media")
    $logDir = (Join-Path $SharedDir "logs")

    Set-EnvValue -FilePath $releaseEnvPath -Key "API_ROOT" -Value $ApiRoot
    Set-EnvValue -FilePath $releaseEnvPath -Key "DATABASE_URL" -Value $databaseUrl
    Set-EnvValue -FilePath $releaseEnvPath -Key "MEDIA_ROOT" -Value $mediaRoot
    Set-EnvValue -FilePath $releaseEnvPath -Key "LOG_DIR" -Value $logDir
    Set-EnvValue -FilePath $releaseEnvPath -Key "ENVIRONMENT" -Value "production"
    Set-EnvValue -FilePath $releaseEnvPath -Key "VERSION" -Value $ResolvedVersion
    Set-EnvValue -FilePath $releaseEnvPath -Key "PORT" -Value $Port

    Write-Success ".env pronto em $releaseEnvPath"
}

function Invoke-ReleaseMigrations {
    param([string]$ReleasePath)

    if ($SkipMigrations) {
        Write-Warning "Migrations ignoradas por parâmetro."
        return
    }

    Write-Step "Executando migrations"
    $pythonPath = Join-Path $ReleasePath "venv\Scripts\python.exe"
    Push-Location $ReleasePath
    try {
        & $pythonPath database\run_migrations.py
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao executar migrations."
        }
    } finally {
        Pop-Location
    }

    Write-Success "Migrations concluídas."
}

function Update-CurrentLink {
    param([string]$TargetPath)

    Write-Step "Atualizando link current"

    if (Test-Path $CurrentLink) {
        Remove-Item -Path $CurrentLink -Recurse -Force
    }

    New-Item -ItemType SymbolicLink -Path $CurrentLink -Target $TargetPath | Out-Null
    Write-Success "current -> $TargetPath"
}

function Install-OrUpdateService {
    Assert-Administrator
    $nssmExe = Test-NSSM

    Write-Step "Configurando serviço Windows"

    $serviceExists = $null -ne (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
    $currentPython = Join-Path $CurrentLink "venv\Scripts\python.exe"
    $stdoutLog = Join-Path $SharedDir "logs\service_stdout.log"
    $stderrLog = Join-Path $SharedDir "logs\service_stderr.log"
    $envBlock = @(
        "API_ROOT=$ApiRoot",
        "PYTHONPATH=$CurrentLink",
        "PORT=$Port"
    ) -join "`n"

    if (-not $serviceExists) {
        & $nssmExe install $ServiceName $currentPython "-m uvicorn main:app --host 0.0.0.0 --port $Port" | Out-Null
    } else {
        & $nssmExe set $ServiceName Application $currentPython | Out-Null
        & $nssmExe set $ServiceName AppParameters "-m uvicorn main:app --host 0.0.0.0 --port $Port" | Out-Null
    }

    & $nssmExe set $ServiceName AppDirectory $CurrentLink | Out-Null
    & $nssmExe set $ServiceName DisplayName "SGP API" | Out-Null
    & $nssmExe set $ServiceName Description "API Sistema de Gestão de Produção" | Out-Null
    & $nssmExe set $ServiceName Start SERVICE_AUTO_START | Out-Null
    & $nssmExe set $ServiceName AppEnvironmentExtra $envBlock | Out-Null
    & $nssmExe set $ServiceName AppStdout $stdoutLog | Out-Null
    & $nssmExe set $ServiceName AppStderr $stderrLog | Out-Null
    & $nssmExe set $ServiceName AppStdoutCreationDisposition 4 | Out-Null
    & $nssmExe set $ServiceName AppStderrCreationDisposition 4 | Out-Null

    Write-Success "Serviço configurado: $ServiceName"
}

function Test-Healthcheck {
    if ($SkipHealthcheck) {
        Write-Warning "Healthcheck ignorado por parâmetro."
        return
    }

    Write-Step "Validando healthcheck"
    $lastError = $null

    for ($attempt = 1; $attempt -le 10; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $HealthCheckUrl -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                Write-Success "Healthcheck OK em $HealthCheckUrl"
                return
            }
            $lastError = "HTTP $($response.StatusCode)"
        } catch {
            $lastError = $_
        }
        Start-Sleep -Seconds 2
    }

    throw "Healthcheck falhou em $HealthCheckUrl. Último erro: $lastError"
}

function Remove-ReleaseDirectory {
    param([string]$ReleasePath)
    if ($ReleasePath -and (Test-Path $ReleasePath)) {
        Remove-Item -Path $ReleasePath -Recurse -Force
    }
}

function Invoke-AutomaticRollback {
    param(
        [string]$PreviousReleasePath,
        [string]$PreviousReleaseVersion
    )

    if (-not $PreviousReleasePath) {
        Write-Warning "Sem release anterior para rollback automático."
        return
    }

    Write-Step "Executando rollback automático"
    Update-CurrentLink -TargetPath $PreviousReleasePath
    Install-OrUpdateService
    Start-ApiService
    if (-not $SkipHealthcheck) {
        Test-Healthcheck
    }
    Write-Warning "Rollback automático concluído para v$PreviousReleaseVersion."
}

function Deploy-Release {
    Assert-Administrator
    Initialize-SharedDirectories
    Test-Python

    if ([string]::IsNullOrWhiteSpace($SourcePath) -and [string]::IsNullOrWhiteSpace($ReleaseZip)) {
        $script:SourcePath = (Get-Location).Path
    }

    $resolvedVersion = Resolve-DeployVersion
    $releaseDir = Get-ReleaseDir -ResolvedVersion $resolvedVersion
    $previousReleasePath = Get-CurrentReleasePath
    $previousReleaseVersion = Get-CurrentReleaseVersion

    if ((Test-Path $releaseDir) -and (-not $Force)) {
        throw "A release v$resolvedVersion já existe em $releaseDir. Use -Force para sobrescrever."
    }

    Stop-ApiService
    $backupPath = Backup-Database
    if ($backupPath) {
        Write-Info "Backup da execução: $backupPath"
    }

    try {
        if (-not [string]::IsNullOrWhiteSpace($ReleaseZip)) {
            Expand-ReleaseArchive -ZipPath $ReleaseZip -TargetPath $releaseDir
        } else {
            Copy-ReleaseFiles -ProjectRoot $SourcePath -TargetPath $releaseDir
        }

        New-ReleaseVenv -ReleasePath $releaseDir
        Install-ReleaseDependencies -ReleasePath $releaseDir
        Initialize-ReleaseEnv -ReleasePath $releaseDir -ResolvedVersion $resolvedVersion
        Invoke-ReleaseMigrations -ReleasePath $releaseDir
        Update-CurrentLink -TargetPath $releaseDir
        Install-OrUpdateService
        Start-ApiService
        Test-Healthcheck

        Write-Host ""
        Write-Success "Deploy concluído com sucesso."
        Write-Info "Versão ativa: v$resolvedVersion"
        Write-Info "current -> $releaseDir"
    } catch {
        Write-ErrorMessage $_
        try {
            Invoke-AutomaticRollback -PreviousReleasePath $previousReleasePath -PreviousReleaseVersion $previousReleaseVersion
        } catch {
            Write-ErrorMessage "Rollback automático falhou: $_"
        }
        throw
    }
}

function Rollback-Release {
    Assert-Administrator
    if ([string]::IsNullOrWhiteSpace($RollbackVersion)) {
        throw "Informe -RollbackVersion para rollback."
    }

    $targetReleasePath = Get-ReleaseDir -ResolvedVersion $RollbackVersion
    if (-not (Test-Path $targetReleasePath)) {
        throw "Release v$RollbackVersion não encontrada em $targetReleasePath"
    }

    Stop-ApiService
    Update-CurrentLink -TargetPath $targetReleasePath
    Install-OrUpdateService
    Start-ApiService
    Test-Healthcheck

    Write-Success "Rollback concluído para v$RollbackVersion"
}

function List-Releases {
    Write-Step "Releases disponíveis"

    if (-not (Test-Path $ReleasesDir)) {
        Write-Warning "Diretório de releases não existe."
        return
    }

    $currentRelease = Get-CurrentReleaseVersion
    $releases = Get-ChildItem -Path $ReleasesDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "v*" } |
        Sort-Object Name -Descending

    if (-not $releases) {
        Write-Warning "Nenhuma release encontrada."
        return
    }

    foreach ($release in $releases) {
        $version = $release.Name.TrimStart("v")
        if ($version -eq $currentRelease) {
            Write-Host "[ATIVA] v$version" -ForegroundColor Green
        } else {
            Write-Host "        v$version" -ForegroundColor Gray
        }
    }
}

function Show-Status {
    Write-Step "Status do ambiente"
    Write-Host "API Root: $ApiRoot"
    Write-Host "Releases: $ReleasesDir"
    Write-Host "Shared: $SharedDir"
    Write-Host "Healthcheck: $HealthCheckUrl"

    $currentRelease = Get-CurrentReleaseVersion
    if ($currentRelease) {
        Write-Host "Release ativa: v$currentRelease"
    } else {
        Write-Warning "Nenhuma release ativa."
    }

    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "Serviço $ServiceName: $($service.Status)"
    } else {
        Write-Warning "Serviço $ServiceName não encontrado."
    }

    List-Releases
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API SGP - Deploy de Releases" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

switch ($Action) {
    "deploy" { Deploy-Release }
    "rollback" { Rollback-Release }
    "list" { List-Releases }
    "status" { Show-Status }
}
