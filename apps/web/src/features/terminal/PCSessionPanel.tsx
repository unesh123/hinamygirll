import {useState} from "react";
import {hinaaIdentityHeaders} from "../../lib/hinaaIdentity";
import {pcSessionToken, setPCSession} from "../../lib/remotePcSession";
const API_BASE = String(import.meta.env.VITE_HINAA_API_BASE_URL || "").replace(/\/+$/, "");
async function request(path: string, method = "GET") {
  const response = await fetch(`${API_BASE}/api/v1/${path}`, {method, headers: hinaaIdentityHeaders(), signal: AbortSignal.timeout(10000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.message || data.error?.message || "PC connection failed");
  return data;
}
export function PCSessionPanel({onChanged}: {onChanged: () => void}) {
  const [code, setCode] = useState("");
  const [issued, setIssued] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
  const act = async (action: "pair" | "connect" | "disconnect") => {
    setBusy(true); setMessage("");
    try {
      if (action === "pair") {
        const result = await request("pc/pair", "POST");
        setIssued(result.token);
        setMessage("Private pairing code expires after 15 minutes. Paste it in your signed-in live workspace.");
      } else if (action === "connect") {
        setPCSession(code.trim());
        const status = await request("terminal/status");
        if (!status.execution_allowed) {setPCSession(""); throw new Error("Pairing code expired or does not match your signed-in owner account.");}
        setCode(""); setMessage("PC session connected. Access expires automatically.");
      } else {
        if (pcSessionToken()) await request("pc/disconnect", "POST");
        setPCSession(""); setIssued(""); setMessage("PC disconnected. Cancel any already-running task separately.");
      }
    } catch (error) {
      if (action === "connect") setPCSession("");
      setMessage(error instanceof Error ? error.message : "PC connection failed");
    } finally {setBusy(false); onChanged();}
  };
  return <details style={{flexShrink: 0, maxHeight: "45%", overflowY: "auto"}}><summary style={{padding: "8px 12px", cursor: "pointer"}}>PC connection</summary><section aria-label="PC connection" style={{padding: 12, display: "grid", gap: 8, borderTop: "1px solid var(--border-subtle)", overflowWrap: "anywhere"}}>
    {local ? <button type="button" disabled={busy} onClick={() => void act("pair")}>Create private pairing code</button> : <>
      <input aria-label="Private PC pairing code" type="password" autoComplete="off" value={code} onChange={event => setCode(event.target.value)} placeholder="Pairing code from your local workspace"/>
      <button type="button" disabled={busy || !code.trim()} onClick={() => void act("connect")}>Connect PC for this session</button>
    </>}
    {issued && <input aria-label="Generated private PC pairing code" type="password" readOnly value={issued} onFocus={event => event.currentTarget.select()}/>}
    <button type="button" disabled={busy} onClick={() => void act("disconnect")}>Disconnect PC</button>
    {message && <p role="status">{message}</p>}
  </section></details>;
}
