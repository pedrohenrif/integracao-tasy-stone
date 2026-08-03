# Instala os 4 processos da integração Stone/Tasy como serviços Windows (NSSM).
# Uso (PowerShell Admin na VM):
#   cd C:\GHR_Tech\integracao-tasy-stone
#   .\deploy\windows\install-services.ps1
#
# Pré-requisitos: NSSM no PATH (ou em C:\Tools\nssm\win64), Poetry, npm build do portal.

param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$NssmPath = ""
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw @"
Este script PRECISA rodar em PowerShell 'Executar como administrador'.

1) Feche este terminal
2) Menu Iniciar → PowerShell → botão direito → Executar como administrador
3) cd C:\GHR_Tech\integracao-tasy-stone
4) .\deploy\windows\install-services.ps1 -NssmPath "C:\Tools\nssm\nssm-2.24\win64\nssm.exe"

Nao use o terminal do VS Code a menos que o proprio VS Code tenha sido aberto como Admin.
"@
}

function Find-Nssm {
    if ($NssmPath -and (Test-Path $NssmPath)) { return (Resolve-Path $NssmPath).Path }
    $cmd = Get-Command nssm -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($c in @(
        "C:\Tools\nssm\win64\nssm.exe",
        "C:\Tools\nssm\nssm-2.24\win64\nssm.exe",
        "C:\nssm\win64\nssm.exe",
        "C:\Program Files\nssm\win64\nssm.exe"
    )) {
        if (Test-Path $c) { return $c }
    }
    $nested = Get-ChildItem "C:\Tools\nssm\nssm-*\win64\nssm.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($nested) { return $nested.FullName }
    throw "NSSM não encontrado. Baixe https://nssm.cc/download , extraia em C:\Tools\nssm e rode de novo (ou passe -NssmPath)."
}

function Get-PoetryPython([string]$ProjectDir) {
    Push-Location $ProjectDir
    try {
        $py = (poetry env info -p 2>$null)
        if (-not $py) { throw "Poetry env não encontrado em $ProjectDir. Rode: poetry install" }
        $exe = Join-Path $py.Trim() "Scripts\python.exe"
        if (-not (Test-Path $exe)) { throw "python.exe não encontrado: $exe" }
        return $exe
    } finally {
        Pop-Location
    }
}

function Install-NssmService {
    param(
        [string]$Name,
        [string]$DisplayName,
        [string]$Application,
        [string]$AppDirectory,
        [string]$AppParameters,
        [string]$Stdout,
        [string]$Stderr
    )

    $logDir = Split-Path $Stdout -Parent
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    $existing = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($existing) {
        & $nssm stop $Name | Out-Null
        & $nssm remove $Name confirm | Out-Null
        Start-Sleep -Seconds 1
    }

    & $nssm install $Name $Application $AppParameters
    if ($LASTEXITCODE -ne 0) { throw "nssm install falhou para $Name (exit $LASTEXITCODE)" }

    foreach ($args in @(
        @("set", $Name, "AppDirectory", $AppDirectory),
        @("set", $Name, "DisplayName", $DisplayName),
        @("set", $Name, "Start", "SERVICE_AUTO_START"),
        @("set", $Name, "AppStdout", $Stdout),
        @("set", $Name, "AppStderr", $Stderr),
        @("set", $Name, "AppRotateFiles", "1"),
        @("set", $Name, "AppRotateBytes", "10485760"),
        @("set", $Name, "AppExit", "Default", "Restart"),
        @("set", $Name, "AppRestartDelay", "5000")
    )) {
        & $nssm @args
        if ($LASTEXITCODE -ne 0) { throw "nssm $($args -join ' ') falhou (exit $LASTEXITCODE)" }
    }
    Write-Host "OK: serviço $Name instalado"
}

$nssm = Find-Nssm
Write-Host "NSSM: $nssm"
Write-Host "Repo: $RepoRoot"

$extracaoDir = Join-Path $RepoRoot "stone-extracao"
$insercaoDir = Join-Path $RepoRoot "tasy-insercao"
$portalDir   = Join-Path $RepoRoot "portal-controle"
$logsDir     = Join-Path $RepoRoot "deploy\windows\logs"
$distDir     = Join-Path $portalDir "dist"

if (-not (Test-Path (Join-Path $extracaoDir ".env"))) { throw "Falta $extracaoDir\.env" }
if (-not (Test-Path (Join-Path $insercaoDir ".env"))) { throw "Falta $insercaoDir\.env" }
if (-not (Test-Path $distDir)) {
    throw "Falta portal-controle\dist. Rode: cd portal-controle; npm run build"
}

$pyExtracao = Get-PoetryPython $extracaoDir
$pyInsercao = Get-PoetryPython $insercaoDir
Write-Host "Python extracao: $pyExtracao"
Write-Host "Python insercao: $pyInsercao"

# 1) stone-extracao (API :8000) — SEM --reload
Install-NssmService `
    -Name "StoneExtracao" `
    -DisplayName "Stone Extracao API (8000)" `
    -Application $pyExtracao `
    -AppDirectory $extracaoDir `
    -AppParameters "-m uvicorn stone_extracao.interfaces.api.main:app --host 0.0.0.0 --port 8000" `
    -Stdout (Join-Path $logsDir "stone-extracao.out.log") `
    -Stderr (Join-Path $logsDir "stone-extracao.err.log")

# 2) tasy-insercao consumer
Install-NssmService `
    -Name "TasyConsumer" `
    -DisplayName "Tasy Insercao Consumer" `
    -Application $pyInsercao `
    -AppDirectory $insercaoDir `
    -AppParameters "-m tasy_insercao" `
    -Stdout (Join-Path $logsDir "tasy-consumer.out.log") `
    -Stderr (Join-Path $logsDir "tasy-consumer.err.log")

# 3) portal API (:8001)
Install-NssmService `
    -Name "TasyPainel" `
    -DisplayName "Tasy Portal API (8001)" `
    -Application $pyInsercao `
    -AppDirectory $insercaoDir `
    -AppParameters "-m tasy_insercao.painel" `
    -Stdout (Join-Path $logsDir "tasy-painel.out.log") `
    -Stderr (Join-Path $logsDir "tasy-painel.err.log")

# 4) portal front (vite preview :5173 + proxy /api → 8001)
$npmCmdObj = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmdObj) { $npmCmdObj = Get-Command npm -ErrorAction Stop }
$npmCmd = $npmCmdObj.Source

Install-NssmService `
    -Name "StonePortal" `
    -DisplayName "Stone Portal Front (5173)" `
    -Application $npmCmd `
    -AppDirectory $portalDir `
    -AppParameters "run preview -- --host 0.0.0.0 --port 5173" `
    -Stdout (Join-Path $logsDir "stone-portal.out.log") `
    -Stderr (Join-Path $logsDir "stone-portal.err.log")

Write-Host ""
Write-Host "Iniciando serviços..."
foreach ($svc in @("StoneExtracao", "TasyConsumer", "TasyPainel", "StonePortal")) {
    Start-Service $svc
    Write-Host ("  {0}: {1}" -f $svc, (Get-Service $svc).Status)
}

Write-Host ""
Write-Host "Pronto. Logs em: $logsDir"
Write-Host "Health: http://127.0.0.1:8000/health  |  http://127.0.0.1:8001/health"
Write-Host "Portal: http://127.0.0.1:5173"
