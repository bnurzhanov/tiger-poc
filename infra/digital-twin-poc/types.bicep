metadata name = 'factory-edge-types'
metadata description = 'Shared type definitions for the Factory Edge to Microsoft Fabric deployment.'

@description('Deployment environment name.')
@export()
type Environment = 'dev' | 'test' | 'prod'

@description('SKU configuration for Event Hubs namespace.')
@export()
type EventHubSku = {
  @description('Name of the Event Hubs SKU.')
  name: 'Basic' | 'Standard' | 'Premium'
  @description('Messaging capacity units.')
  capacity: int
}

@description('Tag dictionary for resource governance.')
@export()
type ResourceTags = {
  @description('Project or accelerator name.')
  project: string
  @description('Environment stage.')
  environment: string
  @description('Workload identifier.')
  workload: string
}
