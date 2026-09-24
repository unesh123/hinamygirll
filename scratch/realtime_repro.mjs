// Reproduce the live voice handshake against the realtime endpoint
const url = "ws://127.0.0.1:8000/v1/realtime";
const ws = new WebSocket(url);
ws.binaryType = "arraybuffer";

const events = [];
let opened = false;

const timeout = setTimeout(() => {
  console.log("TIMEOUT 20s reached. Events so far:");
  for (const e of events) console.log(JSON.stringify(e).slice(0, 300));
  try { ws.close(); } catch {}
  process.exit(1);
}, 20000);

ws.addEventListener("open", () => {
  opened = true;
  // Match what useLiveConversation.connect() sends
  ws.send(JSON.stringify({
    type: "session.hello",
    protocolVersion: "1.0",
    sessionId: "repro-test",
    companionId: "hinaa",
    providerMode: "cx-gateway",
    brainModel: "cx/gpt-5.6-sol",
    generation: 1,
    language: "mixed",
    languageMode: "auto",
    calibration: "natural",
  }));
});

ws.addEventListener("message", (m) => {
  if (typeof m.data !== "string") {
    events.push({ type: "<binary>", bytes: m.data.byteLength });
    return;
  }
  try {
    const ev = JSON.parse(m.data);
    events.push(ev);
    if (ev.type === "session.ready") {
      // Immediately commit with a mock transcript so we don't need real audio.
      // Many providers will transcribe empty audio, so use the mockTranscript
      // shortcut the API exposes for non-mock modes is not available,
      // so we must send frames. Instead, exercise the path that picks the
      // brain and TTS — first send some valid frames then commit.
      const FRAME_BYTES = 1280; // matches the API's frame size window
      // Build 1 frame of 16kHz mono PCM16 silence
      const frame = new ArrayBuffer(FRAME_BYTES);
      const view = new DataView(frame);
      for (let i = 0; i < FRAME_BYTES; i += 2) view.setInt16(i, 0, true);
      ws.send(JSON.stringify({
        type: "audio.frame",
        sequence: 0,
        generation: 1,
        capturedAtMs: Date.now(),
        byteLength: FRAME_BYTES,
      }));
      ws.send(frame);
      setTimeout(() => {
        ws.send(JSON.stringify({
          type: "audio.commit",
          generation: 1,
          endedAtMs: Date.now(),
          mockTranscript: "Hello HINAA, this is a connectivity test.",
        }));
      }, 200);
    }
    if (events.length > 30 || ev.type === "turn.complete" || ev.type === "error") {
      clearTimeout(timeout);
      console.log("=== EVENTS (" + events.length + ") ===");
      for (const e of events) console.log(JSON.stringify(e).slice(0, 400));
      try { ws.close(); } catch {}
      process.exit(0);
    }
  } catch (e) {
    events.push({ type: "parse-err", text: String(m.data).slice(0, 200) });
  }
});

ws.addEventListener("error", (e) => {
  console.log("WS ERROR:", e.message || e);
});
ws.addEventListener("close", () => {
  console.log("WS closed. opened=", opened, "events=", events.length);
  for (const e of events.slice(-15)) console.log(JSON.stringify(e).slice(0, 400));
  process.exit(0);
});