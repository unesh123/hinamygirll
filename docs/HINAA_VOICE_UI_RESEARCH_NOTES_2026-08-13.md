# HINAA Voice and Interface Research Notes — 2026-08-13

## Design direction

Taste Skill recommends an audit-first redesign with a declared direction, one accent color, one shape system, one page theme, clear contrast, and motion that is purposeful rather than decorative. It specifically cautions against generic purple gradients, equal-card grids, excess status dots, and nested-card density.[1]

Impeccable recommends a product-specific design context, contrast-safe tinted surfaces, non-default typography, restrained corners, and a detector/audit before release. Its documented workflow is useful as a design-review reference; no unreviewed third-party component code will be copied into HINAA.[2]

21st.dev is a registry of React/shadcn-compatible source components rather than a runtime dependency. HINAA can borrow only a small number of compatible interaction patterns, then implement them with the existing React, Framer Motion, and Lucide stack to preserve architecture ownership.[3]

## Voice architecture conclusions

HINAA is intentionally a chained local-first voice architecture: browser capture → VAD/turn controller → server STT → text agent → TTS → browser playback. This is the appropriate architecture when durable transcripts, explicit approvals, and existing text-agent reuse matter. It can still reduce first-audio latency by starting phrase-level synthesis after stable clause boundaries and emitting/playback-scheduling audio as each phrase becomes ready instead of waiting for the full model answer.[4]

The browser should request echo cancellation, noise suppression, and automatic gain control, but record the settings actually applied because noise suppression is not uniformly supported. Echo cancellation reduces speaker-output crosstalk in microphone input, while suppression targets ambient hum/noise.[5] [6]

The existing implementation already requests these browser constraints, maintains a VAD turn controller, supports interruption generations, streams assistant deltas, creates phrase-synthesis tasks during generation, and queues gapless playback. The key measured improvement target is server event scheduling: completed phrase synthesis should be emitted immediately, not only after the full text plan has completed.

## Scope boundary

No conclusion above proves a particular Windows microphone, VSeeFace camera tracker, CX gateway, ElevenLabs key, or ComfyUI instance. Those remain local runtime integrations that require actual user-device evidence after the code changes.

## References

[1]: https://www.tasteskill.dev/docs "Taste Skill documentation"
[2]: https://github.com/pbakaus/impeccable "Impeccable GitHub repository"
[3]: https://21st.dev/ "21st.dev component registry"
[4]: https://developers.openai.com/api/docs/guides/voice-agents "Voice agents guide"
[5]: https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackSettings/echoCancellation "MDN echo cancellation"
[6]: https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackSettings/noiseSuppression "MDN noise suppression"
