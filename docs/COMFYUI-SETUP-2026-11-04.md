# Connect Hina to ComfyUI — step by step

Assumption: “Complify” means **ComfyUI**, the node-based image generator. This setup uses your existing Hina bridge, your RTX 4060 Laptop GPU (8 GB VRAM), and a local ComfyUI server. No Comfy Cloud API key is needed for local model inference. Cloud/API nodes have separate account and billing requirements.

## 1. Start ComfyUI locally

Open your installed ComfyUI. Confirm its server is at `http://127.0.0.1:8188`. A different local port is fine, but Hina must use the same address. Do not change the server to a public listener to connect two apps on this PC.

At the initial inspection on 2026-11-04, ComfyUI was offline. Hina's frontend and backend were subsequently restarted in local runner sessions and both returned HTTP 200. ComfyUI readiness still reported `serverReachable: false`; a successful image generation is not yet verified in this session.

## 2. Choose the first workflow

Start with a small, ordinary text-to-image graph before adding custom nodes. Use the installed model's matching workflow. The included starter is specifically for an **SDXL checkpoint**; it is not a drop-in workflow for FLUX, Anima, Qwen Image or NewBie.

Starter file: `docs/workflows/hina-sdxl-starter-api.json`. Its checkpoint name is deliberately a placeholder: replace it with the exact installed SDXL checkpoint filename. The readiness check will report it as missing until you do.

If you already have a working ComfyUI graph, use that and export its API version instead. Preserve Hina's existing Anima and NewBie JSON files.

## 3. Build the seven-node starter

Add these nodes in ComfyUI:

1. **Load Checkpoint** (`CheckpointLoaderSimple`). Select your SDXL checkpoint from the dropdown.
2. **CLIP Text Encode** for the positive prompt.
3. **CLIP Text Encode** for the negative prompt.
4. **Empty Latent Image**.
5. **KSampler**.
6. **VAE Decode**.
7. **Save Image**.

Connect the sockets exactly as follows:

| Source | Destination |
|---|---|
| Load Checkpoint: MODEL | KSampler: model |
| Load Checkpoint: CLIP | Both CLIP Text Encode nodes: clip |
| Positive CLIP Text Encode: CONDITIONING | KSampler: positive |
| Negative CLIP Text Encode: CONDITIONING | KSampler: negative |
| Empty Latent Image: LATENT | KSampler: latent_image |
| KSampler: LATENT | VAE Decode: samples |
| Load Checkpoint: VAE | VAE Decode: vae |
| VAE Decode: IMAGE | Save Image: images |

Initial debugging settings: **768 × 768**, batch **1**, **20** steps, CFG **6**, sampler **euler**, scheduler **normal**, denoise **1**, seed **42**. These are starting settings for this starter, not universal settings for every model. After a successful run, try 1024 × 1024 and measure VRAM use and generation time. Keep batch 1 while the avatar and other GPU apps are running.

Use a simple test prompt such as a mountain lake at sunrise. Run it in ComfyUI and confirm Save Image contains an actual generated image. Fix errors in this small graph before adding an upscaler or reference pipeline.

## 4. Export a workflow Hina can execute

Use **File → Export Workflow (API)** / **Export (API)** in ComfyUI. The exported JSON must contain node IDs mapped to `class_type` and `inputs`; a UI-layout JSON containing a top-level `nodes` array is a different format.

Save your export inside this project, for example:

`docs/workflows/my-sdxl-api.json`

The current generic fast-workflow bridge expects one KSampler, positive and negative CLIPTextEncode inputs, an EmptyLatentImage and SaveImage. Arbitrary multi-sampler, video, or custom conditioning graphs need explicit adaptation; exporting them alone does not establish compatibility.

## 5. Connect the export to Hina

In `apps/api/.env.local`, add or update:

```dotenv
HINAA_COMFYUI_BASE_URL=http://127.0.0.1:8188
HINAA_COMFYUI_WORKFLOW_PATH=docs/workflows/my-sdxl-api.json
HINAA_COMFYUI_MAX_CONCURRENT_JOBS=1
```

Restart the Hina backend after editing these settings. No credentials are needed in chat. The optional separate ultra-workflow setting is `HINAA_COMFYUI_ULTRA_WORKFLOW_PATH`; leave it unset until an ultra graph has been validated.

## 6. Run the dependency check

From the Hina project root:

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 scripts/check_comfyui_bridge.py --workflow docs/workflows/my-sdxl-api.json
```

This reads ComfyUI's node catalog without submitting a generation. It reports server reachability, missing node classes, and unavailable model selections. `ready: true` means the fast workflow's checked dependencies are present; a real generation is still required to verify execution. The updated Hina diagnostic is also available at `/api/v1/local-services/comfyui` when the backend is running.

## 7. Test the full Hina path

First test the local bridge explicitly, without invoking a cloud renderer:

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 scripts/check_comfyui_bridge.py --workflow docs/workflows/my-sdxl-api.json --generate
```

The `--generate` flag queues one real 768 × 768 GPU job, waits for it, validates its download, and prints its local file path. Open that image to inspect the result. The bridge verifies PNG/JPEG/WebP contents before returning downloaded paths, so an upstream HTML error cannot become a completed image.

Then open Hina's image studio, request **one** image in fast mode, and confirm the job's renderer is `comfyui-local`, its queue completes, and the download opens. The current studio chooses providers automatically; it does not have a verified local-renderer override in this checkpoint.

The existing renderer selection prefers a configured cloud provider; a cloud result is not evidence that the local bridge worked. Keep your cloud credentials intact. Use the explicit local test above to verify ComfyUI independently, and check the job's renderer and ComfyUI queue when testing through Hina.

## 8. Add reference images

The bridge already supports an uploaded reference through:

`Load Image → Image Scale → VAE Encode → KSampler.latent_image`

It uses the output decoder's VAE and sets denoise to 0.55. This is image-to-image conditioning, not guaranteed identity preservation. Hina accepts bounded uploaded PNG/JPEG/WebP data for this local path. Validate the reference at the same resolution as the output.

For more precise control, add one capability at a time in ComfyUI: an image-adapter model for appearance/identity, a compatible ControlNet with its corresponding pose/depth/edge preprocessor, or an inpainting workflow with a mask. Each requires a workflow compatible with your base model and a corresponding bridge mapping. Do not wire every optional extension into the first graph.

## 9. Your existing advanced workflow dependencies

The shipped **Anima fast/quality graph** currently references:

- `anima-base-v1.0.safetensors` via UNETLoader.
- `qwen_3_06b_base.safetensors` via CLIPLoader.
- `qwen_image_vae.safetensors` via VAELoader.
- `anima-turbo-lora-v0.2.safetensors` via LoraLoaderModelOnly.
- Nodes including ResolutionSelector, ComfySwitchNode, PrimitiveInt/Float/Boolean, plus KSampler, CLIPTextEncode, EmptyLatentImage, VAEDecode and SaveImage.

The shipped **NewBie ultra graph** references:

- `NewBie-Image-Exp0.1-bf16.safetensors`, `ae.safetensors`, `gemma_3_4b_it_bf16.safetensors`, `jina_clip_v2_bf16.safetensors`.
- UNETLoader, DualCLIPLoader with the matching model type, ModelSamplingAuraFlow, EmptySD3LatentImage, StringReplace, PrimitiveStringMultiline, KSampler, CLIPTextEncode, VAEDecode and SaveImage.

These filenames come from your actual project graphs. They have not been confirmed installed on your ComfyUI server. Large full-precision models and multiple encoders can require offloading on an 8 GB GPU and should not be assumed fast. First verify the starter, then use the readiness report to install the exact dependencies for the advanced graph you choose.

## 10. Quality and speed progression

Keep a fixed seed to compare settings. Save a known working graph and model combination before increasing resolution or adding LoRAs, reference conditioning or an upscale pass. Add an upscaler after the base image is correct, and verify its file and node dependencies too. Measure queue time, sampling time and download time separately from Hina's text-generation latency.

Sources: [official text-to-image node guide](https://docs.comfy.org/tutorials/basic/text-to-image), [official API workflow example](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/basic_api_example.py), [official API-format documentation](https://github.com/Comfy-Org/docs/blob/main/development/api-development/workflow-api-format.mdx).
