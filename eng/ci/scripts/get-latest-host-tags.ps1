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
