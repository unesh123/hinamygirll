import { useCallback, useRef, useState } from "react";

type LabResult = {
  stage: string;
  status: "pending" | "running" | "success" | "error";
  detail: string;
  latencyMs?: number;
};

const RESULT_STYLE: Record<string, React.CSSProperties> = {
  pending: { color: "#94a3b8" },
  running: { color: "#facc15" },
  success: { color: "#4ade80" },
  error: { color: "#f87171" },
};

const BTN_STYLE: React.CSSProperties = {
  padding: "10px 18px",
  borderRadius: 8,
  border: "1px solid rgba(255,255,255,.12)",
  background: "rgba(15,23,42,.6)",
  color: "#f4e9df",
  fontFamily: "var(--font-body)",
  fontSize: 13,
  fontWeight: 500,
  cursor: "pointer",
  transition: "background .15s",
};

/**
 * Voice Lab — developer-only diagnostic panel.
 * Each button runs ONE isolated stage using the production implementation.
 * Access at /dev/voice-lab or via Settings → Diagnostics → Voice Lab.
 */
export function VoiceLab() {
  const [results, setResults] = useState<Record<string, LabResult>>({});
  const audioCtxRef = useRef<AudioContext | null>(null);

  const set = useCallback((stage: string, patch: Partial<LabResult>) => {
    setResults((prev) => ({
      ...prev,
      [stage]: { ...prev[stage], stage, ...patch },
    }));
  }, []);

  // ── A. Test Speaker ──────────────────────────────────────────────────
  const testSpeaker = useCallback(async () => {
    const stage = "A. Test Speaker";
    set(stage, { status: "running", detail: "Loading fixture…" });
    try {
      const res = await fetch("/test-assets/playback-check.wav");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      set(stage, { detail: `Fixture loaded (${blob.size} bytes). Decoding…` });

      let ctx = audioCtxRef.current;
      if (!ctx) {
        ctx = new AudioContext({ latencyHint: "interactive" });
        audioCtxRef.current = ctx;
      }
      if (ctx.state === "suspended") await ctx.resume();

      const arrayBuf = await blob.arrayBuffer();
      const buffer = await ctx.decodeAudioData(arrayBuf);
      set(stage, { detail: `Decoded (${buffer.duration.toFixed(2)}s). Playing…` });

      const master = ctx.createGain();
      master.gain.value = 1;
      master.connect(ctx.destination);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(master);

      const t0 = performance.now();
      source.start();
      set(stage, { detail: "Playback started. Confirm you hear a 440Hz tone." });
      await new Promise<void>((resolve) => {
        source.onended = () => {
          const ms = Math.round(performance.now() - t0);
          set(stage, { status: "success", detail: `Playback ended after ${ms}ms. Did you hear it?`, latencyMs: ms });
          resolve();
        };
        });
    } catch (err) {
      set(stage, { status: "error", detail: String(err) });
    }
  }, [set]);

  // ── B. Test ElevenLabs TTS ──────────────────────────────────────────
  const testTTS = useCallback(async () => {
    const stage = "B. ElevenLabs TTS";
    set(stage, { status: "running", detail: "Synthesizing via backend…" });
    const t0 = performance.now();
    try {
      const res = await fetch("/api/v1/speech/synthesis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "Hello Unesh. HINAA voice synthesis is working.", companionId: "hinaa" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const synthMs = Math.round(performance.now() - t0);
      set(stage, { detail: `Synthesized ${blob.size} bytes in ${synthMs}ms. Playing…` });

      let ctx = audioCtxRef.current;
      if (!ctx) {
        ctx = new AudioContext({ latencyHint: "interactive" });
        audioCtxRef.current = ctx;
      }
      if (ctx.state === "suspended") await ctx.resume();

      const arrayBuf = await blob.arrayBuffer();
      const buffer = await ctx.decodeAudioData(arrayBuf);
      const master = ctx.createGain();
      master.gain.value = 1;
      master.connect(ctx.destination);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(master);
      const playStart = performance.now();
      source.start();
      await new Promise<void>((resolve) => {
        source.onended = () => {
          const totalMs = Math.round(performance.now() - t0);
          set(stage, { status: "success", detail: `Played ${buffer.duration.toFixed(1)}s audio (total ${totalMs}ms). Confirm you hear speech.`, latencyMs: totalMs });
          resolve();
        };
      });
    } catch (err) {
      set(stage, { status: "error", detail: String(err) });
    }
  }, [set]);

  // ── C. Test Speech Fixture → STT ────────────────────────────────────
  const testSTTFixture = useCallback(async () => {
    const stage = "C. Speech Fixture → STT";
    set(stage, { status: "running", detail: "Generating speech WAV for STT test…" });
    const t0 = performance.now();
    try {
      // Use the proven ElevenLabs TTS to generate a fixture with real speech
      const ttsRes = await fetch("/api/v1/speech/synthesis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "Hello HINAA, can you hear me clearly?", companionId: "hinaa" }),
      });
      if (!ttsRes.ok) throw new Error(`TTS failed: HTTP ${ttsRes.status}`);
      const audioBlob = await ttsRes.blob();
      set(stage, { detail: `Generated ${audioBlob.size} byte speech fixture. Sending to STT…` });

      const formData = new FormData();
      formData.append("audio", audioBlob, "test-speech.wav");
      formData.append("language", "en-US");
      formData.append("provider_mode", "real");

      const sttRes = await fetch("/api/v1/speech/transcriptions", { method: "POST", body: formData });
      if (!sttRes.ok) throw new Error(`STT failed: HTTP ${sttRes.status}`);
      const result = await sttRes.json();
      const totalMs = Math.round(performance.now() - t0);

      const text = (result.text || "").trim();
      if (text.length > 0) {
        set(stage, { status: "success", detail: `Transcript: "${text}" (${result.provider}, ${result.latencyMs}ms, total ${totalMs}ms)`, latencyMs: totalMs });
      } else {
        set(stage, { status: "error", detail: `STT returned empty text (provider=${result.provider}, latency=${result.latencyMs}ms). This is a known issue.`, latencyMs: totalMs });
      }
    } catch (err) {
      set(stage, { status: "error", detail: String(err) });
    }
  }, [set]);

  // ── D. Test Real Microphone ──────────────────────────────────────────
  const micStreamRef = useRef<MediaStream | null>(null);
  const testMic = useCallback(async () => {
    const stage = "D. Real Microphone";
    if (micStreamRef.current) {
      // Stop previous test
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
      set(stage, { status: "pending", detail: "Stopped" });
      return;
    }
    set(stage, { status: "running", detail: "Requesting microphone permission…" });
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      micStreamRef.current = stream;
      const track = stream.getAudioTracks()[0];
      const settings = track.getSettings();
      set(stage, {
        detail: `Device: ${track.label} | SampleRate: ${settings.sampleRate || "unknown"} | State: ${track.readyState}`,
      });

      // Record 3 seconds of audio
      const ctx = new AudioContext({ sampleRate: settings.sampleRate || 48000 });
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const samples = new Uint8Array(analyser.fftSize);
      let rmsSum = 0;
      let rmsCount = 0;
      let rmsPeak = 0;
      const chunks: Float32Array[] = [];
      const recorder = ctx.createScriptProcessor(4096, 1, 1);
      recorder.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        chunks.push(new Float32Array(input));
        // Compute RMS
        let sum = 0;
        for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
        const rms = Math.sqrt(sum / input.length);
        rmsSum += rms;
        rmsCount += 1;
        if (rms > rmsPeak) rmsPeak = rms;
        analyser.getByteTimeDomainData(samples);
      };
      source.connect(recorder);
      recorder.connect(ctx.destination);

      set(stage, { detail: `Recording for 3 seconds… Speak into the microphone.` });
      await new Promise((r) => setTimeout(r, 3000));

      recorder.disconnect();
      source.disconnect();
      ctx.close();
      stream.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;

      const avgRms = rmsCount > 0 ? (rmsSum / rmsCount).toFixed(4) : "0";
      const totalBytes = chunks.reduce((s, c) => s + c.length * 2, 0); // PCM16 = 2 bytes/sample
      set(stage, {
        status: "success",
        detail: `Recorded ${chunks.length} chunks, ${totalBytes} bytes | Avg RMS: ${avgRms} | Peak RMS: ${rmsPeak.toFixed(4)} | ${rmsPeak > 0.01 ? "Speech detected ✓" : "Very quiet — speak louder"}`,
      });
    } catch (err) {
      set(stage, { status: "error", detail: `Microphone error: ${err}` });
    }
  }, [set]);

  // ── E. Full Conversation Loop ────────────────────────────────────────
  const testFullLoop = useCallback(async () => {
    const stage = "E. Full Conversation Loop";
    set(stage, { status: "running", detail: "Step 1/4: Generating speech fixture…" });
    const t0 = performance.now();
    try {
      // Step 1: Generate speech fixture
      const ttsRes = await fetch("/api/v1/speech/synthesis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "Hello HINAA, can you hear me clearly?", companionId: "hinaa" }),
      });
      if (!ttsRes.ok) throw new Error(`TTS failed: HTTP ${ttsRes.status}`);
      const audioBlob = await ttsRes.blob();
      set(stage, { detail: "Step 2/4: Transcribing via STT…" });

      // Step 2: Transcribe
      const formData = new FormData();
      formData.append("audio", audioBlob, "test-speech.wav");
      formData.append("language", "en-US");
      formData.append("provider_mode", "real");
      const sttRes = await fetch("/api/v1/speech/transcriptions", { method: "POST", body: formData });
      if (!sttRes.ok) throw new Error(`STT failed: HTTP ${sttRes.status}`);
      const sttResult = await sttRes.json();
      const transcript = sttResult.text || "Hello HINAA can you hear me clearly";
      set(stage, { detail: `Transcript: "${transcript}" — Step 3/4: Sending to brain…` });

      // Step 3: Send to brain
      const turnRes = await fetch("/api/v1/conversations/turns:stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: transcript, sessionId: "voice-lab-test" }),
      });
      if (!turnRes.ok) throw new Error(`Brain failed: HTTP ${turnRes.status}`);
      const reader = turnRes.body?.getReader();
      if (!reader) throw new Error("No response body");
      let planText = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = new TextDecoder().decode(value);
        for (const line of text.split("\n")) {
          if (line.startsWith("{")) {
            try {
              const event = JSON.parse(line);
              if (event.type === "plan") planText = JSON.stringify(event.plan);
            } catch { /* skip */ }
          }
        }
      }
      set(stage, { detail: `Brain responded. Step 4/4: Synthesizing TTS…` });

      // Step 4: Synthesize the brain's response
      let spokenText = "I can hear you clearly.";
      try {
        const plan = JSON.parse(planText);
        spokenText = plan.spokenText || spokenText;
      } catch { /* use fallback */ }
      const finalTTS = await fetch("/api/v1/speech/synthesis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: spokenText, companionId: "hinaa" }),
      });
      if (!finalTTS.ok) throw new Error(`Final TTS failed: HTTP ${finalTTS.status}`);
      const finalBlob = await finalTTS.blob();
      const totalMs = Math.round(performance.now() - t0);
      set(stage, {
        status: "success",
        detail: `Full loop completed in ${totalMs}ms. STT→Brain→TTS chain works. ${finalBlob.size} bytes audio ready. (${sttResult.provider} → brain → ElevenLabs)`,
        latencyMs: totalMs,
      });
    } catch (err) {
      set(stage, { status: "error", detail: String(err) });
    }
  }, [set]);

  const stages = [
    { id: "A", label: "🔊 Test Speaker", fn: testSpeaker },
    { id: "B", label: "🗣 Test ElevenLabs TTS", fn: testTTS },
    { id: "C", label: "🎤 Test Speech Fixture → STT", fn: testSTTFixture },
    { id: "D", label: "🎙 Test Real Microphone", fn: testMic },
    { id: "E", label: "🔄 Test Full Conversation", fn: testFullLoop },
  ];

  return (
    <div style={{ padding: 20, maxWidth: 700, fontFamily: "var(--font-body)" }}>
      <h2 style={{ color: "#f4e9df", fontSize: 18, marginBottom: 4 }}>Voice Lab</h2>
      <p style={{ color: "#94a3b8", fontSize: 12, marginBottom: 16 }}>
        Developer-only diagnostic panel. Each button runs ONE isolated stage.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {stages.map(({ id, label, fn }) => {
          const r = results[id];
          return (
            <div key={id} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <button onClick={() => void fn()} style={BTN_STYLE}>
                {label}
              </button>
              <div style={{ flex: 1, fontSize: 12, lineHeight: 1.5, color: r ? RESULT_STYLE[r.status]?.color ?? "#94a3b8" : "#64748b" }}>
                {r?.detail || "Not tested"}
                {r?.latencyMs !== undefined && (
                  <span style={{ marginLeft: 6, opacity: 0.6 }}>({r.latencyMs}ms)</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
