// Repro: send session.hello with providerMode=claude (unconfigured), capture all events
import { writeFileSync } from "node:fs";
const ws = new WebSocket("ws://127.0.0.1:8000/v1/realtime");
ws.binaryType = "arraybuffer";
const events = [];
const log = (s) => { process.stdout.write(s + "\n"); };
ws.addEventListener("open", () => {
  log("[open] sending session.hello providerMode=claude");
  ws.send(JSON.stringify({
    type: "session.hello", protocolVersion: "1.0", sessionId: "repro-claude-2",
    companionId: "hinaa", providerMode: "claude",
    generation: 1, language: "mixed", languageMode: "auto", calibration: "natural",
  }));
});
ws.addEventListener("message", (m) => {
  if (typeof m.data !== "string") { log("[bin] " + m.data.byteLength); return; }
  const ev = JSON.parse(m.data);
  events.push(ev);
  log("[evt] " + ev.type + (ev.code ? " code=" + ev.code : "") + (ev.message ? " msg=" + ev.message : ""));
  if (events.length > 4 || ev.type === "error") { ws.close(); }
});
ws.addEventListener("error", (e) => log("[err] " + (e.message||e)));
ws.addEventListener("close", () => { log("[close] events=" + events.length); process.exit(0); });
setTimeout(() => { log("[timeout]"); process.exit(1); }, 10000);