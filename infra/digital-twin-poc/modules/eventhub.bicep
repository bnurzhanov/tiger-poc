metadata name = 'eventhub-module'
metadata description = 'Azure Event Hubs module for Fabric Eventstream Custom App ingestion endpoint.'

import { ResourceTags } from '../types.bicep'

@description('Azure region for the Event Hubs namespace.')
param location string

@description('Name of the Event Hubs namespace.')
param namespaceName string

@description('Name of the Event Hub for process events.')
param eventHubName string

@description('Principal ID of the managed identity authorized to publish process events.')
param producerPrincipalId string

@description('SKU name for Event Hubs namespace. Managed identity producer auth requires Standard or Premium.')
@allowed([
  'Standard'
  'Premium'
])
param skuName string = 'Standard'

@description('Capacity units for the namespace.')
param skuCapacity int = 1

@description('Message retention in days.')
param messageRetentionInDays int = 1

@description('Partition count for the Event Hub.')
param partitionCount int = 2

@description('Resource tags.')
param tags ResourceTags

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  sku: {
    name: skuName
    tier: skuName
    capacity: skuCapacity
  }
  tags: tags
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubNamespace
  name: eventHubName
  properties: {
    messageRetentionInDays: messageRetentionInDays
    partitionCount: partitionCount
  }
}

var senderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2b629674-e913-4c01-ae53-ef4638d8f975')

resource producerSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHub.id, producerPrincipalId, senderRoleDefinitionId)
  scope: eventHub
  properties: {
    principalId: producerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: senderRoleDefinitionId
  }
}

resource fabricConsumerAuthRule 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2024-01-01' = {
  parent: eventHub
  name: 'FabricConsumerPolicy'
  properties: {
    rights: [
      'Listen'
    ]
  }
}

@description('Resource ID of the Event Hubs Namespace.')
output namespaceId string = eventHubNamespace.id

@description('Name of the Event Hub.')
output eventHubName string = eventHub.name

@description('Service Bus / Event Hubs Endpoint URL.')
output serviceBusEndpoint string = eventHubNamespace.properties.serviceBusEndpoint

@description('Namespace hostname for Event Hubs SDK authentication.')
output namespaceHostname string = parseUri(eventHubNamespace.properties.serviceBusEndpoint).host

@description('Resource ID of the Event Hub.')
output eventHubId string = eventHub.id

@description('Name of the optional Listen-only Fabric consumer policy; no key is returned.')
output fabricConsumerPolicyName string = fabricConsumerAuthRule.name
