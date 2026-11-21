# Lokalny start bez Dockera (Windows). Docker: `docker compose up -d` w katalogu głównym.
#   powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1            # start
#   powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1 -Reset     # czysta baza + ponowny skan
#   powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1 -EnvOnly   # tylko utwórz .env
param([switch]$Reset, [switch]$EnvOnly)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$env:Path = "C:\Program Files\nodejs;" + $env:Path
$env:PYTHONIOENCODING = "utf-8"

# sekrety z kryptograficznego generatora (nie Get-Random)
function New-RandomBytes([int]$n) { $b = New-Object byte[] $n; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); return ,$b }
function New-Secret { -join ((New-RandomBytes 32) | ForEach-Object { '{0:x2}' -f $_ }) }

# --- .env z losowymi sekretami -------------------------------------------------------------
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    $content = Get-Content (Join-Path $root ".env.example") -Raw -Encoding utf8
    $content = $content -replace "IW_INTERNAL_TOKEN=.*", ("IW_INTERNAL_TOKEN=" + (New-Secret))
    $content = $content -replace "POSTGRES_PASSWORD=.*", ("POSTGRES_PASSWORD=" + (New-Secret))
    $content = $content -replace "S3_SECRET_KEY=.*", ("S3_SECRET_KEY=" + (New-Secret))
    [IO.File]::WriteAllText($envFile, $content, (New-Object Text.UTF8Encoding $false))
    Write-Host "Utworzono .env z losowymi sekretami"
}
if ($EnvOnly) { return }

# --- zależności --------------------------------------------------------------------------
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
foreach ($svc in "backend", "ai-engine") {
    $vp = Join-Path $root "$svc\.venv\Scripts\python.exe"
    if (-not (Test-Path $vp)) {
        & $py -m venv (Join-Path $root "$svc\.venv")
        & $vp -m pip install -q --require-hashes -r (Join-Path $root "$svc\requirements.lock")
    }
}
$bpy = Join-Path $root "backend\.venv\Scripts\python.exe"
& $bpy -m playwright install chromium | Out-Null
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) { Push-Location (Join-Path $root "frontend"); npm ci; Pop-Location }

# --- Ollama (opcjonalnie) ------------------------------------------------------------------
$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (Test-Path $ollama) {
    try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2 | Out-Null } catch { Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden }
} else { Write-Host "Ollama nie jest zainstalowana – LLM wyłączony, embeddingi w trybie zapasowym." }

# --- baza i dane demo ----------------------------------------------------------------------
$data = Join-Path $root "backend\data"
if ($Reset -and (Test-Path $data)) { Remove-Item -Recurse -Force $data -Confirm:$false }
$firstRun = -not (Test-Path (Join-Path $data "investwatch.db"))

Start-Process -FilePath (Join-Path $root "ai-engine\.venv\Scripts\python.exe") -ArgumentList "-m", "uvicorn", "iw_ai.main:app", "--port", "8100" -WorkingDirectory (Join-Path $root "ai-engine") -WindowStyle Minimized
Start-Process -FilePath $bpy -ArgumentList "-m", "uvicorn", "iw_backend.api:asgi", "--port", "8000" -WorkingDirectory (Join-Path $root "backend") -WindowStyle Minimized
for ($i = 0; $i -lt 40; $i++) { try { Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1 } }
Push-Location (Join-Path $root "backend"); & $bpy -m iw_backend.cli init; Pop-Location
Start-Process -FilePath (Join-Path $root "backend\.venv\Scripts\huey_consumer.exe") -ArgumentList "iw_backend.tasks.huey", "-w", "3", "-k", "thread" -WorkingDirectory (Join-Path $root "backend") -WindowStyle Minimized
Start-Process -FilePath "C:\Program Files\nodejs\node.exe" -ArgumentList "node_modules/vite/bin/vite.js", "--port", "5173" -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Minimized

if ($firstRun) {
    Start-Sleep 3
    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/jobs -ContentType "application/json" -Body '{"kind":"all"}' | Out-Null
    Write-Host "Zlecono pierwszy skan (WWW + social media)."
}
Write-Host "Dashboard: http://localhost:5173   API: http://127.0.0.1:8000/docs   AI: http://127.0.0.1:8100/docs"
Start-Process "http://localhost:5173"
