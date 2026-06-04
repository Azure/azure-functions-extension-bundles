@description('Azure Container Registry name.')
param acrName string

@description('Azure Container Registry SKU.')
param acrSku string

@description('Azure region for the registry.')
param location string

@description('Key Vault secret URI for the Docker Hub username used by the ACR artifact cache credential set.')
param dockerHubUsernameSecretUri string

@description('Key Vault secret URI for the Docker Hub personal access token used by the ACR artifact cache credential set.')
param dockerHubTokenSecretUri string

var dockerHubLoginServer = 'docker.io'
var dockerHubCredentialName = 'dockerhub'

var cacheRules = [
  {
    name: 'confluent-cp-kafka-760'
    sourceRepository: 'docker.io/confluentinc/cp-kafka'
    targetRepository: 'cache/confluentinc/cp-kafka'
  }
  {
    name: 'confluent-cp-schema-registry'
    sourceRepository: 'docker.io/confluentinc/cp-schema-registry'
    targetRepository: 'cache/confluentinc/cp-schema-registry'
  }
  {
    name: 'confluent-cp-zookeeper-531'
    sourceRepository: 'docker.io/confluentinc/cp-zookeeper'
    targetRepository: 'cache/confluentinc/cp-zookeeper'
  }
  {
    name: 'confluent-cp-enterprise-kafka-531'
    sourceRepository: 'docker.io/confluentinc/cp-enterprise-kafka'
    targetRepository: 'cache/confluentinc/cp-enterprise-kafka'
  }
  {
    name: 'confluent-cp-kafka-rest-531'
    sourceRepository: 'docker.io/confluentinc/cp-kafka-rest'
    targetRepository: 'cache/confluentinc/cp-kafka-rest'
  }
  {
    name: 'confluent-cp-enterprise-control-center-531'
    sourceRepository: 'docker.io/confluentinc/cp-enterprise-control-center'
    targetRepository: 'cache/confluentinc/cp-enterprise-control-center'
  }
  {
    name: 'cnfldemos-kafka-connect-datagen-013-531'
    sourceRepository: 'docker.io/cnfldemos/kafka-connect-datagen'
    targetRepository: 'cache/cnfldemos/kafka-connect-datagen'
  }
  {
    name: 'openjdk-8-jdk-alpine'
    sourceRepository: 'docker.io/library/openjdk'
    targetRepository: 'cache/library/openjdk'
  }
  {
    name: 'rabbitmq-3-management'
    sourceRepository: 'docker.io/library/rabbitmq'
    targetRepository: 'cache/library/rabbitmq'
  }
  {
    name: 'mysql-90'
    sourceRepository: 'docker.io/library/mysql'
    targetRepository: 'cache/library/mysql'
  }
]

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: {
    name: acrSku
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      retentionPolicy: {
        days: 7
        status: 'disabled'
      }
      trustPolicy: {
        status: 'disabled'
        type: 'Notary'
      }
    }
  }
}

resource credentialSet 'Microsoft.ContainerRegistry/registries/credentialSets@2023-11-01-preview' = {
  parent: registry
  name: dockerHubCredentialName
  properties: {
    loginServer: dockerHubLoginServer
    authCredentials: [
      {
        name: 'Credential1'
        usernameSecretIdentifier: dockerHubUsernameSecretUri
        passwordSecretIdentifier: dockerHubTokenSecretUri
      }
    ]
  }
}

resource cacheRule 'Microsoft.ContainerRegistry/registries/cacheRules@2023-11-01-preview' = [for rule in cacheRules: {
  parent: registry
  name: rule.name
  properties: {
    sourceRepository: rule.sourceRepository
    targetRepository: rule.targetRepository
    credentialSetResourceId: credentialSet.id
  }
}]

output acrName string = registry.name
output acrLoginServer string = registry.properties.loginServer
