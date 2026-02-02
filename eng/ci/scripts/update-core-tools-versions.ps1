#!/usr/bin/env pwsh
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

<#
.SYNOPSIS
    Updates host and worker package versions in core-tools Packages.props

.DESCRIPTION
    This script updates the Microsoft.Azure.WebJobs.Script.WebHost version
    and fetches matching worker versions from the azure-functions-host repository
    to update in the core-tools Packages.props file.

.PARAMETER HostVersion
    The host version to update to (e.g., 4.1046.100)

.PARAMETER PackagesPropsPath
    Path to the Packages.props file to update

.EXAMPLE
    .\update-core-tools-versions.ps1 -HostVersion 4.1046.100 -PackagesPropsPath "tests/build/core-tools-source/eng/build/Packages.props"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$HostVersion,
    
    [Parameter(Mandatory=$true)]
    [string]$PackagesPropsPath
)

$ErrorActionPreference = "Stop"

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "Updating Core Tools Versions for Host $HostVersion" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# Verify the Packages.props file exists
if (-not (Test-Path $PackagesPropsPath)) {
    Write-Error "Packages.props not found at: $PackagesPropsPath"
    exit 1
}

Write-Host "Packages.props: $PackagesPropsPath" -ForegroundColor Yellow

# Get core tools root path for global.json update
$coreToolsRootForGlobal = Split-Path (Split-Path (Split-Path $PackagesPropsPath -Parent) -Parent) -Parent

# Sync global.json with host repo
$GlobalJsonPath = Join-Path $coreToolsRootForGlobal "global.json"
if (Test-Path $GlobalJsonPath) {
    Write-Host "`nSyncing global.json with host repo..." -ForegroundColor Yellow
    
    $hostGlobalJsonUri = "https://raw.githubusercontent.com/Azure/azure-functions-host/refs/tags/v$HostVersion/global.json"
    
    try {
        $hostGlobalJsonContent = (Invoke-WebRequest -Uri $hostGlobalJsonUri -Headers @{"User-Agent" = "azure-functions-extension-bundles-emulator-tests"} -ErrorAction Stop).Content
        $hostGlobalJson = $hostGlobalJsonContent | ConvertFrom-Json
        $hostSdkVersion = $hostGlobalJson.sdk.version
        
        $localGlobalJson = Get-Content $GlobalJsonPath -Raw | ConvertFrom-Json
        $localSdkVersion = $localGlobalJson.sdk.version
        
        if ($localSdkVersion -ne $hostSdkVersion) {
            # Update SDK version from host repo
            $localGlobalJson.sdk.version = $hostSdkVersion
            $localGlobalJson.sdk.rollForward = "latestMajor"
            $localGlobalJson | ConvertTo-Json -Depth 10 | Set-Content $GlobalJsonPath
            Write-Host "  ✓ Updated global.json SDK: $localSdkVersion -> $hostSdkVersion (from host repo)" -ForegroundColor Green
        } else {
            Write-Host "  global.json SDK version: $localSdkVersion (no change)" -ForegroundColor Gray
        }
    } catch {
        Write-Warning "  Could not fetch global.json from host repo: $_"
        Write-Host "  Keeping existing global.json" -ForegroundColor Gray
    }
}

# Set up GitHub API headers for compliance with GitHub API requirements
$script:GitHubHeaders = @{
    "User-Agent" = "azure-functions-extension-bundles-emulator-tests"
}

# Verify the host tag exists
$tagUri = "https://api.github.com/repos/Azure/azure-functions-host/git/refs/tags/v$HostVersion"
try {
    Write-Host "Verifying host tag v$HostVersion..." -ForegroundColor Gray
    $response = Invoke-WebRequest -Uri $tagUri -Headers $script:GitHubHeaders -ErrorAction Stop
    
    # Check if we got HTML instead of JSON (GitHub error page)
    $contentType = $response.Headers['Content-Type']
    if ($contentType -like '*text/html*') {
        Write-Warning "Received HTML response instead of JSON - tag verification failed"
        Write-Host "Response preview: $($response.Content.Substring(0, [Math]::Min(200, $response.Content.Length)))" -ForegroundColor Yellow
        throw "GitHub returned an error page for tag v$HostVersion"
    }
    
    if ($response.StatusCode -ne 200) {
        throw "Host tag v$HostVersion does not exist (HTTP $($response.StatusCode))"
    }
    
    Write-Host "✓ Verified host tag v$HostVersion exists" -ForegroundColor Green
} catch {
    $errorMsg = $_.Exception.Message
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "GitHub API returned status code: $statusCode" -ForegroundColor Yellow
    }
    Write-Error "Failed to verify host tag v$HostVersion : $errorMsg"
    exit 1
}

# Load Packages.props
[xml]$packagesXml = Get-Content $PackagesPropsPath

# Helper function to get worker version from host repo
function Get-WorkerVersionFromHost {
    param(
        [string]$WorkerPropsFile,
        [string]$PackageName
    )
    
    $uri = "https://raw.githubusercontent.com/Azure/azure-functions-host/refs/tags/v$HostVersion/$WorkerPropsFile"
    
    try {
        $content = (Invoke-WebRequest -Uri $uri -Headers $script:GitHubHeaders -ErrorAction Stop).Content
        [xml]$workerXml = $content

        # Check for PackageVersion elements (used in Directory.Packages.props)
        $node = Select-Xml -Xml $workerXml -XPath "//PackageVersion[@Include='$PackageName']" | 
                Select-Object -ExpandProperty Node
        
        if ($node -and $node.Version) {
            return $node.Version
        }
        
        # Check for PackageReference elements (used in worker props)
        $node = Select-Xml -Xml $workerXml -XPath "//PackageReference[@Include='$PackageName']" | 
                Select-Object -ExpandProperty Node
        
        if ($node) {
            # Worker props files use VersionOverride attribute
            if ($node.VersionOverride) {
                return $node.VersionOverride
            }
            if ($node.Version) {
                return $node.Version
            }
        }
        
        Write-Warning "Could not find version for $PackageName in $WorkerPropsFile"
        return $null
    } catch {
        # For Directory.Packages.props, file might not exist in older tags - this is OK
        if ($WorkerPropsFile -eq "Directory.Packages.props" -and $_.Exception.Message -match "404") {
            return $null
        }
        Write-Warning "Failed to fetch $WorkerPropsFile from host repo: $_"
        return $null
    }
}

# Update Microsoft.Azure.WebJobs.Script.WebHost version
Write-Host "`nUpdating WebHost version..." -ForegroundColor Yellow
$hostNode = Select-Xml -Xml $packagesXml -XPath "//PackageVersion[@Include='Microsoft.Azure.WebJobs.Script.WebHost']" | 
            Select-Object -ExpandProperty Node

if (-not $hostNode) {
    Write-Error "Failed to find Microsoft.Azure.WebJobs.Script.WebHost in Packages.props"
    exit 1
}

$oldHostVersion = $hostNode.Version
$hostNode.Version = $HostVersion
Write-Host "  Microsoft.Azure.WebJobs.Script.WebHost: $oldHostVersion -> $HostVersion" -ForegroundColor Green

# Define worker packages and their source files in the host repo
$workers = @{
    "Microsoft.Azure.Functions.JavaWorker" = "eng/build/Workers.Java.props"
    "Microsoft.Azure.Functions.NodeJsWorker" = "eng/build/Workers.Node.props"
    "Microsoft.Azure.Functions.PythonWorker" = "eng/build/Workers.Python.props"
    "Microsoft.Azure.Functions.PowerShellWorker.PS7.0" = "eng/build/Workers.Powershell.props"
    "Microsoft.Azure.Functions.PowerShellWorker.PS7.2" = "eng/build/Workers.Powershell.props"
    "Microsoft.Azure.Functions.PowerShellWorker.PS7.4" = "eng/build/Workers.Powershell.props"
}

# Fix until core tool can sync with new host changes
# Define additional packages to sync from host repo
$additionalPackages = @{
    "Azure.Core" = "Directory.Packages.props"
    "Azure.Storage.Blobs" = "Directory.Packages.props"
    "Azure.Identity" = "Directory.Packages.props"
    "Microsoft.Identity.Client" = "Directory.Packages.props"
    "System.Private.Uri" = "Directory.Packages.props"
    "Microsoft.ApplicationInsights" = "Directory.Packages.props"
}

# Update worker versions
Write-Host "`nUpdating worker versions from host repo..." -ForegroundColor Yellow

foreach ($packageName in $workers.Keys) {
    $workerPropsFile = $workers[$packageName]
    
    Write-Host "  Processing $packageName..." -ForegroundColor Gray
    
    # Get version from host repo
    $hostWorkerVersion = Get-WorkerVersionFromHost -WorkerPropsFile $workerPropsFile -PackageName $packageName
    
    if (-not $hostWorkerVersion) {
        Write-Warning "    Skipping $packageName - could not determine version from host"
        continue
    }
    
    # Find and update in Packages.props
    $workerNode = Select-Xml -Xml $packagesXml -XPath "//PackageVersion[@Include='$packageName']" | 
                  Select-Object -ExpandProperty Node
    
    if (-not $workerNode) {
        Write-Warning "    $packageName not found in Packages.props"
        continue
    }
    
    $oldWorkerVersion = $workerNode.Version
    
    if ($oldWorkerVersion -ne $hostWorkerVersion) {
        $workerNode.Version = $hostWorkerVersion
        Write-Host "    $packageName`: $oldWorkerVersion -> $hostWorkerVersion" -ForegroundColor Green
    } else {
        Write-Host "    $packageName`: $oldWorkerVersion (no change)" -ForegroundColor Gray
    }
}

# Update additional packages
Write-Host "`nUpdating additional packages from host repo..." -ForegroundColor Yellow

foreach ($packageName in $additionalPackages.Keys) {
    $sourceFile = $additionalPackages[$packageName]
    
    Write-Host "  Processing $packageName..." -ForegroundColor Gray
    
    # Get version from host repo
    $hostPackageVersion = Get-WorkerVersionFromHost -WorkerPropsFile $sourceFile -PackageName $packageName
    
    if (-not $hostPackageVersion) {
        Write-Warning "    Skipping $packageName - could not determine version from host"
        continue
    }
    
    # Find and update in Packages.props
    $packageNode = Select-Xml -Xml $packagesXml -XPath "//PackageVersion[@Include='$packageName']" | 
                  Select-Object -ExpandProperty Node
    
    if (-not $packageNode) {
        # Package doesn't exist, add it
        Write-Host "    Adding new package $packageName`: $hostPackageVersion" -ForegroundColor Cyan
        
        # Find the func ItemGroup (after the comment "<!-- func -->")
        $funcItemGroup = $packagesXml.Project.ItemGroup | Where-Object { 
            $_.PreviousSibling -and $_.PreviousSibling.Value -match "func"
        } | Select-Object -First 1
        
        if ($funcItemGroup) {
            # Create new PackageVersion element
            $newPackage = $packagesXml.CreateElement("PackageVersion")
            $newPackage.SetAttribute("Include", $packageName)
            $newPackage.SetAttribute("Version", $hostPackageVersion)
            $funcItemGroup.AppendChild($newPackage) | Out-Null
        } else {
            Write-Warning "    Could not find appropriate ItemGroup to add $packageName"
            continue
        }
    } else {
        # Package exists, update it
        $oldPackageVersion = $packageNode.Version
        
        if ($oldPackageVersion -ne $hostPackageVersion) {
            $packageNode.Version = $hostPackageVersion
            Write-Host "    $packageName`: $oldPackageVersion -> $hostPackageVersion" -ForegroundColor Green
        } else {
            Write-Host "    $packageName`: $oldPackageVersion (no change)" -ForegroundColor Gray
        }
    }
}

# Save the updated Packages.props
Write-Host "`nSaving updated Packages.props..." -ForegroundColor Yellow
$packagesXml.Save($PackagesPropsPath)
Write-Host "✓ Successfully updated Packages.props" -ForegroundColor Green

# Get core tools root path for subsequent file modifications until core tools adopt the new host changes in v4.1047.100
$coreToolsRoot = Split-Path (Split-Path (Split-Path $PackagesPropsPath -Parent) -Parent) -Parent

# Update Startup.cs to remove deprecated IApplicationLifetime usage (for host version >= 4.1047.100)
Write-Host "`nChecking for Startup.cs updates..." -ForegroundColor Yellow

# Parse version to compare
$versionParts = $HostVersion -split '\.'
$majorVersion = [int]$versionParts[0]
$minorVersion = [int]$versionParts[1]
$patchVersion = [int]$versionParts[2]

# Check if version >= 4.1047.100
$shouldUpdateStartup = ($majorVersion -gt 4) -or 
                       ($majorVersion -eq 4 -and $minorVersion -gt 1047) -or 
                       ($majorVersion -eq 4 -and $minorVersion -eq 1047 -and $patchVersion -ge 100)

if ($shouldUpdateStartup) {
    $startupPath = Join-Path $coreToolsRoot "src\Cli\func\Actions\HostActions\Startup.cs"
    
    if (Test-Path $startupPath) {
        $startupContent = Get-Content $startupPath -Raw
        
        # Define the old code pattern to replace
        $oldCode = @"
            }
#pragma warning disable CS0618 // IApplicationLifetime is obsolete
            IApplicationLifetime applicationLifetime = app.ApplicationServices
                .GetRequiredService<IApplicationLifetime>();

            app.UseWebJobsScriptHost(applicationLifetime);
#pragma warning restore CS0618 // Type is obsolete
        }
"@
        
        # Define the new simplified code
        $newCode = @"
            }

            app.UseWebJobsScriptHost();
        }
"@
        
        if ($startupContent.Contains($oldCode)) {
            $startupContent = $startupContent.Replace($oldCode, $newCode)
            Set-Content -Path $startupPath -Value $startupContent -NoNewline
            Write-Host "  ✓ Updated Startup.cs - removed deprecated IApplicationLifetime usage" -ForegroundColor Green
        } else {
            Write-Host "  Startup.cs already updated or pattern not found (no change needed)" -ForegroundColor Gray
        }
    } else {
        Write-Warning "  Startup.cs not found at: $startupPath"
    }
} else {
    Write-Host "  Skipping Startup.cs update (host version $HostVersion < 4.1047.100)" -ForegroundColor Gray
}

# Disable UpdateBuildNumber in Directory.Version.props to prevent build output from updating Azure DevOps build number
Write-Host "`nDisabling UpdateBuildNumber in Directory.Version.props..." -ForegroundColor Yellow
$versionPropsPath = Join-Path $coreToolsRoot "src\Cli\func\Directory.Version.props"

if (Test-Path $versionPropsPath) {
    [xml]$versionPropsXml = Get-Content $versionPropsPath
    $updateBuildNumberNode = Select-Xml -Xml $versionPropsXml -XPath "//UpdateBuildNumber" | 
                            Select-Object -ExpandProperty Node
    
    if ($updateBuildNumberNode) {
        $oldValue = $updateBuildNumberNode.'#text'
        $updateBuildNumberNode.'#text' = 'false'
        $versionPropsXml.Save($versionPropsPath)
        Write-Host "  UpdateBuildNumber: $oldValue -> false" -ForegroundColor Green
    } else {
        Write-Host "  UpdateBuildNumber node not found (already disabled)" -ForegroundColor Gray
    }
} else {
    Write-Warning "  Directory.Version.props not found at: $versionPropsPath"
}

Write-Host "`n===========================================================" -ForegroundColor Cyan
Write-Host "Update Complete" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
