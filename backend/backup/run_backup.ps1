$ProjectRoot = "C:\Users\user\Documents\realtime-ai-chat"

Set-Location $ProjectRoot

& "$ProjectRoot\.venv\Scripts\python.exe" `
    "$ProjectRoot\backend\backup\snapshot.py"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Database backup failed."
    exit $LASTEXITCODE
}

Write-Host "Database backup completed successfully."