# ACR Artifact Cache

This azd project deploys an Azure Container Registry with Artifact Cache rules for the Docker Hub images used by the Kafka, RabbitMQ, and extension bundle emulator tests.

## Prerequisites

- Azure Developer CLI (`azd`)
- Azure CLI (`az`)
- Docker Hub account and personal access token
- Azure Key Vault that stores the Docker Hub username and token as secrets

Docker Hub upstreams require authenticated pulls for ACR Artifact Cache. Use a Docker Hub personal access token instead of an account password.

The Bicep template expects Key Vault secret URIs, not raw Docker Hub credentials.

## Prepare Key Vault secrets

Create or choose a Key Vault, then store the Docker Hub credentials as secrets:

```powershell
$resourceGroup = "rg-acr-artifact-cache"
$location = "westus2"
$keyVaultName = "<globally-unique-key-vault-name>"

az group create --name $resourceGroup --location $location
az keyvault create --resource-group $resourceGroup --name $keyVaultName --location $location --enable-rbac-authorization false

az keyvault secret set --vault-name $keyVaultName --name dockerhub-username --value "<docker-hub-username>"
az keyvault secret set --vault-name $keyVaultName --name dockerhub-token --value "<docker-hub-token>"

$dockerHubUsernameSecretUri = az keyvault secret show --vault-name $keyVaultName --name dockerhub-username --query id -o tsv
$dockerHubTokenSecretUri = az keyvault secret show --vault-name $keyVaultName --name dockerhub-token --query id -o tsv
```

The deploying identity must be able to read the secrets and create the ACR credential set. Keep the Key Vault in the same tenant as the deployment.

## Deploy

```powershell
cd infra\acr-artifact-cache
azd auth login
azd env new acr-artifact-cache
azd env set AZURE_LOCATION westus2
azd env set AZURE_RESOURCE_GROUP rg-acr-artifact-cache
azd env set ACR_NAME <globally-unique-acr-name>
azd env set ACR_SKU Standard
azd env set ACR_ANONYMOUS_PULL_ENABLED false
azd env set DOCKERHUB_USERNAME_SECRET_URI $dockerHubUsernameSecretUri
azd env set DOCKERHUB_TOKEN_SECRET_URI $dockerHubTokenSecretUri
azd provision
```

Set `ACR_ANONYMOUS_PULL_ENABLED` to `true` only when cached images should be pullable without ACR authentication. Anonymous pull removes the need for `az acr login` or Docker credentials for image pulls, but anyone who can reach the registry login server can pull repositories that allow anonymous access.

## Deploy from 1ES pipeline

Use `eng/deploy-acr-artifact-cache.yml` from the mirror repository to reprovision the same ACR after cache rule changes. The pipeline is manual-only and uses the 1ES official template.

Recommended setup:

1. Run the first deployment locally to choose and verify stable names for the resource group, ACR, and Key Vault secrets.
2. Create an Azure Resource Manager service connection in Azure DevOps that uses Workload Identity Federation.
3. Grant the service connection identity `Contributor` on the subscription or target resource group.
4. If Key Vault access is managed by the deployment identity, grant the service connection identity the required Key Vault management permissions. The preferred steady-state model is that ACR reads Docker Hub credentials through Key Vault secret URIs.
5. Create an Azure DevOps variable group named `acr-artifact-cache` with these values:

| Variable | Secret | Description |
|---|---:|---|
| `AZURE_SERVICE_CONNECTION` | No | Name of the Azure Resource Manager service connection used by `AzureCLI@2`. |
| `AZURE_SUBSCRIPTION_ID` | No | Subscription for the deployment. |
| `AZURE_LOCATION` | No | Azure region, for example `westus2`. |
| `AZURE_RESOURCE_GROUP` | No | Stable resource group name. |
| `ACR_NAME` | No | Stable, globally unique ACR name. Keep this unchanged after first deployment. |
| `ACR_SKU` | No | ACR SKU, for example `Standard`. |
| `ACR_ANONYMOUS_PULL_ENABLED` | No | `true` or `false`. Keep `false` unless unauthenticated pulls are intended. |
| `DOCKERHUB_USERNAME_SECRET_URI` | Yes | Key Vault secret URI containing the Docker Hub username. |
| `DOCKERHUB_TOKEN_SECRET_URI` | Yes | Key Vault secret URI containing the Docker Hub token. |

When cache rules or image paths change, update the Bicep files and run the pipeline. Because `ACR_NAME` and `AZURE_RESOURCE_GROUP` are fixed in the variable group, the deployment updates the existing registry instead of creating a new one.

## Cache rules and pull paths

Artifact Cache creates rules, but it does not pre-populate tags. A tag is cached only after the first successful pull through the ACR login server.

After deployment, get the ACR login server:

```powershell
azd env get-values
```

Then warm the cache by pulling each required tag through ACR:

```powershell
$acr = "<acr-login-server>"

docker pull "$acr/cache/confluentinc/cp-kafka:7.6.0"
docker pull "$acr/cache/confluentinc/cp-schema-registry:7.6.0"
docker pull "$acr/cache/confluentinc/cp-zookeeper:5.3.1"
docker pull "$acr/cache/confluentinc/cp-enterprise-kafka:5.3.1"
docker pull "$acr/cache/confluentinc/cp-schema-registry:5.3.1"
docker pull "$acr/cache/confluentinc/cp-kafka-rest:5.3.1"
docker pull "$acr/cache/confluentinc/cp-enterprise-control-center:5.3.1"
docker pull "$acr/cache/cnfldemos/kafka-connect-datagen:0.1.3-5.3.1"
docker pull "$acr/cache/library/openjdk:8-jdk-alpine"
docker pull "$acr/cache/library/rabbitmq:3-management"
docker pull "$acr/cache/library/mysql:9.0"
```

The `confluentinc/cp-schema-registry` and `rabbitmq` entries are intentionally shared by duplicate image requirements.

If anonymous pull is disabled, authenticate before pulling:

```powershell
az acr login --name <acr-name>
```

## Security scanning

This template creates ACR and cache rules. Vulnerability assessment is performed by Microsoft Defender for Cloud for registries in supported plans, not directly by the Bicep cache rule itself.

Enable Defender for Containers or the relevant Defender for Cloud registry vulnerability assessment in the subscription, then warm the cache. Scans are triggered after images are imported into ACR by the first pull. Review findings in Microsoft Defender for Cloud.

## Sharing azd files

It is safe to share source files such as `azure.yaml`, Bicep templates, and this README. Do not commit `.azure` environment files if they contain secrets or Key Vault secret URIs.

Resource names like an ACR name, resource group name, or Key Vault name are not secrets by themselves, but they can reveal environment naming and subscription organization details. Sharing them in a repo is usually acceptable for non-sensitive test infrastructure, but avoid committing Docker Hub credentials, access tokens, Key Vault secret URIs, subscription IDs, tenant IDs, or production-only naming details.
