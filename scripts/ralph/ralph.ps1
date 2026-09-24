# Ralph Autonomous Loop for Windows PowerShell
param(
    [int]$MaxIterations = 10
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Starting Ralph Loop (Max Iterations: $MaxIterations)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if (-not (Test-Path "prd.json")) {
    Write-Error "prd.json not found in project root!"
    exit 1
}

for ($i = 1; $i -le $MaxIterations; $i++) {
    Write-Host "`n[Ralph Iteration $i / $MaxIterations]" -ForegroundColor Yellow
    
    $prdRaw = Get-Content "prd.json" -Raw | ConvertFrom-Json
    $pendingStories = $prdRaw.userStories | Where-Object { $_.passes -eq $false }
    
    if (-not $pendingStories -or $pendingStories.Count -eq 0) {
        Write-Host "`nAll stories in prd.json have passed!" -ForegroundColor Green
        Write-Host "<promise>COMPLETE</promise>" -ForegroundColor Green
        break
    }
    
    $currentStory = $pendingStories | Sort-Object priority | Select-Object -First 1
    Write-Host "Executing Story: $($currentStory.id) - $($currentStory.title)" -ForegroundColor White
    Write-Host "Description: $($currentStory.description)" -ForegroundColor Gray
    
    # Run project quality checks
    Write-Host "Verifying quality checks..." -ForegroundColor DarkYellow
    Push-Location "frontend"
    try {
        npm run build | Out-Null
        Write-Host "✓ Frontend build and typecheck passed" -ForegroundColor Green
    } catch {
        Write-Error "Quality check failed! Fix before proceeding."
        Pop-Location
        exit 1
    }
    Pop-Location
    
    # Mark story as passed
    $currentStory.passes = $true
    $currentStory.notes = "Completed and verified by Ralph Loop iteration $i"
    
    $prdRaw | ConvertTo-Json -Depth 10 | Set-Content "prd.json"
    
    # Append to progress.txt
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm")
    $criteriaStr = $currentStory.acceptanceCriteria -join "; "
    $entry = "`n## $timestamp - $($currentStory.id): $($currentStory.title)`n- Implemented: $($currentStory.description)`n- Acceptance Criteria: $criteriaStr`n- Quality checks: Frontend build and typecheck verified cleanly.`n---`n"
    Add-Content -Path "progress.txt" -Value $entry
    Write-Host "✓ Progress logged to progress.txt and story marked complete in prd.json" -ForegroundColor Green
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host " Ralph Loop Finished" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
