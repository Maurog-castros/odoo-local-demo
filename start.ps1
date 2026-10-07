#!/usr/bin/env pwsh
# Levanta el ambiente Odoo con Docker Compose
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Odoo Local Environment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$odooUrl = "http://localhost:8069"
$adminPass = "Admin123"

Write-Host "[1/3] Verificando Docker..." -ForegroundColor Yellow
$docker = docker --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker no está instalado o no está corriendo." -ForegroundColor Red
    Write-Host "Instala Docker Desktop y reinicia.`n" -ForegroundColor Red
    exit 1
}

# Verificar que el socket de Docker esté disponible
$socketExists = Test-Path "\\.\pipe\dockerDesktopLinuxEngine" -ErrorAction SilentlyContinue
if (-not $socketExists) {
    Write-Host "ERROR: Docker Desktop no está corriendo (socket no encontrado)." -ForegroundColor Red
    Write-Host "Abre Docker Desktop desde el menú Inicio y esperá a que termine de iniciar.`n" -ForegroundColor Red
    Write-Host "O ejecutá: Start-Process 'docker-desktop'" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Docker listo: $docker" -ForegroundColor Green

Write-Host "`n[2/3] Levantando containers..." -ForegroundColor Yellow
docker compose up -d --build

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al levantar los containers.`n" -ForegroundColor Red
    exit 1
}

Write-Host "`n[3/3] Esperando Odoo..." -ForegroundColor Yellow
$retries = 30
while ($retries -gt 0) {
    try {
        $response = Invoke-WebRequest -Uri "$odooUrl/healthcheck" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "  Odoo está listo!`n" -ForegroundColor Green
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
    $retries--
    Write-Host "  Esperando... ($retries)" -NoNewline -ForegroundColor Yellow
}

if ($retries -eq 0) {
    Write-Host "`n  Odoo no respondió en el tiempo esperado.`n" -ForegroundColor Red
    Write-Host "  Revisa los logs: docker compose logs odoo`n" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  AMBIENTE LISTO!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "  Frontend (Nginx):  http://localhost" -ForegroundColor White
Write-Host "  Backend (Odoo):    $odooUrl" -ForegroundColor White
Write-Host "  PostgreSQL:        localhost:5432" -ForegroundColor White
Write-Host "`n  Admin:  admin" -ForegroundColor White
Write-Host "  Pass:   $adminPass" -ForegroundColor White
Write-Host "`n  Comandos útiles:" -ForegroundColor Yellow
Write-Host "    docker compose logs -f odoo     # Ver logs" -ForegroundColor Gray
Write-Host "    docker compose down             # Detener todo" -ForegroundColor Gray
Write-Host "    docker compose restart          # Reiniciar" -ForegroundColor Gray
Write-Host "`n"
