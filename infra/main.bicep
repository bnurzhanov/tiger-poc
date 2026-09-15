@description('Location to create the Microsoft Foundry account in.')
param location string = resourceGroup().location

@description('Name of the Microsoft Foundry account to create. Must be globally unique.')
param accountName string

@description('Pricing tier for the account.')
param accountSku string = 'S0'

@allowed([
  'Enabled'
  'Disabled'
])
@description('Whether public network access is allowed for this account.')
param publicNetworkAccess string = 'Enabled'

@description('Whether API-key authentication is allowed in addition to Microsoft Entra ID.')
param allowApiKeyAuth bool = true

@description('List of models to deploy, each with provider, name, version, sku and capacity. Defaults to models.json.')
param models array = loadJsonContent('models.json')

module foundryAccount 'modules/ai-foundry-account.bicep' = {
  name: 'foundry-account'
  params: {
    accountName: accountName
    location: location
    sku: accountSku
    publicNetworkAccess: publicNetworkAccess
    allowApiKeyAuth: allowApiKeyAuth
  }
}

// Foundry model deployments on the same account must be created one at a time.
@batchSize(1)
module modelDeployments 'modules/model-deployment.bicep' = [
  for item in models: {
    name: 'deployment-${item.name}'
    params: {
      accountName: accountName
      modelName: item.name
      modelVersion: item.version
      modelPublisher: item.provider
      skuName: item.sku
      capacity: item.capacity
    }
    dependsOn: [
      foundryAccount
    ]
  }
]

@description('Resource ID of the Foundry account.')
output accountId string = foundryAccount.outputs.id

@description('Base inference endpoint for models deployed under this account.')
output endpoint string = foundryAccount.outputs.endpoint

@description('Names of the model deployments created under the account, usable as the "model" value in inference requests.')
output deployedModels array = [for i in range(0, length(models)): modelDeployments[i].outputs.deploymentName]
