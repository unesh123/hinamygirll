import React, { useState, useEffect, useRef } from "react";

export type CreativeMode = "create_image" | "edit_image" | "create_video" | "timeline_video";

export interface CreativeCapability {
  operation: string;
  status: "AVAILABLE" | "UNAVAILABLE" | "BLOCKED" | "CONFIG_REQUIRED";
  provider: string;
  model: string;
  description_en: string;
  description_ne: string;
  limitations: string[];
}

export interface CreativeAsset {
  asset_id: string;
  filename: string;
  media_type: "IMAGE" | "VIDEO" | "ANIMATION";
  mime_type: string;
  width: number;
  height: number;
  file_size_bytes: number;
  sha256_hash: string;
  created_at: string;
  operation: string;
  provider: string;
  prompt?: string;
  seed?: number;
  duration_seconds?: number;
}

export const CreativeStudioPanel: React.FC = () => {
  const [mode, setMode] = useState<CreativeMode>("create_image");
  const [capabilities, setCapabilities] = useState<Record<string, CreativeCapability>>({});
  const [prompt, setPrompt] = useState<string>("");
  const [promptNe, setPromptNe] = useState<string>("");
  const [aspectRatio, setAspectRatio] = useState<string>("1:1");
  const [seed, setSeed] = useState<string>("");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<string>("IDLE");
  const [jobProgress, setJobProgress] = useState<number>(0);
  const [jobLabel, setJobLabel] = useState<string>("");
  const [assets, setAssets] = useState<CreativeAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<CreativeAsset | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Inpainting mask canvas state
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [uploadedSourceId, setUploadedSourceId] = useState<string | null>(null);
  const [uploadedSourceUrl, setUploadedSourceUrl] = useState<string | null>(null);
  const [brushSize, setBrushSize] = useState<number>(20);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);

  // Fetch capabilities on mount
  useEffect(() => {
    fetch("/api/creative/capabilities")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.capabilities) {
          setCapabilities(data.capabilities);
        }
      })
      .catch((err) => console.error("Capabilities fetch error:", err));

    fetchAssets();
  }, []);

  const fetchAssets = () => {
    fetch("/api/creative/assets")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.assets) {
          setAssets(data.assets);
        }
      })
      .catch((err) => console.error("Assets fetch error:", err));
  };

  // Connect SSE for active job
  useEffect(() => {
    if (!activeJobId) return;

    const eventSource = new EventSource(`/api/creative/jobs/${activeJobId}/events`);

    eventSource.addEventListener("creative_event", (e: MessageEvent) => {
      try {
        const ev = JSON.parse(e.data);
        setJobState(ev.state);
        setJobProgress(ev.progress_percent || 0);
        setJobLabel(ev.label || "");

        if (["COMPLETED", "FAILED", "CANCELLED", "BLOCKED_UNAVAILABLE"].includes(ev.state)) {
          setIsSubmitting(false);
          eventSource.close();
          fetchAssets();
        }
      } catch (err) {
        console.error("SSE parse error:", err);
      }
    });

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [activeJobId]);

  const handleCreateImage = async () => {
    if (!prompt.trim()) return;
    setIsSubmitting(true);
    setErrorMsg(null);
    setJobState("PREPARING");
    setJobProgress(5);

    try {
      const res = await fetch("/api/creative/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operation: "TEXT_TO_IMAGE",
          prompt,
          prompt_ne: promptNe || undefined,
          aspect_ratio: aspectRatio,
          seed: seed ? parseInt(seed, 10) : undefined,
          width: 512,
          height: 512,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Submission failed");
      }

      const data = await res.json();
      setActiveJobId(data.job_id);
      setJobState(data.state);
      setJobLabel(data.progress_label);
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMsg(err.message);
      setJobState("FAILED");
    }
  };

  const handleExportTimeline = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    setJobState("PREPARING");
    setJobProgress(10);

    try {
      const res = await fetch("/api/creative/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operation: "TIMELINE_EXPORT",
          prompt: prompt || "Timeline Animation Video",
          fps: 24,
          duration_seconds: 3.0,
          width: 512,
          height: 512,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Timeline export failed");
      }

      const data = await res.json();
      setActiveJobId(data.job_id);
      setJobState(data.state);
      setJobLabel(data.progress_label);
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMsg(err.message);
      setJobState("FAILED");
    }
  };

  const handleCancelJob = async () => {
    if (!activeJobId) return;
    await fetch(`/api/creative/jobs/${activeJobId}/cancel`, { method: "POST" });
  };

  // Canvas drawing handlers for inpainting mask
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDrawing(true);
    draw(e);
  };

  const stopDrawing = () => {
    setIsDrawing(false);
    if (canvasRef.current) {
      const ctx = canvasRef.current.getContext("2d");
      if (ctx) ctx.beginPath();
    }
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    ctx.lineWidth = brushSize;
    ctx.lineCap = "round";
    ctx.strokeStyle = "white"; // White mask on black canvas
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const clearMask = () => {
    if (!canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "black";
      ctx.fillRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("operation", "IMAGE_TO_IMAGE");

    const res = await fetch("/api/creative/assets/upload", {
      method: "POST",
      body: formData,
    });

    if (res.ok) {
      const data = await res.json();
      setUploadedSourceId(data.asset_id);
      setUploadedSourceUrl(`/api/creative/assets/${data.asset_id}/download`);

      // Initialize canvas with black background
      setTimeout(() => {
        clearMask();
      }, 100);
    }
  };

  const handleRunInpaint = async () => {
    if (!uploadedSourceId || !canvasRef.current) {
      setErrorMsg("Please upload a source image and draw an inpaint mask.");
      return;
    }

    // Export canvas as blob
    canvasRef.current.toBlob(async (blob) => {
      if (!blob) return;
      setIsSubmitting(true);
      setErrorMsg(null);

      // Upload mask asset
      const maskData = new FormData();
      maskData.append("file", blob, "mask.png");
      maskData.append("operation", "INPAINT");

      const maskRes = await fetch("/api/creative/assets/upload", {
        method: "POST",
        body: maskData,
      });

      if (!maskRes.ok) {
        setIsSubmitting(false);
        setErrorMsg("Failed to upload inpainting mask.");
        return;
      }

      const maskMeta = await maskRes.json();

      // Submit inpaint job
      const inpaintRes = await fetch("/api/creative/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operation: "INPAINT",
          prompt: prompt || "Inpaint masked region",
          prompt_ne: promptNe || undefined,
          source_asset_id: uploadedSourceId,
          mask_asset_id: maskMeta.asset_id,
        }),
      });

      if (!inpaintRes.ok) {
        setIsSubmitting(false);
        const err = await inpaintRes.json();
        setErrorMsg(err.detail || "Inpaint job submission failed");
        return;
      }

      const jobData = await inpaintRes.json();
      setActiveJobId(jobData.job_id);
      setJobState(jobData.state);
    }, "image/png");
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 border border-slate-800 rounded-lg overflow-hidden">
      {/* Top Header / Mode Switcher */}
      <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-900/50">
        <div>
          <h2 className="text-lg font-semibold tracking-wide text-slate-100 flex items-center gap-2">
            <span>🎨</span>
            <span>Creative Studio | क्रियेटिभ स्टुडियो</span>
          </h2>
          <p className="text-xs text-slate-400">
            Multimodal Intelligence • Text-to-Image • Inpainting • Timeline Video Export
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex bg-slate-800 p-1 rounded-md text-xs font-medium">
          <button
            onClick={() => setMode("create_image")}
            className={`px-3 py-1.5 rounded transition ${
              mode === "create_image" ? "bg-indigo-600 text-white shadow" : "text-slate-300 hover:text-white"
            }`}
          >
            Create Image (छवि)
          </button>
          <button
            onClick={() => setMode("edit_image")}
            className={`px-3 py-1.5 rounded transition ${
              mode === "edit_image" ? "bg-indigo-600 text-white shadow" : "text-slate-300 hover:text-white"
            }`}
          >
            Edit / Inpaint (सम्पादन)
          </button>
          <button
            onClick={() => setMode("create_video")}
            className={`px-3 py-1.5 rounded transition flex items-center gap-1 ${
              mode === "create_video" ? "bg-indigo-600 text-white shadow" : "text-slate-300 hover:text-white"
            }`}
          >
            <span>AI Video</span>
            <span className="text-[10px] bg-rose-900/80 text-rose-300 px-1 rounded">Blocked</span>
          </button>
          <button
            onClick={() => setMode("timeline_video")}
            className={`px-3 py-1.5 rounded transition flex items-center gap-1 ${
              mode === "timeline_video" ? "bg-indigo-600 text-white shadow" : "text-slate-300 hover:text-white"
            }`}
          >
            <span>Timeline Video (FFmpeg)</span>
            <span className="text-[10px] bg-emerald-900/80 text-emerald-300 px-1 rounded">Active</span>
          </button>
        </div>
      </div>

      {/* Main Studio Body */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-3 min-h-0 divide-y md:divide-y-0 md:divide-x divide-slate-800 overflow-y-auto">
        {/* Left Column: Controls & Prompt Composer */}
        <div className="p-4 flex flex-col gap-4 overflow-y-auto">
          {mode === "create_image" && (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Prompt (English / नेपाली)
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="A cinematic neon-lit cityscape in Kathmandu at night..."
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  नेपाली भाषा विवरण (वैकल्पिक)
                </label>
                <input
                  type="text"
                  value={promptNe}
                  onChange={(e) => setPromptNe(e.target.value)}
                  placeholder="काठमाडौँको सुन्दर रात्रिकालीन दृश्य..."
                  className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Aspect Ratio</label>
                  <select
                    value={aspectRatio}
                    onChange={(e) => setAspectRatio(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-100"
                  >
                    <option value="1:1">1:1 Square</option>
                    <option value="16:9">16:9 Landscape</option>
                    <option value="4:5">4:5 Portrait</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Seed (Optional)</label>
                  <input
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(e.target.value)}
                    placeholder="Random"
                    className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-100"
                  >
                  </input>
                </div>
              </div>

              <button
                onClick={handleCreateImage}
                disabled={isSubmitting || !prompt.trim()}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded shadow transition"
              >
                {isSubmitting ? "Generating Image..." : "Generate Image (छवि सिर्जना)"}
              </button>
            </>
          )}

          {mode === "edit_image" && (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Upload Source Image</label>
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  onChange={handleImageUpload}
                  className="w-full text-xs text-slate-400 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Brush Size ({brushSize}px)</label>
                <input
                  type="range"
                  min="5"
                  max="60"
                  value={brushSize}
                  onChange={(e) => setBrushSize(parseInt(e.target.value, 10))}
                  className="w-full"
                />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={clearMask}
                  className="flex-1 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 rounded"
                >
                  Clear Mask
                </button>
                <button
                  onClick={handleRunInpaint}
                  disabled={isSubmitting || !uploadedSourceId}
                  className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs text-white rounded font-medium"
                >
                  Apply Inpaint (पुनर्निर्माण)
                </button>
              </div>
            </>
          )}

          {mode === "create_video" && (
            <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded text-xs text-rose-200 flex flex-col gap-2">
              <div className="font-semibold text-rose-100 flex items-center gap-1.5">
                <span>⚠️</span>
                <span>Generative Neural Video Blocked</span>
              </div>
              <p>
                Local video diffusion checkpoints (e.g. SVD, CogVideo) and external paid video APIs are not configured on this host machine.
              </p>
              <p className="text-[11px] text-rose-300">
                To export animated video from keyframes and still frames, please use the <strong>Timeline Video (FFmpeg)</strong> tab.
              </p>
            </div>
          )}

          {mode === "timeline_video" && (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Animation Title / Prompt</label>
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Keyframe Animation Video"
                  className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-100 placeholder-slate-500"
                />
              </div>

              <div className="p-3 bg-slate-900/60 border border-slate-800 rounded text-xs text-slate-400 space-y-1">
                <div>Format: <strong>H.264 MP4</strong></div>
                <div>Framerate: <strong>24.0 fps</strong></div>
                <div>Engine: <strong>FFmpeg 7.1 Verified Local Encoder</strong></div>
              </div>

              <button
                onClick={handleExportTimeline}
                disabled={isSubmitting}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium text-sm rounded shadow transition"
              >
                {isSubmitting ? "Encoding Video..." : "Export MP4 Video (भिडियो निर्यात)"}
              </button>
            </>
          )}

          {/* Progress / Status Block */}
          {activeJobId && (
            <div className="mt-4 p-3 bg-slate-900 border border-slate-800 rounded flex flex-col gap-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-medium text-slate-200">Job: {activeJobId}</span>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-900/60 text-indigo-300">
                  {jobState}
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-indigo-500 h-1.5 transition-all duration-300"
                  style={{ width: `${jobProgress}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-[11px] text-slate-400">
                <span>{jobLabel || "Processing..."}</span>
                {isSubmitting && (
                  <button onClick={handleCancelJob} className="text-rose-400 hover:text-rose-300 font-medium">
                    Cancel
                  </button>
                )}
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="p-2.5 bg-rose-950/60 border border-rose-800 rounded text-xs text-rose-200">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Center Column: Live Canvas / Inpaint Workspace */}
        <div className="p-4 flex flex-col items-center justify-center bg-slate-950/80 min-h-[300px]">
          {mode === "edit_image" && uploadedSourceUrl ? (
            <div className="relative border border-slate-700 rounded overflow-hidden shadow-lg">
              <img
                src={uploadedSourceUrl}
                alt="Source for inpaint"
                className="max-h-[360px] object-contain block"
              />
              <canvas
                ref={canvasRef}
                width={512}
                height={512}
                onMouseDown={startDrawing}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onMouseMove={draw}
                className="absolute inset-0 w-full h-full opacity-60 cursor-crosshair"
              />
            </div>
          ) : (
            <div className="text-center p-6 text-slate-500 flex flex-col items-center gap-2">
              <span className="text-4xl">🖼️</span>
              <p className="text-xs">
                {mode === "edit_image"
                  ? "Upload a source image to begin drawing an inpaint mask"
                  : "Generated image or video preview will appear here"}
              </p>
            </div>
          )}
        </div>

        {/* Right Column: Asset Gallery & Download */}
        <div className="p-4 flex flex-col gap-3 overflow-y-auto">
          <div className="flex justify-between items-center">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Asset Gallery ({assets.length})
            </h3>
            <button onClick={fetchAssets} className="text-[11px] text-indigo-400 hover:text-indigo-300">
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2 overflow-y-auto">
            {assets.map((asset) => (
              <div
                key={asset.asset_id}
                onClick={() => setSelectedAsset(asset)}
                className="group relative border border-slate-800 rounded overflow-hidden cursor-pointer bg-slate-900/60 hover:border-indigo-500 transition"
              >
                {asset.media_type === "VIDEO" ? (
                  <video
                    src={`/api/creative/assets/${asset.asset_id}/download`}
                    className="w-full h-24 object-cover"
                    muted
                  />
                ) : (
                  <img
                    src={`/api/creative/assets/${asset.asset_id}/download`}
                    alt={asset.filename}
                    className="w-full h-24 object-cover"
                  />
                )}
                <div className="p-1.5 text-[10px] text-slate-300 truncate">
                  {asset.filename}
                </div>
              </div>
            ))}
          </div>

          {selectedAsset && (
            <div className="mt-auto p-3 bg-slate-900 border border-slate-800 rounded text-xs flex flex-col gap-2">
              <div className="font-semibold text-slate-200 truncate">{selectedAsset.filename}</div>
              <div className="text-[11px] text-slate-400">
                <div>Type: {selectedAsset.media_type} ({selectedAsset.mime_type})</div>
                <div>Size: {(selectedAsset.file_size_bytes / 1024).toFixed(1)} KB</div>
                <div className="truncate">SHA-256: {selectedAsset.sha256_hash.slice(0, 16)}...</div>
              </div>
              <a
                href={`/api/creative/assets/${selectedAsset.asset_id}/download`}
                download={selectedAsset.filename}
                className="w-full py-1.5 text-center bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium"
              >
                Download Verified Media
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
