import { useEffect, useRef, useState } from "react";
import { ImagePlus, Loader2, Sparkles, Wand2 } from "lucide-react";

interface ImageResult {
  id?: string;
  url?: string;
  image_url?: string;
}

interface ImageSlot {
  id: string;
  index: number;
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  seed?: number;
  width?: number;
  height?: number;
  promptId?: string | null;
  url?: string | null;
}

export function LocalImageStudio({ onClose }: { onClose: () => void }) {
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [mode, setMode] = useState<"fast" | "quality" | "ultra">("quality");
  const [count, setCount] = useState(1);
  const [seed, setSeed] = useState("");
  const [state, setState] = useState<"idle" | "starting" | "processing" | "complete" | "failed">("idle");
  const [message, setMessage] = useState("Your images stay in your local Hinaa library.");
  const [images, setImages] = useState<Array<ImageResult | string>>([]);
  const [slots, setSlots] = useState<ImageSlot[]>([]);
  const [comfyStatus, setComfyStatus] = useState<"checking" | "ready" | "unavailable">("checking");
  const abortRef = useRef(false);

  const checkComfy = async () => {
    setComfyStatus("checking");
    try {
      const response = await fetch("/api/v1/local-services/comfyui");
      const data = await response.json();
      setComfyStatus(response.ok ? "ready" : "unavailable");
      if (!response.ok) setMessage(data?.hint || "ComfyUI is unavailable. Start it locally, then refresh.");
    } catch {
      setComfyStatus("unavailable");
      setMessage("Could not reach Hinaa’s local API to check ComfyUI.");
    }
  };

  useEffect(() => { void checkComfy(); }, []);

  const generate = async () => {
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt || state === "starting" || state === "processing") return;
    if (comfyStatus !== "ready") {
      setState("failed");
      setMessage("ComfyUI is not ready yet. Start it on http://127.0.0.1:8188 and click Check again.");
      return;
    }
    setState("starting");
    setMessage("Preparing the local image job…");
    setImages([]);
    setSlots(Array.from({ length: count }, (_, index) => ({
      id: `preparing-${index + 1}`,
      index: index + 1,
      status: "pending" as const,
    })));
    abortRef.current = false;
    try {
      const start = await fetch("/api/v1/tools/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          toolName: "image_generate",
          confirmed: true,
          parameters: {
            prompt: cleanPrompt,
            negative_prompt: negativePrompt.trim(),
            seed: seed ? Number(seed) : undefined,
            count,
            mode,
          },
        }),
      });
      const startData = await start.json();
      // Direct terminal tool results are preferred. Accept the prior nested
      // envelope too so an upgraded UI can still recover gracefully against a
      // running older local API during a staged desktop restart.
      const toolResult = startData?.data?.data ?? startData?.data ?? startData;
      const jobId = toolResult?.job_id ?? startData?.job_id;
      if (!start.ok || toolResult?.status === "error" || !jobId) {
        throw new Error(
          toolResult?.error
          || startData?.error
          || startData?.message
          || "The local image job could not start.",
        );
      }

      setState("processing");
      setMessage("Hinaa is generating locally. You can keep chatting while this finishes.");
      for (let attempt = 0; attempt < 180 && !abortRef.current; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        const poll = await fetch(`/api/v1/tools/poll?job_id=${encodeURIComponent(jobId)}`);
        const result = await poll.json();
        if (!poll.ok) throw new Error(result?.message || "Could not read image progress.");
        setImages(result.images || []);
        if (Array.isArray(result.slots)) setSlots(result.slots);
        if (result.status === "success" || result.status === "partial") {
          setState("complete");
          const completed = Number(result.completed ?? result.images?.length ?? 0);
          const total = Number(result.total ?? completed);
          setMessage(result.status === "partial"
            ? `${completed} of ${total} local images are ready. ${result.error || "Some outputs did not finish."}`
            : `${completed} local image${completed === 1 ? "" : "s"} ready.`);
          return;
        }
        if (result.status === "error" || result.status === "failed") throw new Error(result.error || "The local image workflow failed.");
        const activeSlot = Array.isArray(result.slots) ? result.slots.find((slot: ImageSlot) => slot.status === "processing") : undefined;
        setMessage(result.total
          ? `Generating ${Number(result.completed ?? result.images?.length ?? 0)} of ${result.total} image outputs${activeSlot ? ` — image ${activeSlot.index} is running` : ""}…`
          : "Generating locally…");
      }
      if (!abortRef.current) throw new Error("The image job took too long. Check that ComfyUI is running locally.");
    } catch (error) {
      setState("failed");
      setMessage(error instanceof Error ? error.message : "Image generation failed.");
    }
  };

  return (
    <section style={{ padding: 20, color: "var(--text-primary)", maxWidth: 940, margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
        <div>
          <p style={{ margin: 0, color: "#f5a7bb", fontSize: 11, fontWeight: 800, letterSpacing: "0.12em" }}>LOCAL CREATOR</p>
          <h2 style={{ margin: "5px 0", fontSize: 25 }}>Image studio</h2>
          <p style={{ margin: 0, color: "var(--text-secondary)", lineHeight: 1.5 }}>Create locally through your configured ComfyUI workflow. Generate is an explicit action; Hinaa will not start image jobs on her own.</p>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 10, color: comfyStatus === "ready" ? "#86efac" : comfyStatus === "unavailable" ? "#f49aad" : "#f2bf7a", fontSize: 12 }}>
            <span style={{ width: 7, height: 7, borderRadius: 99, background: "currentColor" }} />
            {comfyStatus === "ready" ? "ComfyUI ready on this device" : comfyStatus === "checking" ? "Checking local ComfyUI…" : "ComfyUI unavailable — start it locally, then check again"}
            <button type="button" onClick={() => void checkComfy()} style={{ ...secondaryButtonStyle, padding: "3px 7px", fontSize: 11 }}>Check again</button>
          </div>
        </div>
        <button type="button" onClick={() => { abortRef.current = true; onClose(); }} style={secondaryButtonStyle}>Close</button>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.25fr) minmax(260px,.75fr)", gap: 18, marginTop: 22 }}>
        <div style={panelStyle}>
          <label style={labelStyle}>What should Hinaa create?</label>
          <textarea aria-label="Image prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the subject, scene, style, lighting, composition, and aspect ratio…" rows={7} style={{ ...inputStyle, width: "100%", resize: "vertical", lineHeight: 1.5 }} />
          <label style={{ ...labelStyle, marginTop: 14 }}>Avoid (optional)</label>
          <input aria-label="Negative image prompt" value={negativePrompt} onChange={(event) => setNegativePrompt(event.target.value)} placeholder="Blur, extra fingers, text artifacts…" style={{ ...inputStyle, width: "100%" }} />
          <button type="button" onClick={() => void generate()} disabled={!prompt.trim() || comfyStatus !== "ready" || state === "starting" || state === "processing"} style={{ ...generateButtonStyle, opacity: !prompt.trim() || comfyStatus !== "ready" || state === "starting" || state === "processing" ? .55 : 1 }}>
            {state === "starting" || state === "processing" ? <Loader2 size={18} className="spin" /> : <Wand2 size={18} />}
            {state === "starting" || state === "processing" ? "Generating locally…" : "Generate images"}
          </button>
          <p role="status" style={{ margin: "12px 0 0", color: state === "failed" ? "#f49aad" : "var(--text-secondary)", fontSize: 13 }}>{message}</p>
        </div>

        <aside style={panelStyle}>
          <label style={labelStyle}>Quality</label>
          <div style={{ display: "grid", gap: 7 }}>
            {(["fast", "quality", "ultra"] as const).map((item) => <button key={item} type="button" onClick={() => setMode(item)} style={{ ...modeButtonStyle, borderColor: mode === item ? "#ee91ad" : "rgba(255,219,231,.16)", background: mode === item ? "rgba(238,145,173,.14)" : "rgba(255,255,255,.025)" }}><strong>{item === "fast" ? "Fast" : item === "quality" ? "Quality" : "Ultra"}</strong><span>{item === "fast" ? "768 × 768" : item === "quality" ? "1024 × 1024" : "1024 × 1536"}</span></button>)}
          </div>
          <label style={{ ...labelStyle, marginTop: 16 }}>Outputs</label>
          <select aria-label="Image count" value={count} onChange={(event) => setCount(Number(event.target.value))} style={{ ...inputStyle, width: "100%" }}>{[1, 2, 4].map((value) => <option key={value} value={value}>{value} image{value > 1 ? "s" : ""}</option>)}</select>
          <label style={{ ...labelStyle, marginTop: 14 }}>Seed (optional)</label>
          <input aria-label="Image seed" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9]/g, ""))} placeholder="Random" style={{ ...inputStyle, width: "100%" }} />
          <p style={{ color: "#94a3b8", fontSize: 12, lineHeight: 1.45, marginBottom: 0 }}><Sparkles size={13} style={{ verticalAlign: "-2px" }} /> Reuse a seed to explore controlled variations after the first output is saved.</p>
        </aside>
      </div>

      {slots.length > 0 && <div aria-label="Local image generation slots" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px,1fr))", gap: 12, marginTop: 20 }}>{slots.map((slot) => {
        const source = slot.url?.replace("http://127.0.0.1:8000", "/api");
        if (source) {
          return <a key={slot.id} href={source} target="_blank" rel="noreferrer" style={{ ...panelStyle, padding: 7, textDecoration: "none" }}><img src={source} alt={`Generated image ${slot.index}`} style={{ width: "100%", display: "block", borderRadius: 9, aspectRatio: "1 / 1", objectFit: "cover" }} /><small style={{ display: "block", color: "#ffd6e1", margin: "8px 4px 2px" }}>Image {slot.index} · seed {slot.seed ?? "—"}</small></a>;
        }
        const color = slot.status === "failed" || slot.status === "cancelled" ? "#f49aad" : slot.status === "processing" ? "#f2bf7a" : "var(--text-muted)";
        return <div key={slot.id} style={{ ...panelStyle, minHeight: 170, display: "grid", placeItems: "center", textAlign: "center", color }}><ImagePlus size={24} /><strong>Image {slot.index}</strong><small>{slot.status === "processing" ? "Generating locally…" : slot.status === "pending" ? "Waiting for its sequential turn" : slot.status}</small></div>;
      })}</div>}
    </section>
  );
}

const panelStyle = { border: "1px solid var(--glass-border)", background: "rgba(255,255,255,.035)", borderRadius: 14, padding: 15, boxShadow: "inset 0 1px 0 rgba(255,255,255,.04)" } as const;
const inputStyle = { border: "1px solid rgba(255,219,231,.16)", background: "rgba(18,12,21,.68)", borderRadius: 9, color: "var(--text-primary)", padding: "10px 11px", fontSize: 13, boxSizing: "border-box" } as const;
const labelStyle = { display: "block", color: "#f5a7bb", fontSize: 11, fontWeight: 800, letterSpacing: ".08em", marginBottom: 7 } as const;
const generateButtonStyle = { width: "100%", marginTop: 16, display: "flex", gap: 9, justifyContent: "center", alignItems: "center", border: "1px solid #ffc3d3", borderRadius: 10, padding: "11px 14px", cursor: "pointer", color: "#28131d", fontWeight: 800, background: "linear-gradient(135deg,#ffd4df,#ee91ad)" } as const;
const secondaryButtonStyle = { border: "1px solid rgba(255,219,231,.18)", borderRadius: 8, background: "rgba(255,255,255,.035)", color: "var(--text-secondary)", padding: "7px 10px", cursor: "pointer" } as const;
const modeButtonStyle = { display: "grid", textAlign: "left", gap: 2, border: "1px solid", borderRadius: 9, color: "var(--text-primary)", padding: "9px 10px", cursor: "pointer" } as const;
