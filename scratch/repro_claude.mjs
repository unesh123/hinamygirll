const ws = new WebSocket("ws://127.0.0.1:8000/v1/realtime");
ws.binaryType = "arraybuffer";
const events = [];
ws.addEventListener("open", () => {
  ws.send(JSON.stringify({
    type: "session.hello", protocolVersion: "1.0", sessionId: "repro-claude",
    companionId: "hinaa", providerMode: "claude",
    generation: 1, language: "mixed", languageMode: "auto", calibration: "natural",
  }));
});
ws.addEventListener("message", (m) => {
  if (typeof m.data !== "string") return;
  const ev = JSON.parse(m.data);
  events.push(ev);
  if (events.length > 3 || ev.type === "turn.complete" || ev.type === "error") {
    console.log(JSON.stringify(ev).slice(0, 350));
    ws.close(); process.exit(0);
  }
});
ws.addEventListener("close", () => process.exit(0));
setTimeout(() => process.exit(1), 12000);
ws.onerror = () => process.exit(1);
