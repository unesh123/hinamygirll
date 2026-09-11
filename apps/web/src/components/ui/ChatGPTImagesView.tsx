import React, { useState, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Download,
  Trash2,
  Image as ImageIcon,
  ChevronDown,
  ChevronUp,
  Layers,
  Check,
  ExternalLink,
  Heart,
  MessageSquare,
  ZoomIn,
  Sliders,
  Scissors,
  Sun,
  RotateCw,
  Loader2,
  Wand2,
  Plus,
} from "lucide-react";
import { MagnificBudgetWidget } from "./MagnificBudgetWidget";

export interface ModelOption {
  id: string;
  name: string;
  cost: number;
  tier: "economy" | "balanced" | "quality" | "premium";
  description: string;
  tag: string;
}

const MAGNIFIC_MODELS: ModelOption[] = [
  {
    id: "classic-fast",
    name: "Classic Fast",
    cost: 1,
    tier: "economy",
    description: "Ultra-fast 1-credit draft model for rapid iteration.",
    tag: "1 credit · Fast",
  },
  {
    id: "classic",
    name: "Classic",
    cost: 5,
    tier: "balanced",
    description: "Balanced composition and lighting for concept art.",
    tag: "5 credits · Standard",
  },
  {
    id: "flux-fast",
    name: "Flux.1 Fast",
    cost: 5,
    tier: "balanced",
    description: "High speed Flux generation with strong prompt adherence.",
    tag: "5 credits · High Speed",
  },
  {
    id: "flux-1",
    name: "Flux.1 Standard",
    cost: 10,
    tier: "quality",
    description: "High-fidelity Flux model for intricate details and anatomy.",
    tag: "10 credits · Quality",
  },
  {
    id: "mystic-1",
    name: "Mystic 1.0",
    cost: 45,
    tier: "premium",
    description: "Photorealistic rendering engine for finished studio portraits.",
    tag: "45 credits · Photoreal",
  },
  {
    id: "mystic-2.5",
    name: "Mystic 2.5",
    cost: 50,
    tier: "premium",
    description: "Flagship engine with unmatched texture, lighting, and realism.",
    tag: "50 credits · Flagship",
  },
];

const ASPECT_RATIOS = [
  { id: "square_1_1", label: "1:1", name: "Square", ratio: "1 / 1" },
  { id: "landscape_16_9", label: "16:9", name: "Landscape", ratio: "16 / 9" },
  { id: "portrait_9_16", label: "9:16", name: "Story", ratio: "9 / 16" },
  { id: "standard_4_3", label: "4:3", name: "Standard", ratio: "4 / 3" },
  { id: "portrait_3_4", label: "3:4", name: "Portrait", ratio: "3 / 4" },
];

const QUICK_PROMPTS = [
  "Sakura blossom garden in Tokyo, Makoto Shinkai anime style, golden sunset",
  "Cyberpunk HINAA portrait, cinematic rim lighting, 8k resolution, photoreal",
  "Cute whimsical pastel vinyl sticker pack, white border, kawaii aesthetic",
  "Minimalist Japandi living room with warm white oak and soft morning sunlight",
];

interface GeneratedImage {
  id: string;
  url: string | null;
  status: "pending" | "processing" | "completed" | "failed";
  prompt: string;
  modelId?: string;
  aspectRatio?: string;
  createdAt: string;
}

interface Props {
  onOpenChat: (initialPrompt?: string, attachedImageUrl?: string) => void;
}

export function ChatGPTImagesView({ onOpenChat }: Props) {
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [showNegative, setShowNegative] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("classic-fast");
  const [aspectRatio, setAspectRatio] = useState<string>("square_1_1");
  const [count, setCount] = useState<number>(1);
  const [showRefs, setShowRefs] = useState(false);
  const [styleRef, setStyleRef] = useState("");
  const [characterRef, setCharacterRef] = useState("");
  const [objectRef, setObjectRef] = useState("");

  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImages, setGeneratedImages] = useState<GeneratedImage[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<"all" | "completed" | "favorites">("all");
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollTimersRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      pollTimersRef.current.forEach((t) => clearInterval(t));
      pollTimersRef.current.clear();
    };
  }, []);

  // Fetch past generated images on mount
  useEffect(() => {
    async function loadPastImages() {
      try {
        const res = await fetch("/api/v1/generated-images?limit=40", {
          headers: { "X-HINAA-Dev-User": "local-web-user" },
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.images) && data.images.length > 0) {
            setGeneratedImages((prev) => {
              const existingIds = new Set(prev.map((p) => p.id));
              const newItems = data.images.filter((img: any) => !existingIds.has(img.id));
              return [...prev, ...newItems];
            });
          }
        }
      } catch {
        // quiet
      }
    }
    loadPastImages();
  }, []);

  const activeModelObj = MAGNIFIC_MODELS.find((m) => m.id === selectedModel) || MAGNIFIC_MODELS[0];
  const totalEstimatedCost = activeModelObj.cost * count;

  const showToast = (msg: string) => {
    setActionFeedback(msg);
    setTimeout(() => setActionFeedback(null), 3000);
  };

  const handleToggleFavorite = (id: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRemoveImage = (id: string) => {
    setGeneratedImages((prev) => prev.filter((img) => img.id !== id));
  };

  const handleGenerate = async (overridePrompt?: string) => {
    const text = (overridePrompt || prompt).trim();
    if (!text || isGenerating) return;

    setIsGenerating(true);
    setError(null);

    try {
      // Create creative job
      const res = await fetch("/api/v1/creative/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-HINAA-Dev-User": "local-web-user",
        },
        body: JSON.stringify({
          prompt: text,
          model: selectedModel,
          aspectRatio,
          negativePrompt: showNegative ? negativePrompt : undefined,
          styleRef: styleRef || undefined,
          characterRef: characterRef || undefined,
          objectRef: objectRef || undefined,
          reference_images: [styleRef, characterRef, objectRef].filter(Boolean),
          count,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || err.detail || `Failed to create job (${res.status})`);
      }

      const data = await res.json();
      const jobId = data.job_id || data.id;

      if (!jobId) {
        throw new Error("No job ID received");
      }

      // Add slot to UI
      const newSlot: GeneratedImage = {
        id: jobId,
        url: null,
        status: "processing",
        prompt: text,
        modelId: selectedModel,
        aspectRatio,
        createdAt: new Date().toISOString(),
      };
      setGeneratedImages((prev) => [newSlot, ...prev]);

      // Poll for completion
      let attempts = 0;
      const maxAttempts = 90;
      const timer = setInterval(async () => {
        attempts++;
        if (attempts >= maxAttempts) {
          clearInterval(timer);
          pollTimersRef.current.delete(jobId);
          setIsGenerating(false);
          setGeneratedImages((prev) =>
            prev.map((img) => (img.id === jobId ? { ...img, status: "failed" } : img))
          );
          setError("Generation timed out");
          return;
        }

        try {
          const pollRes = await fetch(`/api/v1/creative/jobs/${jobId}`, {
            headers: { "X-HINAA-Dev-User": "local-web-user" },
          });
          if (pollRes.ok) {
            const jobData = await pollRes.json();
            if (jobData.status === "completed" || jobData.status === "failed") {
              clearInterval(timer);
              pollTimersRef.current.delete(jobId);
              setIsGenerating(false);

              const resolvedUrl =
                jobData.url ||
                (jobData.file_path ? `/api/v1/generated-images/${jobId}` : null);

              setGeneratedImages((prev) =>
                prev.map((img) =>
                  img.id === jobId
                    ? {
                        ...img,
                        status: jobData.status,
                        url: resolvedUrl,
                      }
                    : img
                )
              );
              if (jobData.status === "completed") {
                showToast("Image generation completed!");
              }
            }
          }
        } catch {
          // ignore network hiccups during polling
        }
      }, 1500);

      pollTimersRef.current.set(jobId, timer);
    } catch (err: any) {
      setError(err.message || "Failed to generate image");
      setIsGenerating(false);
    }
  };

  const handleUpscale = async (img: GeneratedImage) => {
    if (!img.url) return;
    showToast("Triggering Magnific 2x Upscale precision…");
    try {
      const res = await fetch("/api/v1/creative/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-HINAA-Dev-User": "local-web-user",
        },
        body: JSON.stringify({
          prompt: `Upscale: ${img.prompt}`,
          model: "upscale-2x",
          imageUrl: img.url,
          scale: 2.0,
        }),
      });
      if (res.ok) {
        showToast("Upscale job submitted successfully!");
      }
    } catch {
      showToast("Upscale queued locally.");
    }
  };

  const filteredImages = generatedImages.filter((img) => {
    if (filter === "completed") return img.status === "completed" && img.url;
    if (filter === "favorites") return favorites.has(img.id);
    return true;
  });

  return (
    <div
      style={{
        flex: 1,
        height: "100%",
        display: "flex",
        overflow: "hidden",
        background: "var(--bg-canvas)",
        color: "var(--text-primary)",
      }}
    >
      {/* ── Left Sticky Control Column (~350px) ────────────────── */}
      <aside
        style={{
          width: "min(360px, 35vw)",
          minWidth: 310,
          flexShrink: 0,
          borderRight: "1px solid var(--border-subtle)",
          background: "var(--bg-surface)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
          padding: "var(--space-4, 16px)",
          gap: "var(--space-4, 16px)",
        }}
      >
        {/* Title */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "var(--radius-md)",
                background: "var(--accent-pale)",
                color: "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Wand2 size={16} />
            </div>
            <div>
              <h2 style={{ fontSize: "var(--text-sm, 14px)", fontWeight: 750, margin: 0, color: "var(--text-primary)" }}>
                Image Studio
              </h2>
              <span style={{ fontSize: "0.68rem", color: "var(--text-tertiary)" }}>Magnific Creative Engine</span>
            </div>
          </div>
          <span
            style={{
              fontSize: "0.7rem",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: "var(--radius-pill)",
              background: "var(--accent-pale)",
              color: "var(--accent)",
            }}
          >
            v3.0
          </span>
        </div>

        {/* Model Selector */}
        <div>
          <label style={{ fontSize: "var(--text-xs, 12px)", fontWeight: 650, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
            Creative Engine & Model
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {MAGNIFIC_MODELS.map((m) => {
              const isSelected = selectedModel === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setSelectedModel(m.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 10px",
                    borderRadius: "var(--radius-md, 8px)",
                    background: isSelected ? "var(--accent-pale, rgba(244,114,182,0.12))" : "var(--bg-surface-raised, #ffffff)",
                    border: isSelected ? "1px solid var(--accent, #f472b6)" : "1px solid var(--border-subtle)",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.12s ease",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "var(--text-xs, 12px)", fontWeight: isSelected ? 700 : 600, color: isSelected ? "var(--accent)" : "var(--text-primary)" }}>
                      {m.name}
                    </div>
                    <div style={{ fontSize: "0.66rem", color: "var(--text-tertiary)", marginTop: 1 }}>
                      {m.description}
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: "0.68rem",
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: "var(--radius-pill)",
                      background: isSelected ? "var(--accent)" : "var(--bg-secondary)",
                      color: isSelected ? "#ffffff" : "var(--text-secondary)",
                      whiteSpace: "nowrap",
                      marginLeft: 8,
                    }}
                  >
                    {m.cost} {m.cost === 1 ? "credit" : "credits"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Prompt Input */}
        <div>
          <label style={{ fontSize: "var(--text-xs, 12px)", fontWeight: 650, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
            Prompt Description
          </label>
          <div
            style={{
              position: "relative",
              borderRadius: "var(--radius-lg, 12px)",
              border: "1px solid var(--border-default)",
              background: "var(--bg-surface-raised)",
              padding: "10px 12px",
              boxShadow: "var(--shadow-xs)",
            }}
          >
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe your vision… (e.g. Makoto Shinkai anime landscape, photoreal portrait, cyberpunk city)"
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                outline: "none",
                fontSize: "var(--text-xs, 12px)",
                lineHeight: 1.45,
                color: "var(--text-primary)",
                resize: "none",
                fontFamily: "inherit",
              }}
            />
            {prompt && (
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  onClick={() => setPrompt("")}
                  style={{
                    background: "none",
                    border: "none",
                    fontSize: "0.68rem",
                    color: "var(--text-tertiary)",
                    cursor: "pointer",
                    padding: 0,
                  }}
                >
                  Clear
                </button>
              </div>
            )}
          </div>

          {/* Quick prompt inspiration chips */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
            {QUICK_PROMPTS.slice(0, 2).map((qp, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setPrompt(qp)}
                style={{
                  fontSize: "0.64rem",
                  padding: "3px 8px",
                  borderRadius: "var(--radius-pill)",
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                  maxWidth: 160,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={qp}
              >
                + {qp}
              </button>
            ))}
          </div>
        </div>

        {/* References Accordion */}
        <div style={{ borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", overflow: "hidden" }}>
          <button
            type="button"
            onClick={() => setShowRefs((v) => !v)}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 12px",
              background: "var(--bg-surface)",
              border: "none",
              cursor: "pointer",
              fontSize: "var(--text-xs, 12px)",
              fontWeight: 650,
              color: "var(--text-secondary)",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Layers size={13} color="var(--accent)" />
              Reference Slots (Style & Character)
            </span>
            {showRefs ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {showRefs && (
            <div style={{ padding: "8px 12px", background: "var(--bg-canvas)", display: "flex", flexDirection: "column", gap: 10 }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span style={{ fontSize: "0.66rem", color: "var(--text-tertiary)" }}>Style Reference</span>
                  <label style={{ fontSize: "0.66rem", color: "var(--accent)", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 3 }}>
                    <Plus size={10} /> Upload Image
                    <input
                      type="file"
                      accept="image/*"
                      style={{ display: "none" }}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) {
                          const r = new FileReader();
                          r.onload = () => { if (typeof r.result === "string") setStyleRef(r.result); };
                          r.readAsDataURL(f);
                        }
                      }}
                    />
                  </label>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {styleRef && styleRef.startsWith("data:") && (
                    <img src={styleRef} alt="Style Ref" style={{ width: 28, height: 28, borderRadius: 4, objectFit: "cover" }} />
                  )}
                  <input
                    type="text"
                    value={styleRef.startsWith("data:") ? "[Uploaded Image Data]" : styleRef}
                    onChange={(e) => setStyleRef(e.target.value)}
                    placeholder="Paste style image URL or upload above…"
                    style={{
                      flex: 1,
                      fontSize: "0.7rem",
                      padding: "4px 8px",
                      borderRadius: 6,
                      border: "1px solid var(--border-default)",
                      background: "var(--bg-surface-raised)",
                      color: "var(--text-primary)",
                    }}
                  />
                  {styleRef && (
                    <button
                      type="button"
                      onClick={() => setStyleRef("")}
                      style={{ background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer", fontSize: 11 }}
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span style={{ fontSize: "0.66rem", color: "var(--text-tertiary)" }}>Character Reference</span>
                  <label style={{ fontSize: "0.66rem", color: "var(--accent)", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 3 }}>
                    <Plus size={10} /> Upload Image
                    <input
                      type="file"
                      accept="image/*"
                      style={{ display: "none" }}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) {
                          const r = new FileReader();
                          r.onload = () => { if (typeof r.result === "string") setCharacterRef(r.result); };
                          r.readAsDataURL(f);
                        }
                      }}
                    />
                  </label>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {characterRef && characterRef.startsWith("data:") && (
                    <img src={characterRef} alt="Char Ref" style={{ width: 28, height: 28, borderRadius: 4, objectFit: "cover" }} />
                  )}
                  <input
                    type="text"
                    value={characterRef.startsWith("data:") ? "[Uploaded Image Data]" : characterRef}
                    onChange={(e) => setCharacterRef(e.target.value)}
                    placeholder="Paste character reference URL or upload above…"
                    style={{
                      flex: 1,
                      fontSize: "0.7rem",
                      padding: "4px 8px",
                      borderRadius: 6,
                      border: "1px solid var(--border-default)",
                      background: "var(--bg-surface-raised)",
                      color: "var(--text-primary)",
                    }}
                  />
                  {characterRef && (
                    <button
                      type="button"
                      onClick={() => setCharacterRef("")}
                      style={{ background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer", fontSize: 11 }}
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Negative Prompt Accordion */}
        <div style={{ borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", overflow: "hidden" }}>
          <button
            type="button"
            onClick={() => setShowNegative((v) => !v)}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 12px",
              background: "var(--bg-surface)",
              border: "none",
              cursor: "pointer",
              fontSize: "var(--text-xs, 12px)",
              fontWeight: 650,
              color: "var(--text-secondary)",
            }}
          >
            <span>Negative Prompt (Exclusions)</span>
            {showNegative ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {showNegative && (
            <div style={{ padding: "8px 12px", background: "var(--bg-canvas)" }}>
              <input
                type="text"
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder="e.g. blurry, lowres, distorted fingers, bad anatomy"
                style={{
                  width: "100%",
                  fontSize: "0.7rem",
                  padding: "6px 8px",
                  borderRadius: 6,
                  border: "1px solid var(--border-default)",
                  background: "var(--bg-surface-raised)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
          )}
        </div>

        {/* Aspect Ratio Selector */}
        <div>
          <label style={{ fontSize: "var(--text-xs, 12px)", fontWeight: 650, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
            Aspect Ratio
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4 }}>
            {ASPECT_RATIOS.map((ar) => {
              const isSelected = aspectRatio === ar.id;
              return (
                <button
                  key={ar.id}
                  type="button"
                  onClick={() => setAspectRatio(ar.id)}
                  style={{
                    padding: "6px 4px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: isSelected ? "var(--accent)" : "var(--bg-secondary)",
                    color: isSelected ? "#ffffff" : "var(--text-secondary)",
                    border: isSelected ? "1px solid var(--accent)" : "1px solid var(--border-subtle)",
                    cursor: "pointer",
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    textAlign: "center",
                  }}
                  title={ar.name}
                >
                  {ar.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Quantity Selector */}
        <div>
          <label style={{ fontSize: "var(--text-xs, 12px)", fontWeight: 650, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
            Quantity
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
            {[1, 2, 4].map((q) => {
              const isSelected = count === q;
              return (
                <button
                  key={q}
                  type="button"
                  onClick={() => setCount(q)}
                  style={{
                    padding: "6px 8px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: isSelected ? "var(--accent-pale)" : "var(--bg-secondary)",
                    color: isSelected ? "var(--accent)" : "var(--text-secondary)",
                    border: isSelected ? "1px solid var(--accent)" : "1px solid var(--border-subtle)",
                    cursor: "pointer",
                    fontSize: "var(--text-xs, 12px)",
                    fontWeight: 700,
                  }}
                >
                  {q} {q === 1 ? "image" : "images"}
                </button>
              );
            })}
          </div>
        </div>

        {/* Dynamic Credit Estimation & Generate Button */}
        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 12px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent-pale, rgba(244, 114, 182, 0.08))",
              border: "1px solid rgba(244, 114, 182, 0.2)",
            }}
          >
            <span style={{ fontSize: "var(--text-xs, 12px)", color: "var(--text-secondary)" }}>
              Estimated Spend:
            </span>
            <span style={{ fontSize: "var(--text-sm, 14px)", fontWeight: 800, color: "var(--accent, #f472b6)" }}>
              ⚡ {totalEstimatedCost} {totalEstimatedCost === 1 ? "credit" : "credits"}
            </span>
          </div>

          <button
            type="button"
            onClick={() => handleGenerate()}
            disabled={isGenerating || !prompt.trim()}
            style={{
              width: "100%",
              padding: "12px 16px",
              borderRadius: "var(--radius-lg, 12px)",
              background: "var(--accent, #f472b6)",
              color: "#ffffff",
              border: "none",
              fontSize: "var(--text-sm, 14px)",
              fontWeight: 750,
              cursor: isGenerating || !prompt.trim() ? "not-allowed" : "pointer",
              opacity: isGenerating || !prompt.trim() ? 0.6 : 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              boxShadow: "0 4px 14px var(--accent-glow)",
              transition: "all 0.15s ease",
            }}
          >
            {isGenerating ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Sparkles size={16} />
                Generate ({totalEstimatedCost}c)
              </>
            )}
          </button>
          {error && (
            <div style={{ fontSize: "0.72rem", color: "var(--danger-text, #e11d48)", textAlign: "center" }}>
              ⚠️ {error}
            </div>
          )}
        </div>
      </aside>

      {/* ── Right Workspace Column (flex-1) ────────────────────── */}
      <main
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "var(--space-6, 24px)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-6, 24px)",
        }}
      >
        {/* Top: Sakura Magnific Budget Bar */}
        <MagnificBudgetWidget />

        {/* Action toast feedback */}
        <AnimatePresence>
          {actionFeedback && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-pill)",
                background: "var(--accent)",
                color: "#ffffff",
                fontSize: "var(--text-xs)",
                fontWeight: 650,
                alignSelf: "center",
                boxShadow: "var(--shadow-md)",
              }}
            >
              {actionFeedback}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Gallery Filter & Status Bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {(["all", "completed", "favorites"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                style={{
                  padding: "4px 12px",
                  borderRadius: "var(--radius-pill)",
                  background: filter === f ? "var(--accent)" : "var(--bg-secondary)",
                  color: filter === f ? "#ffffff" : "var(--text-secondary)",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "var(--text-xs, 12px)",
                  fontWeight: 650,
                  cursor: "pointer",
                  textTransform: "capitalize",
                }}
              >
                {f}
              </button>
            ))}
          </div>

          <span style={{ fontSize: "var(--text-xs, 12px)", color: "var(--text-tertiary)" }}>
            {filteredImages.length} {filteredImages.length === 1 ? "creation" : "creations"}
          </span>
        </div>

        {/* Creations Grid */}
        {filteredImages.length === 0 ? (
          <div
            style={{
              padding: "60px 20px",
              textAlign: "center",
              borderRadius: "var(--radius-xl, 16px)",
              background: "var(--bg-surface-raised)",
              border: "1px dashed var(--border-default)",
              color: "var(--text-tertiary)",
            }}
          >
            <ImageIcon size={40} style={{ margin: "0 auto 12px auto", opacity: 0.5 }} />
            <h3 style={{ fontSize: "var(--text-sm, 14px)", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
              No images in this view
            </h3>
            <p style={{ fontSize: "var(--text-xs, 12px)", maxWidth: 360, margin: "0 auto" }}>
              Compose a prompt in the left controls panel and click Generate to produce your first high-fidelity Magnific visual.
            </p>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: 16,
            }}
          >
            {filteredImages.map((img) => {
              const isFav = favorites.has(img.id);
              return (
                <motion.div
                  key={img.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  style={{
                    borderRadius: "var(--radius-lg, 12px)",
                    overflow: "hidden",
                    background: "var(--bg-surface-raised)",
                    border: "1px solid var(--border-subtle)",
                    boxShadow: "var(--shadow-sm)",
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                  }}
                >
                  {/* Image Viewport */}
                  <div
                    style={{
                      width: "100%",
                      aspectRatio: "1 / 1",
                      background: "var(--bg-secondary)",
                      position: "relative",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      overflow: "hidden",
                    }}
                  >
                    {img.status === "completed" && img.url ? (
                      <img
                        src={img.url}
                        alt={img.prompt}
                        referrerPolicy="no-referrer"
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    ) : img.status === "failed" ? (
                      <div style={{ textAlign: "center", padding: 16, color: "var(--danger-text)" }}>
                        <span style={{ fontSize: "1.5rem" }}>⚠️</span>
                        <div style={{ fontSize: "0.75rem", marginTop: 6, fontWeight: 650 }}>Generation Failed</div>
                      </div>
                    ) : (
                      <div style={{ textAlign: "center", padding: 16 }}>
                        <Loader2 size={28} className="animate-spin" style={{ color: "var(--accent)", margin: "0 auto" }} />
                        <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)", marginTop: 8 }}>
                          Rendering {img.modelId || "creative"}…
                        </div>
                      </div>
                    )}

                    {/* Top Right Floating Actions: Favorite & Remove */}
                    <div style={{ position: "absolute", top: 8, right: 8, display: "flex", gap: 4, zIndex: 2 }}>
                      <button
                        type="button"
                        onClick={() => handleToggleFavorite(img.id)}
                        style={{
                          width: 26,
                          height: 26,
                          borderRadius: "50%",
                          background: "rgba(255, 255, 255, 0.85)",
                          backdropFilter: "blur(6px)",
                          border: "none",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: isFav ? "#ec4899" : "var(--text-secondary)",
                          cursor: "pointer",
                        }}
                        title={isFav ? "Remove Favorite" : "Favorite"}
                      >
                        <Heart size={13} fill={isFav ? "#ec4899" : "none"} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveImage(img.id)}
                        style={{
                          width: 26,
                          height: 26,
                          borderRadius: "50%",
                          background: "rgba(255, 255, 255, 0.85)",
                          backdropFilter: "blur(6px)",
                          border: "none",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "var(--text-tertiary)",
                          cursor: "pointer",
                        }}
                        title="Remove Card"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  {/* Info and Actions Toolbar */}
                  <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
                    <p
                      style={{
                        margin: 0,
                        fontSize: "0.72rem",
                        color: "var(--text-secondary)",
                        lineHeight: 1.35,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                      }}
                      title={img.prompt}
                    >
                      {img.prompt}
                    </p>

                    {/* Action Buttons Row */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        paddingTop: 6,
                        borderTop: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div style={{ display: "flex", gap: 4 }}>
                        {img.url && img.status === "completed" && (
                          <>
                            {/* Upscale */}
                            <button
                              type="button"
                              onClick={() => handleUpscale(img)}
                              style={{
                                padding: "3px 7px",
                                borderRadius: 6,
                                background: "var(--bg-secondary)",
                                border: "1px solid var(--border-subtle)",
                                color: "var(--text-secondary)",
                                fontSize: "0.68rem",
                                fontWeight: 600,
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                gap: 3,
                              }}
                              title="Magnific 2x Upscale"
                            >
                              <ZoomIn size={11} /> Upscale
                            </button>

                            {/* Use as Reference */}
                            <button
                              type="button"
                              onClick={() => {
                                setStyleRef(img.url!);
                                setShowRefs(true);
                                showToast("Added image as Style Reference in controls!");
                              }}
                              style={{
                                padding: "3px 7px",
                                borderRadius: 6,
                                background: "var(--bg-secondary)",
                                border: "1px solid var(--border-subtle)",
                                color: "var(--text-secondary)",
                                fontSize: "0.68rem",
                                fontWeight: 600,
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                gap: 3,
                              }}
                              title="Use as Style Reference"
                            >
                              <Sliders size={11} /> Ref
                            </button>

                            {/* Use in Chat */}
                            <button
                              type="button"
                              onClick={() => {
                                onOpenChat(img.prompt, img.url!);
                              }}
                              style={{
                                padding: "3px 7px",
                                borderRadius: 6,
                                background: "var(--accent-pale)",
                                border: "1px solid rgba(244,114,182,0.25)",
                                color: "var(--accent)",
                                fontSize: "0.68rem",
                                fontWeight: 650,
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                gap: 3,
                              }}
                              title="Chat about this image with HINAA"
                            >
                              <MessageSquare size={11} /> Chat
                            </button>
                          </>
                        )}
                      </div>

                      {/* Download link */}
                      {img.url && img.status === "completed" && (
                        <a
                          href={img.url}
                          download={`hinaa-${img.id}.jpg`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            width: 24,
                            height: 24,
                            borderRadius: 6,
                            background: "var(--bg-secondary)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "var(--text-secondary)",
                            textDecoration: "none",
                          }}
                          title="Download Asset"
                        >
                          <Download size={12} />
                        </a>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
