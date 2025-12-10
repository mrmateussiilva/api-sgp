<#
.SYNOPSIS
  Atualiza o SGP automaticamente no Windows sem depender de Python.

.DESCRIPTION
  1. Consulta um manifesto JSON com as releases disponíveis.
  2. Compara a versão instalada (guardada em C:\ProgramData\SGP\version.json).
  3. Se houver versão mais nova, baixa o MSI e chama o msiexec em modo silencioso.

.PARAMETER ManifestUrl
  URL do manifesto JSON. Aceita também a variável de ambiente SGP_UPDATE_MANIFEST.

.PARAMETER Platform
  Chave da plataforma dentro do manifesto (ex.: windows-x86_64).

.PARAMETER VersionFile
  Caminho do arquivo que armazena a versão local. Default: C:\ProgramData\SGP\version.json.

.PARAMETER DownloadDir
  Pasta temporária para armazenar o MSI baixado (default: %TEMP%\sgp_updater).

.PARAMETER MsiArgs
  Argumentos adicionais passados para o msiexec (default: /qn).

.PARAMETER Force
  Força a reinstalação mesmo se a versão local for igual.
#>
param(
    [Parameter()][string]$ManifestUrl = $env:SGP_UPDATE_MANIFEST ?? "https://sgp.finderbit.com.br/update/releases/latest.json",
    [Parameter()][string]$Platform = $env:SGP_UPDATE_PLATFORM ?? "windows-x86_64",
    [Parameter()][string]$VersionFile = (Join-Path -Path ${env:ProgramData} -ChildPath "SGP\version.json"),
    [Parameter()][string]$DownloadDir = (Join-Path -Path $env:TEMP -ChildPath "sgp_updater"),
    [Parameter()][string]$MsiArgs = "/qn",
    [Parameter()][switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $timestamp = (Get-Date).ToString("u")
    Write-Host "[updater][$timestamp] $Message"
}

function Get-LocalVersion {
+    param([string]$Path)
    if (!(Test-Path -Path $Path)) {
        return $null
    }
    try {
        $content = Get-Content -Path $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        return $content.version
    }
    catch {
        throw "Arquivo de versão inválido: $Path"
    }
}

function Save-LocalVersion {
    param([string]$Path, [string]$Version)
    $dir = Split-Path -Path $Path -Parent
    if (!(Test-Path -Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    @{ version = $Version } | ConvertTo-Json | Set-Content -Path $Path -Encoding UTF8
}

function Normalize-Version {
    param([string]$Version)
    return $Version.Replace("-", ".").Split(".") | ForEach-Object {
        if ($_ -eq "") { return 0 }
        if ($_ -match "^\d+$") { return [int]$_ }
        return [int]([char[]]$_ | Measure-Object -Sum).Sum
    }
}

function Is-NewerVersion {
    param([string]$Remote, [string]$Local)
    if ([string]::IsNullOrEmpty($Local)) { return $true }
    $remoteParts = Normalize-Version -Version $Remote
    $localParts = Normalize-Version -Version $Local
    $length = [Math]::Max($remoteParts.Count, $localParts.Count)
    for ($i = 0; $i -lt $length; $i++) {
        $r = ($i -lt $remoteParts.Count) ? $remoteParts[$i] : 0
        $l = ($i -lt $localParts.Count) ? $localParts[$i] : 0
        if ($r -gt $l) { return $true }
        if ($r -lt $l) { return $false }
    }
    return $false
}

function Download-Installer {
    param([string]$Url, [string]$DestinationDir)
    if (!(Test-Path -Path $DestinationDir)) {
        New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
    }
    $fileName = Split-Path -Path $Url -Leaf
    $target = Join-Path -Path $DestinationDir -ChildPath $fileName
    Write-Log "Baixando $Url para $target"
    Invoke-WebRequest -Uri $Url -OutFile $target -UseBasicParsing
    return $target
}

try {
    Write-Log "Lendo manifesto em $ManifestUrl"
    $manifest = Invoke-RestMethod -Uri $ManifestUrl -UseBasicParsing
    $platformInfo = $manifest.platforms.$Platform
    if (-not $platformInfo) {
        throw "Manifesto não contém plataforma '$Platform'."
    }

    $remoteVersion = $manifest.version
    if (-not $remoteVersion) {
        throw "Manifesto não define o campo 'version'."
    }

    $localVersion = Get-LocalVersion -Path $VersionFile
    Write-Log "Versão local: $($localVersion ?? 'desconhecida')"
    Write-Log "Versão remota: $remoteVersion"

    if (-not $Force -and -not (Is-NewerVersion -Remote $remoteVersion -Local $localVersion)) {
        Write-Log "Nenhuma atualização necessária."
        exit 0
    }

    $installer = Download-Installer -Url $platformInfo.url -DestinationDir $DownloadDir

    $arguments = "/i `"$installer`" $MsiArgs"
    Write-Log "Executando msiexec $arguments"
    $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "msiexec retornou código $($process.ExitCode)."
    }

    Save-LocalVersion -Path $VersionFile -Version $remoteVersion
    Write-Log "Atualização concluída com sucesso."
}
catch {
    Write-Error "[updater] Falha: $_"
    exit 1
}
