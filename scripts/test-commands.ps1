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

# Phase 2: Advanced test execution commands
function Test-Auth {
    Write-Host "Running authentication tests..." -ForegroundColor DarkMagenta
    python -m pytest tests/ -m "auth" --durations=5 --tb=short
}

function Test-Search {
    Write-Host "Running search functionality tests..." -ForegroundColor DarkCyan
    python -m pytest tests/ -m "search" --durations=5 --tb=short
}

function Test-Embedding {
    Write-Host "Running embedding tests..." -ForegroundColor DarkRed
    python -m pytest tests/ -m "embedding" --durations=5 --tb=short
}

function Test-VectorStore {
    Write-Host "Running vector store tests..." -ForegroundColor DarkYellow
    python -m pytest tests/ -m "vector_store" --durations=5 --tb=short
}

function Test-Agent {
    Write-Host "Running AI agent tests..." -ForegroundColor DarkGreen
    python -m pytest tests/ -m "agent" --durations=5 --tb=short
}

function Test-MockHeavy {
    Write-Host "Running tests with heavy dependency mocking..." -ForegroundColor Gray
    python -m pytest tests/ -m "mock_heavy" --durations=5 --tb=short
}

function Test-SessionScoped {
    Write-Host "Running tests with session-scoped fixtures..." -ForegroundColor Magenta
    python -m pytest tests/ -m "session_scoped" --durations=5 --tb=short
}

function Test-ModuleScoped {
    Write-Host "Running tests with module-scoped fixtures..." -ForegroundColor Cyan
    python -m pytest tests/ -m "module_scoped" --durations=5 --tb=short
}

function Test-Performance-Monitor {
    Write-Host "Running tests with performance monitoring..." -ForegroundColor Yellow
    python -m pytest tests/ -m "performance" --durations=10 --tb=short
}

function Test-Memory-Monitor {
    Write-Host "Running tests with memory monitoring..." -ForegroundColor Blue
    python -m pytest tests/ -m "memory" --durations=10 --tb=short
}

# Coverage optimization
function Test-Coverage-Fast {
    Write-Host "Running fast tests with optimized coverage..." -ForegroundColor Green
    $env:COVERAGE_CORE = "sysmon"
    python -m pytest tests/ -m "fast" --cov=src --cov-report=term-missing --durations=5
}

# Advanced workflow commands
function Test-Development {
    Write-Host "Running development workflow tests..." -ForegroundColor White
    python -m pytest tests/ -m "fast and unit and not network" --durations=5 --tb=short
}

function Test-CI-Fast {
    Write-Host "Running fast CI tests..." -ForegroundColor DarkBlue
    python -m pytest tests/ -m "not slow and not performance and not memory" --durations=10 --tb=short
}

function Test-Benchmark {
    Write-Host "Running benchmark tests..." -ForegroundColor Red
    python -m pytest tests/ -m "performance or memory" --durations=0 --tb=short
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
Export-ModuleMember -Function Test-Fast, Test-Medium, Test-File, Test-Single, Test-PreCommit, Test-Complete, Test-Performance, Test-Network, Test-Unit, Test-Auth, Test-Search, Test-Embedding, Test-VectorStore, Test-Agent, Test-MockHeavy, Test-SessionScoped, Test-ModuleScoped, Test-Performance-Monitor, Test-Memory-Monitor, Test-Coverage-Fast, Test-Development, Test-CI-Fast, Test-Benchmark

Write-Host "OneNote Copilot test optimization commands loaded! (Phase 2)" -ForegroundColor Green
Write-Host "Phase 1 Commands:" -ForegroundColor Yellow
Write-Host "  Test-Fast      - Quick development tests (<10s)" -ForegroundColor White
Write-Host "  Test-Medium    - Tests without slow ones" -ForegroundColor White
Write-Host "  Test-File      - Test specific file" -ForegroundColor White
Write-Host "  Test-Single    - Test specific test" -ForegroundColor White
Write-Host "  Test-PreCommit - Pre-commit validation" -ForegroundColor White
Write-Host "  Test-Complete  - Full test suite" -ForegroundColor White
Write-Host "  Test-Performance - Performance measurement" -ForegroundColor White
Write-Host "  Test-Network   - Network tests only" -ForegroundColor White
Write-Host "  Test-Unit      - Unit tests only" -ForegroundColor White
Write-Host ""
Write-Host "Phase 2 Commands:" -ForegroundColor Cyan
Write-Host "  Test-Auth      - Authentication tests" -ForegroundColor White
Write-Host "  Test-Search    - Search functionality tests" -ForegroundColor White
Write-Host "  Test-Embedding - Embedding generation tests" -ForegroundColor White
Write-Host "  Test-VectorStore - Vector storage tests" -ForegroundColor White
Write-Host "  Test-Agent     - AI agent tests" -ForegroundColor White
Write-Host "  Test-MockHeavy - Tests with heavy mocking" -ForegroundColor White
Write-Host "  Test-SessionScoped - Session-scoped fixture tests" -ForegroundColor White
Write-Host "  Test-ModuleScoped - Module-scoped fixture tests" -ForegroundColor White
Write-Host "  Test-Performance-Monitor - Performance monitored tests" -ForegroundColor White
Write-Host "  Test-Memory-Monitor - Memory monitored tests" -ForegroundColor White
Write-Host "  Test-Coverage-Fast - Fast tests with optimized coverage" -ForegroundColor White
Write-Host "  Test-Development - Development workflow tests" -ForegroundColor White
Write-Host "  Test-CI-Fast   - Fast CI tests" -ForegroundColor White
Write-Host "  Test-Benchmark - Benchmark tests" -ForegroundColor White
