#!/usr/bin/env pwsh
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

<#
.SYNOPSIS
    Builds multiple versions of Azure Functions Core Tools based on latest host tags.

.DESCRIPTION
    This script:
    1. Fetches the latest N host tags from azure-functions-host repository
    2. For each tag version:
       - Updates Packages.props with the host version
       - Runs validate-worker-versions.ps1 to sync worker versions
       - Builds the core tools with that version
    3. Outputs all build artifacts

.PARAMETER Count
    Number of latest host tags to build (default: 2)

.PARAMETER Configuration
    Build configuration - Debug or Release (default: Release)

.PARAMETER CloneDir
    Directory where the core-tools repository is located

.EXAMPLE
    .\build-multi-version-core-tools.ps1 -Count 2 -Configuration Release
#>

param(
    [int]$Count = 2,
    [string]$Configuration = "Release",
    [string]$CloneDir = ""
)

$ErrorActionPreference = "Stop"

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "Multi-Version Azure Functions Core Tools Build Script" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "Building $Count version(s) of Core Tools" -ForegroundColor Yellow
Write-Host "Configuration: $Configuration" -ForegroundColor Yellow
Write-Host "===========================================================" -ForegroundColor Cyan

# Get the script directory
$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path (Split-Path (Split-Path $ScriptDir -Parent) -Parent) -Parent

# Set default CloneDir if not provided
if ([string]::IsNullOrEmpty($CloneDir)) {
    $CloneDir = Join-Path $RepoRoot "tests\build\core-tools-source"
}

# Resolve paths
if (Test-Path $CloneDir) {
    $CloneDir = Resolve-Path $CloneDir
} else {
    Write-Error "Clone directory does not exist: $CloneDir"
    exit 1
}
$PackagesPropsPath = Join-Path $CloneDir "eng/build/Packages.props"
$UpdateVersionsScript = Join-Path $ScriptDir "update-core-tools-versions.ps1"
$GetLatestTagsScript = Join-Path $ScriptDir "get-latest-host-tags.ps1"

Write-Host "`nPaths:" -ForegroundColor Yellow
Write-Host "  Repo Root: $RepoRoot"
Write-Host "  Clone Dir: $CloneDir"
Write-Host "  Packages.props: $PackagesPropsPath"
Write-Host "  Update Versions Script: $UpdateVersionsScript"
Write-Host ""

# Verify required files exist
if (-not (Test-Path $PackagesPropsPath)) {
    Write-Error "Packages.props not found at: $PackagesPropsPath"
    exit 1
}

if (-not (Test-Path $UpdateVersionsScript)) {
    Write-Error "update-core-tools-versions.ps1 not found at: $UpdateVersionsScript"
    exit 1
}

if (-not (Test-Path $GetLatestTagsScript)) {
    Write-Error "get-latest-host-tags.ps1 not found at: $GetLatestTagsScript"
    exit 1
}

# Step 1: Get latest host tags
Write-Host "Step 1: Fetching latest $Count host tag(s)..." -ForegroundColor Cyan
$latestTags = & $GetLatestTagsScript -Count $Count

if (-not $latestTags) {
    Write-Error "Failed to fetch host tags"
    exit 1
}

Write-Host "`nFound $($latestTags.Count) tag(s) to build:" -ForegroundColor Green
$latestTags | ForEach-Object {
    Write-Host "  - $($_.Tag) -> $($_.VersionNoPrefix)" -ForegroundColor White
}

# Backup original Packages.props
$BackupPath = "$PackagesPropsPath.backup"
Copy-Item $PackagesPropsPath $BackupPath -Force
Write-Host "`nBacked up Packages.props to: $BackupPath" -ForegroundColor Gray

# Array to store build results
$buildResults = @()

try {
    # Step 2: Build each version
    $versionIndex = 1
    foreach ($tagInfo in $latestTags) {
        $hostVersion = $tagInfo.VersionNoPrefix
        
        Write-Host "`n===========================================================" -ForegroundColor Cyan
        Write-Host "Building Version $versionIndex of $($latestTags.Count): $hostVersion" -ForegroundColor Cyan
        Write-Host "===========================================================" -ForegroundColor Cyan
            
        # Step 2a: Update host and worker versions in Packages.props
        Write-Host "`nStep 2.$versionIndex.a: Updating host and worker versions to $hostVersion" -ForegroundColor Yellow
        
        try {
            & $UpdateVersionsScript -HostVersion $hostVersion -PackagesPropsPath $PackagesPropsPath
            
            if ($LASTEXITCODE -ne 0) {
                throw "update-core-tools-versions.ps1 failed with exit code $LASTEXITCODE"
            }
            
            Write-Host "  ✓ Host and worker versions updated successfully" -ForegroundColor Green
        }
        catch {
            throw "Failed to update versions: $_"
        }
        
        # Step 2b: Build core tools
        Write-Host "`nStep 2.$versionIndex.b: Building Core Tools for version $hostVersion..." -ForegroundColor Yellow
        
        $buildScript = Join-Path $ScriptDir "build-core-tools.ps1"
        $buildOutput = & $buildScript -Configuration $Configuration -CoreToolsDir $CloneDir -ZipOutputDir "$hostVersion-artifacts-coretools-zip"
        
        if ($LASTEXITCODE -ne 0) {
            throw "Core Tools build failed with exit code $LASTEXITCODE"
        }
        
        # Store result
        $buildResults += [PSCustomObject]@{
            HostVersion = $hostVersion
            Tag = $tagInfo.Tag
            BuildOutput = $buildOutput
            Success = $true
        }
        
        Write-Host "`n  ✓ Successfully built Core Tools for version $hostVersion" -ForegroundColor Green
        Write-Host "  Build Output: $buildOutput" -ForegroundColor White
        
        $versionIndex++
    }
    
    # Summary
    Write-Host "`n===========================================================" -ForegroundColor Cyan
    Write-Host "Build Summary" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "Successfully built $($buildResults.Count) version(s):" -ForegroundColor Green
    
    $buildResults | ForEach-Object {
        Write-Host "  ✓ $($_.Tag) ($($_.HostVersion))" -ForegroundColor Green
        Write-Host "    Output: $($_.BuildOutput)" -ForegroundColor White
    }
    
    Write-Host "`n===========================================================" -ForegroundColor Cyan
    
    # Return build results
    return $buildResults
    
} catch {
    Write-Error "Build failed: $_"
    exit 1
} finally {
    # Restore original Packages.props
    if (Test-Path $BackupPath) {
        Write-Host "`nRestoring original Packages.props..." -ForegroundColor Gray
        Copy-Item $BackupPath $PackagesPropsPath -Force
        Remove-Item $BackupPath -Force
        Write-Host "  ✓ Restored Packages.props" -ForegroundColor Green
    }
}
