#!/usr/bin/env pwsh
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

<#
.SYNOPSIS
    Builds Azure Functions Core Tools from an existing local clone.

.DESCRIPTION
    This script builds the Azure Functions Core Tools from an existing local repository clone,
    compiles the Azure.Functions.Cli.csproj project, and outputs the build artifacts.

.PARAMETER Configuration
    Build configuration - Debug or Release (default: Release)

.PARAMETER CoreToolsDir
    Directory containing an existing Azure Functions Core Tools repository clone

.EXAMPLE
    .\build-core-tools.ps1 -Configuration Release -CoreToolsDir "path/to/core-tools"
#>

param(
    [string]$Configuration = "Release",
    [string]$CoreToolsDir = "$(Build.Repository.LocalPath)/azure-functions-core-tools",
    [string]$ZipOutputDir = "artifacts-coretools-zip"
    
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
Write-Host "Configuration: $Configuration" -ForegroundColor Yellow
Write-Host "Runtime: $Runtime" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan

# Locate the project file
$ProjectPath = Join-Path $CoreToolsDir "src\Cli\func\Azure.Functions.Cli.csproj"

if (-not (Test-Path $ProjectPath)) {
    Write-Error "Project file not found at $ProjectPath"
    exit 1
}

Write-Host "`nProject file found: $ProjectPath" -ForegroundColor Green

# Set output directory
$OutputDir = Join-Path $CoreToolsDir "artifacts\$Runtime"

# Use the provided ZipOutputDir parameter, or default to artifacts-coretools-zip
# Make it an absolute path if it's relative
if (-not [System.IO.Path]::IsPathRooted($ZipOutputDir)) {
    $ZipOutputDir = Join-Path $CoreToolsDir $ZipOutputDir
}

Write-Host "Zip Output Directory: $ZipOutputDir" -ForegroundColor Yellow

# Build the project
Write-Host "`nPublishing Azure.Functions.Cli with $Configuration configuration..." -ForegroundColor Yellow
Write-Host "Output Directory: $OutputDir" -ForegroundColor Yellow

Push-Location $CoreToolsDir

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
