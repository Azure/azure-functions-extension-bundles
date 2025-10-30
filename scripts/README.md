# List Extension Bundle versions for Function Apps in your subscription

This repository contains scripts to check the Extension Bundle configuration and versions for all Azure Function Apps in your subscription.

## Overview

Azure Functions Extension Bundles provide a way to add a pre-compiled set of binding extensions to your function app. These scripts help you audit and monitor the extension bundle versions across all your Function Apps to ensure they are up-to-date and properly configured.

## Scripts Available

### PowerShell Script

- **File**: `get-function-apps-bundle-version.ps1`
- **Platform**: Windows PowerShell / PowerShell Core
- **Compatible with**: Azure Cloud Shell PowerShell

### Bash Script

- **File**: `get-function-apps-bundle-version.sh`
- **Platform**: Linux/macOS Bash
- **Compatible with**: Azure Cloud Shell Bash

## Prerequisites

### System Requirements

#### For PowerShell Script (Windows/Linux/macOS)

- **PowerShell 5.1** or **PowerShell Core 6.0+**
- **Azure CLI 2.0+** - [Installation Guide](https://docs.microsoft.com/cli/azure/install-azure-cli)
- **Internet connectivity** to access Azure APIs

#### For Bash Script (Linux/macOS/WSL)

- **Bash 4.0+**
- **Azure CLI 2.0+** - [Installation Guide](https://docs.microsoft.com/cli/azure/install-azure-cli)
- **jq** - JSON processor ([Installation Guide](https://stedolan.github.io/jq/download/))
- **curl** - Usually pre-installed on most systems
- **Internet connectivity** to access Azure APIs

### Azure Authentication & Permissions

#### 1. Azure CLI Authentication

```bash
# Login to Azure
az login

# Verify you're logged in
az account show

# List available subscriptions
az account list --output table

# Set specific subscription (if needed)
az account set --subscription "your-subscription-id"
```

#### 2. Required Azure Permissions

Your Azure account needs the following permissions:

- **Reader** role on the subscription or resource groups containing Function Apps
- **Function App Contributor** or **Website Contributor** role to access Function App keys
- Permission to call Azure Resource Manager APIs

#### 3. Network Access Requirements

- Access to Azure management endpoints (`management.azure.com`)
- Access to Function App endpoints (`*.azurewebsites.net`)
- Outbound HTTPS (port 443) connectivity

### File Execution Permissions

#### Windows PowerShell

```powershell
# Check current execution policy
Get-ExecutionPolicy

# Set execution policy (choose one):
# Option 1: For current session only (recommended)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# Option 2: For current user
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Option 3: Unblock the specific file
Unblock-File ".\get-function-apps-bundle-version.ps1"
```

#### Linux/macOS/WSL Bash

```bash
# Make the script executable
chmod +x get-function-apps-bundle-version.sh

# Verify permissions
ls -la get-function-apps-bundle-version.sh
```

### Installation Steps

#### Windows Setup

1. **Install Azure CLI**:

   ```powershell
   # Using winget (Windows 10/11)
   winget install Microsoft.AzureCLI
   
   # Or download from: https://aka.ms/installazurecliwindows
   ```

2. **Install PowerShell Core (optional but recommended)**:

   ```powershell
   winget install Microsoft.PowerShell
   ```

3. **Authenticate and test**:

   ```powershell
   az login
   .\get-function-apps-bundle-version.ps1 -Help
   ```

#### Linux/macOS Setup

1. **Install Azure CLI**:

   ```bash
   # Ubuntu/Debian
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   
   # RHEL/CentOS/Fedora
   sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
   sudo dnf install azure-cli
   
   # macOS
   brew install azure-cli
   ```

2. **Install jq**:

   ```bash
   # Ubuntu/Debian
   sudo apt-get install jq
   
   # RHEL/CentOS/Fedora
   sudo dnf install jq
   
   # macOS
   brew install jq
   ```

3. **Make script executable and test**:

   ```bash
   chmod +x get-function-apps-bundle-version.sh
   az login
   ./get-function-apps-bundle-version.sh -h
   ```

#### Azure Cloud Shell Setup

**Azure Cloud Shell** is the easiest way to run these scripts as it comes pre-configured with all dependencies.

##### Advantages of Cloud Shell

- **Pre-installed**: Azure CLI, PowerShell, Bash, jq already available
- **Pre-authenticated**: Automatically logged into your Azure account
- **No local setup**: No need to install anything on your machine
- **Network access**: Direct access to all Azure endpoints
- **Cross-platform**: Works from any web browser

##### Using PowerShell in Cloud Shell

1. **Open Azure Cloud Shell**: [https://shell.azure.com](https://shell.azure.com)
2. **Select PowerShell** from the shell dropdown
3. **Upload the script**:

   ```powershell
   # Upload via Cloud Shell interface or clone repository
   git clone https://github.com/Azure/azure-functions-extension-bundles.git
   cd azure-functions-extension-bundles/scripts
   ```

4. **Run the script**:

   ```powershell
   .\get-function-apps-bundle-version.ps1
   ```

##### Using Bash in Cloud Shell

1. **Open Azure Cloud Shell**: [https://shell.azure.com](https://shell.azure.com)  
2. **Select Bash** from the shell dropdown
3. **Upload the script**:

   ```bash
   # Upload via Cloud Shell interface or clone repository
   git clone https://github.com/Azure/azure-functions-extension-bundles.git
   cd azure-functions-extension-bundles/tools
   ```

4. **Make executable and run**:

   ```bash
   chmod +x get-function-apps-bundle-version.sh
   ./get-function-apps-bundle-version.sh
   ```

##### Cloud Shell Considerations

- **Session timeout**: Cloud Shell sessions timeout after 20 minutes of inactivity
- **File persistence**: Files are stored in your Cloud Shell storage account
- **Resource limits**: Limited CPU and memory compared to local execution
- **Subscription context**: Already authenticated, but verify correct subscription:

  ```bash
  az account show
  az account set --subscription "your-subscription-id"  # if needed
  ```

##### Cloud Shell vs Local Execution

| Aspect | Cloud Shell | Local Machine |
|--------|-------------|---------------|
| **Setup Time** | Instant | 15-30 minutes |
| **Dependencies** | Pre-installed | Manual installation |
| **Authentication** | Automatic | Manual login |
| **Performance** | Limited resources | Full machine power |
| **Persistence** | Cloud storage | Local storage |
| **Network** | Always connected | May have restrictions |
| **Cost** | Storage costs | Free (after setup) |

**Recommendation**: Use **Cloud Shell** for quick one-time scans or testing. Use **local execution** for regular monitoring or large-scale operations.

### Quick Verification

After setup, verify everything works:

```bash
# Test Azure CLI
az account show

# Test script execution
# PowerShell
.\get-function-apps-bundle-version.ps1 -Help

# Bash
./get-function-apps-bundle-version.sh -h
```

### Common Deployment Scenarios

#### Corporate Environment

- **Proxy Settings**: Configure Azure CLI for corporate proxies

  ```bash
  az configure --defaults proxy_use_system_settings=true
  ```

- **Certificate Issues**: Use `--no-verify-ssl` if needed (not recommended for production)
- **Firewall Rules**: Ensure access to `*.azure.com`, `*.azurewebsites.net`, `*.microsoft.com`

#### CI/CD Pipeline Integration

- Use **Service Principal** authentication instead of interactive login

  ```bash
  az login --service-principal -u <app-id> -p <password> --tenant <tenant>
  ```

- Store credentials securely (Azure Key Vault, GitHub Secrets, etc.)
- Consider using **Managed Identity** when running on Azure VMs/Container Instances

#### Multi-Tenant Scenarios

- Specify tenant explicitly:

  ```bash
  az login --tenant <tenant-id>
  ```

- Switch between tenants as needed:

  ```bash
  az account set --subscription <subscription-id>
  ```

## Usage

### PowerShell Script

```powershell
# Use current subscription
.\get-function-apps-bundle-version.ps1

# Use specific subscription
.\get-function-apps-bundle-version.ps1 "12345678-1234-1234-1234-123456789012"

# Show help
.\get-function-apps-bundle-version.ps1 -Help
```

### Bash Script

```bash
# Use current subscription
./get-function-apps-bundle-version.sh

# Use specific subscription
./get-function-apps-bundle-version.sh 12345678-1234-1234-1234-123456789012

# Show help
./get-function-apps-bundle-version.sh -h
```

## Output

The scripts will display a table showing:

| Column | Description |
|--------|-------------|
| **FunctionApp** | Name of the Function App |
| **ExtensionBundleID** | The ID of the extension bundle being used |
| **ExtensionBundleVersion** | The version of the extension bundle |

### Status Indicators

| Status | Color | Description |
|--------|-------|-------------|
| **Bundle Version < 4** | Red | Function App using older extension bundle (version < 4) |
| **`<NOT_RUNNING>`** | Yellow | Function App is not in Running state |
| **`<NO_MASTER_KEY>`** | Yellow | Unable to retrieve master key for the Function App |
| **`<App in Error State>`** | Yellow | Function App encountered an error during scanning |
| **`NotConfigured`** | Normal | Extension bundles are not configured for this Function App |
| **Normal Response** | Normal | Successfully retrieved bundle information |

## Important Considerations

⚠️ **Please be aware of the following limitations:**

### 1. Running State Requirement

- **This script can only scan apps that are in 'Running' state**
- Function Apps that are stopped, suspended, or in any other state will be skipped
- Consider starting your Function Apps temporarily if you need to scan them

### 2. Public Access Requirement

- **If your app has public access disabled, this script cannot scan the app**
- The script accesses the Function App's admin API endpoint which requires public network access or run the script or admin endpoint inside the accessible network
- Function Apps with:
  - Private endpoints only
  - IP restrictions blocking your current IP
  - VNet integration without public access
  - Will show as `<App in Error State>`

### 3. Authentication Requirements

- The script uses the Function App's master key to access the admin endpoint
- Ensure your Azure CLI session has sufficient permissions to retrieve Function App keys
- Some Function Apps may have additional security restrictions

## Troubleshooting

### Common Issues

1. **"Not logged in to Azure"**
   - Run `az login` to authenticate with Azure CLI

2. **"Failed to retrieve function apps"**
   - Check your subscription permissions
   - Verify you have Reader or Contributor access to the subscription

3. **Many apps showing `<App in Error State>`**
   - Check if Function Apps are running (`az functionapp list --query "[?state=='Stopped'].name"`)
   - Verify network access to Function Apps
   - Check if Function Apps have IP restrictions
   - Check if Function App host runtime is not in error state

4. **PowerShell execution policy error**
   - Run `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process` (temporary)
   - Or unblock the file: `Unblock-File .\get-function-apps-bundle-version.ps1`

## Extension Bundle Versions

### Recommended Actions

- **Version < 4**: Consider upgrading to version 4.x for latest features and security updates
- **Version 4.x**: Current and supported versions

### Extension Bundle Types

- **Microsoft.Azure.Functions.ExtensionBundle**: Standard extension bundle
- **Microsoft.Azure.Functions.ExtensionBundle.Preview**: Preview version - Review if you can upgrade to standard bundle
- **Microsoft.Azure.Functions.ExtensionBundle.Experimental**: Experimental features version - Review if you can upgrade to standard bundle

## Contributing

This tool is part of the Azure Functions Extension Bundles repository. Please refer to the main repository guidelines for contributions.

---

**Note**: This script is provided as-is for auditing and monitoring purposes. Always test in a non-production environment first.
