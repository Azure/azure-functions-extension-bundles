#!/bin/bash

# Script to check Extension Bundle configuration for Azure Function Apps
# Usage: ./check-function-extensions.sh [subscription-id]
# If no subscription ID is provided, uses current context

SUBSCRIPTION_ID="$1"

# Color codes
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to display usage
show_usage() {
    echo "Usage: $0 [subscription-id]"
    echo ""
    echo "Parameters:"
    echo "  subscription-id  (optional) Azure subscription ID to switch to"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Use current subscription"
    echo "  $0 12345678-1234-1234-1234-123456789012  # Switch to specific subscription"
    echo ""
    exit 1
}

# Check for help flags
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_usage
fi

echo "==============================================================================================================="
echo "Azure Function Apps Extension Bundle Checker"
echo "==============================================================================================================="

# Check if Azure CLI is installed and user is logged in
if ! command -v az &> /dev/null; then
    echo "Azure CLI is not installed or not in PATH"
    exit 1
fi

# Check if user is logged in
if ! az account show &> /dev/null; then
    echo "Not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# Handle subscription context
if [[ -n "$SUBSCRIPTION_ID" ]]; then
    echo "Switching to subscription: $SUBSCRIPTION_ID"
    
    # Validate subscription ID format (basic check)
    if [[ ! "$SUBSCRIPTION_ID" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
        echo "Invalid subscription ID format. Expected: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        exit 1
    fi
    
    # Set the subscription context
    if ! az account set --subscription "$SUBSCRIPTION_ID"; then
        echo "Failed to set subscription context to: $SUBSCRIPTION_ID"
        echo "   Please verify the subscription ID and ensure you have access to it."
        exit 1
    fi
    
    echo "Successfully switched to subscription: $SUBSCRIPTION_ID"
else
    # Get current subscription info
    CURRENT_SUB=$(az account show --query "{id:id, name:name}" -o json 2>/dev/null)
    if [[ $? -eq 0 ]]; then
        CURRENT_SUB_ID=$(echo "$CURRENT_SUB" | jq -r '.id')
        CURRENT_SUB_NAME=$(echo "$CURRENT_SUB" | jq -r '.name')
        echo "Using current subscription: $CURRENT_SUB_NAME ($CURRENT_SUB_ID)"
    else
        echo "Failed to get current subscription information"
        exit 1
    fi
fi

echo "==============================================================================================================="
echo -e "FunctionApp\t\t\t\tExtensionBundleID\t\t\t\tExtensionBundleVersion"
echo "==============================================================================================================="

# Get all function apps in the subscription
functionApps=$(az functionapp list --query "[].{name:name, resourceGroup:resourceGroup, state:state}" -o json 2>/dev/null)

# Check if the command was successful
if [[ $? -ne 0 ]]; then
    echo "Failed to retrieve function apps. Please check your permissions."
    exit 1
fi

# Check if we got any function apps
if [[ -z "$functionApps" || "$functionApps" == "[]" ]]; then
    echo "No function apps found in the current subscription."
    exit 0
fi

# Count function apps
APP_COUNT=$(echo "$functionApps" | jq '. | length')

# Process each function app
PROCESSED=0
SUCCESSFUL=0
for row in $(echo "${functionApps}" | jq -c '.[]'); do
    name=$(echo "$row" | jq -r '.name')
    rg=$(echo "$row" | jq -r '.resourceGroup')
    state=$(echo "$row" | jq -r '.state')
    
    ((PROCESSED++))

    # Skip if not running
    if [[ "$state" != "Running" ]]; then
        printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<NOT_RUNNING>" "<SKIPPED>"
        continue
    fi

    key=$(az functionapp keys list --name "$name" --resource-group "$rg" --query "masterKey" -o tsv 2>/dev/null)

    if [[ -z "$key" || "$key" == "null" ]]; then
        printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<NO_MASTER_KEY>" "<SKIPPED>"
        continue
    fi


    # Get the default hostname for the function app
    hostname="$name.azurewebsites.net"  # Default fallback
    
    default_hostname=$(az functionapp show --name "$name" --resource-group "$rg" --query "properties.defaultHostName || defaultHostName" -o tsv 2>/dev/null)
    
    if [[ $? -eq 0 && -n "$default_hostname" && "$default_hostname" != "null" ]]; then
        hostname="$default_hostname"
    fi

    # Make the HTTP request and capture both response and curl exit code
    response=$(curl -s --max-time 15 --connect-timeout 10 \
        -w "%{http_code}" \
        -H "Content-Type: application/json" \
        "https://$hostname/admin/host/status?code=$key" 2>/dev/null)
    
    curl_exit_code=$?
    
    # Extract HTTP status code (last 3 characters)
    if [[ ${#response} -ge 3 ]]; then
        http_code="${response: -3}"
        response_body="${response%???}"
    else
        http_code=""
        response_body="$response"
    fi

    # Handle curl errors first
    if [[ $curl_exit_code -ne 0 ]]; then
        case $curl_exit_code in
            6)  printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<DNS_RESOLUTION_FAILED>" "<SKIPPED>" ;;
            7)  printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<CONNECTION_FAILED>" "<SKIPPED>" ;;
            28) printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<TIMEOUT>" "<SKIPPED>" ;;
            *)  printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<CONNECTION_ERROR>" "<SKIPPED>" ;;
        esac
        continue
    fi

    # Handle HTTP status codes
    case "$http_code" in
        200)
            # Success - validate JSON response
            if echo "$response_body" | jq empty 2>/dev/null; then
                # Check if extensionBundle exists in the response
                has_bundle=$(echo "$response_body" | jq -r 'has("extensionBundle")')

                if [[ "$has_bundle" == "true" ]]; then
                    ext_id=$(echo "$response_body" | jq -r '.extensionBundle.id // "N/A"')
                    ext_ver=$(echo "$response_body" | jq -r '.extensionBundle.version // "N/A"')
                    
                    # Check if version is less than 4 and apply red color
                    if [[ "$ext_ver" != "N/A" && "$ext_ver" =~ ^[0-9]+ && ${ext_ver%%.*} -lt 4 ]]; then
                        printf "${RED}%-35s %-45s %-25s${NC}\n" "$name" "$ext_id" "$ext_ver"
                    else
                        printf "%-35s %-45s %-25s\n" "$name" "$ext_id" "$ext_ver"
                    fi
                    ((SUCCESSFUL++))
                else
                    printf "%-35s %-45s %-25s\n" "$name" "NotConfigured" "NotConfigured"
                    ((SUCCESSFUL++))
                fi
            else
                printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<INVALID_JSON>" "<SKIPPED>"
                echo "  ERROR: Invalid JSON response"
            fi
            ;;
        401)
            printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<UNAUTHORIZED>" "<SKIPPED>" ;;
        403)
            printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<IP_FORBIDDEN>" "<SKIPPED>" ;;
        404)
            printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<ENDPOINT_NOT_FOUND>" "<SKIPPED>" ;;
        "")
            # No HTTP code - likely no response
            if [[ -z "$response_body" ]]; then
                printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<NO_RESPONSE>" "<SKIPPED>"
            else
                printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<APP_IN_ERROR_STATE>" "<SKIPPED>"
            fi
            ;;
        *)
            printf "${YELLOW}%-35s %-45s %-25s${NC}\n" "$name" "<APP_IN_ERROR_STATE>" "<SKIPPED>"
            ;;
    esac
    echo ""
done

echo "==============================================================================================================="
echo "Summary: Processed $PROCESSED Function Apps, $SUCCESSFUL successful responses"
echo ""
echo "Legend:"
echo "  <NOT_RUNNING>              - Function App is not in Running state"
echo "  <NO_MASTER_KEY>            - Unable to retrieve master key"
echo "  <FAILED_TO_GET_URL>        - Unable to determine Function App hostname"
echo "  <DNS_RESOLUTION_FAILED>    - Hostname could not be resolved"
echo "  <CONNECTION_FAILED>        - Failed to connect to endpoint"
echo "  <CONNECTION_ERROR>         - Network connection error"
echo "  <TIMEOUT>                  - Request timed out"
echo "  <NO_RESPONSE>              - No response from the endpoint"
echo "  <UNAUTHORIZED>             - Authentication failed (401)"
echo "  <IP_FORBIDDEN>             - IP address blocked (403)"
echo "  <ENDPOINT_NOT_FOUND>       - Admin endpoint not available (404)"
echo "  <INVALID_JSON>             - Response is not valid JSON"
echo "  <HTTP_XXX>                 - Other HTTP error codes"
echo "  NotConfigured              - Extension bundles are not configured"
echo "  <NOT_RUNNING>              - Function App is not in Running state"
echo "  <NO_MASTER_KEY>            - Unable to retrieve master key"
echo "  <APP_IN_ERROR_STATE>       - Function App encountered an error"
echo "  NotConfigured              - Extension bundles are not configured"
echo "  <Bundle Version < 4>       - Outdated bundle version (shown in red)"
echo "==============================================================================================================="
