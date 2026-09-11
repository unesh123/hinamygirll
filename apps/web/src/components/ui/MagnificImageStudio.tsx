/**
 * MagnificImageStudio — Hinaa's cloud-first image generation room.
 *
 * Replaces the old ComfyUI-config-first studio: this UI speaks Magnific FLUX
 * (prompt enhancement, style presets, quality tiers, reference-guided
 * generation, seed families) and only mentions the local renderer as a
 * fallback line in the status strip. Job lifecycle stays on the durable
 * tools API (execute → poll), so generation survives closing the panel.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { gsap } from "gsap";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check, Copy, Dice5, Download, Eraser, ImagePlus, Loader2, RefreshCw,
  Sparkles, Upload, Wand2, X,
} from "lucide-react";
import styles from "./MagnificImageStudio.module.css";

type Quality = "fast" | "quality" | "ultra";
type StyleId = "custom" | "anime" | "realistic" | "cinematic" | "3d-art" | "watercolor" | "digital";

interface Slot {
  id: string;
  index: number;
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  seed?: number;
  width?: number;
  height?: number;
  url?: string | null;
}

const STYLES: Array<{ id: StyleId; label: string; hint: string }> = [
  { id: "anime", label: "Anime", hint: "cel shaded · vibrant" },
  { id: "realistic", label: "Realistic", hint: "photographic · 8k" },
  { id: "cinematic", label: "Cinematic", hint: "movie still · drama" },
  { id: "3d-art", label: "3D Art", hint: "octane · volumetric" },
  { id: "watercolor", label: "Watercolor", hint: "soft pigment wash" },
  { id: "digital", label: "Digital", hint: "concept art polish" },
  { id: "custom", label: "Custom", hint: "your words only" },
];

const QUALITY: Array<{ id: Quality; label: string; detail: string }> = [
  { id: "fast", label: "Fast", detail: "768² · quick draft" },
  { id: "quality", label: "Quality", detail: "1024² · balanced" },
  { id: "ultra", label: "Ultra", detail: "1024×1536 + Magnific upscale" },
];

function normalizeSlots(raw: Array<Partial<Slot> & Record<string, unknown>>): Slot[] {
  return raw.map((slot, i) => ({
    id: String(slot.id ?? `slot-${i}`),
    index: Number(slot.index ?? i + 1),
    status: (slot.status as Slot["status"]) ?? "pending",
    seed: slot.seed == null ? undefined : Number(slot.seed),
    width: slot.width == null ? undefined : Number(slot.width),
    height: slot.height == null ? undefined : Number(slot.height),
    url: typeof slot.url === "string" && slot.url
      ? slot.url.replace(/^https?:\/\/127\.0\.0\.1:8000\/v1\//, "/api/v1/")
      : null,
  }));
}

interface MagnificImageStudioProps {
  onClose?: () => void;
}

export function MagnificImageStudio({ onClose }: MagnificImageStudioProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState("");
  const [showNegative, setShowNegative] = useState(false);
  const [style, setStyle] = useState<StyleId>("anime");
  const [quality, setQuality] = useState<Quality>("quality");
  const [count, setCount] = useState(1);
  const [seed, setSeed] = useState("");
  const [enhance, setEnhance] = useState(true);
  const [reference, setReference] = useState<{ kind: "data" | "query"; value: string; name?: string } | null>(null);
  const [status, setStatus] = useState<"idle" | "starting" | "processing" | "done" | "error">("idle");
  const [message, setMessage] = useState("Describe anything. Hinaa sharpens the prompt, then Magnific FLUX renders it.");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [renderer, setRenderer] = useState<string | null>(null);
  const [enhancedPrompt, setEnhancedPrompt] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const abortRef = useRef(false);
  const seedRef = useRef("");
  const busy = status === "starting" || status === "processing";

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    // jsdom never ticks rAF, so an autoAlpha entrance would strand the panel
    // hidden and starve accessibility queries.
    if (import.meta.env.MODE === "test") return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (reduce) return;
    const ctx = gsap.context(() => {
      gsap.from(root.querySelectorAll("[data-studio-section]"), {
        autoAlpha: 0,
        y: 14,
        duration: 0.55,
        ease: "power3.out",
        stagger: 0.06,
      });
    }, root);
    return () => ctx.revert();
  }, []);

  const previewReference = useCallback(async (file: File) => {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setReference({ kind: "data", value: reader.result, name: file.name });
        setMessage("Reference attached. Hinaa will guide the generation with this image.");
      }
    };
    reader.readAsDataURL(file);
  }, []);

  const stop = useCallback(() => {
    abortRef.current = true;
    setStatus("idle");
    setMessage("Watching was paused. The durable job keeps running server-side; re-open later to see results.");
  }, []);

  const generate = useCallback(async () => {
    const clean = prompt.trim();
    if (!clean || busy) return;
    abortRef.current = false;
    setStatus("starting");
    setMessage(enhance ? "Hinaa is sharpening the prompt…" : "Queuing the job…");
    setSlots(Array.from({ length: count }, (_, i) => ({ id: `pre-${i}`, index: i + 1, status: "pending" as const })));
    setEnhancedPrompt(null);
    try {
      const parameters: Record<string, unknown> = {
        prompt: clean,
        negative_prompt: negative.trim(),
        mode: quality,
        style,
        enhance,
        count,
        strategy: "VARIATIONS",
      };
      if (seedRef.current.trim() && Number.isFinite(Number(seedRef.current))) parameters.seed = Number(seedRef.current);
      if (reference?.kind === "data") parameters.reference_image_b64 = reference.value;
      if (reference?.kind === "query") parameters.reference_query = reference.value;

      const start = await fetch("/api/v1/tools/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ toolName: "image_generate", confirmed: true, parameters }),
      });
      const body = await start.json();
      const tool = body?.data?.data ?? body?.data ?? body;
      const newJobId: string | null = tool?.job_id ?? body?.job_id ?? null;
      if (!start.ok || tool?.status === "error" || !newJobId) {
        throw new Error(tool?.error || body?.error || body?.message || "The image job could not start.");
      }
      setRenderer(tool?.renderer ?? null);
      if (Array.isArray(tool?.slots)) setSlots(normalizeSlots(tool.slots));
      if (tool?.enhanced_prompt) setEnhancedPrompt(String(tool.enhanced_prompt));
      setStatus("processing");
      setMessage(tool?.renderer === "magnific-flux" ? "Magnific FLUX is rendering." : "Local renderer is working — the cloud key was not found.");

      for (let attempt = 0; attempt < 240 && !abortRef.current; attempt += 1) {
        await new Promise((r) => setTimeout(r, 1500));
        let poll: Response;
        try {
          poll = await fetch(`/api/v1/tools/poll?job_id=${encodeURIComponent(newJobId)}`);
        } catch {
          continue; // transient network blips must not kill the watch
        }
        const result = await poll.json();
        if (!poll.ok) throw new Error(result?.message || "Progress could not be read.");
        if (Array.isArray(result.slots)) setSlots(normalizeSlots(result.slots));
        if (result.status === "success" || result.status === "partial") {
          const done = Number(result.completed ?? result.images?.length ?? 0);
          setStatus("done");
          setMessage(result.status === "partial"
            ? `${done} of ${result.total ?? done} images are ready — some slots failed.`
            : `${done} image${done === 1 ? "" : "s"} ready in your studio.`);
          return;
        }
        if (result.status === "error") throw new Error(result.error || "The generation workflow failed.");
        const active = (result.slots as Slot[] | undefined)?.find((s) => s.status === "processing");
        setMessage(active
          ? `Rendering image ${active.index} of ${result.total ?? count}${active.seed ? ` · seed ${active.seed}` : ""}…`
          : `Generating ${result.completed ?? 0}/${result.total ?? count}…`);
      }
      if (!abortRef.current) setStatus("done");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Generation failed. Check the API key and retry.");
    }
  }, [busy, count, enhance, negative, prompt, quality, reference, style]);

  const results = useMemo(() => slots.filter((s) => s.status === "completed" && s.url), [slots]);

  const exploreVariations = useCallback(async (fromSeed?: number) => {
    if (fromSeed && Number.isFinite(fromSeed)) {
      seedRef.current = String(fromSeed);
      setSeed(String(fromSeed));
      setMessage(`Seed ${fromSeed} locked. Generating a variation family from it…`);
    }
    await generateRef.current();
  }, []);
  const generateRef = useRef<() => Promise<void>>(async () => undefined);
  useEffect(() => { generateRef.current = generate; }, [generate]);

  return (
    <div ref={rootRef} className={styles.studio} data-testid="magnific-image-studio">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>MAGNIFIC · FLUX.2 CLOUD STUDIO</p>
          <h2>Image Studio</h2>
          <p className={styles.sub}>
            Hinaa enhances every prompt with lighting, camera, mood, and quality markers before it renders.
          </p>
        </div>
        {onClose && (
          <button type="button" className={styles.iconBtn} onClick={onClose} aria-label="Close image studio">
            <X size={16} />
          </button>
        )}
      </header>

      <section className={styles.card} data-studio-section>
        <label className={styles.label} htmlFor="magnific-prompt">Prompt</label>
        <textarea
          id="magnific-prompt"
          className={styles.prompt}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Mikasa standing on the wall at sunset, scarves in the wind…"
          rows={3}
        />
        <div className={styles.promptMeta}>
          <button
            type="button"
            className={`${styles.toggle} ${enhance ? styles.toggleOn : ""}`}
            onClick={() => setEnhance((v) => !v)}
            aria-pressed={enhance}
          >
            <Wand2 size={12} /> {enhance ? "Prompt enhancer on" : "Prompt enhancer off"}
          </button>
          <button type="button" className={styles.linkBtn} onClick={() => setShowNegative((v) => !v)}>
            {showNegative ? "Hide" : "Add"} negative prompt
          </button>
        </div>
        <AnimatePresence initial={false}>
          {showNegative && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              style={{ overflow: "hidden" }}
            >
              <input
                className={styles.input}
                value={negative}
                onChange={(e) => setNegative(e.target.value)}
                placeholder="extra fingers, text, watermark…"
                aria-label="Negative prompt"
              />
            </motion.div>
          )}
        </AnimatePresence>
        {enhancedPrompt && (
          <div className={styles.enhanced}>
            <span><Sparkles size={11} /> Enhanced prompt</span>
            <p>{enhancedPrompt}</p>
            <button
              type="button"
              className={styles.linkBtn}
              onClick={() => { void navigator.clipboard?.writeText(enhancedPrompt); setCopied(true); window.setTimeout(() => setCopied(false), 1400); }}
            >
              {copied ? <Check size={11} /> : <Copy size={11} />} {copied ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </section>

      <section className={styles.card} data-studio-section>
        <span className={styles.label}>Style preset</span>
        <div className={styles.chips}>
          {STYLES.map((s) => (
            <motion.button
              key={s.id}
              type="button"
              className={`${styles.chip} ${style === s.id ? styles.chipActive : ""}`}
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setStyle(s.id)}
              aria-pressed={style === s.id}
            >
              <strong>{s.label}</strong>
              <small>{s.hint}</small>
            </motion.button>
          ))}
        </div>

        <span className={styles.label}>Quality tier</span>
        <div className={styles.segRow}>
          {QUALITY.map((q) => (
            <button
              key={q.id}
              type="button"
              className={`${styles.seg} ${quality === q.id ? styles.segActive : ""}`}
              onClick={() => setQuality(q.id)}
              aria-pressed={quality === q.id}
            >
              <strong>{q.label}</strong>
              <small>{q.detail}</small>
            </button>
          ))}
        </div>

        <div className={styles.row}>
          <div className={styles.rowGrow}>
            <span className={styles.label}>Count</span>
            <div className={styles.stepper}>
              {[1, 2, 3, 4].map((n) => (
                <button key={n} type="button" className={count === n ? styles.stepActive : ""} onClick={() => setCount(n)} aria-pressed={count === n}>
                  {n}
                </button>
              ))}
            </div>
          </div>
          <div className={styles.rowGrow}>
            <span className={styles.label}>Seed</span>
            <div className={styles.seedRow}>
              <input
                className={styles.input}
                inputMode="numeric"
                value={seed}
                onChange={(e) => { const v = e.target.value.replace(/[^\d]/g, ""); setSeed(v); seedRef.current = v; }}
                placeholder="auto"
                aria-label="Seed (leave empty for automatic)"
              />
              <button type="button" className={styles.iconBtn} onClick={() => { const v = String(Math.floor(Math.random() * 999_999)); setSeed(v); seedRef.current = v; }} aria-label="Randomize seed">
                <Dice5 size={14} />
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.card} data-studio-section>
        <span className={styles.label}>Visual reference</span>
        <div className={styles.refRow}>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className={styles.srFile}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void previewReference(f); e.target.value = ""; }}
          />
          <button type="button" className={styles.refBtn} onClick={() => fileRef.current?.click()}>
            <Upload size={13} /> Upload image
          </button>
          <button
            type="button"
            className={`${styles.refBtn} ${reference?.kind === "query" ? styles.refBtnActive : ""}`}
            onClick={() => setReference(reference?.kind === "query" ? null : { kind: "query", value: prompt.trim() || "the subject" })}
          >
            <ImagePlus size={13} /> Find on web
          </button>
          {reference && (
            <span className={styles.refChip}>
              {reference.kind === "data" ? `📎 ${reference.name ?? "upload"}` : `🔎 “${reference.value.slice(0, 40)}”`}
              <button type="button" aria-label="Remove reference" onClick={() => setReference(null)}><Eraser size={11} /></button>
            </span>
          )}
        </div>
        <p className={styles.hint}>
          “Find on web” lets Hinaa fetch a fresh reference for your subject — say it in chat and she does the same after image searches.
        </p>
      </section>

      <div className={styles.actions} data-studio-section>
        <motion.button
          type="button"
          className={styles.generate}
          onClick={() => void generate()}
          disabled={!prompt.trim() || busy}
          whileTap={{ scale: 0.98 }}
        >
          {busy ? <Loader2 size={15} className={styles.spin} /> : <Sparkles size={15} />}
          {status === "processing" ? "Generating…" : "✨ Generate with Magnific"}
        </motion.button>
        {busy && (
          <button type="button" className={styles.stopBtn} onClick={stop}>
            <RefreshCw size={12} /> Stop watching
          </button>
        )}
      </div>

      <p className={styles.status} role="status">
        {renderer && <span className={styles.badge}>{renderer === "magnific-flux" ? "MAGNIFIC FLUX" : "LOCAL RENDER"}</span>}
        {message}
      </p>

      {(slots.length > 0 || busy) && (
        <section className={styles.results} data-studio-section>
          <h3>Results</h3>
          <div className={styles.grid}>
            {Array.from({ length: Math.max(count, slots.length) }).map((_, i) => {
              const slot = slots[i];
              const completed = slot?.status === "completed" && slot.url;
              const failed = slot?.status === "failed";
              return (
                <motion.div
                  key={slot?.id ?? `slot-${i}`}
                  className={`${styles.slot} ${completed ? styles.slotDone : ""} ${failed ? styles.slotFailed : ""}`}
                  layout
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.32, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
                >
                  {completed ? (
                    <button type="button" className={styles.thumbBtn} onClick={() => setLightbox(slot.url!)} aria-label={`Open image ${i + 1}`}>
                      <img src={slot.url!} alt={`Generated ${slot.index ?? i + 1}`} loading="lazy" />
                    </button>
                  ) : (
                    <div className={styles.slotBusy}>
                      {failed ? <X size={16} /> : <div className={styles.shimmer} />}
                      <span>{failed ? "Slot failed" : slot?.status === "processing" ? "Rendering…" : "Queued"}</span>
                      {slot?.seed ? <small>seed {slot.seed}</small> : null}
                    </div>
                  )}
                  {completed && (
                    <div className={styles.slotActions}>
                      <a href={slot.url!} download={`hinaa-${slot.seed ?? i}.png`} aria-label="Download image"><Download size={12} /></a>
                      <button type="button" onClick={() => void exploreVariations(slot.seed)} aria-label="Explore variations from this seed"><Dice5 size={12} /></button>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
          {results.length > 0 && (
            <p className={styles.hint}>Re-use a seed or the “Find on web” reference to explore variations Hinaa remembers.</p>
          )}
        </section>
      )}

      <AnimatePresence>
        {lightbox && (
          <motion.div
            className={styles.lightbox}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setLightbox(null)}
            role="dialog"
            aria-label="Image preview"
          >
            <motion.img
              src={lightbox}
              alt="Generated preview"
              initial={{ scale: 0.92, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: "spring", stiffness: 260, damping: 24 }}
              onClick={(e) => e.stopPropagation()}
            />
            <button type="button" className={styles.lightboxClose} onClick={() => setLightbox(null)} aria-label="Close preview">
              <X size={16} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default MagnificImageStudio;
