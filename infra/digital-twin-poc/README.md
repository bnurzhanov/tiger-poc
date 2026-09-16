---
title: Factory Edge to Microsoft Fabric Infrastructure
description: Deploy Event Hubs and a scoped producer identity without exposing credentials in deployment outputs.
---

This directory contains Bicep Infrastructure-as-Code templates for provisioning supporting Azure connectivity resources that bridge factory edge perception workloads into Microsoft Fabric Eventstream.

## Architecture

```text
[Edge Workload / Replay Simulator]
        |
        | AMQP (Managed Identity / Data Sender)
        v
[Azure Event Hubs]
        |
        | Eventstream Source (Workspace Identity / Listen Policy)
        v
[Microsoft Fabric Eventstream]
        |
        +---> [Fabric Eventhouse / KQL Database] ---> [Real-Time Dashboard & Power BI]
        |
        +---> [Fabric Digital Twin Builder (Ontology)]
```

## Resources Deployed

- Azure Event Hubs namespace (`Standard` by default) and `process-events` hub
- User-assigned managed identity with Azure Event Hubs Data Sender scoped to that hub
- `FabricConsumerPolicy` with `Listen` rights for an optional Fabric SAS connection

The templates do not create Fabric resources, a compute host, a Key Vault, or a
Fabric workspace identity role assignment. No access keys or connection strings
are returned by either the root or nested deployment.

## Deployment Commands

Run from the repository root with Azure CLI and Bicep installed. The deploying
principal needs permission to create these resources and role assignments at the
target scope, including `Microsoft.Authorization/roleAssignments/write`.

NOTE: This should be a script

```bash
RESOURCE_GROUP="rg-tiger-edge-dev"
DEPLOYMENT_NAME="deploy-tiger-edge-$(date +%Y%m%dT%H%M%S)"

az group create --name "$RESOURCE_GROUP" --location eastus --output none
az deployment group create \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
  --template-file infra/digital-twin-poc/main.bicep \
        --parameters infra/digital-twin-poc/main.bicepparam \
        --output none

az deployment group show \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.outputs.{namespace:eventHubNamespaceHostname.value,hub:eventHubName.value,eventHubId:eventHubId.value,clientId:managedIdentityClientId.value,identityResourceId:managedIdentityResourceId.value}' \
        --output json
```

Continue only after deployment succeeds. Keep `DEPLOYMENT_NAME` for later lookups;
do not generate a new timestamp when reading this deployment's outputs. The query
above selects only nonsecret configuration.

## Producer Authentication

For an Azure-hosted relay, attach the identity from `managedIdentityResourceId`
to the compute host using that service's identity settings. Configure the relay's
process environment from these deployment outputs:

| Environment variable | Deployment output |
| --- | --- |
| `FABRIC_EVENTSTREAM_NAMESPACE` | `eventHubNamespaceHostname` |
| `FABRIC_EVENTSTREAM_EVENTHUB_NAME` | `eventHubName` |
| `AZURE_CLIENT_ID` | `managedIdentityClientId` |

The template grants the sender role to `managedIdentityPrincipalId`, not the
client ID. Allow time for RBAC propagation before testing. `DefaultAzureCredential`
reads `AZURE_CLIENT_ID` to select its user-assigned managed-identity candidate;
other configured credentials can precede it in the chain.

For local WSL/laptop execution, use an authenticated developer credential and
grant that developer principal Azure Event Hubs Data Sender on `eventHubId`
separately. Setting `AZURE_CLIENT_ID` does not attach or impersonate an Azure
managed identity locally. Follow the [detect relay guide](../../apps/detect/README.md#fabric-publishing-and-edge-migration)
to send demo events or completed JSONL files.

## Fabric Consumer Authentication

The Fabric consumer is separate from the producer. Prefer the Event Hubs
connector's extended features with Workspace identity authentication where
available. Enable identity in Fabric Workspace settings, grant that workspace
identity Azure Event Hubs Data Receiver on `eventHubId`, and select Workspace
identity in the connection. These steps are not performed by this template.
See [Microsoft Learn's Event Hubs source setup](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/add-source-azure-event-hubs).

For a Shared Access Key connection, use `fabricConsumerPolicyName`
(`FabricConsumerPolicy`), which has only `Listen` rights. An authorized operator
can obtain its key through the Event Hub's Shared access policies blade and enter
it directly into Fabric's connection credentials UI. Store any retained copy in
an approved Key Vault with restricted access; automation should expose only a
secret reference, never its value. Do not print keys or connection strings in
terminal/CI logs, pass them through ordinary deployment outputs, or commit them.
This template does not provision or populate a vault. It retains local SAS
authentication for this fallback; do not disable it until all SAS clients have
migrated. Continue with the [Fabric setup guide](../../apps/fabric/README.md#setup).


