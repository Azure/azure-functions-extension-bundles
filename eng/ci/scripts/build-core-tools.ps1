#!/usr/bin/env pwsh
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

<#
.SYNOPSIS
    Clones and builds Azure Functions Core Tools from source.

.DESCRIPTION
    This script clones the Azure Functions Core Tools repository from GitHub,
    builds the Azure.Functions.Cli.csproj project, and outputs the build location.

.PARAMETER Branch
    Git branch to clone (default: main)

.PARAMETER Configuration
    Build configuration - Debug or Release (default: Release)

.PARAMETER CloneDir
    Directory where the repository will be cloned (default: tests/build/core-tools-source)

.EXAMPLE
    .\build-core-tools.ps1 -Branch main -Configuration Release -Runtime win-x64
#>

param(
    [string]$Branch = "main",
    [string]$Configuration = "Release",
    [string]$CloneDir = "$(Build.Repository.LocalPath)/azure-functions-core-tools"
)

$ErrorActionPreference = "Stop"


if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $osName = "win"
} elseif ($IsMacOS) {
    $osName = "osx"
} elseif ($IsLinux) {
    $osName = "linux"
} else {
    Write-Error "Unsupported platform"
    exit 1
}

# Determine architecture
$arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }

$Runtime = "$osName-$arch"
Write-Host "Auto-detected runtime: $Runtime" -ForegroundColor Yellow

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Azure Functions Core Tools Build Script" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Branch: $Branch" -ForegroundColor Yellow
Write-Host "Configuration: $Configuration" -ForegroundColor Yellow
Write-Host "Runtime: $Runtime" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan

# Locate the project file
$ProjectPath = Join-Path $CloneDir "src\Cli\func\Azure.Functions.Cli.csproj"

if (-not (Test-Path $ProjectPath)) {
    Write-Error "Project file not found at $ProjectPath"
    exit 1
}

Write-Host "`nProject file found: $ProjectPath" -ForegroundColor Green

# Set output directory
$OutputDir = Join-Path $CloneDir "artifacts\$Runtime"
$ZipOutputDir = Join-Path $CloneDir "artifacts-coretools-zip"

# Build the project
Write-Host "`nPublishing Azure.Functions.Cli with $Configuration configuration..." -ForegroundColor Yellow
Write-Host "Output Directory: $OutputDir" -ForegroundColor Yellow

Push-Location $CloneDir

try {
    $publishArgs = @(
        "publish",
        $ProjectPath,
        "-o", $OutputDir,
        "-c", $Configuration,
        "-f", "net8.0",
        "--self-contained",
        "/p:ZipAfterPublish=true",
        "/p:ZipArtifactsPath=$ZipOutputDir"
    )
    
    if (-not [string]::IsNullOrEmpty($Runtime)) {
        $publishArgs += "-r", $Runtime
    }
    
    Write-Host "Running: dotnet $($publishArgs -join ' ')" -ForegroundColor Cyan
    
    & dotnet $publishArgs
    
    if ($LASTEXITCODE -ne 0) {
        throw "Publish failed with exit code $LASTEXITCODE"
    }
    
    Write-Host "✓ Publish completed successfully" -ForegroundColor Green
    
} catch {
    Pop-Location
    Write-Error "Publish failed: $_"
    exit 1
} finally {
    Pop-Location
}

# Find the build output directory
$BuildOutput = $OutputDir

if (Test-Path $BuildOutput) {
    Write-Host "`n==================================================" -ForegroundColor Cyan
    Write-Host "Build Output: $BuildOutput" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Cyan
    
    # Output the path for the calling script to capture
    Write-Output $BuildOutput
} else {
    Write-Error "Build output not found at $BuildOutput"
    exit 1
}
