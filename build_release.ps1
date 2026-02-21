$source = "c:\##-Antigravity\servicebox"
$dest = "c:\##-Antigravity\ServiceBox_1.0_Release"

Write-Host "Creating staging directory..."
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Write-Host "Copying files..."
robocopy $source $dest /MIR /XD .venv __pycache__ downloads .git .pytest_cache /XF servicebox.log servicebox_history.db servicebox.db *.db-journal build_release.ps1 /NFL /NDL /NJH /NJS

# robocopy exit codes: 1-7 are success, >7 is failure
if ($LASTEXITCODE -gt 7) {
    Write-Host "Robocopy failed with exit code $LASTEXITCODE"
    exit 1
}

Write-Host "Zipping package..."
$zipPath = "c:\##-Antigravity\ServiceBox_1.0.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$dest\*" -DestinationPath $zipPath -Force

Write-Host "Cleaning up staging directory..."
Remove-Item -Recurse -Force $dest

Write-Host "Release created at $zipPath"
