#!/usr/bin/env pwsh
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

<#
.SYNOPSIS
    Builds multiple versions of Azure Functions Core Tools based on latest host tags.

.DESCRIPTION
    This script:
    1. Fetches the latest N host tags from azure-functions-host repository
    2. Resolves each host version to a core-tools tag or origin/main
    3. For each version:
       - Checks out the matching core-tools tag or origin/main (no patching needed)
       - Applies minimal build compatibility fixes (rollForward, UpdateBuildNumber)
       - Builds the core tools
    4. Outputs all build artifacts

    Resolution order per host version:
    - Exact core-tools tag match → checkout tag (cleanest, no patching)
    - origin/main already has this host version → checkout main (no patching)
    - No match → checkout main + run update-core-tools-versions.ps1 (fallback)

.PARAMETER Count
    Number of latest host tags to build (default: 2)

.PARAMETER Pattern
    Version pattern to match host tags (default: v4.10)
    Example: "v4.10" matches v4.1046.100, v4.1047.200
    Update when moving to new major/minor versions (e.g., v4.11, v5.0)

.PARAMETER Configuration
    Build configuration - Debug or Release (default: Release)

.PARAMETER CloneDir
    Directory where the core-tools repository is located (must have full git history + tags)

.EXAMPLE
    .\build-multi-version-core-tools.ps1 -Count 2 -Pattern "v4.10" -Configuration Release
#>

param(
    [int]$Count = 2,
    [string]$Pattern = "v4.10",
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

$GetLatestTagsScript = Join-Path $ScriptDir "get-latest-host-tags.ps1"
$ResolveTagsScript = Join-Path $ScriptDir "resolve-core-tools-tags.ps1"
$UpdateVersionsScript = Join-Path $ScriptDir "update-core-tools-versions.ps1"
$BuildScript = Join-Path $ScriptDir "build-core-tools.ps1"
$CoreToolsGitHubUrl = "https://github.com/Azure/azure-functions-core-tools.git"
$PackagesPropsPath = Join-Path $CloneDir "eng/build/Packages.props"
$FinalZipDir = Join-Path $CloneDir "artifacts-coretools-zip"

Write-Host "`nPaths:" -ForegroundColor Yellow
Write-Host "  Repo Root: $RepoRoot"
Write-Host "  Clone Dir: $CloneDir"
Write-Host "  Artifacts Output: $FinalZipDir"
Write-Host ""

# Verify required scripts exist
foreach ($script in @($GetLatestTagsScript, $ResolveTagsScript, $UpdateVersionsScript, $BuildScript)) {
    if (-not (Test-Path $script)) {
        Write-Error "Required script not found: $script"
        exit 1
    }
}

# Create artifacts output directory
if (-not (Test-Path $FinalZipDir)) {
    New-Item -ItemType Directory -Path $FinalZipDir -Force | Out-Null
}

# Applies minimal build compatibility fixes after checkout.
# These are universal fixes needed regardless of checkout source (tag, main, or fallback).
function Apply-PostCheckoutFixes {
    param(
        [string]$RepoDir,
        [string]$HostVersion
    )
    
    Write-Host "  Applying post-checkout compatibility fixes..." -ForegroundColor Gray
    
    # Fix 1: Sync global.json SDK version from the host repo, then adjust to installed SDKs
    # The host's global.json is the source of truth for SDK expectations.
    $globalJsonPath = Join-Path $RepoDir "global.json"
    if (Test-Path $globalJsonPath) {
        $globalJson = Get-Content $globalJsonPath -Raw | ConvertFrom-Json
        $oldSdkVersion = $globalJson.sdk.version
        $oldRollForward = $globalJson.sdk.rollForward
        
        # Step 1a: Fetch SDK version from the host repo's global.json
        $hostGlobalJsonUri = "https://raw.githubusercontent.com/Azure/azure-functions-host/refs/tags/v$HostVersion/global.json"
        try {
            $hostGlobalJsonContent = (Invoke-WebRequest -Uri $hostGlobalJsonUri -Headers @{"User-Agent" = "azure-functions-extension-bundles"} -ErrorAction Stop).Content
            $hostGlobalJson = $hostGlobalJsonContent | ConvertFrom-Json
            $hostSdkVersion = $hostGlobalJson.sdk.version
            
            if ($oldSdkVersion -ne $hostSdkVersion) {
                $globalJson.sdk.version = $hostSdkVersion
                Write-Host "    ✓ Synced SDK version from host: $oldSdkVersion -> $hostSdkVersion" -ForegroundColor Green
            } else {
                Write-Host "    SDK version already matches host: $oldSdkVersion" -ForegroundColor Gray
            }
        } catch {
            Write-Host "    ⚠ Could not fetch host global.json, keeping core-tools version: $oldSdkVersion" -ForegroundColor Yellow
        }
        
        # Step 1b: Set rollForward to latestFeature (stay within major, allow patch flexibility)
        $globalJson.sdk.rollForward = "latestFeature"
        
        # Step 1c: Adjust SDK version to closest installed match if exact version isn't available
        $requestedVersion = $globalJson.sdk.version
        $installedSdks = (dotnet --list-sdks 2>$null) | ForEach-Object { ($_ -split '\s')[0] }
        
        if ($installedSdks -and $requestedVersion) {
            $reqParts = $requestedVersion -split '\.'
            $reqMajorMinor = "$($reqParts[0]).$($reqParts[1])"
            
            # Find installed SDKs in the same major.minor
            $matchingSdks = $installedSdks | Where-Object { $_.StartsWith("$reqMajorMinor.") } | Sort-Object { [version]$_ } -Descending
            
            if ($matchingSdks -and ($matchingSdks -notcontains $requestedVersion)) {
                $bestMatch = $matchingSdks | Select-Object -First 1
                $globalJson.sdk.version = $bestMatch
                Write-Host "    ✓ Adjusted SDK to installed: $requestedVersion -> $bestMatch" -ForegroundColor Green
            }
        }
        
        $globalJson | ConvertTo-Json -Depth 10 | Set-Content $globalJsonPath
        if ($oldRollForward -ne "latestFeature") {
            Write-Host "    ✓ Set rollForward to latestFeature (was: $oldRollForward)" -ForegroundColor Green
        }
    }
    
    # Fix 2: Disable UpdateBuildNumber to prevent build from updating Azure DevOps build number
    $versionPropsPath = Join-Path $RepoDir "src/Cli/func/Directory.Version.props"
    if (Test-Path $versionPropsPath) {
        [xml]$versionPropsXml = Get-Content $versionPropsPath
        $node = Select-Xml -Xml $versionPropsXml -XPath "//UpdateBuildNumber" | Select-Object -ExpandProperty Node
        if ($node -and $node.'#text' -ne 'false') {
            $node.'#text' = 'false'
            $versionPropsXml.Save($versionPropsPath)
            Write-Host "    ✓ Set UpdateBuildNumber to false" -ForegroundColor Green
        }
    }
}

# Step 1: Get latest host tags
Write-Host "Step 1: Fetching latest $Count host tag(s) matching pattern $Pattern..." -ForegroundColor Cyan
$latestTags = & $GetLatestTagsScript -Count $Count -Pattern $Pattern

if (-not $latestTags) {
    Write-Error "Failed to fetch host tags"
    exit 1
}

Write-Host "`nFound $($latestTags.Count) tag(s) to build:" -ForegroundColor Green
$latestTags | ForEach-Object {
    Write-Host "  - $($_.Tag) -> $($_.VersionNoPrefix)" -ForegroundColor White
}

# Step 2: Resolve host versions to core-tools refs
Write-Host "`nStep 2: Resolving core-tools refs for each host version..." -ForegroundColor Cyan
$hostVersions = $latestTags | ForEach-Object { $_.VersionNoPrefix }
$refMap = & $ResolveTagsScript -HostVersions $hostVersions -CoreToolsDir $CloneDir

if (-not $refMap) {
    Write-Error "Failed to resolve core-tools tags"
    exit 1
}

# Array to store build results
$buildResults = @()

try {
    # Step 3: Build each version
    $versionIndex = 1
    foreach ($tagInfo in $latestTags) {
        $hostVersion = $tagInfo.VersionNoPrefix
        $refInfo = $refMap[$hostVersion]
        
        Write-Host "`n===========================================================" -ForegroundColor Cyan
        Write-Host "Building Version $versionIndex of $($latestTags.Count): $hostVersion" -ForegroundColor Cyan
        Write-Host "  Resolution: $($refInfo.DisplayRef)" -ForegroundColor White
        Write-Host "===========================================================" -ForegroundColor Cyan
        
        # Step 3a: Reset repo to clean state
        Write-Host "`nStep 3.$versionIndex.a: Resetting repo to clean state..." -ForegroundColor Yellow
        Push-Location $CloneDir
        try {
            $null = git reset --hard 2>&1
            # Clean untracked files but preserve the final artifacts directory
            $null = git clean -fdx -e "artifacts-coretools-zip" 2>&1
            Write-Host "  ✓ Repo reset to clean state" -ForegroundColor Green
        } finally {
            Pop-Location
        }
        
        # Step 3b: Checkout the resolved ref
        Write-Host "`nStep 3.$versionIndex.b: Checking out $($refInfo.DisplayRef)..." -ForegroundColor Yellow
        Push-Location $CloneDir
        try {
            if ($refInfo.Type -eq "tag") {
                # Shallow clone may not have the tag's commit — fetch from GitHub
                Write-Host "  Fetching tag $($refInfo.Ref) from GitHub..." -ForegroundColor Gray
                $fetchOutput = git fetch $CoreToolsGitHubUrl tag $refInfo.Ref --no-tags --depth=1 2>&1
                if ($LASTEXITCODE -ne 0) { throw "git fetch tag failed: $fetchOutput" }
                $checkoutOutput = git checkout $refInfo.Ref 2>&1
                if ($LASTEXITCODE -ne 0) { throw "git checkout failed: $checkoutOutput" }
            } else {
                # main or fallback — fetch latest main from GitHub
                Write-Host "  Fetching main from GitHub..." -ForegroundColor Gray
                $fetchOutput = git fetch $CoreToolsGitHubUrl main --depth=1 2>&1
                if ($LASTEXITCODE -ne 0) { throw "git fetch main failed: $fetchOutput" }
                $checkoutOutput = git checkout FETCH_HEAD 2>&1
                if ($LASTEXITCODE -ne 0) { throw "git checkout FETCH_HEAD failed: $checkoutOutput" }
            }
            Write-Host "  ✓ Checked out $($refInfo.DisplayRef)" -ForegroundColor Green
        } finally {
            Pop-Location
        }
        
        # Step 3c: Apply version patching if this is a fallback (no exact match)
        if ($refInfo.Type -eq "fallback") {
            Write-Host "`nStep 3.$versionIndex.c: Applying version patching (fallback)..." -ForegroundColor Yellow
            try {
                & $UpdateVersionsScript -HostVersion $hostVersion -PackagesPropsPath $PackagesPropsPath
                if ($LASTEXITCODE -ne 0) {
                    throw "update-core-tools-versions.ps1 failed with exit code $LASTEXITCODE"
                }
                Write-Host "  ✓ Version patching applied" -ForegroundColor Green
            } catch {
                throw "Failed to apply version patching: $_"
            }
        } else {
            Write-Host "`nStep 3.$versionIndex.c: No patching needed ($($refInfo.Type) match)" -ForegroundColor Green
        }
        
        # Step 3d: Apply minimal post-checkout fixes (all paths)
        Apply-PostCheckoutFixes -RepoDir $CloneDir -HostVersion $hostVersion
        
        # Step 3e: Build core tools
        Write-Host "`nStep 3.$versionIndex.e: Building Core Tools for version $hostVersion..." -ForegroundColor Yellow
        
        # Use a temp zip dir inside the repo (will be cleaned by git clean next iteration)
        $versionZipDir = "artifacts-coretools-zip-$hostVersion"
        $buildOutput = & $BuildScript -Configuration $Configuration -CoreToolsDir $CloneDir -ZipOutputDir $versionZipDir
        
        if ($LASTEXITCODE -ne 0) {
            throw "Core Tools build failed with exit code $LASTEXITCODE"
        }
        
        # Step 3f: Move artifacts to output directory (outside repo tree)
        Write-Host "`nStep 3.$versionIndex.f: Moving artifacts..." -ForegroundColor Yellow
        
        $tempZipDir = Join-Path $CloneDir $versionZipDir
        if (Test-Path $tempZipDir) {
            $zipFile = Get-ChildItem -Path $tempZipDir -Filter "*.zip" | Select-Object -First 1
            if ($zipFile) {
                $newName = "$versionIndex-cli-host-$hostVersion.zip"
                $destPath = Join-Path $FinalZipDir $newName
                Copy-Item -Path $zipFile.FullName -Destination $destPath -Force
                Write-Host "  ✓ $($zipFile.Name) -> $newName" -ForegroundColor Green
            } else {
                Write-Warning "  No zip files found in $tempZipDir"
            }
        }
        
        # Step 3g: Clean up to save disk space
        Write-Host "`nStep 3.$versionIndex.g: Cleaning up..." -ForegroundColor Yellow
        
        $artifactsDir = Join-Path $CloneDir "artifacts"
        if (Test-Path $artifactsDir) {
            Remove-Item -Path $artifactsDir -Recurse -Force
        }
        
        # Clean obj/bin
        $srcDir = Join-Path $CloneDir "src"
        if (Test-Path $srcDir) {
            Get-ChildItem -Path $srcDir -Include "obj","bin" -Recurse -Directory -Force | ForEach-Object {
                Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            }
        }

        # Clear NuGet cache between builds to reclaim disk space
        Write-Host "  Clearing NuGet cache..." -ForegroundColor Gray
        & dotnet nuget locals all --clear 2>$null
        Write-Host "  ✓ Cleanup complete" -ForegroundColor Green
        
        # Store result
        $buildResults += [PSCustomObject]@{
            HostVersion = $hostVersion
            Tag = $tagInfo.Tag
            CoreToolsRef = $refInfo.DisplayRef
            RefType = $refInfo.Type
            Success = $true
        }
        
        Write-Host "`n  ✓ Successfully built Core Tools for version $hostVersion" -ForegroundColor Green
        
        $versionIndex++
    }
    
    # Summary
    Write-Host "`n===========================================================" -ForegroundColor Cyan
    Write-Host "Build Summary" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "Successfully built $($buildResults.Count) version(s):" -ForegroundColor Green
    
    $buildResults | ForEach-Object {
        $icon = if ($_.RefType -eq "fallback") { "⚠" } else { "✓" }
        Write-Host "  $icon $($_.Tag) ($($_.HostVersion)) via $($_.CoreToolsRef)" -ForegroundColor $(if ($_.RefType -eq "fallback") { "Yellow" } else { "Green" })
    }
    
    # Verify artifacts
    Write-Host "`nVerifying artifacts in: $FinalZipDir" -ForegroundColor Cyan
    if (Test-Path $FinalZipDir) {
        $zipFiles = Get-ChildItem -Path $FinalZipDir -Filter "*.zip"
        Write-Host "Found $($zipFiles.Count) zip file(s):" -ForegroundColor Green
        $zipFiles | ForEach-Object {
            $sizeKB = [math]::Round($_.Length / 1KB, 2)
            Write-Host "  - $($_.Name) (${sizeKB} KB)" -ForegroundColor White
        }
    } else {
        Write-Host "##[error]Artifacts directory not found: $FinalZipDir" -ForegroundColor Red
    }
    
    Write-Host "`n===========================================================" -ForegroundColor Cyan
    
    return $buildResults
    
} catch {
    Write-Error "Build failed: $_"
    exit 1
}
