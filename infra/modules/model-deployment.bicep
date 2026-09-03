@description('Name of the Microsoft Foundry account to deploy the model into. The account must already exist.')
param accountName string

@description('Catalog name of the model to deploy, e.g. "Phi-3.5-vision-instruct".')
param modelName string

@description('Catalog version of the model to deploy.')
param modelVersion string

@allowed([
  'AI21 Labs'
  'Cohere'
  'Core42'
  'DeepSeek'
  'xAI'
  'Meta'
  'Microsoft'
  'Mistral AI'
  'OpenAI'
  'NTT DATA'
]
)
@description('Publisher of the model in the Foundry model catalog.')
param modelPublisher string

@allowed([
  'GlobalStandard'
  'DataZoneStandard'
  'Standard'
  'GlobalProvisioned'
  'Provisioned'
])
@description('Deployment SKU (throughput/availability tier) for the model.')
param skuName string = 'GlobalStandard'

@description('Deployment capacity, in the units defined by the chosen SKU (e.g. thousands of tokens per minute).')
param capacity int = 1

@description('Name of the content-filter (RAI) policy to apply. Use "Microsoft.DefaultV2" for the built-in default.')
param contentFilterPolicyName string = 'Microsoft.DefaultV2'

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: accountName
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: modelName
  sku: {
    name: skuName
    capacity: capacity
  }
  properties: {
    model: {
      format: modelPublisher
      name: modelName
      version: modelVersion
    }
    raiPolicyName: contentFilterPolicyName
  }
}

@description('Resource ID of the model deployment.')
output id string = deployment.id

@description('Deployment name, used as the model name in inference requests.')
output deploymentName string = deployment.name
