import { useEffect, useRef, useState } from "react";
import { ImagePlus, Loader2, Sparkles, Wand2 } from "lucide-react";

interface ImageResult {
  id?: string;
  url?: string;
  image_url?: string;
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
      const jobId = startData.job_id ?? startData.data?.job_id;
      if (!start.ok || !jobId) throw new Error(startData?.message || "The local image job could not start.");

      setState("processing");
      setMessage("Hinaa is generating locally. You can keep chatting while this finishes.");
      for (let attempt = 0; attempt < 180 && !abortRef.current; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        const poll = await fetch(`/api/v1/tools/poll?job_id=${encodeURIComponent(jobId)}`);
        const result = await poll.json();
        if (!poll.ok) throw new Error(result?.message || "Could not read image progress.");
        if (result.status === "success") {
          setImages(result.images || []);
          setState("complete");
          setMessage(`${(result.images || []).length} local image${(result.images || []).length === 1 ? "" : "s"} ready.`);
          return;
        }
        if (result.status === "error" || result.status === "failed") throw new Error(result.error || "The local image workflow failed.");
        setMessage(result.total ? `Generating ${result.images?.length || 0} of ${result.total} image outputs…` : "Generating locally…");
      }
      if (!abortRef.current) throw new Error("The image job took too long. Check that ComfyUI is running locally.");
    } catch (error) {
      setState("failed");
      setMessage(error instanceof Error ? error.message : "Image generation failed.");
    }
  };

  return (
    <section style={{ padding: 20, color: "#e2e8f0", maxWidth: 940, margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
        <div>
          <p style={{ margin: 0, color: "#5eead4", fontSize: 11, fontWeight: 800, letterSpacing: "0.12em" }}>LOCAL CREATOR</p>
          <h2 style={{ margin: "5px 0", fontSize: 25 }}>Image studio</h2>
          <p style={{ margin: 0, color: "#94a3b8", lineHeight: 1.5 }}>Create locally through your configured ComfyUI workflow. Generate is an explicit action; Hinaa will not start image jobs on her own.</p>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 10, color: comfyStatus === "ready" ? "#6ee7b7" : comfyStatus === "unavailable" ? "#fda4af" : "#fde68a", fontSize: 12 }}>
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
          <p role="status" style={{ margin: "12px 0 0", color: state === "failed" ? "#fda4af" : "#cbd5e1", fontSize: 13 }}>{message}</p>
        </div>

        <aside style={panelStyle}>
          <label style={labelStyle}>Quality</label>
          <div style={{ display: "grid", gap: 7 }}>
            {(["fast", "quality", "ultra"] as const).map((item) => <button key={item} type="button" onClick={() => setMode(item)} style={{ ...modeButtonStyle, borderColor: mode === item ? "#2dd4bf" : "rgba(148,163,184,.28)", background: mode === item ? "rgba(20,184,166,.14)" : "rgba(15,23,42,.5)" }}><strong>{item === "fast" ? "Fast" : item === "quality" ? "Quality" : "Ultra"}</strong><span>{item === "fast" ? "768 × 768" : item === "quality" ? "1024 × 1024" : "1024 × 1536"}</span></button>)}
          </div>
          <label style={{ ...labelStyle, marginTop: 16 }}>Outputs</label>
          <select aria-label="Image count" value={count} onChange={(event) => setCount(Number(event.target.value))} style={{ ...inputStyle, width: "100%" }}>{[1, 2, 4].map((value) => <option key={value} value={value}>{value} image{value > 1 ? "s" : ""}</option>)}</select>
          <label style={{ ...labelStyle, marginTop: 14 }}>Seed (optional)</label>
          <input aria-label="Image seed" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9]/g, ""))} placeholder="Random" style={{ ...inputStyle, width: "100%" }} />
          <p style={{ color: "#94a3b8", fontSize: 12, lineHeight: 1.45, marginBottom: 0 }}><Sparkles size={13} style={{ verticalAlign: "-2px" }} /> Reuse a seed to explore controlled variations after the first output is saved.</p>
        </aside>
      </div>

      {images.length > 0 && <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px,1fr))", gap: 12, marginTop: 20 }}>{images.map((image, index) => {
        const source = typeof image === "string" ? image.replace("http://127.0.0.1:8000", "/api") : image.url || image.image_url || (image.id ? `/api/v1/generated-images/${image.id}` : "");
        return source ? <a key={source} href={source} target="_blank" rel="noreferrer" style={{ ...panelStyle, padding: 7, textDecoration: "none" }}><img src={source} alt={`Generated image ${index + 1}`} style={{ width: "100%", display: "block", borderRadius: 9, aspectRatio: "1 / 1", objectFit: "cover" }} /></a> : <div key={index} style={panelStyle}><ImagePlus /> Image result ready</div>;
      })}</div>}
    </section>
  );
}

const panelStyle = { border: "1px solid rgba(148,163,184,.22)", background: "rgba(15,23,42,.65)", borderRadius: 14, padding: 15 } as const;
const inputStyle = { border: "1px solid rgba(148,163,184,.28)", background: "rgba(2,6,23,.62)", borderRadius: 9, color: "#f8fafc", padding: "10px 11px", fontSize: 13, boxSizing: "border-box" } as const;
const labelStyle = { display: "block", color: "#99f6e4", fontSize: 11, fontWeight: 800, letterSpacing: ".08em", marginBottom: 7 } as const;
const generateButtonStyle = { width: "100%", marginTop: 16, display: "flex", gap: 9, justifyContent: "center", alignItems: "center", border: 0, borderRadius: 10, padding: "11px 14px", cursor: "pointer", color: "#042f2e", fontWeight: 800, background: "linear-gradient(135deg,#5eead4,#7dd3fc)" } as const;
const secondaryButtonStyle = { border: "1px solid rgba(148,163,184,.3)", borderRadius: 8, background: "transparent", color: "#cbd5e1", padding: "7px 10px", cursor: "pointer" } as const;
const modeButtonStyle = { display: "grid", textAlign: "left", gap: 2, border: "1px solid", borderRadius: 9, color: "#e2e8f0", padding: "9px 10px", cursor: "pointer" } as const;
