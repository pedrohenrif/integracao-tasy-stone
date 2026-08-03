# Remove os serviços Windows instalados por install-services.ps1
param(
    [string]$NssmPath = ""
)

$ErrorActionPreference = "Stop"

function Find-Nssm {
    if ($NssmPath -and (Test-Path $NssmPath)) { return (Resolve-Path $NssmPath).Path }
    $cmd = Get-Command nssm -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($c in @(
        "C:\Tools\nssm\win64\nssm.exe",
        "C:\nssm\win64\nssm.exe",
        "C:\Program Files\nssm\win64\nssm.exe"
    )) {
        if (Test-Path $c) { return $c }
    }
    throw "NSSM não encontrado."
}

$nssm = Find-Nssm
foreach ($svc in @("StonePortal", "TasyPainel", "TasyConsumer", "StoneExtracao")) {
    if (Get-Service -Name $svc -ErrorAction SilentlyContinue) {
        & $nssm stop $svc | Out-Null
        & $nssm remove $svc confirm | Out-Null
        Write-Host "Removido: $svc"
    } else {
        Write-Host "Não existe: $svc"
    }
}
