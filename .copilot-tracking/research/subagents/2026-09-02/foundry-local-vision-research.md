<!-- markdownlint-disable-file -->
# Foundry Local Vision / Image Inference Research

**Date:** 2026-09-02
**Status:** Complete
**Scope:** Whether Microsoft Foundry Local can perform vision/image inference, and credible local alternatives for image-based perception in Python on Ubuntu (CPU-only, ~2fps).

## Research Questions

1. Does the Foundry Local model catalog include any vision-capable / multimodal models?
2. Does the OpenAI-compatible endpoint accept image inputs?
3. Can users bring their own models (custom ONNX / Olive / Hugging Face conversion)?
4. If Foundry Local cannot do vision, what are the credible local alternatives?
5. Single most practical recommendation for CPU-only object/person detection.

## Executive Answer

**Foundry Local DOES support vision input today — but only through the `/v1/responses` (Responses API) path, with VLM chat models, and it is not a good fit for 2fps object detection.**

The `/v1/chat/completions` `image_url` content-part path is explicitly documented as **out of scope / not yet implemented** in the current C++ SDK core. Vision arrives via `POST /v1/responses` with `input_image` content parts.

Critically: even where vision works, it is **image→text chat** (a VLM describing a scene), not object detection. A 0.8B-parameter VLM on CPU generating tokens per frame will not sustain 2fps and does not return bounding boxes.

---

## Q1 — Vision-capable models in the Foundry Local catalog

### Answer: YES, but narrow and chat-oriented.

Evidence — Foundry Local repo contains a first-party Python vision sample that filters the live catalog for vision models:

Source: <https://raw.githubusercontent.com/microsoft/foundry-local/main/samples/python/web-server-responses-vision/src/app.py>

```python
vision_models = [
    m for m in manager.catalog.list_models()
    if getattr(m, "info", None)
    and m.info.task
    and "vision" in m.info.task.lower()
]
```

The sample's usage text names concrete identifiers:

```text
Usage: python src/app.py <model_alias_or_id> [image_path]
  Example: python src/app.py qwen3.5-0.8b
  Example: python src/app.py Qwen2.5-VL-7B-Instruct-generic-cpu
```

Sample README (<https://raw.githubusercontent.com/microsoft/foundry-local/main/samples/python/web-server-responses-vision/README.md>) documents the run command as `python src\app.py qwen3.5-0.8b`.

### Model families recognized as multimodal

Source: <https://raw.githubusercontent.com/microsoft/foundry-local/main/sdk_v2/cpp/docs/MigrationPlan_VisionInput.md>

> "The set of vision-language model types we enable on the C++ side is bounded by what the C# server's `IsMultiModal()` recognizes after PR 14989371:
> - `phi3v`, `phi4mm`, `fara`, `qwen2_5_vl`, `qwen3_vl`, `qwen3_5`
> (`whisper` is also `IsMultiModal` but it's the audio path, not vision.)
> These are the model types our model catalog actually ships…"

Explicitly **NOT** covered: `gemma3`, `gemma4`, `mistral3`. Florence-2, LLaVA, Moondream are not mentioned anywhere.

### Confirmed vision-capable identifiers

| Identifier | Type | Notes |
|---|---|---|
| `qwen3.5-0.8b` | alias | Used as the default example in the official Python vision sample |
| `Qwen2.5-VL-7B-Instruct-generic-cpu` | variant id | Explicit CPU variant; 7B params — heavy for 2fps |
| Model *types* `phi3v`, `phi4mm`, `fara`, `qwen2_5_vl`, `qwen3_vl`, `qwen3_5` | genai config types | Recognized by `IsMultiModal()` |

### Important caveat — marketing docs still say text + audio only

Both Microsoft Learn and the repo README describe the catalog as chat + audio only, with no mention of vision:

> "The catalog covers chat completions (for example, GPT OSS, Qwen, DeepSeek, Mistral, and Phi) and audio transcription (for example, Whisper)."
> — <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local>
> — <https://github.com/microsoft/foundry-local> (README, Key Features)

The published REST reference (<https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-catalog-api>) documents only `/v1/chat/completions` and `/v1/audio/transcriptions` — there is no `/v1/responses` documented and no vision endpoint documented. **Vision is real in code but undocumented on Learn**, i.e. effectively unsupported/preview surface.

---

## Q2 — Does the OpenAI-compatible endpoint accept image inputs?

### `/v1/chat/completions` with `image_url`: NO (documented out of scope)

Source: MigrationPlan_VisionInput.md, "Scope" section:

> Out of scope (track separately):
> - `POST /v1/chat/completions` `image_url` content parts (mirror once the Responses path is verified).

And "Out of Scope / Follow-ups":

> **`POST /v1/chat/completions` `image_url` content parts.** Same plumbing as the Responses path, but through `chat_completions_converter.cc`. Add as a follow-up once Responses is verified.

The Learn REST reference for `/v1/chat/completions` types `content` as:

> `content` (string) The actual message text.

— a plain string, not a content-part array. No `image_url` support documented.

### `/v1/responses` with `input_image`: YES

Working sample payload (from `samples/python/web-server-responses-vision/src/app.py`):

```python
vision_input = [
    {
        "type": "message",
        "role": "user",
        "content": [
            {"type": "input_text", "text": "Describe this image."},
            {
                "type": "input_image",
                "image_data": image_b64,
                "media_type": media_type,
            },
        ],
    }
]

stream = openai.responses.create(
    model=model.id,
    input="placeholder",
    extra_body={"input": vision_input, "max_output_tokens": 8192},
    stream=True,
)
```

Note the sample must smuggle the real input through `extra_body` — the OpenAI SDK's typed `input` is bypassed. This is a strong signal of preview-grade API stability.

### Documented restrictions

From MigrationPlan_VisionInput.md:

- **Single image per request.** More than one `ImageItem` per user message → `FOUNDRY_LOCAL_ERROR_INVALID_ARGUMENT`.
- **Data URLs and local file paths only.** `http(s)://` image URLs are rejected with `NOT_IMPLEMENTED`.
- **Image output not supported** (input only).
- **No KV-cache reuse on vision turns** — "vision path always rebuilds"; the cached generator is destroyed/bypassed when an image is present. This means every frame pays full prefill cost. Bad for 2fps.
- Image bytes are **not retained across turns** — only text is committed to history.

---

## Q3 — Bring your own model (custom ONNX / Olive)

### Answer: YES, documented and reasonably mature for LLMs; unproven for arbitrary CV models.

Source: <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-compile-hugging-face-models>

Documented workflow:

```bash
pip install olive-ai
pip install transformers onnxruntime-genai

olive optimize \
    --model_name_or_path meta-llama/Llama-3.2-1B-Instruct \
    --trust_remote_code \
    --output_path models/llama \
    --device cpu \
    --provider CPUExecutionProvider \
    --precision int4 \
    --log_level 1
```

Then write `inference_model.json` into the model dir:

```json
{ "Name": "llama-3.2:1" }
```

Then point the SDK at it:

```python
config = Configuration(app_name="run-compiled-model", model_cache_dir="../models")
FoundryLocalManager.initialize(config)
model = next(m for m in manager.catalog.get_cached_models() if "llama-3.2:1" in m.id)
model.load()
```

Architecture doc confirms the capability:

> "You aren't limited to models in the Foundry Catalog. You can also compile and optimize your own models in the ONNX format."
> — <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture>

### Maturity assessment: LOW for computer vision

- Microsoft's own caveat: "The Olive CLI and optimization settings change over time, and a single command line example might not work for every model, device, or execution provider."
- The entire BYO path runs through **`onnxruntime-genai`** — a *generative* (token-producing) runtime. Foundry Local's Core API surface is `get_chat_client()` / `get_audio_client()`. There is **no** detection/classification client, no tensor-in/tensor-out API.
- **You cannot load a YOLO or RT-DETR ONNX model into Foundry Local and get boxes out.** Foundry Local is a chat/audio runtime built on ORT GenAI, not a general ONNX Runtime wrapper.

Conclusion: BYO model = "bring your own *LLM/VLM*", not "bring your own detector".

---

## Q4 — Local alternatives for image perception in Python on Linux (CPU)

Note: Foundry Local itself runs on ONNX Runtime (<https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture>). Using ONNX Runtime directly is therefore the *same inference engine* Foundry Local uses — it preserves the "edge inference on ONNX Runtime" story without the chat abstraction.

### Option A — ONNX Runtime directly with a detection model

**Packages:** `onnxruntime` (MIT), plus `numpy`, `opencv-python`.

| Model | Package/source | License | ONNX size | Notes |
|---|---|---|---|---|
| RT-DETRv2 R18 | `onnx-community/rtdetr_v2_r18vd-ONNX` | **Apache-2.0** | ~81 MB fp32 (`onnx/model.onnx`), quantized variants ~21–65 MB | NMS-free, ~20M params (`PekingU/rtdetr_v2_r18vd`, Apache-2.0) |
| DETR ResNet-50 | `facebook/detr-resnet-50` | Apache-2.0 | ~166 MB (41.6M params fp32) | Slower; ResNet-50 backbone |
| YOLOv8 / YOLO11 / YOLOv10 | `ultralytics` / `onnx-community/yolov10n` | **AGPL-3.0** | ~10–12 MB (nano) | See licensing warning below |

Verified licenses (Hugging Face model API):
- `onnx-community/rtdetr_v2_r18vd-ONNX` → `license:apache-2.0` (<https://huggingface.co/api/models/onnx-community/rtdetr_v2_r18vd-ONNX>)
- `PekingU/rtdetr_r18vd_coco_o365` → `license:apache-2.0`, 20,209,680 params
- `facebook/detr-resnet-50` → `license:apache-2.0`, 41,631,008 params
- `onnx-community/yolov10n` → `license:agpl-3.0`

**CPU speed expectation at 640x640:** RT-DETRv2-R18 fp32 on a modern 4-8 core x86 CPU lands roughly in the 150–400 ms/frame range single-threaded-ish; INT8 quantized roughly halves that. At **2fps (500 ms budget)** this is comfortable. YOLOv8n/YOLO11n at 640x640 is faster still (~30–80 ms/frame) but carries AGPL.

### Option B — Florence-2 / Moondream via transformers or ONNX

| Model | License (verified) | Params | Fit |
|---|---|---|---|
| `microsoft/Florence-2-base` | **MIT** (<https://huggingface.co/api/models/microsoft/Florence-2-base>) | ~230M | Grounded captioning + `<OD>` task detection; requires `trust_remote_code=True`, PyTorch, ~1 GB download w/ deps |
| `vikhyatk/moondream2` | **Apache-2.0** (<https://huggingface.co/api/models/vikhyatk/moondream2>) | ~1.9B | VQA-style; `custom_code`; multi-GB PyTorch download |

Both are **generative** — they produce tokens. On CPU, a single Florence-2-base `<OD>` pass is typically 1–4 seconds; Moondream2 is several seconds to tens of seconds. **Neither sustains 2fps on CPU.** They are viable only for periodic semantic snapshots (e.g., one frame every 10–30s), not per-frame perception.

Florence-2 is attractive licensing-wise (MIT, Microsoft-authored — good narrative fit) but heavy: requires `torch`, `transformers`, `einops`, `timm`, and `trust_remote_code`.

### Option C — OpenCV DNN module

**Package:** `opencv-python` (Apache-2.0), already in the workspace's dependency tree given RTSP capture usage.

- `cv2.dnn.readNetFromONNX(...)` / `readNetFromCaffe(...)` / `readNetFromTensorflow(...)`.
- Classic pairing: **SSD-MobileNet-v2 COCO** or **MobileNet-SSD Caffe** — ~10–25 MB, ~30–60 ms/frame on CPU, Apache-2.0 model weights (TF Object Detection API).
- Zero extra dependency (OpenCV already needed for RTSP).
- Downsides: weaker accuracy than RT-DETR/YOLO; the OpenCV DNN backend has patchy support for transformer ops (RT-DETR/DETR export often fails to load); model acquisition is manual (`.pb`/`.pbtxt` or `.caffemodel`/`.prototxt` URLs, some of which have rotted).
- Also worth noting: OpenCV ships `cv2.HOGDescriptor` (`getDefaultPeopleDetector()`) for person detection with **zero model download** — low accuracy but instantly available.

### YOLOv8 / Ultralytics licensing warning

The `ultralytics` package and all YOLOv5/v8/v10/YOLO11/YOLO26 weights are **AGPL-3.0**. AGPL-3.0 is a strong copyleft license with a network clause: if the software is conveyed *or made available over a network*, the complete corresponding source of the whole combined work must be offered under AGPL-3.0. For a POC that could become a customer-facing or partner-delivered pipeline, this is a real contamination risk. Ultralytics sells a commercial Enterprise License as the alternative (<https://www.ultralytics.com/license>).

Practical implication: **avoid YOLO for anything that might ship**, even though it is the easiest to get running.

### Comparison summary

| Approach | pip install | Model acquisition | Size | ~CPU ms/frame | License | 2fps viable |
|---|---|---|---|---|---|---|
| ONNX Runtime + RT-DETRv2-R18 | `onnxruntime` | `huggingface_hub` download of one `.onnx` | ~81 MB (or ~21 MB int8) | ~150–400 | Apache-2.0 ✅ | **Yes** |
| ONNX Runtime + YOLO11n | `onnxruntime` (+`ultralytics` to export) | `.pt` → export, or prebuilt onnx | ~10 MB | ~30–80 | AGPL-3.0 ⚠️ | Yes |
| OpenCV DNN + SSD-MobileNet | none (already have `opencv-python`) | manual `.pb`/`.pbtxt` | ~25 MB | ~30–60 | Apache-2.0 ✅ | Yes |
| Florence-2-base (transformers) | `torch`,`transformers`,`timm`,`einops` | HF auto-download | ~1 GB+ w/ torch | ~1000–4000 | MIT ✅ | No |
| Moondream2 | `torch`,`transformers` | HF auto-download | ~4 GB+ | ~5000+ | Apache-2.0 ✅ | No |
| Foundry Local `/v1/responses` + `qwen3.5-0.8b` | `foundry-local-sdk`,`openai`,`Pillow` | auto from Foundry catalog | small (0.8B quantized) | seconds (token gen, no KV reuse) | model-specific | No |

---

## Q5 — Recommendation

### Primary: ONNX Runtime + RT-DETRv2-R18 ONNX

```bash
uv add onnxruntime huggingface-hub
```

```python
from huggingface_hub import hf_hub_download
path = hf_hub_download("onnx-community/rtdetr_v2_r18vd-ONNX", "onnx/model.onnx")
```

Rationale against the stated priorities:

| Priority | RT-DETRv2-R18 |
|---|---|
| Permissive license | **Apache-2.0** for both code path (`onnxruntime`, MIT) and weights. No copyleft. |
| Small download | ~81 MB fp32; quantized variants down to ~21 MB. |
| Simple pip install | `onnxruntime` is a single wheel, no PyTorch, no CUDA. |
| Reliable CPU perf at low fps | Comfortably inside a 500 ms budget at 2fps. Deterministic latency (no token generation). |
| "Edge inference" narrative | **Same runtime Foundry Local uses** — ONNX Runtime. The design doc's edge-inference requirement is satisfied by the engine, and the Foundry Local dependency becomes an optional add-on rather than a blocker. |
| Output shape | Boxes + class ids + scores → maps cleanly onto the existing `Observation` / `LineMonitoringMapper` contract in `src/tiger_poc/perception/` and `src/tiger_poc/ontology/`. |

RT-DETR is also NMS-free, so there is no post-processing dependency beyond a score threshold — less code than YOLO.

### Fallback (fastest to a demo, licensing caveat)

If time-to-first-detection matters more than license purity for the POC only, `pip install ultralytics` + `YOLO("yolo11n.pt")` is ~5 lines and works immediately. Treat it as **throwaway** and flag the AGPL-3.0 constraint before anything ships.

### Optional: keep Foundry Local in the architecture as the reasoning layer

A defensible hybrid that satisfies the design doc without breaking the frame budget:

- **Per-frame (2fps):** RT-DETRv2 via ONNX Runtime → structured detections → `Observation` objects.
- **Periodic / on-event:** Foundry Local text LLM (`qwen2.5-0.5b`, `phi-3.5-mini`) summarizes accumulated observations, or classifies station state from a structured prompt. This is what Foundry Local's catalog is actually good at.
- Optionally, on state-change events only, send one frame to Foundry Local `/v1/responses` with `qwen3.5-0.8b` for a natural-language scene description (accepting the multi-second latency).

This preserves "Foundry Local as edge inference runtime" in the design while putting real detection on the right tool.

---

## Key Discoveries

1. **Foundry Local vision exists but is undocumented on Microsoft Learn.** It lives in `/v1/responses` with `input_image` content parts, demonstrated only by a repo sample (`samples/python/web-server-responses-vision`). Learn docs and the repo README still describe the catalog as chat + audio only.
2. **`/v1/chat/completions` + `image_url` is explicitly out of scope** in the current C++ core, per `MigrationPlan_VisionInput.md`.
3. **Vision aliases:** `qwen3.5-0.8b` (alias), `Qwen2.5-VL-7B-Instruct-generic-cpu` (variant). Model types: `phi3v`, `phi4mm`, `fara`, `qwen2_5_vl`, `qwen3_vl`, `qwen3_5`. **No Florence-2, no LLaVA, no Moondream.**
4. **Vision turns bypass the KV cache** ("vision path always rebuilds"), so per-frame vision inference pays full prefill every frame. Structurally unsuited to 2fps.
5. **BYO model is LLM-only.** Olive + `inference_model.json` works, but the runtime is `onnxruntime-genai` and the client surface is chat/audio. A detection ONNX cannot be served through Foundry Local.
6. **Foundry Local's engine is ONNX Runtime.** Using `onnxruntime` directly is architecturally consistent with the design doc's edge-inference intent.
7. **RT-DETRv2-R18 ONNX is Apache-2.0, ~81 MB (int8 ~21 MB), NMS-free, and fits a 2fps CPU budget.**
8. **All Ultralytics YOLO artifacts are AGPL-3.0**, including `onnx-community/yolov10n`.

## References

### Microsoft Learn
- What is Foundry Local — <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local>
- Foundry Local architecture overview — <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/concepts/foundry-local-architecture>
- Foundry Local REST API reference — <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-catalog-api>
- Compile Hugging Face models and run on Foundry Local — <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-compile-hugging-face-models>

### microsoft/foundry-local GitHub
- Repo README — <https://github.com/microsoft/foundry-local>
- Vision migration plan (authoritative on scope/limits) — <https://raw.githubusercontent.com/microsoft/foundry-local/main/sdk_v2/cpp/docs/MigrationPlan_VisionInput.md>
- Python vision sample source — <https://raw.githubusercontent.com/microsoft/foundry-local/main/samples/python/web-server-responses-vision/src/app.py>
- Python vision sample README — <https://raw.githubusercontent.com/microsoft/foundry-local/main/samples/python/web-server-responses-vision/README.md>
- Python samples index — <https://github.com/microsoft/foundry-local/tree/main/samples/python>
- Foundry Local model catalog (JS-rendered, requires browser) — <https://foundrylocal.ai/models>

### Model cards / licenses
- `onnx-community/rtdetr_v2_r18vd-ONNX` (Apache-2.0) — <https://huggingface.co/api/models/onnx-community/rtdetr_v2_r18vd-ONNX>
- `PekingU/rtdetr_r18vd_coco_o365` (Apache-2.0) — <https://huggingface.co/api/models/PekingU/rtdetr_r18vd_coco_o365>
- `facebook/detr-resnet-50` (Apache-2.0) — <https://huggingface.co/api/models/facebook/detr-resnet-50>
- `microsoft/Florence-2-base` (MIT) — <https://huggingface.co/api/models/microsoft/Florence-2-base>
- `vikhyatk/moondream2` (Apache-2.0) — <https://huggingface.co/api/models/vikhyatk/moondream2>
- `onnx-community/yolov10n` (AGPL-3.0) — <https://huggingface.co/api/models/onnx-community/yolov10n>
- Ultralytics FAQ / model list — <https://docs.ultralytics.com/help/FAQ/>
- Ultralytics licensing — <https://www.ultralytics.com/license>
- RF-DETR (Apache-2.0 for nano/small/medium/large; PML 1.0 for XL/2XL) — <https://pypi.org/project/rfdetr/>

## Not Verified / Limitations

- The live Foundry Local catalog page (<https://foundrylocal.ai/models>) is client-side rendered; the vision model list could not be enumerated without a browser. Vision aliases are inferred from first-party sample code, not from a rendered catalog listing.
- No CPU benchmark was run locally. Latency figures are order-of-magnitude estimates from published model characteristics, not measurements on this machine.
- Whether `qwen3.5-0.8b` is currently present in the production catalog (vs. only in a preview channel) was not confirmed against a live catalog query.
- Ultralytics license page returned no extractable content; AGPL-3.0 is confirmed via the `license:agpl-3.0` tag on `onnx-community/yolov10n` and Ultralytics' well-known repo license.

## Recommended Next Research

- [ ] Run `foundry model list` on this machine (Linux CLI: `foundry-0.10.3-linux-x64.tar.gz`) and grep for vision tasks to confirm catalog contents empirically.
- [ ] Benchmark RT-DETRv2-R18 ONNX on this machine's CPU at 640x640 to confirm the 2fps budget with real numbers.
- [ ] Evaluate whether the int8/quantized RT-DETRv2 variant in `onnx-community/rtdetr_v2_r18vd-ONNX` retains acceptable accuracy for person detection.
- [ ] Determine the exact RT-DETRv2 ONNX input/output tensor signature (input names, expected normalization, output decoding) before implementation.
- [ ] Confirm whether `onnxruntime` CPU wheels are compatible with the project's pinned Python version in `pyproject.toml`.
- [ ] Investigate `supervision` (Roboflow, MIT) as a light post-processing/annotation helper — avoids hand-rolling box decode and drawing.

## Clarifying Questions

1. **Is the "Foundry Local" requirement in `docs/mvp-design.md` a hard contractual/demo requirement, or a proxy for "edge/on-device inference"?** If the latter, ONNX Runtime directly satisfies it (Foundry Local *is* ONNX Runtime). If the former, the hybrid architecture in Q5 is the way to keep it.
2. **Does this POC have any path to being shipped, demoed to a customer, or delivered to a partner?** This determines whether AGPL-3.0 YOLO is acceptable as a shortcut.
3. **What is the actual perception target — "station active vs idle" (motion/occupancy, no detector needed), or "person/object present" (detector needed)?** The existing `src/tiger_poc/perception/motion.py` may already answer the former; a detector is only required for the latter.
4. **What classes matter?** COCO-pretrained models give person/vehicle/common-object classes out of the box. Domain-specific objects would require fine-tuning, which changes the recommendation toward RF-DETR (Apache-2.0, purpose-built for fine-tuning).
5. **Is GPU available on the target edge device, or is CPU-only a firm constraint?** GPU availability would reopen VLM options.
