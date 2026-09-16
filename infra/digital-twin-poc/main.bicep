metadata name = 'factory-edge-digital-twin-main'
metadata description = 'Main orchestration template for Factory Edge to Microsoft Fabric ingestion infrastructure.'

import { Environment, ResourceTags } from './types.bicep'

@description('Azure deployment location.')
param location string = resourceGroup().location

@description('Deployment environment.')
param environment Environment = 'dev'

@description('Unique suffix for resource names.')
param resourceSuffix string = uniqueString(resourceGroup().id)

@description('Base name for the factory edge ingestion resources.')
param baseName string = 'tiger-edge'

@description('Event Hubs SKU configuration.')
param skuName 'Basic' | 'Standard' | 'Premium' = 'Standard'

@description('Tags applied to all provisioned resources.')
param tags ResourceTags = {
  project: 'factory-perception-poc'
  environment: environment
  workload: 'edge-to-fabric-digital-twin'
}

var formattedSuffix = take(resourceSuffix, 6)
var eventHubNamespaceName = '${baseName}-ehns-${environment}-${formattedSuffix}'
var eventHubName = 'process-events'
var identityName = '${baseName}-id-${environment}-${formattedSuffix}'

/*
  Deploy User-Assigned Managed Identity
*/
module identityModule 'modules/identity.bicep' = {
  name: 'deploy-identity'
  params: {
    location: location
    identityName: identityName
    tags: tags
  }
}

/*
  Deploy Event Hubs Namespace and Topic for Fabric Eventstream ingestion
*/
module eventHubModule 'modules/eventhub.bicep' = {
  name: 'deploy-eventhub'
  params: {
    location: location
    namespaceName: eventHubNamespaceName
    eventHubName: eventHubName
    producerPrincipalId: identityModule.outputs.principalId
    skuName: skuName
    tags: tags
  }
}

@description('Event Hubs Namespace Name.')
output eventHubNamespaceName string = eventHubNamespaceName

@description('Event Hub Topic Name.')
output eventHubName string = eventHubName

@description('Event Hubs namespace hostname for producer authentication.')
output eventHubNamespaceHostname string = eventHubModule.outputs.namespaceHostname

@description('Resource ID of the Event Hub for scoped role assignments.')
output eventHubId string = eventHubModule.outputs.eventHubId

@description('Name of the optional Listen-only Fabric consumer policy; no key is returned.')
output fabricConsumerPolicyName string = eventHubModule.outputs.fabricConsumerPolicyName

@description('Managed Identity Client ID.')
output managedIdentityClientId string = identityModule.outputs.clientId

@description('Managed Identity Principal ID for role assignments.')
output managedIdentityPrincipalId string = identityModule.outputs.principalId

@description('Managed Identity Resource ID for host attachment.')
output managedIdentityResourceId string = identityModule.outputs.identityId
