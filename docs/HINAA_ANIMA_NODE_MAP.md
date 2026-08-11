# HINAA Anima Quality API - Node Mapping

This document describes the node mapping for `HINAA_ANIMA_QUALITY_API.json` to safely inject parameters before sending the workflow to ComfyUI.

## Core Nodes

- **KSampler** (`90:76`): The main diffusion sampler.
  - Injects: `seed` (integer)
- **SaveImage** (`46`): Saves the final output.
  - Injects: `filename_prefix` (string)
- **EmptyLatentImage** (`90:74`): Determines resolution and batch size.
  - Injects: `width` (integer), `height` (integer), `batch_size` (integer)
  - Note: In the raw JSON, `width` and `height` are linked to a `ResolutionSelector` (`91`). The HINAA backend safely overwrites these link arrays with raw integer values (e.g. 1024) at runtime, which ComfyUI accepts.
- **CLIPTextEncode (Positive Prompt)** (`90:77`): The positive prompt.
  - Injects: `text` (string)
- **CLIPTextEncode (Negative Prompt)** (`90:75`): The negative prompt.
  - Injects: `text` (string)

## Model Family
- UNETLoader: `anima-base-v1.0.safetensors`
- LoraLoaderModelOnly: `anima-turbo-lora-v0.2.safetensors`
- CLIPLoader: `qwen_3_06b_base.safetensors`
- VAELoader: `qwen_image_vae.safetensors`
