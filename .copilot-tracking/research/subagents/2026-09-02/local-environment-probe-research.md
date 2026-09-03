# Local Environment Probe: Microsoft Foundry Local + ONNX Runtime

Date: 2026-09-02
Scope: Empirical, read-only probe of the local machine to determine whether Microsoft Foundry Local and ONNX Runtime can actually run here.
Constraint honored: no files under `src/`, `scripts/`, `pyproject.toml`, or `uv.lock` were modified. All installs were confined to a throwaway venv at `/tmp/fl-probe` (removed at the end).

## Research Questions

1. Platform: OS, kernel, WSL2, architecture, glibc version (Foundry Local Linux wheels need glibc >= 2.28).
2. Resources: RAM, CPU, free disk.
3. GPU: NVIDIA present? `/dev/dxg`? CPU-only or accelerated?
4. Python: project venv version vs `requires-python`; foundry-local-sdk needs Python 3.11-3.14.
5. Foundry Local availability: `foundry` CLI present? Does `foundry-local-sdk` install? What does it expose? Can a local service start without downloading a multi-GB model?
6. ONNX Runtime: installs? version? `get_available_providers()`?
7. Network: PyPI and huggingface.co reachable?

## Executive Summary

| Question | Answer |
|---|---|
| Platform | Ubuntu 24.04.4 LTS on WSL2, x86_64 |
| glibc | 2.39 (wheel needs >= 2.28) — PASS |
| GPU | None usable. CPU-only. |
| Python (project venv) | 3.13.7 — within SDK range `>=3.11,<3.15` |
| `foundry` CLI installed | NO |
| `foundry-local-sdk` installs | YES — version 2.0.1, linux-x64 wheel, no errors |
| Native runtime initializes | YES — `libfoundry_local.so` loads and `initialize()` succeeds |
| Local service without model download | YES — OpenAI-compatible web service starts and serves `/v1/models` |
| `onnxruntime` installs | YES — 1.28.0 |
| ORT providers | `['AzureExecutionProvider', 'CPUExecutionProvider']` |
| ORT real inference | YES — verified end to end on CPU |
| PyPI / huggingface.co | Both reachable |
| Blockers | None hard. Constraints: CPU-only, 7.7 GiB RAM, `onnxruntime` hard-pinned to `==1.28.0`. |

## 1. Platform

`cat /etc/os-release`:

```
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
UBUNTU_CODENAME=noble
```

`uname -a`:

```
Linux LAPTOP-F0BCUSHR 6.18.33.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun 18 21:54:43 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux
```

`cat /proc/version`:

```
Linux version 6.18.33.2-microsoft-standard-WSL2 (root@f1bbfb02316b) (gcc (GCC) 13.2.0, GNU ld (GNU Binutils) 2.41) #1 SMP PREEMPT_DYNAMIC Thu Jun 18 21:54:43 UTC 2026
```

`uname -m`: `x86_64`

`ldd --version`:

```
ldd (Ubuntu GLIBC 2.39-0ubuntu8.8) 2.39
```

Findings:

- WSL2 confirmed — `microsoft-standard-WSL2` appears in both the kernel string and `/proc/version`.
- Architecture is `x86_64`, matching the `manylinux_2_28_x86_64` wheel tag.
- glibc 2.39 >= 2.28 required by the Foundry Local wheel. PASS with margin.

## 2. Resources

`free -h`:

```
               total        used        free      shared  buff/cache   available
Mem:           7.7Gi       3.5Gi       3.1Gi        32Mi       1.3Gi       4.2Gi
Swap:          2.0Gi          0B       2.0Gi
```

`lscpu` (filtered):

```
Architecture:                            x86_64
CPU(s):                                  12
Vendor ID:                               GenuineIntel
Model name:                              12th Gen Intel(R) Core(TM) i7-1265U
Thread(s) per core:                      2
Core(s) per socket:                      6
Socket(s):                               1
```

`df -h ~`:

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/sdd       1007G   81G  876G   9% /
```

Findings:

- 7.7 GiB total RAM, only ~4.2 GiB available at probe time. This is the tightest resource constraint. It caps practical model size well below the largest catalog entries.
- Intel Core i7-1265U, 12 logical CPUs (6 physical cores, hyperthreaded). This is a mobile-class P/E-core hybrid — usable for small ONNX models, slow for multi-billion-parameter LLM decode.
- 876 GB free disk. Model storage is not a constraint.
- WSL memory ceiling is configurable via `.wslconfig` on the Windows host if more RAM is needed.

## 3. GPU

- `nvidia-smi`: `nvidia-smi not found`
- `/dev/nvidia*`: no matches
- `/dev/dxg`: present — `crw-rw-rw- 10,258 root 2 Sep 10:43 /dev/dxg`
- `/usr/lib/wsl/lib` contents: `libd3d12.so`, `libd3d12core.so`, `libdxcore.so` (no `libcuda.so`, no `libdirectml`)
- `/dev/dri`: does not exist
- `vainfo`, `clinfo`: not installed

Verdict: **CPU-only.**

`/dev/dxg` exists because WSL2 always exposes the DirectX kernel shim, but the only WSL libraries present are D3D12/DXCore graphics stubs. There is no CUDA driver library, no NVIDIA device node, and no `/dev/dri` render node. Consequences:

- ONNX Runtime CUDA EP: not available (no NVIDIA hardware/driver).
- ONNX Runtime DirectML EP: Windows-only for the Python package; not usable from the Linux side of WSL.
- ONNX Runtime OpenVINO EP targeting the Intel iGPU: not viable, no `/dev/dri` render node is exposed to WSL.

This is confirmed independently by ORT itself and by the Foundry Local catalog, which resolves only `generic-cpu` model variants on this machine (see sections 5 and 6).

## 4. Python

| Item | Value |
|---|---|
| Project venv (`/home/bakha/development/tiger-poc/.venv/bin/python`) | Python 3.13.7 |
| System python3 | Python 3.12.3 |
| `uv` | 0.8.22 at `/home/bakha/.local/bin/uv` |
| `pyproject.toml` `requires-python` | `>=3.11` |
| `foundry-local-sdk` `Requires-Python` (from wheel METADATA) | `<3.15,>=3.11` |

Findings:

- Project venv Python 3.13.7 sits inside the SDK's supported range. Compatible.
- The project's own `requires-python = ">=3.11"` is open-ended upward; the SDK adds an implicit upper bound of `<3.15`. Worth noting if the project is ever built on 3.15+.

## 5. Foundry Local

### 5a. CLI presence

```
which foundry  -> foundry not found
foundry --version -> command not found: foundry
```

No standalone `foundry` CLI is installed. **This does not block usage** — the v2 Python SDK bundles the native runtime and does not require the separate CLI/service (verified in 5d).

### 5b. SDK installation

Command:

```
uv venv /tmp/fl-probe --python 3.13
uv pip install --python /tmp/fl-probe/bin/python foundry-local-sdk
```

Result: **SUCCESS, no errors.** 27 packages installed:

```
+ foundry-local-sdk==2.0.1
+ onnxruntime==1.28.0
+ onnxruntime-genai-core==0.15.2
+ openai==3.7.0
+ numpy==2.5.2
+ pydantic==2.13.5   + pydantic-core==2.46.5
+ cffi==2.1.1        + pycparser==3.0
+ httpx2==2.12.0     + httpcore2==2.12.0   + h11==0.16.0
+ requests==2.34.2   + urllib3==2.7.0      + certifi==2026.7.22
+ idna==3.19         + charset-normalizer==3.5.1
+ anyio==4.15.0      + sniffio==1.3.1
+ protobuf==7.36.1   + flatbuffers==25.12.19
+ jiter==0.16.0      + packaging==26.3     + truststore==0.10.4
+ typing-extensions==4.16.0 + typing-inspection==0.4.4 + annotated-types==0.8.0
```

Wheel metadata (`foundry_local_sdk-2.0.1.dist-info/WHEEL`):

```
Root-Is-Purelib: false
Tag: cp311-abi3-manylinux_2_28_x86_64
```

Wheel metadata (`METADATA`):

```
Version: 2.0.1
Requires-Python: <3.15,>=3.11
Requires-Dist: cffi>=1.16
Requires-Dist: typing_extensions>=4.5
Requires-Dist: pydantic>=2.0.0
Requires-Dist: requests>=2.32.4
Requires-Dist: openai>=2.24.0
Requires-Dist: onnxruntime==1.28.0
Requires-Dist: onnxruntime-genai-core==0.15.2
```

Key facts:

- The wheel is `manylinux_2_28_x86_64` — an official native Linux x64 build, matching this machine exactly.
- `abi3` tagged at cp311, so it works across 3.11-3.14 without per-version builds.
- **`onnxruntime` is hard-pinned to `==1.28.0`** (not a range). This is the single most important integration constraint: any other project dependency needing a different ORT version will conflict.

### 5c. Import name and exposed API

Important gotcha: the distribution is `foundry-local-sdk` but the **import name is `foundry_local_sdk`**, not `foundry_local`. `import foundry_local` raises `ModuleNotFoundError`.

```
import foundry_local_sdk as fl
fl.__file__   -> /tmp/fl-probe/lib/python3.13/site-packages/foundry_local_sdk/__init__.py
fl.__version__ -> 2.0.1
```

Public names exposed:

```
AudioItem, AudioSession, BytesItem, Catalog, ChatSession, Configuration,
DeviceType, EmbeddingsSession, EpDownloadResult, EpInfo, FinishReason,
FoundryLocalException, FoundryLocalManager, IModel, ImageItem, Item, ItemQueue,
ItemType, LogLevel, MessageItem, MessageRole, Model, ModelInfo, ModelSettings,
Parameter, PromptTemplate, Request, RequestOptions, Response, Runtime,
SearchOptions, Session, SpeechResultItem, SpeechSegmentItem, SpeechSegmentKind,
SpeechWord, StreamingResponse, TensorDataType, TensorItem, TextItem,
TextItemType, TokenUsage, ToolCallItem, ToolChoice, ToolResultItem
```

Relevant signatures:

```
Configuration.__init__(self, app_name: str, foundry_local_core_path: str | None = None,
    app_data_dir: str | None = None, model_cache_dir: str | None = None,
    logs_dir: str | None = None, log_level: LogLevel | None = LogLevel.WARNING,
    web: Configuration.WebService | None = None,
    additional_settings: dict[str, str] | None = None,
    catalog_urls: list[tuple[str, str | None]] | None = None,
    catalog_region: str | None = None,
    disable_nonessential_telemetry: bool = False) -> None

Configuration.WebService.__init__(self, urls: str | None = None, external_url: str | None = None) -> None

FoundryLocalManager.initialize(config: Configuration) -> None    # static; takes config, NOT self
FoundryLocalManager.instance                                     # property, not a callable
FoundryLocalManager.discover_eps(self) -> list[EpInfo]
FoundryLocalManager.download_and_register_eps(self, names=None, progress_callback=None) -> EpDownloadResult
FoundryLocalManager.start_web_service(self) -> None
FoundryLocalManager.stop_web_service(self) -> None
FoundryLocalManager.shutdown(self) -> None

Catalog: get_cached_models, get_latest_version, get_loaded_models, get_model,
         get_model_variant, get_model_versions, list_models
         (obtained via manager.catalog, NOT constructed directly)

DeviceType: [DeviceType.CPU, DeviceType.GPU, DeviceType.NPU]
```

API gotchas discovered empirically:

- `FoundryLocalManager.initialize(config)` is effectively static — calling `mgr.initialize()` on an instance raises `TypeError: missing 1 required positional argument: 'config'`.
- `FoundryLocalManager.instance` is a property. `M.instance()` raises `TypeError: 'FoundryLocalManager' object is not callable`.
- `fl.Catalog()` cannot be constructed directly (`missing 1 required positional argument: 'native_catalog_ptr'`). Use `manager.catalog`.
- `Configuration.WebService` takes `urls="http://127.0.0.1:PORT"`, not `port=`.

Bundled console script:

```
foundry-local-install --help
usage: foundry-local-install [-h] [--verbose]
(Re)install the Foundry Local SDK wheel and verify its ORT/GenAI native
dependencies are reachable.
```

Native library shipped in the wheel:

```
foundry_local_sdk/_native/linux-x64/libfoundry_local.so   (22 MB)
ELF 64-bit LSB shared object, x86-64, version 1 (GNU/Linux), dynamically linked
```

`ldd` on that library reports `libonnxruntime-genai.so => not found` and `libonnxruntime.so.1 => not found`. This is **expected and not a failure** — `foundry_local_sdk/_native/lib_loader.py` resolves those from the pip-installed `onnxruntime` / `onnxruntime_genai_core` package directories at import time. The import and runtime initialization both succeed.

### 5d. Runtime initialization and local service without model download

Native runtime initialization succeeded:

```
INITIALIZE OK -> native libfoundry_local.so loaded
instance: <foundry_local_sdk.foundry_local_manager.FoundryLocalManager object at 0x...>
```

Execution provider discovery:

```
discover_eps count: 0
```

Zero downloadable EPs — consistent with CPU-only hardware. `CPUExecutionProvider` is built in and is not listed as a downloadable EP package. On a machine with a discrete GPU or NPU this would list installable EP bundles.

Catalog query (metadata only, **no model bytes downloaded**):

```
[warning] RegionFallback: region 'westus2' unhealthy (transport failure); trying next candidate.
CATALOG list_models count: 48
cached: []
```

The region-fallback warning is benign; the catalog resolved successfully via the next candidate region. `get_cached_models()` returns `[]`, confirming nothing was downloaded.

**Built-in OpenAI-compatible web service started successfully with no model present:**

```python
ws  = fl.Configuration.WebService(urls="http://127.0.0.1:52001")
cfg = fl.Configuration(app_name="probe", app_data_dir=..., model_cache_dir=...,
                       logs_dir=..., web=ws, disable_nonessential_telemetry=True)
fl.FoundryLocalManager.initialize(cfg)
inst = fl.FoundryLocalManager.instance
inst.start_web_service()
```

Output:

```
WEB SERVICE STARTED
urls: ['http://127.0.0.1:52001']
GET /v1/models      -> 200 {"data":[{"created":1775581172,"id":"deepseek-r1-distill-qwen-14b-generic-cpu:4","object":"model","owned_by":"Microsoft"}, ...]}
GET /openai/status  -> 404
GET /health         -> 404
GET /foundry/list   -> 404
web service stopped
```

Confirmed: an in-process, OpenAI-compatible HTTP endpoint runs locally with zero model bytes on disk. `/v1/models` is live. Only `/openai/status` and `/health` (v1-era endpoints) are absent in this v2 build.

### 5e. Model catalog resolved for THIS machine

All 48 catalog entries resolve to `generic-cpu` variants with `execution_provider='CPUExecutionProvider'` and `device_type=DeviceType.CPU` — independent confirmation that the machine is CPU-only. Each model exposed exactly 1 variant (the CPU one).

Smallest entries, with sizes and tasks:

| MB | alias | task |
|---:|---|---|
| 131 | whisper-tiny | automatic-speech-recognition |
| 205 | whisper-base | automatic-speech-recognition |
| 438 | whisper-small | automatic-speech-recognition |
| 495 | qwen3-embedding-0.6b | embeddings |
| 593 | qwen3-0.6b | chat-completion |
| 692 | parakeet-tdt-0.6b-v2 | automatic-speech-recognition |
| 822 | qwen2.5-0.5b | chat-completion |
| 937 | whisper-medium | automatic-speech-recognition |
| **1037** | **qwen3.5-0.8b** | **vision-language-chat** |
| 1354 | qwen3-1.7b | chat-completion |
| **1374** | **qwen3-vl-2b-instruct** | **vision-language-chat** |
| 1464 | qwen3.5-2b-text | chat-completion |
| **1790** | **qwen3.5-2b** | **vision-language-chat** |
| 1822 | qwen2.5-1.5b | chat-completion |
| 2131 | smollm3-3b | chat-completion |
| 2590 | phi-3-mini-4k / phi-3.5-mini | chat-completion |
| **2797** | **qwen3-vl-4b-instruct** | **vision-language-chat** |
| 3085 | qwen3.5-4b | vision-language-chat |
| 4691 | ministral-3-3b-instruct-2512 | vision-language-chat |
| 4915 | phi-4-mini | chat-completion |
| 5081 | qwen3-vl-8b-instruct | vision-language-chat |
| 6031 | gemma-4-e2b-it | vision-language-chat |
| 10403 | phi-4 / phi-4-reasoning | chat-completion |
| 12552 | gpt-oss-20b | chat-completion |

Directly relevant to this project (camera perception): **vision-language-chat models are available and CPU-runnable.** The smallest VLM is `qwen3.5-0.8b` at 1037 MB, then `qwen3-vl-2b-instruct` at 1374 MB. Given ~4.2 GiB available RAM, models up to roughly the 2-3 GB tier are realistic; anything at or above the 5 GB tier is not.

Sample `ModelInfo` for `qwen2.5-0.5b`:

```
id = qwen2.5-0.5b-instruct-generic-cpu:4
display_name = qwen2.5-0.5b-instruct-generic-cpu
uri = azureml://registries/azureml/models/qwen2.5-0.5b-instruct-generic-cpu/versions/4
model_type = ONNX
task = chat-completion
runtime = Runtime(device_type=DeviceType.CPU, execution_provider='CPUExecutionProvider')
file_size_mb = 822
supports_tool_calling = True
max_output_tokens = 2048
publisher = Microsoft
license = apache-2.0
```

`ModelInfo` fields available: `alias, capabilities, context_length, created_at_unix, display_name, file_size_mb, id, input_modalities, license, license_description, max_output_tokens, min_fl_version, model_settings, model_type, name, output_modalities, prompt_template, provider_type, publisher, runtime, supports_tool_calling, task, uri, version`.

`Model` (from `catalog.get_model`) methods: `download, get_audio_client, get_chat_client, get_embedding_client, get_path, is_cached, is_loaded, load, remove_from_cache, select_variant, unload, variants, info`.

## 6. ONNX Runtime

Installed as a transitive dependency of `foundry-local-sdk`; also confirmed standalone-importable.

```
onnxruntime version: 1.28.0
onnxruntime.get_available_providers() -> ['AzureExecutionProvider', 'CPUExecutionProvider']
onnxruntime.get_device()              -> CPU
onnxruntime_genai_core: 0.15.2
```

Real inference verified end to end (built a tiny MatMul ONNX graph in the throwaway env and executed it):

```
session providers: ['CPUExecutionProvider']
INFERENCE OK -> [[60. 70. 80.]]
1000 runs in 0.013s
```

Notes:

- `AzureExecutionProvider` is a remote-endpoint EP, not local acceleration. The only real local compute path is `CPUExecutionProvider`.
- No `CUDAExecutionProvider`, no `DmlExecutionProvider`, no `OpenVINOExecutionProvider`. Consistent with the section 3 GPU findings.

## 7. Network

| Target | Result |
|---|---|
| `https://pypi.org/simple/` | 200 (0.61s, 0.97s, 1.07s across 3 attempts) |
| `https://files.pythonhosted.org` | 200 |
| `https://huggingface.co` | 200 (0.21s) |
| `https://huggingface.co/api/models?limit=1` | 200, returned valid JSON |
| `https://learn.microsoft.com` | 302 (normal redirect) |
| Foundry Local catalog service | Reachable — 48 models listed |

One caveat: the very first `curl` to `pypi.org` failed with `Could not resolve host: pypi.org`, but three immediate retries all returned 200 and every `uv pip install` succeeded. This was a transient DNS hiccup on the WSL NAT resolver (`nameserver 172.22.176.1`), not a persistent block. Worth remembering if a CI-style run intermittently fails DNS.

No proxy or custom index environment variables are set. `~/.config/pip/` contains only `pip.conf.cfs-backup.20260821100543.absent` (an absent-marker backup, i.e. no active pip.conf).

## 8. Integration Compatibility with tiger-poc

Current `pyproject.toml` dependencies (read-only, unmodified):

```toml
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "onvif-zeep>=0.2.12",
    "opencv-python>=4.10",
]
```

Current project venv packages: `numpy 2.5.2`, `opencv-python 5.0.0.93`, `onvif-zeep 0.2.12`, `zeep 4.3.3`, `lxml 6.1.3`, `requests 2.34.2`, plus `tiger-poc` editable.

Dependency resolution dry-run (`uv pip compile`, no files written) combining the project's declared dependencies with `foundry-local-sdk`:

```
foundry-local-sdk==2.0.1
numpy==2.5.2
onnxruntime==1.28.0
onnxruntime-genai-core==0.15.2
openai==3.7.0
opencv-python==5.0.0.93
```

**Resolution succeeded with no conflicts.** The resolved `numpy` and `opencv-python` versions are identical to what is already installed in the project venv, so adding `foundry-local-sdk` would be purely additive — no downgrades or churn to existing packages.

Caveat to carry forward: `foundry-local-sdk` pins `onnxruntime==1.28.0` exactly. If the project later needs a different ORT build (for example an `onnxruntime-openvino` or `onnxruntime-gpu` variant), that will conflict with the SDK pin and require pinning strategy work.

## Key Discoveries

1. **Foundry Local works on this machine.** The `manylinux_2_28_x86_64` wheel installs cleanly, the bundled native runtime loads, initialization succeeds, the catalog resolves 48 models, and the OpenAI-compatible web service starts and serves `/v1/models` — all without downloading a single model byte.
2. **No `foundry` CLI needed.** The v2 SDK is self-contained; the separate CLI/service install is not a prerequisite.
3. **CPU-only, definitively.** Confirmed three independent ways: absence of NVIDIA driver/device and `/dev/dri`; ORT reporting only `AzureExecutionProvider` + `CPUExecutionProvider`; and Foundry Local resolving `generic-cpu` variants with `CPUExecutionProvider` for every single catalog model, with `discover_eps()` returning zero installable EPs.
4. **RAM is the binding constraint, not disk or CPU.** 7.7 GiB total / ~4.2 GiB available versus 876 GB free disk. Model choice must be RAM-driven.
5. **Vision-language models are available on CPU** — `qwen3.5-0.8b` (1037 MB) and `qwen3-vl-2b-instruct` (1374 MB) are `vision-language-chat` and fit comfortably. Directly applicable to frame-level perception in this project.
6. **Import name trap:** the package is `foundry_local_sdk`, not `foundry_local`.
7. **API shape traps:** `initialize(config)` is static, `instance` is a property, `Catalog` must come from `manager.catalog`, and `WebService` takes `urls=` not `port=`.
8. **`onnxruntime==1.28.0` is an exact pin** in the SDK's metadata — the main forward-looking dependency risk.

## Blockers

No hard blockers. Constraints to plan around:

| Constraint | Impact | Mitigation |
|---|---|---|
| CPU-only, no GPU/NPU | LLM/VLM token throughput will be slow | Choose sub-2 GB models; keep prompts short; avoid per-frame VLM calls, gate on motion events |
| 7.7 GiB RAM (~4.2 GiB free) | Models above ~3 GB are impractical | Prefer `qwen3.5-0.8b` / `qwen3-vl-2b-instruct`; raise WSL memory in `.wslconfig` if needed |
| `onnxruntime==1.28.0` exact pin | Blocks alternative ORT builds | Accept the pin, or isolate Foundry Local in its own venv/process |
| No `foundry` CLI | Only matters for CLI-based workflows | Not needed — SDK is self-contained |
| Transient WSL DNS hiccup | Occasional first-request resolution failure | Add retry on network calls |
| Model download not yet exercised | Actual download speed/size on disk unverified | Deliberately out of scope here (no multi-GB downloads); verify separately when a model is chosen |

## Reproduction Notes

Throwaway environment used:

```
uv venv /tmp/fl-probe --python 3.13
uv pip install --python /tmp/fl-probe/bin/python foundry-local-sdk
uv pip install --python /tmp/fl-probe/bin/python onnx   # for the ORT inference test only
```

Scratch data dir: `/tmp/fl-probe-data` (app data, model cache, logs — model cache stayed empty).

All of `/tmp/fl-probe`, `/tmp/fl-probe-data`, `/tmp/fl-probe-tiny.onnx`, `/tmp/fl-probe-reqs.txt` were removed after the probe. No project files were modified.

## Recommended Next Research

- [ ] Download and time one small CPU model end to end (`qwen3.5-0.8b` VLM, 1037 MB) — measure download duration, on-disk size, RAM at load, and tokens/sec on this i7-1265U.
- [ ] Benchmark VLM latency on a single 1080p camera frame to determine whether per-event (not per-frame) invocation is viable for the perception pipeline.
- [ ] Compare `qwen3.5-0.8b` vs `qwen3-vl-2b-instruct` on representative factory frames for accuracy vs latency.
- [ ] Verify the OpenAI-compatible `/v1/chat/completions` path with an image payload once a VLM is cached.
- [ ] Evaluate whether Foundry Local should run in a separate process/venv to isolate the `onnxruntime==1.28.0` pin from the main project.
- [ ] Confirm behavior when the Foundry Local catalog is unreachable (offline/air-gapped factory scenario) — does a cached model still load?
- [ ] Measure WSL memory headroom under combined load (OpenCV capture + RTSP decode + VLM inference) to confirm the 7.7 GiB ceiling is sufficient.

## Clarifying Questions

1. Is the target deployment this same WSL2 laptop, or is this only a development machine with different production hardware (edge box, GPU server)? The CPU-only finding may or may not carry forward.
2. Is offline/air-gapped operation a requirement? Catalog access currently requires network at first load.
3. Is the intended perception mode per-frame or event-triggered? This drives whether CPU-only VLM latency is acceptable.
4. Is raising the WSL memory limit via `.wslconfig` on the Windows host acceptable, or must the solution fit within the current 7.7 GiB?
5. Should Foundry Local be added to the main project dependencies (accepting the `onnxruntime==1.28.0` pin), or run out-of-process behind the OpenAI-compatible HTTP endpoint?
