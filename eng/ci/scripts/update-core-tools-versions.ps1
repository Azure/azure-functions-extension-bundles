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

# Verify the host tag exists
$tagUri = "https://api.github.com/repos/Azure/azure-functions-host/git/refs/tags/v$HostVersion"
try {
    $tagCheck = Invoke-WebRequest -Uri $tagUri -ErrorAction Stop
    if ($tagCheck.StatusCode -ne 200) {
        Write-Error "Host tag v$HostVersion does not exist in azure-functions-host repository"
        exit 1
    }
    Write-Host "✓ Verified host tag v$HostVersion exists" -ForegroundColor Green
} catch {
    Write-Error "Failed to verify host tag v$HostVersion : $_"
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
        $content = (Invoke-WebRequest -Uri $uri -ErrorAction Stop).Content
        [xml]$workerXml = $content
        
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

# Save the updated Packages.props
Write-Host "`nSaving updated Packages.props..." -ForegroundColor Yellow
$packagesXml.Save($PackagesPropsPath)
Write-Host "✓ Successfully updated Packages.props" -ForegroundColor Green

Write-Host "`n===========================================================" -ForegroundColor Cyan
Write-Host "Update Complete" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
