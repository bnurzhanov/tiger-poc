<!-- markdownlint-disable-file -->
# Foundry Local Platform Research

Date: 2026-09-02
Status: Complete (with explicitly-flagged gaps)
Scope: Microsoft Foundry Local — the on-device / local inference runtime and SDK.

Target environment for the consuming project: **Ubuntu running under WSL2 on Windows**.

## Research Questions

1. What is Foundry Local, and how does it relate to Microsoft Foundry / Azure AI Foundry and "Azure Local"? Standalone local inference server?
2. Supported operating systems — is Linux supported? Ubuntu? WSL2?
3. Installation commands per platform, CLI name and common commands.
4. API surface — OpenAI-compatible HTTP endpoint, default port, endpoint discovery.
5. Python SDK — PyPI package, class names, key methods, minimal example, combination with `openai`.
6. Hardware acceleration — execution providers, minimum hardware requirements.
7. Model catalog — concrete model names/aliases, ONNX/ONNX Runtime.
8. Known limitations, preview status, licensing caveats.

## HEADLINE FINDING (Q2 — Linux / WSL2)

**Linux IS officially supported.** Microsoft Learn and the official GitHub README both state platform support explicitly:

> "Foundry Local supports Windows, macOS (Apple silicon), and Linux."
> — [What is Foundry Local?](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local) (FAQ → "What platforms are supported?")
> — [microsoft/Foundry-Local README](https://github.com/microsoft/Foundry-Local) (FAQ → "What platforms are supported?")

Supporting evidence for Linux being first-class, not incidental:

- v1.0.0 GA release notes publish a platform-support matrix: Windows (x64, ARM64), macOS (ARM64), **Linux (x64)** — [v1.0.0 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.0.0).
- v1.2.0 added "support for Linux ARM64 / aarch64" — [v1.2.0 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.2.0).
- v2.0.1 (latest at time of research) explicitly improved Linux packaging: "Linux and ARM64 packaging has been improved. Linux packages now target `manylinux_2_28` compatibility"; and fixed "Linux Python wheels now use valid `manylinux_2_28_x86_64` and `manylinux_2_28_aarch64` tags", "Fixed Linux HTTPS failures caused by unavailable CA bundle paths", "common CA bundle discovery and `SSL_CERT_FILE` support" — [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1).
- PyPI `foundry-local-sdk` Requirements section: "Windows (x64), Linux (x64), or macOS (arm64)"; classifiers include `Operating System :: POSIX :: Linux` — [PyPI foundry-local-sdk](https://pypi.org/project/foundry-local-sdk/).
- The architecture doc names the native library per-OS: "`.dll` on Windows, `.so` on Linux, and `.dylib` on macOS"; and "On Linux and macOS, the Core API registers execution providers directly with ONNX Runtime without a platform intermediary" — [Foundry Local architecture overview](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture).
- CLI release assets ship `foundry-<ver>-linux-x64.tar.gz` and `foundry-<ver>-linux-arm64.tar.gz` — [CLI preview 0.10.3 release](https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-0.10.3).

### What the docs do NOT say (uncertainty — read carefully)

- **WSL2 is never named as a supported platform in the product documentation.** No Microsoft Learn Foundry Local page, no release note, and no README section mentions WSL, WSL2, or Windows Subsystem for Linux as a supported target.
- The only WSL references anywhere in `microsoft/Foundry-Local` are in **C++ developer tooling**, not product support statements:
  - `sdk_v2/cpp/cmake/Sanitizers.cmake`: "FOUNDRY_LOCAL_ENABLE_ASAN=ON is only supported on Linux (including WSL)."
  - `sdk_v2/cpp/scripts/run_sanitizer_tests.py`: "It runs on Linux / WSL only".
  - `.github/instructions/cpp-memory-validation.instructions.md`: "**Linux / WSL only** ... Linux or WSL (Ubuntu 22.04+ recommended)."
  These confirm Microsoft engineers build and test the native runtime on Linux/WSL Ubuntu, but they are about an ASAN/UBSAN validation pass, not a supported-runtime claim.
- **No specific Linux distribution or version is named** in the product docs. "Ubuntu" appears only in the sanitizer instructions above ("Ubuntu 22.04+ recommended").
- The practical, citable Linux compatibility floor is the wheel tag: `manylinux_2_28` → glibc ≥ 2.28. Ubuntu 20.04 (glibc 2.31), 22.04 (2.35), and 24.04 (2.39) all clear that bar. This is an inference from the packaging tags in the [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1), not an explicit Microsoft support statement about Ubuntu.

### Assessment for Ubuntu-on-WSL2

- CPU inference on Ubuntu x64 under WSL2 is very likely to work: WSL2 runs a real Linux kernel with glibc from the distro, and the SDK ships a plain `manylinux_2_28_x86_64` wheel with a bundled `libfoundry_local.so`, ONNX Runtime, and ONNX Runtime GenAI. Nothing in the documented Linux path requires systemd, a display server, or Windows-side integration.
- GPU acceleration under WSL2 is **undocumented and unverified**. Docs list CUDA as available on "Windows, Linux" ([architecture — hardware abstraction](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture)), but WSL2 CUDA passthrough is never discussed. WebGPU/Dawn under WSLg is likewise undocumented. Treat GPU on WSL2 as "must be empirically tested".
- On Linux there is **no WinML layer** — the Windows-only plugin EP ecosystem (QNN, OpenVINO, VitisAI, TensorRT RTX) is not available. See Q6.
- Bottom line: **Linux support = documented and explicit. WSL2 support = not documented either way; not endorsed, not excluded.** If the project needs a supported-configuration guarantee, this is a gap to raise with Microsoft or validate by running it.

## Q1 — What Foundry Local is, and how it relates to other "Foundry"/"Local" products

Definition (Microsoft Learn):

> "Foundry Local is an end-to-end local AI solution for shipping applications that run entirely on your device. ... It provides an easy-to-use SDK (C#, JavaScript, Rust, and Python), a curated catalog of optimized models, and automatic hardware acceleration—all in a lightweight package."
> — [What is Foundry Local?](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)

Key structural facts:

- **It is NOT primarily a standalone inference server.** The docs answer this directly: "Is Foundry Local a web server and CLI tool? **No.** Foundry Local is an end-to-end local AI solution that your application ships with. It handles model acquisition, hardware acceleration, and inference inside your app process through the SDK. The optional web server and CLI are available for development workflows, but the core product is the local AI runtime and SDK that you integrate directly into your application." — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)
- Architecture: a native Core API library (`.so` on Linux) loaded **in-process** by your app via a language SDK; it calls ONNX Runtime for execution and the cloud-hosted Foundry Catalog for model acquisition. Runtime footprint ≈ 20 MB. — [architecture overview](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture), [README](https://github.com/microsoft/Foundry-Local)
- An **optional** OpenAI-compatible HTTP server can be started from within the app process for multi-process/REST scenarios (LangChain, Open WebUI). — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local), [architecture — optional REST API](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture)

Relationship to Microsoft Foundry / Azure AI Foundry:

- Documented under the Foundry docset (`ms.service: microsoft-foundry`, `ms.subservice: foundry-local`) and shares the Foundry model catalog brand, but **no Azure subscription is required and no cloud inference occurs**: "Is an Azure subscription required? No. Foundry Local runs entirely on local hardware." — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)
- Network is used only for model/EP downloads and optional diagnostics; prompts and outputs are processed locally. — same page.

Relationship to "Azure Local" (a genuinely different product):

- **Foundry Local on Azure Local** is a separate offering: an Azure Arc extension on an Arc-enabled Kubernetes cluster, with `Model` and `ModelDeployment` CRDs, an inference operator, API-key/Entra ID auth, TLS gateway, and both ONNX-GenAI and vLLM engines. It is for enterprise-scale, multi-node, on-premises inference, and it **is in preview and requires requesting deployment access**. — [What is Foundry Local on Azure Local?](https://learn.microsoft.com/en-us/azure/azure-sovereign-clouds/private/foundry-local/what-is-foundry-local-on-azure-local)
- The device-side page explicitly disambiguates: "If you need enterprise-scale AI inference on your own infrastructure with Kubernetes-native operations and Azure Arc management instead, see Foundry Local on Azure Local." — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)
- **Do not conflate the two.** For a single Ubuntu/WSL2 dev box, the relevant product is plain Foundry Local (SDK), not Foundry Local on Azure Local.

Also explicitly out of scope per Microsoft:

> "Can Foundry Local run on a server? ... it isn't designed as a server inference stack. Server-oriented runtimes like vLLM or Triton Inference Server are built for multi-user scenarios ... Foundry Local doesn't provide these capabilities."
> — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)

And: "Foundry Local is for on-device inference, not distributed, containerized, or multi-machine production deployments." — [Best practices and troubleshooting](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-best-practice)

## Q3 — Installation

There are two independent things to install. For an application (including a Python pipeline), **only the SDK is required** — the CLI is a development convenience.

### A. SDK (recommended path; works on Linux)

| Language | Command | Source |
| --- | --- | --- |
| Python | `pip install foundry-local-sdk` | [README](https://github.com/microsoft/Foundry-Local), [PyPI](https://pypi.org/project/foundry-local-sdk/) |
| Python + REST/LangChain client | `pip install foundry-local-sdk openai` | [get-started (Cross-Platform tab)](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started) |
| JavaScript | `npm install foundry-local-sdk` | [README](https://github.com/microsoft/Foundry-Local) |
| C# | `dotnet add package Microsoft.AI.Foundry.Local` | [get-started](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started) |
| Rust | `cargo add foundry-local-sdk` | [get-started](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started) |

Notes:

- Docs present **"Windows" vs "Cross-Platform" tabs**. The Windows tab uses `-winml` package variants (`foundry-local-sdk-winml`, `Microsoft.AI.Foundry.Local.WinML`) that integrate with the Windows ML runtime for broader hardware acceleration. The **Cross-Platform tab is the correct tab for Linux** and uses the plain package. — [get-started](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started)
- **As of v2.0.1 the `-winml` split is gone**: "There is now one package per SDK; separate `-winml` packages are no longer needed"; migration table says Python `foundry-local-sdk-winml` → `foundry-local-sdk`. Docs pages still show the old two-tab guidance in places — a docs/release lag to be aware of. — [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1)
- The Python wheel bundles the native library and depends on `onnxruntime` and `onnxruntime-genai-core` on every platform. A helper entry point `foundry-local-install` installs/verifies native binaries. — [PyPI](https://pypi.org/project/foundry-local-sdk/)

### B. CLI (`foundry`) — preview

| Platform | Install command | Source |
| --- | --- | --- |
| Windows | `winget install Microsoft.FoundryLocal` | [CLI reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli) |
| macOS (Apple Silicon) | `brew tap microsoft/foundrylocal` then `brew install foundrylocal` | [CLI reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli) |
| Linux x64 | `tar xzf foundry-0.10.3-linux-x64.tar.gz` → `cd foundry-0.10.3-linux-x64` → `./lib/foundry --version` | [CLI preview 0.10.3 release](https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-0.10.3) |
| Linux ARM64 | `foundry-0.10.3-linux-arm64.tar.gz` (same tarball pattern) | [CLI preview 0.10.3 release](https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-0.10.3) |

**Important asymmetry:** the Microsoft Learn CLI reference only documents install for Windows (winget) and macOS (brew). **It does not document a Linux install path at all.** Linux tarballs exist only as GitHub release assets and on the [foundrylocal.ai model catalog page](https://www.foundrylocal.ai/models) ("Linux CLI download on GitHub"). Similarly, Upgrade/Uninstall instructions on Learn cover only Windows/macOS. Direct download shortcut: <https://aka.ms/foundry-local-installer>.

Verify: `foundry --version`, `foundry --help`.

### Common CLI commands

Command groups: Model (`model`, `cache`), Run (`run`, `chat`, `complete`, `transcribe`), Server (`server`), Setup (`config`), Help (`status`, `report`). — [CLI reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli)

```bash
foundry status                                    # system info + server state
foundry model list                                # available models (downloads EPs on first run)
foundry model list --device gpu --type chat       # filters: --device cpu|gpu|npu, --type chat|speech|embedding
foundry model list --variants --verbose           # per-hardware variants, license/model ID columns
foundry model download <model>                    # cache without running
foundry model load <model> / foundry model unload <model>
foundry model info <model>                        # (v2 CLI: foundry model show <model>)
foundry run qwen2.5-0.5b                          # auto-routes to chat or transcription
foundry chat qwen2.5-0.5b                         # interactive chat
foundry complete <model> "<prompt>"               # one stateless completion
foundry transcribe -m whisper-tiny -f audio.wav
foundry server start --port 39839 --idle-timeout 0
foundry server status                             # prints local endpoint URL(s), PID, uptime, log path
foundry server stop | restart | logs [-n N] [-f]
foundry cache location | list | cd <path> | remove [<model>] [--force]
foundry config show | set log-level debug | reset log-level
foundry report                                    # pre-filled GitHub issue with diagnostics
```

Sources: [CLI reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli), [CLI preview 0.10.3 release](https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-0.10.3).

**CLI naming caveat (matters for the user's question):** the older service-based CLI used `foundry service start|stop|restart|ps|diag` and `foundry model run <alias>`. The current CLI replaced these with `foundry server ...` and `foundry run <alias>`. The user's phrasing "`foundry service status`" / "`foundry model run`" reflects the **legacy** CLI. Current equivalents: `foundry server status` and `foundry run <alias>`. — [CLI preview 0.10.0/0.10.3 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-0.10.3). Note Learn's CLI reference still documents `foundry model list/info/download/load/unload` alongside `foundry server ...`, so both `model` and `server` groups are current; only `service` is retired.

Most commands accept `--output json` for scripting.

## Q4 — API surface (OpenAI compatibility, port, discovery)

- **OpenAI-compatible: yes.** "OpenAI-compatible API — Supports OpenAI request and response formats including the OpenAI Responses API format. If your application already uses the OpenAI SDK, point it to a Foundry Local endpoint with minimal code changes." — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)
- The HTTP server is **optional and started from your process**, not a background daemon you must run. — [architecture — optional REST API](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture)

### Endpoints

OpenAI-compatible surface (v1):

- `POST /v1/chat/completions` — "fully compatible with the OpenAI Chat Completions API" (supports `model`, `messages`, `temperature`, `top_p`, `n`, `stream`, `stop`, `max_tokens`/`max_completion_tokens`, penalties, `tools`, plus Foundry extras `top_k`, `random_seed`, `ep`, `ttl`).
- `POST /v1/audio/transcriptions` — multipart, OpenAI-compatible.
- `POST /v1/chat/completions/tokenizer/encode/count` — token counting without inference.
- v2 retains: `/v1/chat/completions`, `/v1/models`, `/v1/models/{model_id}`, `/v1/embeddings`, `/v1/audio/transcriptions`, `/v1/responses` (with response retrieval and input-item operations), image/audio inputs, and SSE streaming.

Foundry management surface:

- `GET /openai/status` → `{ "Endpoints": [...], "ModelDirPath": ..., "PipeName": ... }`
- `GET /foundry/list` (catalog), `GET /openai/models` (cached), `GET /openai/loadedmodels`
- `POST /openai/download`, `GET /openai/load/{name}?ttl=&ep=`, `GET /openai/unload/{name}?force=`, `GET /openai/unloadall`
- `GET /openai/getgpudevice`, `GET /openai/setgpudevice/{deviceId}`

Sources: [REST API reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest), [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1).

### Default port and base URL — IMPORTANT

**There is no stable default port. The port is dynamic by default.** The docs are emphatic:

> "Replace `<PORT>` with the dynamic port of the Foundry Local service ... In the SDK, use `manager.endpoint` (JS) or `config.Web.Urls` (C#) to get the endpoint — **never hardcode the port**."
> — [REST API reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest)

> "Copy the endpoint URL. Foundry Local assigns a dynamic port each time the server starts."
> — [CLI reference — Open WebUI section](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli)

Base URL shape: `http://localhost:<PORT>/v1`. Port numbers seen in official material are examples only, not defaults: `5272` (in the `/openai/status` sample response, [REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest)), `39839` (fixed-port CLI example, [CLI reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli)), `5764` and `6543` (JS sample code, [LangChain how-to](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-use-langchain-with-foundry-local) and repo `samples/js/copilot-sdk-foundry-local`).

### Programmatic endpoint discovery

- Python: `manager.start_web_service()` then `manager.urls` → `base_url = f"{manager.urls[0]}/v1"`. — [LangChain how-to, Python](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-use-langchain-with-foundry-local), [PyPI](https://pypi.org/project/foundry-local-sdk/)
- JS: `manager.endpoint`; C#: `config.Web.Urls`. — [REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest)
- You can also pin a port: SDK config accepts web service URLs (JS `webServiceUrls: 'http://localhost:5764'`), or CLI `foundry server start --port 39839 --idle-timeout 0`, then read it back with `foundry server status` or `GET /openai/status`.

## Q5 — Python SDK

- Package: **`foundry-local-sdk` on PyPI**, import name `foundry_local_sdk`. Latest version at research time: **2.0.1**, released 2026-08-31, maintainer `microsoft`, license MIT. — [PyPI](https://pypi.org/project/foundry-local-sdk/)
- Requires **Python 3.11+** (`Requires: Python <3.15, >=3.11`); single `cp311-abi3` wheel. Platforms: Windows x64, Linux x64, macOS arm64. Development Status classifier is **3 - Alpha**. — [PyPI](https://pypi.org/project/foundry-local-sdk/)
- Binding mechanism: `cffi` (API mode) into the native `foundry_local.{dll,so,dylib}`. In-process — no HTTP hop, no separate service. — [PyPI](https://pypi.org/project/foundry-local-sdk/)

### Core API objects (v2)

| Symbol | Role |
| --- | --- |
| `Configuration(app_name=..., model_cache_dir=..., log_level=...)` | SDK config |
| `FoundryLocalManager.initialize(config)` / `FoundryLocalManager.instance` | Singleton entry point |
| `manager.catalog` → `Catalog` | `list_models()`, `get_model(alias)`, `get_model_variant(id)`, `get_cached_models()`, `get_loaded_models()` |
| `IModel` | `.id`, `.alias`, `.context_length`, `.input_modalities`, `.capabilities`, `.supports_tool_calling`, `.is_cached`, `.is_loaded`, `.download(cb)`, `.load()`, `.unload()` |
| `manager.discover_eps()` / `manager.download_and_register_eps(progress_callback=...)` | Execution provider management (`EpInfo`, `EpDownloadResult`) |
| `ChatSession`, `EmbeddingsSession`, `AudioSession` | Typed sessions (context managers) |
| Session methods | `process_request(request)`, `process_streaming_request(request)`, `set_options(RequestOptions)`, `set_streaming(bool)`; `ChatSession` adds `add_tool_definition(...)`, `turn_count`, `undo_turns(n)` |
| `Request`, `Response`, `RequestOptions`, `SearchOptions`, `FinishReason`, `TokenUsage` | Request/response types |
| Items | `TextItem`, `MessageItem` (`.system/.user/.assistant`), `ImageItem`, `AudioItem`, `BytesItem`, `ToolCallItem`, `ToolResultItem`, `TensorItem`, `ItemQueue` |
| `manager.start_web_service()` / `manager.urls` / `manager.stop_web_service()` | Optional OpenAI-compatible HTTP server |

Source: [PyPI foundry-local-sdk](https://pypi.org/project/foundry-local-sdk/).

### Minimal native (in-process) example — v2 Session API

```python
from foundry_local_sdk import (
    ChatSession, Configuration, FoundryLocalManager,
    MessageItem, Request, RequestOptions, SearchOptions, TextItem,
)

config = Configuration(app_name="MyApp")
FoundryLocalManager.initialize(config)
manager = FoundryLocalManager.instance

model = manager.catalog.get_model("qwen2.5-0.5b")
model.download(lambda pct: print(f"\rDownloading: {pct:.1f}%", end="", flush=True))
model.load()

with ChatSession(model) as session:
    session.set_options(RequestOptions(search=SearchOptions(temperature=0.0, max_output_tokens=128)))
    with Request().add_item(MessageItem.user("Why is the sky blue?")) as req:
        with session.process_request(req) as response:
            for item in response:
                if isinstance(item, TextItem):
                    print(item.text)

model.unload()
```

Source: [PyPI quick start](https://pypi.org/project/foundry-local-sdk/).

### Simpler in-process form shown in current Learn docs (deprecated client style)

```python
from foundry_local_sdk import Configuration, FoundryLocalManager

config = Configuration(app_name="foundry_local_samples")
FoundryLocalManager.initialize(config)
manager = FoundryLocalManager.instance

manager.download_and_register_eps(progress_callback=lambda ep, pct: None)

model = manager.catalog.get_model("qwen2.5-0.5b")
model.download()
model.load()

client = model.get_chat_client()
for chunk in client.complete_streaming_chat([{"role": "user", "content": "What is the golden ratio?"}]):
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)

model.unload()
```

Source: [get-started, Python Cross-Platform tab](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started), [README](https://github.com/microsoft/Foundry-Local).

**Deprecation warning:** v2.0.1 states "In-process OpenAI-style SDK clients are replaced by the Session API... The deprecated OpenAI-style clients remain temporarily available in C#, Python, JavaScript/TypeScript, and Rust to ease migration" and "Direct OpenAI-style in-process clients remain available but are deprecated and **scheduled for removal at the end of 2026**." Prefer `ChatSession`. — [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1)

### Combining with the `openai` package (HTTP path)

Docs install `pip install foundry-local-sdk openai` for the cross-platform Python path ([get-started](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started)). The documented pattern is: start the built-in web service, read the URL from the manager, point an OpenAI-protocol client at `<url>/v1` with a dummy API key. The Learn sample uses `langchain_openai.ChatOpenAI`, which is the OpenAI client protocol:

```python
manager.start_web_service()
base_url = f"{manager.urls[0]}/v1"

llm = ChatOpenAI(base_url=base_url, api_key="none", model=model.id)
# ... later
manager.stop_web_service()
```

Source: [Build a translation app with LangChain — Python](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-use-langchain-with-foundry-local).

The equivalent with the raw `openai` package follows the same shape (`OpenAI(base_url=base_url, api_key="none")`, `model=model.id`), since `/v1/chat/completions` is documented as fully OpenAI-compatible ([REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest)). **Caveat: I did not find a current Learn page that shows the plain `openai` Python client verbatim** — the Python examples use LangChain's `ChatOpenAI`; the JS example uses `@langchain/openai` with `baseURL: endpointUrl + '/v1'`, `apiKey: 'notneeded'`. Treat the raw-`openai` snippet as a straightforward adaptation, not a verbatim doc quote.

Note also that `model.id` (the resolved variant ID, e.g. `phi-4-mini-instruct-generic-cpu:2`) is what gets passed as `model`, not the alias.

## Q6 — Hardware acceleration and requirements

### Execution providers

From [v1.0.0 GA release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.0.0):

| EP | Purpose | Platforms |
| --- | --- | --- |
| CPU | Universal fallback (MLAS) | All platforms |
| WebGPU (Dawn) | GPU acceleration | Windows x64, macOS arm64 |
| CUDA | NVIDIA GPUs | **Windows x64, Linux x64** |
| OpenVINO | Intel GPUs and NPUs | Windows x64 |
| QNN | Qualcomm NPUs | Windows ARM64 |
| TensorRT RTX | NVIDIA GPUs | Windows x64 |
| VitisAI | AMD NPUs | Windows x64 |

The [architecture doc](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture) gives a slightly different WebGPU row — "WebGPU (via Dawn) | GPU | Windows, Linux, macOS" — i.e. it lists Linux for WebGPU where the v1.0.0 notes did not. **Flagged inconsistency; WebGPU-on-Linux support is ambiguous across sources.**

For Linux specifically: **CUDA and CPU are the clearly-supported EPs; WebGPU is ambiguous; QNN / OpenVINO / VitisAI / TensorRT RTX are Windows-only.** The Windows plugin-EP mechanism runs through WinML, which is Windows-only: "On Linux and macOS, the Core API registers execution providers directly with ONNX Runtime without a platform intermediary. The SDK bundles the required execution provider plugins for each target platform." — [architecture](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture)

v2.0.1: "The unified package detects the available hardware and loads the appropriate WinML, WebGPU, CPU, or CUDA execution provider." — [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1)

### Documented driver/hardware minimums (per-EP, Windows-centric)

From [CLI reference — execution providers](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli):

- **CUDA EP**: "requires an NVIDIA GeForce RTX 30 series and later with a minimum recommended driver version 32.0.15.5585 and CUDA version 12.5."
- **NvTensorRTRTX**: NVIDIA GeForce RTX 30XX+, driver 32.0.15.5585, CUDA 12.5.
- **OpenVINO**: CPU Intel TigerLake (11th Gen)+ driver 32.0.100.9565; GPU AlderLake (12th Gen)+ driver 32.0.101.1029; NPU ArrowLake (15th Gen)+ driver 32.0.100.4239.
- **QNN**: Snapdragon X Elite (X1Exxxxx) / X Plus (X1Pxxxxx) Hexagon NPU, driver 30.0.140.0+.
- **VitisAI (AMD NPU)**: Adrenalin Edition 25.6.3 (NPU driver 32.00.0203.280) through 25.9.1 (32.00.0203.297).

### Minimum RAM / disk / VRAM — NOT DOCUMENTED

**I could not find published minimum RAM, free-disk, or GPU VRAM requirements in the current Microsoft Learn Foundry Local docs, the README, or the release notes.** The pages that would carry them ([what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local), [get-started](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started), [best practices](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-best-practice)) list only software prerequisites (Python 3.11+ / Node 20+ / .NET 8 / Rust 1.70+) and internet access for first download. The current get-started page has no OS-version or system-requirements table at all.

What the docs do say about sizing:

- Runtime footprint ≈ 20 MB added to your app package. — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)
- Performance guidance: use GPU when available; "Identify bottlenecks by monitoring memory usage during inference"; "Try more quantized model variants (for example, INT8 instead of FP16)". — [best practices](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-best-practice)
- Model file sizes are exposed per model via `fileSizeMb` in `GET /foundry/list`. — [REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest)

Practical sizing must therefore be derived per model from the catalog rather than from a published system-requirements table. **Earlier (pre-v1) Foundry Local docs did carry a requirements table; I did not find it on any live page during this research and am not citing remembered numbers.**

## Q7 — Model catalog

Catalog description:

> "Curated model catalog — A catalog of high-quality models optimized for on-device use ... The catalog covers chat completions (for example, **GPT OSS, Qwen, DeepSeek, Mistral, and Phi**) and audio transcription (for example, **Whisper**). Every model goes through extensive quantization and compression..."
> — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local), [README](https://github.com/microsoft/Foundry-Local)

**Yes, these are ONNX models served via ONNX Runtime.** "The runtime handles model acquisition, hardware acceleration, model management, and inference (via ONNX Runtime)"; catalog provides "pre-compiled ONNX models tuned for specific hardware configurations (CPU, GPU, NPU)"; `GET /foundry/list` returns `modelType` "(for example, ONNX)". — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local), [architecture](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture), [REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest)

### Concrete aliases seen in official material

| Alias / name | Type | Source |
| --- | --- | --- |
| `qwen2.5-0.5b` | chat (used in nearly every official sample) | [get-started](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started), [README](https://github.com/microsoft/Foundry-Local), [foundrylocal.ai](https://www.foundrylocal.ai/models) |
| `qwen2.5-coder-0.5b` | chat/code | repo `sdk/cpp/test/e2e_test.cpp` |
| `qwen3-0.6b` | chat | [CLI 0.10.3 quick start](https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-0.10.3) |
| `qwen3.5-vision` | vision-language (multimodal) | [v1.1.0 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.1.0) |
| `qwen3-0.6b-embedding` / `qwen3-embedding-0.6b` | embeddings | [v1.1.0 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.1.0) uses `qwen3-0.6b-embedding`; [PyPI](https://pypi.org/project/foundry-local-sdk/) uses `qwen3-embedding-0.6b`. **Naming conflict — verify at runtime.** |
| `phi-3.5-mini` | chat | [PyPI](https://pypi.org/project/foundry-local-sdk/), repo Rust examples |
| `phi-4-mini` / `phi-4-mini-instruct` | chat | repo `sdk_v2/cpp/src/catalog.h`, `samples/js/copilot-sdk-foundry-local`, JS tests |
| `whisper-tiny`, `whisper-base`, `whisper-small` | audio transcription | [REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest) |
| NVIDIA-Nemotron-3.5-ASR-Streaming-Multilingual-0.6b | streaming ASR | [v1.2.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.2.1) |
| `deepseek-r1-distill-qwen-14b-generic-cpu`, `deepseek-r1-distill-llama-8b-cuda-gpu` | chat (variant IDs) | repo `www/src/routes/models/service.ts` |
| `Phi-4-mini-instruct-generic-cpu`, `phi-3.5-mini-instruct-generic-cpu`, `qwen2.5-0.5b-instruct-generic-cpu`, `phi-4-mini-instruct-generic-cpu:2`, `Phi-4-mini-instruct-cuda-gpu` | variant IDs | [REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest), repo tests |
| `llama-3.2` (BYOM via Olive) | chat, user-compiled | [Compile Hugging Face models](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-compile-hugging-face-models) |

"Mistral" and "GPT OSS" are named as families in the catalog description but I found no concrete alias string for them in the docs or repo during this research.

### Alias vs model ID semantics

> "Using an alias: selects the best model for your available hardware automatically... If you want to run a specific model, use the model ID. For example, to run the `qwen2.5-0.5b` on CPU, regardless of your available hardware, use `foundry run qwen2.5-0.5b-instruct-generic-cpu`."
> — [CLI reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli)

Variant ID pattern: `<name>-<hardware>-<device>:<version>`, e.g. `phi-4-mini-instruct-generic-cpu:2`.

### The catalog is dynamic

The authoritative list is the live catalog: browse at <https://www.foundrylocal.ai/models> (the page is client-rendered and could not be scraped in this research), or enumerate programmatically via `catalog.list_models()` / `foundry model list` / `GET /foundry/list`. **Do not treat the table above as complete.** On Linux, the available variants will be the CPU and CUDA ones; NPU variants will not surface.

### BYOM

You are not limited to the catalog: compile Hugging Face models to ONNX with [Olive](https://github.com/microsoft/olive) (`pip install olive-ai`, `olive optimize --device cpu --provider CPUExecutionProvider --precision int4 ...`), add an `inference_model.json` with a `Name`, and point `Configuration(model_cache_dir=...)` at the folder. Recipes: [microsoft/olive-recipes](https://github.com/microsoft/olive-recipes). — [Compile Hugging Face models](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-compile-hugging-face-models). v1.2.1 added BYOM cache discovery without a service restart. — [v1.2.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.2.1)

## Q8 — Limitations, preview status, licensing

### Status

- **Foundry Local runtime/SDK: GA.** v1.0.0 was the "General Availability" release; latest is **v2.0.1** (published ~2026-08-31). — [releases](https://github.com/microsoft/Foundry-Local/releases)
- **Foundry Local CLI: public preview.** "Foundry Local CLI is available in preview... Features, approaches, and processes can change or have limited capabilities, before General Availability (GA)." Each CLI release repeats: "This is an early CLI build. Expect rough edges, missing polish, and changes between releases." Latest: `cli-preview-0.10.3`. — [CLI reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli), [CLI 0.10.3](https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-0.10.3)
- **REST API: under active development with breaking changes.** "This API refers to the REST API available in the Foundry Local CLI. This API is under active development and may include breaking changes without notice. We strongly recommend monitoring the changelog before building production applications." — [REST reference](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-rest)
- **Python SDK PyPI classifier is `Development Status :: 3 - Alpha`** despite the GA runtime branding. — [PyPI](https://pypi.org/project/foundry-local-sdk/)
- **Foundry Local on Azure Local: preview, access by request.** — [Azure Local overview](https://learn.microsoft.com/en-us/azure/azure-sovereign-clouds/private/foundry-local/what-is-foundry-local-on-azure-local)

### Functional limitations

- Not a multi-user server: no concurrent request queuing, continuous batching, or GPU sharing; use vLLM/Triton for that. — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)
- "Foundry Local is for on-device inference, **not distributed, containerized, or multi-machine production deployments**." — [best practices](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-best-practice)
- Curated (intentionally limited) model catalog; not a general-purpose model playground. — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)
- Inference cancellation is cooperative and may not take effect until the current generation step completes; **inference requests have no built-in timeout**. — [README FAQ](https://github.com/microsoft/Foundry-Local)
- Requires network for first-time model and EP downloads; offline afterwards. — [architecture](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture)
- Known issues in v2.0.1: TensorRT RTX models fail first load with `top_k` decoding on RTX Spark (Windows Arm); Rust SDK package publishing in progress. — [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1)
- Deprecation: OpenAI-style in-process clients removed end of 2026; migrate to Session API. — [v2.0.1 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v2.0.1)
- Model downloads are capped at three hours per blob (README commit "Limit model blob downloads to three hours").

### Licensing

- **SDK: MIT.** "Foundry Local SDK is licensed under the MIT license." PyPI license expression: MIT. — [README](https://github.com/microsoft/Foundry-Local), [PyPI](https://pypi.org/project/foundry-local-sdk/)
- **CLI: Microsoft Software License Terms** (not MIT). — [README](https://github.com/microsoft/Foundry-Local)
- **Models carry their own licenses.** "Individual models made available for use with Foundry Local are subject to each model's license terms, notices, and use restrictions. Refer to the model's documentation or download/listing page for the applicable terms before using or redistributing a model." Docs echo: "Review the license terms from the model publisher before you use a model." — [README](https://github.com/microsoft/Foundry-Local), [best practices](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-best-practice)
- **Execution providers carry third-party licenses**: CUDA/TensorRT RTX under the NVIDIA SDK EULA; OpenVINO under the Intel OBL Distribution Commercial Use License Agreement; QNN under the Qualcomm Neural Processing SDK license; VitisAI requires no additional license. — [CLI reference — execution providers](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-cli)
- Privacy: prompts/outputs processed locally; network used for downloads and optional diagnostics; governed by product terms and the [Microsoft Privacy Statement](https://www.microsoft.com/privacy/privacystatement). — [what-is-foundry-local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local)

## Cross-Source Inconsistencies to Watch

1. **WebGPU on Linux**: [v1.0.0 release notes](https://github.com/microsoft/Foundry-Local/releases/tag/v1.0.0) list WebGPU as "Windows x64, macOS arm64"; [architecture doc](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture) lists "Windows, Linux, macOS". Unresolved.
2. **`-winml` packages**: v2.0.1 removed them, but multiple Learn pages still instruct `pip install foundry-local-sdk-winml`. Irrelevant on Linux (use the plain package), but a docs-lag signal.
3. **Embedding model alias**: `qwen3-0.6b-embedding` (v1.1.0 notes) vs `qwen3-embedding-0.6b` (PyPI). Verify with `catalog.list_models()`.
4. **CLI command naming**: legacy `foundry service ...` / `foundry model run` vs current `foundry server ...` / `foundry run`. Learn's CLI reference and the CLI release notes describe slightly different surfaces (Learn documents `foundry model info`; release notes map it to `foundry model show`).
5. **Docs URL paths**: both `learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/...` and the canonical `learn.microsoft.com/en-us/azure/foundry-local/...` serve the same content.

## Answers at a Glance

| Question | Answer |
| --- | --- |
| Linux supported? | **Yes, explicitly** — x64 and ARM64, `manylinux_2_28` wheels |
| Ubuntu specifically? | Not named in product docs; glibc ≥ 2.28 implies Ubuntu 20.04+ works. "Ubuntu 22.04+" appears only in internal C++ sanitizer dev instructions |
| WSL2 supported? | **Not documented either way.** No product-doc mention. Only WSL references are in dev tooling. CPU path highly likely to work; GPU under WSL2 unverified |
| Standalone server? | No — SDK/in-process runtime is the product; HTTP server and CLI are optional dev conveniences |
| Python package | `pip install foundry-local-sdk` (v2.0.1, Python 3.11–3.14, MIT, PyPI status Alpha) |
| OpenAI-compatible HTTP? | Yes — `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`, `/v1/audio/transcriptions`, `/v1/responses` |
| Default port | **None — dynamic.** Discover via `manager.urls` (Python) / `manager.endpoint` (JS) / `foundry server status` / `GET /openai/status`. Pin with `--port` if needed |
| EPs on Linux | CPU + CUDA (clear); WebGPU ambiguous; NPU EPs are Windows-only |
| Min RAM/disk/VRAM | **Not published in current docs** — derive per model from `fileSizeMb` in the catalog |
| Models | ONNX via ONNX Runtime; qwen2.5-0.5b, qwen3-0.6b, phi-3.5-mini, phi-4-mini, whisper-tiny/base/small, deepseek-r1-distill-*, qwen3.5-vision, + GPT OSS / Mistral families |

## Recommended Next Research (not completed)

- [ ] Empirically validate `pip install foundry-local-sdk` + a CPU chat completion inside the target Ubuntu/WSL2 environment (this is the only way to close the WSL2 gap).
- [ ] Determine whether CUDA EP functions under WSL2 GPU passthrough (`/usr/lib/wsl/lib` driver stubs) — no documentation exists.
- [ ] Search `microsoft/Foundry-Local` GitHub Issues/Discussions for community WSL2 reports (not done; repo API access blocked by SAML SSO on the current token, and issue search was not attempted).
- [ ] Enumerate the live catalog on Linux (`catalog.list_models()`) to produce an authoritative alias list with `fileSizeMb` for RAM/disk sizing.
- [ ] Read the full `reference-sdk-current` Learn page (fetch failed: "Failed to extract meaningful content").
- [ ] Locate any archived pre-v1 Foundry Local system-requirements table if a formal minimum-hardware figure is required.
- [ ] Confirm the raw `openai` Python client pattern against an official sample (only LangChain-based Python samples were found).
- [ ] Compare against alternatives for this use case (Ollama, llama.cpp, vLLM) if the WSL2 gap proves blocking.

## Clarifying Questions

1. Does the project need a **Microsoft-supported configuration**, or is "it works empirically on Ubuntu/WSL2" sufficient? This determines whether the undocumented WSL2 status is a blocker.
2. Is **GPU acceleration required**, or is CPU inference on small models acceptable? GPU-under-WSL2 is the highest-risk unknown.
3. Is the intended integration **in-process Python SDK** or the **OpenAI-compatible HTTP endpoint**? The dynamic-port behavior materially affects service wiring for the HTTP path.
4. Is there a target model/size, so disk and RAM can be sized from catalog `fileSizeMb`?
5. Should Windows-native (outside WSL2) be considered as a fallback, given that Windows has the richest EP support?
