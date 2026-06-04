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

@secure()
@description('Docker Hub username used by the ACR artifact cache credential set.')
param dockerHubUsername string

@secure()
@description('Docker Hub personal access token or password used by the ACR artifact cache credential set.')
param dockerHubPassword string

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
    location: location
    dockerHubUsername: dockerHubUsername
    dockerHubPassword: dockerHubPassword
  }
}

output acrName string = registry.outputs.acrName
output acrLoginServer string = registry.outputs.acrLoginServer
output resourceGroupName string = rg.name
