#!/usr/bin/env pwsh
# Quick Authentication Fix Script for OneNote Copilot
# Resolves "OAuth2 error: server_error" issues after user logout

Write-Host "🔧 OneNote Copilot Authentication Fix" -ForegroundColor Blue
Write-Host "Resolving 'server_error' authentication issues..." -ForegroundColor Gray
Write-Host ""

# Step 1: Clear authentication cache
Write-Host "1. Clearing authentication cache..." -ForegroundColor Yellow
$cacheLocations = @(
    "$env:USERPROFILE\.onenote_copilot",
    ".\.onenote_copilot"
)

$clearedFiles = 0
foreach ($location in $cacheLocations) {
    if (Test-Path $location) {
        try {
            Remove-Item $location -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "   ✅ Cleared: $location" -ForegroundColor Green
            $clearedFiles++
        } catch {
            Write-Host "   ⚠️  Could not clear: $location" -ForegroundColor Yellow
        }
    }
}

if ($clearedFiles -eq 0) {
    Write-Host "   ℹ️  No cache files found to clear" -ForegroundColor Cyan
} else {
    Write-Host "   ✅ Cleared $clearedFiles authentication cache locations" -ForegroundColor Green
}

# Step 2: Check port availability
Write-Host ""
Write-Host "2. Checking port 8080 availability..." -ForegroundColor Yellow
$portCheck = netstat -an | findstr ":8080"
if ($portCheck) {
    Write-Host "   ⚠️  Port 8080 is in use by another process:" -ForegroundColor Yellow
    Write-Host "   $portCheck" -ForegroundColor Gray
    Write-Host "   Consider closing other applications using this port" -ForegroundColor Gray
} else {
    Write-Host "   ✅ Port 8080 is available" -ForegroundColor Green
}

# Step 3: Provide browser guidance
Write-Host ""
Write-Host "3. Browser cleanup recommendations:" -ForegroundColor Yellow
Write-Host "   📋 Clear browser data for Microsoft authentication:" -ForegroundColor Cyan
Write-Host "      • Chrome/Edge: Settings → Privacy → Clear browsing data" -ForegroundColor Gray
Write-Host "      • Firefox: Settings → Privacy → Clear Data" -ForegroundColor Gray
Write-Host "      • Focus on: *.microsoftonline.com and *.live.com" -ForegroundColor Gray
Write-Host ""
Write-Host "   🔒 Try incognito/private browsing mode for next login" -ForegroundColor Cyan
Write-Host "   🔄 Restart browser completely after clearing data" -ForegroundColor Cyan

# Step 4: Next steps
Write-Host ""
Write-Host "4. Ready to retry authentication:" -ForegroundColor Yellow
Write-Host "   Run: python -m src.main --auth-only" -ForegroundColor Green
Write-Host "   Or:  onenote-copilot --auth-only" -ForegroundColor Green
Write-Host ""
Write-Host "   If still having issues:" -ForegroundColor Cyan
Write-Host "   - Wait 5-10 minutes for Microsoft session cleanup" -ForegroundColor Gray
Write-Host "   - Use: onenote-copilot fix-auth --force-clear" -ForegroundColor Gray
Write-Host "   - Try different browser or incognito mode" -ForegroundColor Gray

Write-Host ""
Write-Host "✅ Authentication fix completed!" -ForegroundColor Green
Write-Host "The 'server_error' issue should now be resolved." -ForegroundColor Gray
