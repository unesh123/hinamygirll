import { useMemo, useState } from "react";
import { Check, Clipboard, FileText, Loader2, Save, ShieldCheck, Sparkles, Wand2 } from "lucide-react";

type HumanizerStyle = "natural" | "warm" | "professional" | "concise";

type HumanizerResponse = {
  text: string;
  style: HumanizerStyle;
  route: string;
  externalTextTransfer: boolean;
  changes: string[];
  originalCharacterCount: number;
  outputCharacterCount: number;
  protectedSegmentCount?: number;
  protectedCharacterCount?: number;
};

const styles: Array<{ id: HumanizerStyle; label: string; detail: string }> = [
  { id: "natural", label: "Natural", detail: "Clear, relaxed, and human" },
  { id: "warm", label: "Warm", detail: "Gentle and encouraging" },
  { id: "professional", label: "Professional", detail: "Clean, direct, and polished" },
  { id: "concise", label: "Concise", detail: "Remove safe filler and tighten flow" },
];

export function LocalHumanizerStudio({ onClose }: { onClose: () => void }) {
  const [source, setSource] = useState("");
  const [style, setStyle] = useState<HumanizerStyle>("natural");
  const [result, setResult] = useState<HumanizerResponse | null>(null);
  const [state, setState] = useState<"idle" | "working" | "complete" | "failed">("idle");
  const [message, setMessage] = useState("Paste a draft to polish it privately on this device.");
  const [copied, setCopied] = useState(false);
  const [sourceBeforeUse, setSourceBeforeUse] = useState<string | null>(null);
  const [savingToProject, setSavingToProject] = useState(false);
  const [savedToProject, setSavedToProject] = useState(false);

  const count = useMemo(() => source.length.toLocaleString(), [source]);
  const clearDraft = () => {
    setSource("");
    setResult(null);
    setSourceBeforeUse(null);
    setCopied(false);
    setSavingToProject(false);
    setSavedToProject(false);
    setState("idle");
    setMessage("Paste a draft to polish it privately on this device.");
  };
  const updateSource = (next: string) => {
    setSource(next);
    setCopied(false);
    if (result && next !== result.text) {
      setResult(null);
      setSavedToProject(false);
    }
  };
  const humanize = async () => {
    if (!source.trim() || state === "working") return;
    setState("working");
    setCopied(false);
    setSavedToProject(false);
    setMessage("HINAA is polishing your text locally…");
    try {
      const response = await fetch("/api/v1/text/humanize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: source, style }),
      });
      const data = await response.json();
      if (!response.ok || !data?.text) throw new Error(data?.detail || "HINAA could not polish this text.");
      setResult(data as HumanizerResponse);
      setState("complete");
      setMessage(data.externalTextTransfer
        ? "This result used the selected external route."
        : "Finished locally — this draft was not sent to an external model or API.");
    } catch (error) {
      setState("failed");
      setMessage(error instanceof Error ? error.message : "HINAA could not polish this text.");
    }
  };

  const copyResult = async () => {
    if (!result?.text) return;
    try {
      await navigator.clipboard.writeText(result.text);
      setCopied(true);
    } catch {
      setMessage("Copy was blocked by the browser. Select the result and copy it manually.");
    }
  };

  const saveResultToActiveProject = async () => {
    if (!result?.text || savingToProject) return;
    const projectId = window.localStorage.getItem("hinaa-active-project-id");
    if (!projectId) {
      setMessage("Choose a local project first, then save this humanized draft as a private artifact.");
      return;
    }
    setSavingToProject(true);
    setMessage("Saving this humanized draft to the active local project…");
    try {
      const response = await fetch(`/api/v1/projects/${projectId}/artifacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "document",
          title: `Humanized ${result.style} draft`,
          content: result.text,
          metadata: {
            origin: "local-humanizer",
            style: result.style,
            route: result.route,
            externalTextTransfer: result.externalTextTransfer,
            originalCharacterCount: result.originalCharacterCount,
            outputCharacterCount: result.outputCharacterCount,
            protectedSegmentCount: result.protectedSegmentCount ?? 0,
          },
        }),
      });
      if (!response.ok) throw new Error("HINAA could not save this draft to the active local project.");
      setSavedToProject(true);
      setMessage("Saved privately to the active local project as a document artifact.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "HINAA could not save this local project artifact.");
    } finally {
      setSavingToProject(false);
    }
  };

  const useResult = () => {
    if (!result?.text) return;
    setSourceBeforeUse(source);
    setSource(result.text);
    setCopied(false);
    setMessage("The polished draft is now your editable source text. You can restore the original draft once if needed.");
  };
  const restoreSource = () => {
    if (sourceBeforeUse === null) return;
    setSource(sourceBeforeUse);
    setSourceBeforeUse(null);
    setCopied(false);
    setMessage("Your original draft was restored locally.");
  };

  return (
    <section style={{ padding: 20, color: "var(--text-primary)", maxWidth: 960, margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
        <div>
          <p style={{ margin: 0, color: "#f5a7bb", fontSize: 11, fontWeight: 800, letterSpacing: ".12em" }}>PRIVATE WRITING TOOL</p>
          <h2 style={{ margin: "5px 0", fontSize: 25 }}>Text humanizer</h2>
          <p style={{ margin: 0, maxWidth: 690, color: "var(--text-secondary)", lineHeight: 1.5 }}>Improve clarity and flow while protecting Markdown code, links, headings, lists, facts, numbers, and Hindi × English text. This local route does not claim to evade detectors or imitate a real person.</p>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, marginTop: 11, border: "1px solid rgba(134,239,172,.24)", borderRadius: 999, padding: "5px 9px", background: "rgba(134,239,172,.07)", color: "#b8f7c9", fontSize: 11, fontWeight: 750 }}><ShieldCheck size={14} /> Local-only route · no provider key required</div>
        </div>
        <button type="button" onClick={onClose} style={secondaryButtonStyle}>Close</button>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))", gap: 18, marginTop: 22 }}>
        <div style={panelStyle}>
          <label style={labelStyle}>Your draft</label>
          <textarea aria-label="Text to humanize" value={source} onChange={(event) => updateSource(event.target.value)} maxLength={60000} placeholder="Paste any draft, note, explanation, or response you want HINAA to make clearer and more natural…" rows={16} style={{ ...inputStyle, width: "100%", resize: "vertical", lineHeight: 1.55, minHeight: 250 }} />
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 7, color: "var(--text-muted)", fontSize: 11, flexWrap: "wrap" }}><span>Markdown, code, links, citations, paths, emails, lists, and quotations stay protected.</span><span>{count} / 60,000</span></div>
          <div style={{ display: "grid", gridTemplateColumns: sourceBeforeUse === null ? "1fr auto" : "1fr auto auto", gap: 8, alignItems: "center" }}>
          <button type="button" onClick={() => void humanize()} disabled={!source.trim() || state === "working"} style={{ ...primaryButtonStyle, marginTop: 16, opacity: !source.trim() || state === "working" ? .55 : 1 }}>
            {state === "working" ? <Loader2 size={17} className="spin" /> : <Wand2 size={17} />}
            {state === "working" ? "Polishing locally…" : "Humanize text"}
          </button>
          {sourceBeforeUse !== null && <button type="button" onClick={restoreSource} style={{ ...secondaryButtonStyle, marginTop: 16 }}><FileText size={14} />Restore original</button>}
          <button type="button" onClick={clearDraft} disabled={!source && !result} style={{ ...secondaryButtonStyle, marginTop: 16, opacity: !source && !result ? .55 : 1 }}>Clear</button>
          </div>
          <p role="status" style={{ margin: "12px 0 0", color: state === "failed" ? "#f49aad" : "var(--text-secondary)", fontSize: 12, lineHeight: 1.45 }}>{message}</p>
        </div>

        <aside style={panelStyle}>
          <label style={labelStyle}>Writing style</label>
          <div role="radiogroup" aria-label="Humanizer writing style" style={{ display: "grid", gap: 7 }}>{styles.map((item) => <button key={item.id} type="button" role="radio" aria-checked={style === item.id} onClick={() => setStyle(item.id)} style={{ ...styleButtonStyle, borderColor: style === item.id ? "#ee91ad" : "rgba(255,219,231,.16)", background: style === item.id ? "rgba(238,145,173,.14)" : "rgba(255,255,255,.025)" }}><strong>{item.label}</strong><span>{item.detail}</span></button>)}</div>
          <div style={{ marginTop: 18, borderTop: "1px solid rgba(255,219,231,.12)", paddingTop: 15 }}>
            <p style={{ margin: 0, color: "#ffd4df", fontWeight: 760, fontSize: 12 }}><Sparkles size={13} style={{ verticalAlign: "-2px" }} /> What this local pass changes</p>
            <p style={{ margin: "7px 0 0", color: "var(--text-secondary)", fontSize: 12, lineHeight: 1.55 }}>It removes safe filler, simplifies overly formal English phrases, smooths transitions, and cleans spacing. For a model-written rewrite, select a configured HINAA brain in chat and explicitly ask her to preserve facts and citations.</p>
          </div>
        </aside>
      </div>

      {result ? <section aria-label="Humanized text result" style={{ ...panelStyle, marginTop: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><div><p style={{ margin: 0, color: "#f5a7bb", fontSize: 11, fontWeight: 800, letterSpacing: ".08em" }}>LOCAL RESULT</p><h3 style={{ margin: "4px 0 0", fontSize: 17 }}>Polished {result.style} draft</h3></div><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button type="button" onClick={() => void copyResult()} style={secondaryButtonStyle}>{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? "Copied" : "Copy"}</button><button type="button" disabled={savingToProject || savedToProject} onClick={() => void saveResultToActiveProject()} style={{ ...secondaryButtonStyle, opacity: savingToProject || savedToProject ? .65 : 1 }}><Save size={14} />{savedToProject ? "Saved to project" : savingToProject ? "Saving…" : "Save to project"}</button><button type="button" onClick={useResult} style={secondaryButtonStyle}><FileText size={14} />Use as draft</button></div></div>
        <textarea aria-label="Humanized result" readOnly value={result.text} rows={12} style={{ ...inputStyle, width: "100%", marginTop: 14, resize: "vertical", lineHeight: 1.55 }} />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>{result.changes.map((change) => <span key={change} style={{ border: "1px solid rgba(255,219,231,.16)", borderRadius: 999, padding: "4px 7px", color: "#e7ccd6", background: "rgba(255,255,255,.03)", fontSize: 10 }}>{change}</span>)}</div>
        <p style={{ margin: "10px 0 0", color: "var(--text-muted)", fontSize: 11, lineHeight: 1.45 }}>
          {result.originalCharacterCount.toLocaleString()} → {result.outputCharacterCount.toLocaleString()} characters
          {typeof result.protectedSegmentCount === "number" ? ` · ${result.protectedSegmentCount.toLocaleString()} protected span${result.protectedSegmentCount === 1 ? "" : "s"}${result.protectedCharacterCount ? ` (${result.protectedCharacterCount.toLocaleString()} characters)` : ""}` : ""}
          {" · local deterministic route"}
        </p>
      </section> : null}
    </section>
  );
}

const panelStyle = { border: "1px solid var(--glass-border)", background: "rgba(255,255,255,.035)", borderRadius: 14, padding: 15, boxShadow: "inset 0 1px 0 rgba(255,255,255,.04)" } as const;
const inputStyle = { border: "1px solid rgba(255,219,231,.16)", background: "rgba(18,12,21,.68)", borderRadius: 9, color: "var(--text-primary)", padding: "10px 11px", fontSize: 13, boxSizing: "border-box", fontFamily: "inherit" } as const;
const labelStyle = { display: "block", color: "#f5a7bb", fontSize: 11, fontWeight: 800, letterSpacing: ".08em", marginBottom: 7 } as const;
const primaryButtonStyle = { width: "100%", marginTop: 16, display: "flex", gap: 9, justifyContent: "center", alignItems: "center", border: "1px solid #ffc3d3", borderRadius: 10, padding: "11px 14px", cursor: "pointer", color: "#28131d", fontWeight: 800, background: "linear-gradient(135deg,#ffd4df,#ee91ad)" } as const;
const secondaryButtonStyle = { display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid rgba(255,219,231,.18)", borderRadius: 8, background: "rgba(255,255,255,.035)", color: "var(--text-secondary)", padding: "7px 10px", cursor: "pointer" } as const;
const styleButtonStyle = { display: "grid", textAlign: "left", gap: 2, border: "1px solid", borderRadius: 9, color: "var(--text-primary)", padding: "9px 10px", cursor: "pointer" } as const;
