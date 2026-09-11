import { writeFileSync } from "node:fs";
const ws = new WebSocket("ws://127.0.0.1:8000/v1/realtime");
ws.binaryType = "arraybuffer";
const events = [];
const log = (s) => { process.stdout.write(s + "\n"); };
let phase = "hello";
ws.addEventListener("open", () => {
  ws.send(JSON.stringify({
    type: "session.hello", protocolVersion: "1.0", sessionId: "repro-c3",
    companionId: "hinaa", providerMode: "claude",
    generation: 1, language: "mixed", languageMode: "auto", calibration: "natural",
  }));
});
ws.addEventListener("message", (m) => {
  if (typeof m.data !== "string") { log("[bin] " + m.data.byteLength); return; }
  const ev = JSON.parse(m.data);
  events.push(ev);
  log("[evt] " + ev.type + (ev.code ? " code=" + ev.code : "") + (ev.message ? " msg=" + ev.message : ""));
  if (ev.type === "session.ready" && phase === "hello") {
    phase = "sending";
    const FRAME = 1280;
    const buf = new ArrayBuffer(FRAME);
    const view = new DataView(buf);
    for (let i = 0; i < FRAME; i += 2) view.setInt16(i, 0, true);
    ws.send(JSON.stringify({ type: "audio.frame", sequence: 0, generation: 1, capturedAtMs: Date.now(), byteLength: FRAME }));
    ws.send(buf);
    setTimeout(() => {
      ws.send(JSON.stringify({ type: "audio.commit", generation: 1, endedAtMs: Date.now(), mockTranscript: "hi" }));
      phase = "done";
    }, 150);
  }
  if (ev.type === "error") { log("[FINAL ERROR] " + JSON.stringify(ev).slice(0,500)); ws.close(); }
});
ws.addEventListener("error", (e) => log("[err] " + (e.message||e)));
ws.addEventListener("close", () => { log("[close] events=" + events.length); process.exit(0); });
setTimeout(() => { log("[timeout]"); process.exit(1); }, 14000);