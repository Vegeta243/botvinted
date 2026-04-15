# Script de lancement officiel du Bot Vinted en production
# Usage : .\start_bot_vinted.ps1

Set-Location "$PSScriptRoot"

# Forcer UTF-8 pour Python et la console PowerShell
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  BOT VINTED -- LANCEMENT EN PRODUCTION" -ForegroundColor Cyan
Write-Host "  Dossier : $PSScriptRoot" -ForegroundColor Gray
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host ">>> PRECHECK en cours..." -ForegroundColor Yellow

python check_production.py
$exitCode = $LASTEXITCODE

Write-Host ""

if ($exitCode -ne 0) {
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "  PRECHECK KO -- BOT NON LANCE" -ForegroundColor Red
    Write-Host "  Corrigez les erreurs ci-dessus avant de relancer." -ForegroundColor Red
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host "  PRECHECK OK" -ForegroundColor Green
Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Lancement du bot Vinted..." -ForegroundColor Cyan
Write-Host "  Dashboard: http://localhost:8000" -ForegroundColor Green
Write-Host "  Appuyez sur Ctrl+C pour arreter le bot." -ForegroundColor Yellow
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

python main.py
$botExit = $LASTEXITCODE

if ($botExit -ne 0) {
    Write-Host ""
    Write-Host "  Le bot s'est arrete avec le code $botExit" -ForegroundColor Red
    exit $botExit
}