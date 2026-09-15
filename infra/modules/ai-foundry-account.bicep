@description('Location of the Microsoft Foundry (Azure AI Services) account.')
param location string = resourceGroup().location

@description('Name of the Microsoft Foundry account. Must be globally unique; also used as the custom subdomain.')
param accountName string

@description('Pricing tier for the account.')
param sku string = 'S0'

@allowed([
  'Enabled'
  'Disabled'
])
@description('Whether public network access is allowed for this account.')
param publicNetworkAccess string = 'Enabled'

@description('Whether API-key authentication is allowed in addition to Microsoft Entra ID.')
param allowApiKeyAuth bool = true

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: sku
  }
  kind: 'AIServices'
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: !allowApiKeyAuth
    // Required so the account can host Foundry projects and model deployments.
    allowProjectManagement: true
  }
}

@description('Resource ID of the Foundry account.')
output id string = account.id

@description('Name of the Foundry account.')
output name string = account.name

@description('Base inference endpoint for models deployed under this account.')
output endpoint string = 'https://${account.name}.services.ai.azure.com/models'
