# HINA local motion studio

HINA can now compose editable motion graphics inside its existing chat tool,
`render_code_animation`. This is local rendering of text, shapes and supplied
images/footage. It uses no paid video-generation API. Hardware, electricity,
storage, and any cloud LLM used by HINA still have their normal costs.

This is an independent implementation. It does not contain Higgsfield/Katana
models, proprietary presets, a generative character animator, automatic subject
replacement, or camera/motion reconstruction from a reference.

## What is implemented

| Capability | Implementation |
| --- | --- |
| Editable scene graph | `composition_json`, up to 20 scenes / 30 seconds |
| Text choreography | `mask_rise`, `word_reveal`, `letter_stagger`, `tracking`, `perspective`, `slash`, `blur_rise`, `typewriter`, `scale_pop`, `none` |
| Transitions | Cut, crossfade, wipe, diagonal, whip, iris |
| Camera choreography | Static, dolly, pan left/right, orbit, crash zoom (2D transforms, not reconstructed 3D cameras) |
| Layered compositing | Ordered text, PNG/JPEG/WebP, MP4/WebM, rectangles, lines, rings; alpha and blend modes; supplied alpha images can occlude text |
| Custom motion | Time-keyed position, scale, rotation, opacity; linear/cubic/exponential/spring easing |
| Depth and trails | Independent parallax offsets and sampled motion trails; dust/embers are optional |
| Music | Actual supplied MP3/WAV, selectable trim, original speed/pitch, optional loudness normalization |
| Timing analysis | Spectral-flux transient times; reference hard-cut candidates sampled at 8 fps |
| Phone readability | Width fitting, line layout, safe margins, outline option and font families |
| Nepali/Unicode | Grapheme-aware segmentation; shaping-sensitive scripts stay in whole words |
| Export | H.264/AAC, up to 1920 per dimension and 60 fps; offline preview, source JSON, analysis and verified MP4 asset |

## Use in chat

Ask HINA:

> Make a 12-second vertical cinematic typography edit using my supplied song.
> Analyze its accents first, use the local composition renderer at 60 fps,
> preserve the music, and give me a playable MP4 and editable composition.
> Use warm ivory, cyan, confident editorial type, deliberate pauses, and varied
> transitions. Do not use the generic neon/HUD template.

The agent has been instructed to inspect music/references, compose to the brief,
review the storyboard and return the real tool asset URL. The web UI's existing
MP4 artifact card continues to display the result. No new frontend is required.
The tool can also be called directly without invoking an LLM.

First inspect (paths are relative to the selected workspace):

```json
{"inspect_only":true,"audio_path":"assets/song.mp3","reference_path":"assets/reference.mp4","duration_seconds":12}
```

The result includes the complete JSON schema, detected transients and candidate
cuts. These are estimates to inspect, not lyric transcription or a guaranteed
beat/downbeat grid. No source pixels are changed by inspection.

Then render:

```json
{
  "title":"My cinematic edit",
  "width":1080,"height":1920,"fps":60,
  "audio_path":"assets/song.mp3","audio_start_seconds":10,
  "audio_preset":"none",
  "composition_json":{
    "version":1,"safe_margin":0.08,
    "scenes":[
      {"duration":3,"background":"#ece7db","camera":"dolly",
       "layers":[
         {"kind":"text","text":"MOVE","y":0.43,"color":"#101820",
          "size":0.24,"motion":"letter_stagger","motion_blur":true},
         {"kind":"text","text":"WITH INTENTION","y":0.58,"color":"#101820",
          "size":0.044,"font":"mono","weight":400,"start":0.45,"motion":"tracking"}
       ]},
      {"duration":3,"transition":"diagonal","camera":"pan_left",
       "layers":[{"kind":"text","text":"MAKE IT\nREADABLE","size":0.18,
                  "motion":"mask_rise"}]}
    ]
  }
}
```

Scene durations define the export duration; they override the tool's default
`duration_seconds`. Layer `start/end` are relative to their scene; keyframe times
and `unit_times` are relative to the layer's start. `unit_times` control individual
word/grapheme entrances for known lyrics; unknown lyrics must not be invented.
Global `accents` are relative to the selected audio trim. When omitted and an
audio file is supplied, the measured transients are used for subtle accents.

Layers draw in array order. For a masked title, place a background/footage layer,
then text, then a supplied transparent subject PNG. This is compositing, not
automatic subject segmentation. Image/video `size` is width / canvas width and
`height` is height / canvas height. `fit` preserves source aspect ratio. Video
frames are sought and awaited at each export timestamp; source footage retains
its original visual cadence even when the composition exports at 60 fps.

Media must exist inside the chosen workspace (including after resolving
symlinks). Only raster images and MP4/WebM are accepted, with a combined 24 MiB
embedded-media budget. Trim large footage locally first. The compiled preview
has no remote dependencies; its page blocks outbound requests while rendering.

The response includes `source_project`: relative paths to `composition.json`,
`preview.html` and `analysis.json` under a unique workspace `motion-projects`
directory. Open the HTML and press Space for a silent visual preview, or call
`window.setAnimationTime(seconds)` for an exact frame. To revise, edit the JSON
and render it again. The soundtrack remains separate from the offline preview.

## Run without the web service

Use HINA's existing Python dependencies, Playwright Chromium (or system Chromium),
FFmpeg and ffprobe. No additional paid service or Python dependency is required.
If Chromium lives at a custom location, set `HINAA_CHROMIUM_EXECUTABLE` to its
executable path. Both the render and HTML verification tools honor this setting.

```sh
python scripts/render_cinematic.py examples/motion/cinematic-typography.json demo.mp4
python scripts/render_cinematic.py my-composition.json demo.mp4 --audio assets/song.mp3 --audio-start 10
```

The script calls HINA's actual tool handler and asset manager and writes an MP4
plus receipt. It does not claim an autonomous AI brain planned the composition.

## What still requires another system

Generative character acting, identity-preserving subject replacement and dense
motion transfer require suitable local neural models or an explicitly configured
provider. Local models can avoid API fees but still require hardware, storage,
model downloads, compatible licenses and practical quality testing. This change
does not enable or charge any external generative service.
