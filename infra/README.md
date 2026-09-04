# Microsoft Foundry model deployment (IaC)

Bicep templates that provision a [Microsoft Foundry](https://ai.azure.com) account
(`Microsoft.CognitiveServices/accounts`, kind `AIServices`) and deploy one or more
models from the Foundry model catalog into it. This gives the "Foundry in the
cloud" runtime described in [`../docs/mvp-design.md`](../docs/mvp-design.md) a
repeatable, code-reviewed provisioning path that can be compared against a
Foundry Local deployment of a small on-device model.

## Layout

```text
infra/
├── main.bicep                        # entry point: account + N model deployments
├── models.json                       # default list of models to deploy
├── main.parameters.json              # example parameter file
└── modules/
    ├── ai-foundry-account.bicep      # the Foundry (AIServices) account
    └── model-deployment.bicep        # a single model deployment on that account
```

## Prerequisites

* [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) with the Bicep tooling (`az bicep install`)
* An Azure subscription and a resource group to deploy into
* Quota for the chosen models/SKUs in the target region

## Deploy

```bash
az login
az account set --subscription "<subscription-id>"

az group create --name rg-tiger-poc-foundry --location eastus2

az deployment group create \
  --resource-group rg-tiger-poc-foundry \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json
```

Edit `infra/models.json` to change which models get deployed, or override
`accountName`/`location` in `main.parameters.json` (or on the command line)
before deploying.

Each entry in `models.json` maps to one
`Microsoft.CognitiveServices/accounts/deployments` resource:

```json
{
  "provider": "Microsoft",
  "name": "Phi-3.5-vision-instruct",
  "version": "2",
  "sku": "GlobalStandard",
  "capacity": 1
}
```

Model deployments on the same account are created serially
(`@batchSize(1)`), which is required by the Foundry control plane.

## Outputs

* `endpoint` — base inference endpoint, `https://<accountName>.services.ai.azure.com/models`
* `deployedModels` — the deployment names to use as the `model` value when
  calling the OpenAI-compatible chat-completions API
* `accountId` — resource ID of the Foundry account

## Recommended vision-capable models

For comparing a cloud-hosted Foundry model against a small model running
locally (e.g. via Foundry Local), the following catalog models support image
input and are configured by default in `models.json`:

| Model | Provider | Size class | Notes |
|---|---|---|---|
| `Phi-3.5-vision-instruct` | Microsoft | Small (~4B) | Closest size/family match to models typically run locally via Foundry Local; good default baseline for a local-vs-cloud comparison. |
| `Phi-4-multimodal-instruct` | Microsoft | Small (~5.6B) | Newer Microsoft small multimodal model (vision + audio + text); also available in Foundry Local's catalog, so the same model family can be run both locally and in the cloud. |
| `gpt-4o-mini` | OpenAI | Small/low-cost | Vision-capable, cheap, low-latency cloud baseline when a Phi-family model isn't available locally. |
| `gpt-4o` | OpenAI | Large | Highest-quality cloud vision baseline, useful as an upper bound when judging accuracy trade-offs. |
| `Llama-3.2-11B-Vision-Instruct` | Meta | Medium (~11B) | Open-weight vision model; a useful mid-size point between the small Phi models and GPT-4o. |

Guidance:

* For a fair "small local model vs. small cloud model" comparison, prefer
  `Phi-3.5-vision-instruct` or `Phi-4-multimodal-instruct` — both have
  same-family counterparts in the Foundry Local catalog, so the local and
  cloud adapters can run comparable model sizes and architectures.
* Keep `gpt-4o` / `gpt-4o-mini` in the list only as a quality/cost reference
  point; they have no equivalent-size local counterpart.
* Not every model/SKU combination is available in every region or
  subscription; check quota before deploying, and remove entries from
  `models.json` that aren't available to you.
