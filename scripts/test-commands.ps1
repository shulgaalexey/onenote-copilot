# OneNote Copilot Test Optimization Commands
# PowerShell script for different test execution workflows

# Quick development tests (target: <10s)
function Test-Fast {
    Write-Host "Running fast development tests..." -ForegroundColor Green
    python -m pytest tests/ -m "fast" --durations=5 --tb=short
}

# Run tests without slow tests
function Test-Medium {
    Write-Host "Running medium tests (excluding slow tests)..." -ForegroundColor Yellow
    python -m pytest tests/ -m "not slow" --durations=10 --tb=short
}

# Current file tests
function Test-File {
    param($FilePath)
    Write-Host "Running tests for file: $FilePath" -ForegroundColor Blue
    python -m pytest $FilePath -v --tb=short
}

# Single test execution
function Test-Single {
    param($TestPath)
    Write-Host "Running single test: $TestPath" -ForegroundColor Cyan
    python -m pytest $TestPath -v --tb=short
}

# Pre-commit validation
function Test-PreCommit {
    Write-Host "Running pre-commit validation tests..." -ForegroundColor Magenta
    python -m pytest tests/ -m "fast and unit" --durations=5 --tb=short
}

# Full test suite with coverage
function Test-Complete {
    Write-Host "Running complete test suite with coverage..." -ForegroundColor Red
    python -m pytest tests/ --cov=src --cov-report=term-missing --durations=10
}

# Performance measurement
function Test-Performance {
    Write-Host "Running performance measurement..." -ForegroundColor DarkGreen
    python -m pytest tests/ --durations=20 --tb=no
}

# Network tests specifically
function Test-Network {
    Write-Host "Running network tests..." -ForegroundColor DarkYellow
    python -m pytest tests/ -m "network" --durations=10 --tb=short
}

# Unit tests specifically
function Test-Unit {
    Write-Host "Running unit tests..." -ForegroundColor DarkBlue
    python -m pytest tests/ -m "unit" --durations=5 --tb=short
}

# Export functions to make them available when script is sourced
Export-ModuleMember -Function Test-Fast, Test-Medium, Test-File, Test-Single, Test-PreCommit, Test-Complete, Test-Performance, Test-Network, Test-Unit

Write-Host "OneNote Copilot test optimization commands loaded!" -ForegroundColor Green
Write-Host "Available commands:" -ForegroundColor Yellow
Write-Host "  Test-Fast      - Quick development tests (<10s)" -ForegroundColor White
Write-Host "  Test-Medium    - Tests without slow ones" -ForegroundColor White
Write-Host "  Test-File      - Test specific file" -ForegroundColor White
Write-Host "  Test-Single    - Test specific test" -ForegroundColor White
Write-Host "  Test-PreCommit - Pre-commit validation" -ForegroundColor White
Write-Host "  Test-Complete  - Full test suite" -ForegroundColor White
Write-Host "  Test-Performance - Performance measurement" -ForegroundColor White
Write-Host "  Test-Network   - Network tests only" -ForegroundColor White
Write-Host "  Test-Unit      - Unit tests only" -ForegroundColor White
