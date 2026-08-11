# HINAA NewBie Ultra API - Node Mapping

This document describes the node mapping for `HINAA_NEWBIE_ULTRA_API.json` to safely inject parameters before sending the workflow to ComfyUI.

## Core Nodes

- **KSampler** (`41:3`): The main diffusion sampler.
  - Injects: `seed` (integer)
- **SaveImage** (`9`): Saves the final output.
  - Injects: `filename_prefix` (string)
- **EmptySD3LatentImage** (`41:31`): Determines resolution and batch size.
  - Injects: `width` (integer), `height` (integer), `batch_size` (integer)
- **PrimitiveStringMultiline (User Prompt)** (`48`): The user's requested character/scene description.
  - Injects: `value` (string). This is safely substituted into the XML-based prompt template.
- **PrimitiveStringMultiline (Caption)** (`44`): Pre-defined dense stylistic caption.
  - Not modified by default, injected via StringReplace into the final prompt.
- **PrimitiveStringMultiline (Prompt Template)** (`47`): The master structural XML template for NewBie.
  - Not modified by default.

## Model Family
- UNETLoader: `NewBie-Image-Exp0.1-bf16.safetensors`
- VAELoader: `ae.safetensors`
- DualCLIPLoader: `gemma_3_4b_it_bf16.safetensors`, `jina_clip_v2_bf16.safetensors`
