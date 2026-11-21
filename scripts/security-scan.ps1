# Audyt łańcucha dostaw: pip-audit (PyPI / OSV) dla obu serwisów Python + npm audit dla dashboardu.
# Raporty trafiają do security/. Kod wyjścia != 0, jeśli wykryto podatności.
#   powershell -ExecutionPolicy Bypass -File scripts\security-scan.ps1
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "security"
New-Item -ItemType Directory -Force $out | Out-Null
$env:Path = "C:\Program Files\nodejs;" + $env:Path
$failed = $false

foreach ($svc in "backend", "ai-engine") {
    $py = Join-Path $root "$svc\.venv\Scripts\python.exe"
    # audyt pełnego lockfile'a (zależności bezpośrednie + pośrednie, z weryfikacją hashy)
    & $py -m pip_audit -r (Join-Path $root "$svc\requirements.lock") --require-hashes --disable-pip --format json -o (Join-Path $out "pip-audit-$svc.json")
    if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[$svc] wykryto podatności – zobacz security\pip-audit-$svc.json" }
    else { Write-Host "[$svc] pip-audit: brak znanych podatności" }
}

Push-Location (Join-Path $root "frontend")
npm audit --json | Out-File -Encoding utf8 (Join-Path $out "npm-audit.json")
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[frontend] wykryto podatności – npm audit fix" } else { Write-Host "[frontend] npm audit: 0 podatności" }
Pop-Location

if ($failed) { exit 1 }
