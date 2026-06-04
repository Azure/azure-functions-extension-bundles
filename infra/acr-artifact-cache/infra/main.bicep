targetScope = 'subscription'

@description('Azure region for the resource group and Azure Container Registry.')
param location string = deployment().location

@description('Resource group name to create or update.')
param resourceGroupName string = 'rg-acr-artifact-cache'

@description('Globally unique Azure Container Registry name. Use lowercase letters and numbers only.')
@minLength(5)
@maxLength(50)
param acrName string = toLower('acr${uniqueString(subscription().id, resourceGroupName)}')

@description('ACR SKU. Artifact cache is supported on Basic, Standard, and Premium.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param acrSku string = 'Standard'

@description('Allow anonymous pull access to cached images in the registry. Keep disabled unless the cache is intended to be public within the registry network boundary.')
param anonymousPullEnabled bool = false

@description('Key Vault secret URI for the Docker Hub username used by the ACR artifact cache credential set.')
param dockerHubUsernameSecretUri string

@description('Key Vault secret URI for the Docker Hub personal access token used by the ACR artifact cache credential set.')
param dockerHubTokenSecretUri string

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
}

module registry 'registry.bicep' = {
  name: 'acr-artifact-cache'
  scope: rg
  params: {
    acrName: acrName
    acrSku: acrSku
    anonymousPullEnabled: anonymousPullEnabled
    location: location
    dockerHubUsernameSecretUri: dockerHubUsernameSecretUri
    dockerHubTokenSecretUri: dockerHubTokenSecretUri
  }
}

output acrName string = registry.outputs.acrName
output acrLoginServer string = registry.outputs.acrLoginServer
output resourceGroupName string = rg.name
