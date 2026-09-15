import { useContext, useEffect, useState } from "react";
import { SpeechPlaybackContext, sampleSpeechPlayback } from "./speechPlaybackBridge";

export function SpeechDiagnostics() {
  const bridge = useContext(SpeechPlaybackContext);
  const [, tick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => tick((value) => value + 1), 150);
    return () => clearInterval(timer);
  }, []);
  if (!bridge) return null;
  const value = sampleSpeechPlayback(bridge);
  return <section aria-label="Speech timing diagnostics" style={{ padding: 12, fontSize: 12 }}>
    <strong>Speech timing</strong>
    <p>{value.source} · {value.state} · {value.timingSource}</p>
    <p>Utterance {value.utteranceId} · {Math.round(value.timeMs)} ms · {value.viseme?.mouth ?? "closed"}</p>
    <label>Timing offset (ms) <input type="number" min={-500} max={500} step={10} value={value.calibrationMs}
      onChange={(event) => { bridge.current.calibrationMs = Math.max(-500, Math.min(500, Number(event.target.value) || 0)); }} /></label>
  </section>;
}
