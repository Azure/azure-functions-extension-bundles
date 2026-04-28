#!/usr/bin/env pwsh
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

<#
.SYNOPSIS
    Maps host versions to core-tools tags by inspecting Packages.props in each tag.

.DESCRIPTION
    For each requested host version, this script finds the core-tools release tag
    that ships with that exact host version. It uses git ls-remote to list tags
    and fetches Packages.props via GitHub raw content URL (works with shallow clones).

    Resolution order:
    1. origin/main already has the requested host version
    2. Exact match in a release tag (e.g., tag 4.9.0 ships host 4.1047.100)
    3. No match — caller should fall back to patching main

.PARAMETER HostVersions
    Array of host versions to resolve (e.g., @("4.1047.100", "4.1048.100"))

.PARAMETER CoreToolsDir
    Path to the core-tools git repository

.EXAMPLE
    .\resolve-core-tools-tags.ps1 -HostVersions @("4.1047.100", "4.1046.100") -CoreToolsDir "path/to/core-tools"
    Returns hashtable: @{ "4.1047.100" = @{ Ref = "4.9.0"; Type = "tag" }; "4.1046.100" = @{ Ref = "4.8.0"; Type = "tag" } }
#>

param(
    [Parameter(Mandatory=$true)]
    [string[]]$HostVersions,
    
    [Parameter(Mandatory=$true)]
    [string]$CoreToolsDir
)

$ErrorActionPreference = "Stop"

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "Resolving Core Tools Tags for Host Versions" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "Host versions to resolve: $($HostVersions -join ', ')" -ForegroundColor Yellow

$GitHubHeaders = @{ "User-Agent" = "azure-functions-extension-bundles-emulator-tests" }

# Helper: extract WebHost version from Packages.props content
function Get-HostVersionFromProps {
    param([string]$Content)
    if ($Content -match 'Include="Microsoft\.Azure\.WebJobs\.Script\.WebHost"\s+Version="([^"]+)"') {
        return $matches[1]
    }
    return $null
}

# Build set of versions we still need to resolve
$unresolved = @{}
foreach ($hv in $HostVersions) {
    $unresolved[$hv] = $true
}

# Result hashtable: hostVersion -> @{ Ref = "tag/ref"; Type = "tag"|"main"|"fallback" }
$result = @{}

Push-Location $CoreToolsDir
try {
    # Step 1: Check main branch via GitHub raw URL (works with shallow clones)
    Write-Host "`nChecking main branch..." -ForegroundColor Yellow
    $mainPropsUrl = "https://raw.githubusercontent.com/Azure/azure-functions-core-tools/refs/heads/main/eng/build/Packages.props"
    try {
        $mainPropsResponse = Invoke-WebRequest -Uri $mainPropsUrl -Headers $GitHubHeaders -ErrorAction Stop -TimeoutSec 10
        $mainHostVersion = Get-HostVersionFromProps -Content $mainPropsResponse.Content
        Write-Host "  main has host version: $mainHostVersion" -ForegroundColor Gray
        
        if ($mainHostVersion -and $unresolved.ContainsKey($mainHostVersion)) {
            $result[$mainHostVersion] = @{ Ref = "main"; Type = "main"; DisplayRef = "main (host $mainHostVersion)" }
            $unresolved.Remove($mainHostVersion)
            Write-Host "  ✓ Matched main for host $mainHostVersion" -ForegroundColor Green
        }
    } catch {
        Write-Host "  ⚠ Could not check main branch: $_" -ForegroundColor Yellow
    }

    if ($unresolved.Count -eq 0) {
        Write-Host "`nAll host versions resolved!" -ForegroundColor Green
        return $result
    }

    # Step 2: List core-tools tags via git ls-remote (same pattern as get-latest-host-tags.ps1)
    Write-Host "`nScanning core-tools tags via GitHub..." -ForegroundColor Yellow
    $coreToolsRepoUrl = "https://github.com/Azure/azure-functions-core-tools.git"
    $remoteTags = git ls-remote --tags $coreToolsRepoUrl 2>&1 |
        Where-Object { $_ -match 'refs/tags/(\d+\.\d+\.\d+)(\^\{\})?$' } |
        ForEach-Object {
            if ($_ -match 'refs/tags/(\d+\.\d+\.\d+)(\^\{\})?$') { $matches[1] }
        } | Select-Object -Unique |
        Where-Object { $_.StartsWith("4.") } |
        Sort-Object { [version]$_ } -Descending

    if (-not $remoteTags) {
        Write-Warning "No core-tools tags found via git ls-remote"
    } else {
        Write-Host "  Found $($remoteTags.Count) core-tools tag(s), scanning newest first..." -ForegroundColor Gray
        
        foreach ($tag in $remoteTags) {
            if ($unresolved.Count -eq 0) { break }
            
            # Fetch Packages.props from GitHub raw content (no local checkout needed)
            $rawUrl = "https://raw.githubusercontent.com/Azure/azure-functions-core-tools/refs/tags/$tag/eng/build/Packages.props"
            try {
                $response = Invoke-WebRequest -Uri $rawUrl -Headers $GitHubHeaders -ErrorAction Stop -TimeoutSec 10
                $tagHostVersion = Get-HostVersionFromProps -Content $response.Content
            } catch {
                Write-Host "  Skipping tag $tag (fetch failed)" -ForegroundColor Gray
                continue
            }
            
            if (-not $tagHostVersion) { continue }
            
            if ($unresolved.ContainsKey($tagHostVersion)) {
                $result[$tagHostVersion] = @{ Ref = $tag; Type = "tag"; DisplayRef = "tag $tag (host $tagHostVersion)" }
                $unresolved.Remove($tagHostVersion)
                Write-Host "  ✓ Tag $tag -> host $tagHostVersion" -ForegroundColor Green
            }
        }
    }

    # Step 3: Anything still unresolved will use main + patching
    foreach ($hv in @($unresolved.Keys)) {
        $result[$hv] = @{ Ref = "main"; Type = "fallback"; DisplayRef = "main + patching (host $hv)" }
        Write-Host "  ⚠ No exact match for host $hv — will use main + patching" -ForegroundColor Yellow
    }

    # Summary
    Write-Host "`n--- Resolution Summary ---" -ForegroundColor Cyan
    foreach ($hv in $HostVersions) {
        $info = $result[$hv]
        $icon = if ($info.Type -eq "fallback") { "⚠" } else { "✓" }
        Write-Host "  $icon Host $hv -> $($info.DisplayRef)" -ForegroundColor $(if ($info.Type -eq "fallback") { "Yellow" } else { "Green" })
    }

    return $result

} finally {
    Pop-Location
}
