<#
.SYNOPSIS
    Fetches the latest N host tags from azure-functions-host repository matching a version pattern.

.DESCRIPTION
    This script retrieves git tags from the Azure Functions Host repository, filters them by
    a version pattern, groups them by middle version number, and returns the latest N tags.
    
    Version Pattern Matching:
    - Pattern "v4.10" matches tags like v4.1046.100, v4.1047.200 (any v4.10*.* tag)
    - The script groups by middle version (4.1046, 4.1047) and picks highest patch per group
    - Then selects the N most recent middle versions
    
    When to Update Pattern:
    - When Azure Functions Host moves to v4.11.x, update pattern to "v4.11"
    - When moving to v5.x, update pattern to "v5.0" or appropriate version

.PARAMETER Count
    Number of latest host tags to return (default: 2)

.PARAMETER Pattern
    Version pattern to match (default: v4.10)
    Must include 'v' prefix to match git tag format
    Example patterns: "v4.10", "v4.11", "v5.0"

.PARAMETER Repository
    Git repository URL (default: https://github.com/Azure/azure-functions-host.git)

.EXAMPLE
    .\get-latest-host-tags.ps1 -Count 2 -Pattern "v4.10"
    Returns: v4.1047.200, v4.1046.100 (example - highest patch from 2 most recent middle versions)

.EXAMPLE
    .\get-latest-host-tags.ps1 -Count 3 -Pattern "v4.11"
    Returns: Latest 3 tags matching v4.11*.* pattern
#>

param(
    [Parameter(Mandatory=$false)]
    [int]$Count = 2,
    
    [Parameter(Mandatory=$false)]
    [string]$Pattern = "v4.10",
    
    [Parameter(Mandatory=$false)]
    [string]$Repository = "https://github.com/Azure/azure-functions-host.git"
)

Write-Host "Fetching tags from $Repository matching $Pattern*..." -ForegroundColor Cyan

# Escape dots in pattern for regex and fetch tags from GitHub
$escapedPattern = [regex]::Escape($Pattern)
$tags = git ls-remote --tags $Repository 2>&1 | 
    Where-Object { $_ -match "refs/tags/${escapedPattern}\d+\.\d+(\^\{\})?$" } |
    ForEach-Object { 
        if ($_ -match 'refs/tags/(v\d+\.\d+\.\d+)(\^\{\})?$') {
            $matches[1]
        }
    } | Select-Object -Unique

if (-not $tags) {
    Write-Host "Debug: Checking all v4.* tags..." -ForegroundColor Gray
    $allV4Tags = git ls-remote --tags $Repository 2>&1 | 
        Where-Object { $_ -match "refs/tags/v4\.\d+" } |
        ForEach-Object { $_.Split("`t")[1] -replace 'refs/tags/', '' -replace '\^\{\}$', '' } |
        Select-Object -Unique |
        Sort-Object -Descending |
        Select-Object -First 10
    Write-Host "Sample v4.* tags found: $($allV4Tags -join ', ')" -ForegroundColor Gray
    Write-Error "No tags found matching pattern $Pattern* (e.g., ${Pattern}45.300)"
    exit 1
}

Write-Host "Found $($tags.Count) tags matching pattern" -ForegroundColor Green

# Parse and group tags
$parsedTags = $tags | ForEach-Object {
    if ($_ -match '^v4\.(\d+)\.(\d+)$') {
        [PSCustomObject]@{
            Tag = $_
            MiddleVersion = [int]$matches[1]
            PatchVersion = [int]$matches[2]
            VersionNoPrefix = $_.TrimStart('v')
        }
    }
} | Where-Object { $_ -ne $null }

# Group by middle version and get the highest patch from each group
$groupedTags = $parsedTags | 
    Group-Object MiddleVersion | 
    ForEach-Object {
        $_.Group | Sort-Object PatchVersion -Descending | Select-Object -First 1
    }

# Sort by middle version descending and take the requested count
$latestTags = $groupedTags | 
    Sort-Object MiddleVersion -Descending | 
    Select-Object -First $Count

Write-Host "`nLatest $Count tag(s) from $Repository ($Pattern*):" -ForegroundColor Yellow
$latestTags | ForEach-Object { 
    Write-Host "  $($_.Tag) -> $($_.VersionNoPrefix)" -ForegroundColor White
}

# Return the version numbers without 'v' prefix
Write-Host "`nVersion numbers (without prefix):" -ForegroundColor Yellow
$versions = $latestTags | ForEach-Object { $_.VersionNoPrefix }
$versions | ForEach-Object { Write-Host "  $_" -ForegroundColor White }

# Output as object for further processing
return $latestTags
