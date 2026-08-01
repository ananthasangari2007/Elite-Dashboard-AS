<#
PowerShell helper to set Neon DATABASE_URL in this session and run Flask migrations.
Usage (PowerShell):
  .\.venv\Scripts\Activate.ps1
  .\scripts\run_migrations.ps1 -Dsn "postgresql://user:pass@host:5432/db?sslmode=require"
#>

param(
  [Parameter(Mandatory=$true)]
  [string]$Dsn
)

Write-Host "Setting DATABASE_URL for this session"
$env:DATABASE_URL = $Dsn
Write-Host "DATABASE_URL set (masked):" ($Dsn.Substring(0,[Math]::Min($Dsn.Length,60)) + "...")

Write-Host "Running database migrations (flask db upgrade)"
try {
    & .\.venv\Scripts\python.exe -m flask --app run.py db upgrade
    Write-Host "Migrations completed"
} catch {
    Write-Host "Migrations failed:" $_.Exception.Message
    exit 1
}

Write-Host "Seeding admin user (optional)"
try {
    & .\.venv\Scripts\python.exe -m flask --app run.py seed-admin
    Write-Host "Admin seeded"
} catch {
    Write-Host "Seeding failed:" $_.Exception.Message
}
