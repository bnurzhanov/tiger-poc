<!-- markdownlint-disable-file -->
# Foundry Local VLM Benchmark Research

**Date:** 2026-09-02
**Status:** In-Progress
**Machine:** WSL2 Ubuntu 24.04, x86_64, CPU-only, 12-thread i7-1265U, ~4.2 GiB RAM available, 876 GB disk, glibc 2.39, Python 3.13

## Research Questions

1. Does the Foundry Local vision-language model `qwen3.5-0.8b` load on this CPU-only WSL2 machine without OOM? What is peak RAM?
2. Which HTTP API path accepts image input: `/v1/chat/completions` (base64 data-URL `image_url`) or `/v1/responses` (`input_image`)?
3. What is the measured end-to-end latency per inference at full (1920x1080) and downscaled (640x360) resolution?
4. What is the text output quality on a real security-camera frame?
5. Is per-frame inference at 2fps feasible, or only low-rate/event-triggered use?

## Environment Baseline

- Test images available under /tmp (real security camera frames): demo_live.jpg (934k), cam2_home.jpg (647k), ptz_default.jpg (606k), frame.jpg (919k), tapo_frame.jpg (909k)
- No pre-existing `~/.foundry` cache, no `foundry` CLI on PATH before this session
- Throwaway venv: /tmp/fl-bench (CPython 3.13.7)
- Scratch work dir: /tmp/fl-bench-work

## Findings

(in progress)
