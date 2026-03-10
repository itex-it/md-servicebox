$file = "version.json"

# Check if git is available and get current hash
try {
    $hash = git rev-parse --short HEAD
    if ($LASTEXITCODE -ne 0) { $hash = "unknown" }
} catch {
    $hash = "unknown"
}

# Increment version
$content = Get-Content $file | ConvertFrom-Json
$v = $content.version.Replace('v', '')
$parts = $v.Split('.')
if ($parts.Length -eq 3) {
    $parts[2] = [int]$parts[2] + 1
    $newV = "v" + ($parts -join '.')
} else {
    $newV = "v1.0.0"
}

$content.version = $newV
$content.commit = $hash
$content.date = (Get-Date).ToString("yyyy-MM-dd")

$json = $content | ConvertTo-Json -Depth 5
$json | Set-Content $file -Encoding UTF8

Write-Host "Bumped version to $newV (hash: $hash) in $file" -ForegroundColor Green

# Optional Auto-Commit for the version bump
$response = Read-Host "Do you want to commit this version bump? [y/N]"
if ($response -eq 'y') {
    git add $file
    git commit -m "chore: bump version to $newV"
    git push
}
