# PowerShell script to check Extension Bundle configuration for Azure Function Apps
# Compatible with Azure Cloud Shell PowerShell
# Usage: ./check-function-extensions.ps1 [subscription-id]

param(
    [Parameter(Mandatory = $false, Position = 0)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory = $false)]
    [switch]$Help
)

# Function to display usage
function Show-Usage {
    Write-Host "Usage: .\check-function-extensions.ps1 [subscription-id]" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Parameters:" -ForegroundColor Yellow
    Write-Host "  -SubscriptionId  (optional) Azure subscription ID to switch to" -ForegroundColor White
    Write-Host "  -Help           Show this help message" -ForegroundColor White
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\check-function-extensions.ps1                                    # Use current subscription" -ForegroundColor White
    Write-Host "  .\check-function-extensions.ps1 12345678-1234-1234-1234-123456789012  # Switch to specific subscription" -ForegroundColor White
    Write-Host "  .\check-function-extensions.ps1 -SubscriptionId 'your-sub-id'"  -ForegroundColor White
    Write-Host ""
    exit
}

# Check for help
if ($Help) {
    Show-Usage
}

Write-Host "=======================================================================================================" -ForegroundColor Green
Write-Host "Azure Function Apps Extension Bundle Checker" -ForegroundColor Green
Write-Host "=======================================================================================================" -ForegroundColor Green

# Check if Azure CLI is available
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Host "Azure CLI is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Check if user is logged in
try {
    $null = az account show 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Not logged in"
    }
} catch {
    Write-Host "Not logged in to Azure. Please run 'az login' first." -ForegroundColor Red
    exit 1
}

# Handle subscription context
if ($SubscriptionId) {
    Write-Host "Switching to subscription: $SubscriptionId" -ForegroundColor Yellow
    
    # Validate subscription ID format
    $guidPattern = '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    if ($SubscriptionId -notmatch $guidPattern) {
        Write-Host "Invalid subscription ID format. Expected: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" -ForegroundColor Red
        exit 1
    }
    
    # Set the subscription context
    az account set --subscription $SubscriptionId 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to set subscription context to: $SubscriptionId" -ForegroundColor Red
        Write-Host "Please verify the subscription ID and ensure you have access to it." -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Successfully switched to subscription: $SubscriptionId" -ForegroundColor Green
} else {
    # Get current subscription info
    try {
        $currentSub = az account show --query "{id:id, name:name}" -o json 2>$null | ConvertFrom-Json
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Using current subscription: $($currentSub.name) ($($currentSub.id))" -ForegroundColor Cyan
        } else {
            throw "Failed to get subscription info"
        }
    } catch {
        Write-Host "Failed to get current subscription information" -ForegroundColor Red
        exit 1
    }
}

Write-Host "=======================================================================================================" -ForegroundColor Green
Write-Host "FunctionApp`t`t`t`tExtensionBundleID`t`t`t`tExtensionBundleVersion" -ForegroundColor Green
Write-Host "=======================================================================================================" -ForegroundColor Green

# Get all function apps in the subscription
try {
    $functionApps = az functionapp list --query "[].{name:name, resourceGroup:resourceGroup, state:state}" -o json 2>$null | ConvertFrom-Json
    
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed"
    }
    
    if (-not $functionApps -or $functionApps.Count -eq 0) {
        Write-Host "No function apps found in the current subscription." -ForegroundColor Yellow
        return
    }
}
catch {
    Write-Host "Failed to retrieve function apps. Please check your permissions." -ForegroundColor Red
    exit 1
}

# Process each function app
$processed = 0
$successful = 0
foreach ($app in $functionApps) {
    $name = $app.name
    $resourceGroup = $app.resourceGroup
    $state = $app.state
    
    $processed++

    # Skip if not running
    if ($state -ne "Running") {
        Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<NOT_RUNNING>", "<SKIPPED>") -ForegroundColor Yellow
        continue
    }

    try {
        $key = az functionapp keys list --name $name --resource-group $resourceGroup --query "masterKey" -o tsv 2>$null
        
        if (-not $key -or $key -eq "null" -or $key.Trim() -eq "") {
            Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<NO_MASTER_KEY>", "<SKIPPED>") -ForegroundColor Yellow
            continue
        }
    }
    catch {
        Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<KEY_ERROR>", "<SKIPPED>") -ForegroundColor Yellow
        continue
    }

    # Get the default hostname for the function app
    $hostName = "$name.azurewebsites.net"  # Default fallback
    
    try {
        $defaultHostName = az functionapp show --name $name --resource-group $resourceGroup --query "properties.defaultHostName || defaultHostName" -o tsv 2>$null
        
        if ($LASTEXITCODE -eq 0 -and $defaultHostName -and $defaultHostName -ne "null" -and $defaultHostName.Trim() -ne "") {
            $hostName = $defaultHostName.Trim()
        }
    }
    catch {
        # Use fallback hostname
    }
    
    try {
        $uri = "https://$hostName/admin/host/status?code=$key"
        
        $response = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 15 -ErrorAction Stop
        
        # Check if extensionBundle exists
        if ($response.PSObject.Properties.Name -contains "extensionBundle") {
            $extId = if ($response.extensionBundle.id) { $response.extensionBundle.id } else { "N/A" }
            $extVer = if ($response.extensionBundle.version) { $response.extensionBundle.version } else { "N/A" }
            
            # Check if version is less than 4 and set color accordingly
            $color = "White"  # Default normal color
            if ($extVer -ne "N/A" -and $extVer -match '^\d+' -and [int]($matches[0]) -lt 4) {
                $color = "Red"
            }
            
            Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, $extId, $extVer) -ForegroundColor $color
            $successful++
        }
        else {
            Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "NotConfigured", "NotConfigured") -ForegroundColor White
            $successful++
        }
    }
    catch {
        $errorMessage = $_.Exception.Message
        if ($errorMessage -like "*Failed to get app details*") {
            Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<FAILED_TO_GET_URL>", "<SKIPPED>") -ForegroundColor Yellow
        }
        elseif ($errorMessage -like "*Unauthorized*" -or $errorMessage -like "*401*") {
            Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<UNAUTHORIZED>", "<SKIPPED>") -ForegroundColor Yellow
        }
        elseif ($errorMessage -like "*404*") {
            Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<ENDPOINT_NOT_FOUND>", "<SKIPPED>") -ForegroundColor Yellow
        }
        elseif ($errorMessage -like "*timeout*") {
            Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<TIMEOUT>", "<SKIPPED>") -ForegroundColor Yellow
        }
        else {
            # Check for specific DNS/hostname issues
            if ($errorMessage -like "*No such host is known*") {
                Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<DNS_RESOLUTION_FAILED>", "<SKIPPED>") -ForegroundColor Yellow
                Write-Host "  ERROR: Hostname '$hostName' could not be resolved" -ForegroundColor Yellow
            }
            elseif ($errorMessage -like "*Ip Forbidden*" -or $errorMessage -like "*403*") {
                Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<IP_FORBIDDEN>", "<SKIPPED>") -ForegroundColor Yellow
            }
            else {
                Write-Host ("{0,-35} {1,-45} {2,-25}" -f $name, "<APP_IN_ERROR_STATE>", "<SKIPPED>") -ForegroundColor Yellow
            }
        }
    }
    Write-Host ""
}

Write-Host "=======================================================================================================" -ForegroundColor Green
Write-Host "Summary: Processed $processed Function Apps, $successful successful responses" -ForegroundColor Green
Write-Host ""
Write-Host "Script completed. Legend:" -ForegroundColor White
Write-Host "  <NOT_RUNNING>        - Function App is not in Running state" -ForegroundColor Yellow
Write-Host "  <NO_MASTER_KEY>      - Unable to retrieve master key" -ForegroundColor Yellow
Write-Host "  <FAILED_TO_GET_URL>  - Unable to determine Function App hostname" -ForegroundColor Yellow
Write-Host "  <DNS_RESOLUTION_FAILED> - Function App hostname could not be resolved" -ForegroundColor Yellow
Write-Host "  <IP_FORBIDDEN>       - IP address blocked by firewall rules" -ForegroundColor Yellow
Write-Host "  <UNAUTHORIZED>       - Authentication failed" -ForegroundColor Yellow
Write-Host "  <ENDPOINT_NOT_FOUND> - Admin endpoint not available" -ForegroundColor Yellow
Write-Host "  <TIMEOUT>            - Request timed out" -ForegroundColor Yellow
Write-Host "  <APP_IN_ERROR_STATE> - General error occurred" -ForegroundColor Yellow
Write-Host "  NotConfigured        - Extension bundles are not configured" -ForegroundColor White
Write-Host "  <Bundle Version < 4> - Outdated bundle version (shown in red)" -ForegroundColor Red
