# 49 — Expressive avatar and themes

## Procedural only

The live avatar remains a **procedural** CSS/engine avatar.
Quarantined VRM assets are not loaded. Amplitude jaw is not phoneme lip-sync.

## Expression source

`AssistantTurnPlan` emotion/gesture allowlists + `PerformanceScheduler`.
Server planner emits allowlisted cues only; no model bone names or asset paths.

## Themes (appearance only)

| Id | Intent |
|---|---|
| `soft` | Gentle gradients |
| `futuristic` | Clean luminous accents |
| `anime-inspired-original` | Original expressive stylization (not a copyrighted character) |
| `minimal` | Low GPU |
| `night` | Darker accessible UI |

Theme preference persists in `localStorage`. Switching themes must not restart
conversation audio resources.

## Performance

- Reduced motion respected.
- Auto/low-performance mode reduces ambient motion.
- Missing audio → closed mouth; interruption clears jaw energy.
