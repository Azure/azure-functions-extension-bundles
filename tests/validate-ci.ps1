# Azure Functions Extension Bundle - CI Validation Script (PowerShell)
# This script helps validate the emulator test setup locally before pushing changes

$ErrorActionPreference = "Stop"

Write-Host "🔍 Validating Azure Functions Extension Bundle CI Setup" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Check if we're in the right directory (now from tests folder)
if (-not (Test-Path "..\src\Microsoft.Azure.Functions.ExtensionBundle\bundleConfig.json")) {
    Write-Host "❌ Error: Please run this script from the tests directory" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Tests directory confirmed" -ForegroundColor Green

# Check required files exist
$requiredFiles = @(
    "test_setup.py",
    "utils\testutils.py",
    "emulator_tests\utils\eventhub\docker-compose.yml",
    "..\eng\ci\templates\jobs\emulator-tests.yml"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✅ $file exists" -ForegroundColor Green
    } else {
        Write-Host "❌ Missing: $file" -ForegroundColor Red
        exit 1
    }
}

# Check Docker is available
try {
    $dockerVersion = docker --version 2>$null
    Write-Host "✅ Docker is available: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker not found - required for emulator tests" -ForegroundColor Red
    exit 1
}

# Check Docker Compose is available
try {
    $composeVersion = docker-compose --version 2>$null
    Write-Host "✅ Docker Compose is available: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose not found - required for emulator services" -ForegroundColor Red
    exit 1
}

# Check Python is available
try {
    $pythonVersion = python --version 2>$null
    Write-Host "✅ Python is available: $pythonVersion" -ForegroundColor Green
    if ($pythonVersion -notmatch "3\.12") {
        Write-Host "⚠️  Warning: Python 3.12 recommended - CI will use Python 3.12" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Warning: Python not found - CI will install Python 3.12" -ForegroundColor Yellow
}

# Check .NET SDK
try {
    $dotnetVersion = dotnet --version 2>$null
    Write-Host "✅ .NET SDK available: $dotnetVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ .NET SDK not found - required for building extension bundles" -ForegroundColor Red
    exit 1
}

# Validate bundleConfig.json
Write-Host "🔍 Validating bundleConfig.json..." -ForegroundColor Cyan
try {
    $bundleConfig = Get-Content "..\src\Microsoft.Azure.Functions.ExtensionBundle\bundleConfig.json" | ConvertFrom-Json
    Write-Host "Bundle ID: $($bundleConfig.bundleId)" -ForegroundColor White
    Write-Host "Bundle Version: $($bundleConfig.bundleVersion)" -ForegroundColor White
    Write-Host "Is Preview: $($bundleConfig.isPreviewBundle)" -ForegroundColor White
    
    $requiredKeys = @("bundleId", "bundleVersion")
    $missingKeys = $requiredKeys | Where-Object { -not $bundleConfig.PSObject.Properties.Name.Contains($_) }
    
    if ($missingKeys.Count -gt 0) {
        Write-Host "❌ Missing keys in bundleConfig.json: $($missingKeys -join ', ')" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "✅ bundleConfig.json is valid" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ bundleConfig.json validation failed: $_" -ForegroundColor Red
    exit 1
}

# Check CI template exists and basic syntax
Write-Host "🔍 Validating CI template..." -ForegroundColor Cyan
if (Test-Path "..\eng\ci\templates\jobs\emulator-tests.yml") {
    $templateContent = Get-Content "..\eng\ci\templates\jobs\emulator-tests.yml" -Raw
    if ($templateContent -match "jobs:" -and $templateContent -match "EmulatorTests") {
        Write-Host "✅ CI template appears valid" -ForegroundColor Green
    } else {
        Write-Host "❌ CI template structure seems incorrect" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "❌ CI template not found" -ForegroundColor Red
    exit 1
}

# Optional: Test Docker Compose configuration
Write-Host "🔍 Testing emulator services configuration..." -ForegroundColor Cyan
try {
    Push-Location "emulator_tests\utils\eventhub"
    docker-compose config 2>$null | Out-Null
    Write-Host "✅ Docker Compose configuration is valid" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Warning: Docker Compose configuration validation failed" -ForegroundColor Yellow
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "🎉 All validations passed!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Build locally: 'cd ..\build && dotnet run'" -ForegroundColor White
Write-Host "2. Test emulator setup: 'python test_setup.py'" -ForegroundColor White
Write-Host "3. Run emulator tests with mock site:" -ForegroundColor White
Write-Host "   invoke mock-extension-site --port 8000 --keep-alive &" -ForegroundColor Gray
Write-Host "   `$env:FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI='http://localhost:8000'" -ForegroundColor Gray
Write-Host "   pytest emulator_tests/" -ForegroundColor Gray
Write-Host ""
Write-Host "The CI pipeline will run emulator tests automatically on:" -ForegroundColor Cyan
Write-Host "- All pull requests" -ForegroundColor White
Write-Host "- Main branch builds" -ForegroundColor White
Write-Host "- Preview branch builds" -ForegroundColor White
Write-Host ""
Write-Host "Key CI environment variables:" -ForegroundColor Cyan
Write-Host "- FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI=http://localhost:8000" -ForegroundColor White
Write-Host "- PYAZURE_WEBHOST_DEBUG=1" -ForegroundColor White
Write-Host ""
