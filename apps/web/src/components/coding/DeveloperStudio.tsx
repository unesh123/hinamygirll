import React, { useState, useEffect, useRef } from "react";

interface FlagshipMission {
  mission_id: string;
  title: string;
  category: string;
  tagline: string;
  description: string;
  viewports: string[];
  files: Record<string, string>;
  key_features: string[];
}

interface WorkspaceFile {
  name: string;
  path: string;
  size_bytes: number;
  modified_at: string;
}

interface DesignFinding {
  rule_id: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "PASS";
  message: string;
  suggestion?: string;
}

interface DesignScorecard {
  overall_score: number;
  layout_responsiveness: number;
  typography_hierarchy: number;
  color_contrast: number;
  interactive_affordance: number;
  accessibility_wcag: number;
  nepali_cultural_fidelity: number;
  findings: DesignFinding[];
}

interface DiffRecord {
  timestamp: string;
  file: string;
  diff: string;
  bytes: number;
}

export const DeveloperStudio: React.FC = () => {
  // Mission state
  const [missions, setMissions] = useState<FlagshipMission[]>([]);
  const [selectedMissionId, setSelectedMissionId] = useState<string>("MISSION-01");
  const [taskId, setTaskId] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [statusText, setStatusText] = useState<string>("Ready");

  // Files & Editor state
  const [files, setFiles] = useState<Record<string, string>>({
    "index.html": "",
    "style.css": "",
    "app.js": "",
  });
  const [previousFiles, setPreviousFiles] = useState<Record<string, string>>({});
  const [activeFile, setActiveFile] = useState<string>("index.html");
  const [modifiedFiles, setModifiedFiles] = useState<Set<string>>(new Set());
  const [changeCount, setChangeCount] = useState<number>(0);

  // Phase 20: Prompt-to-Production State
  const [promptInput, setPromptInput] = useState<string>("");
  const [isCompilingSpec, setIsCompilingSpec] = useState<boolean>(false);
  const [activeSpec, setActiveSpec] = useState<any>(null);

  // Phase 21: Task lifecycle & midway change state
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [midwayPrompt, setMidwayPrompt] = useState<string>("");
  const [isApplyingChange, setIsApplyingChange] = useState<boolean>(false);

  // Viewport & UI state
  const [viewport, setViewport] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [activeTab, setActiveTab] = useState<"changes" | "terminal" | "critic" | "events" | "evidence">("changes");

  // Telemetry & Logs
  const [eventLogs, setEventLogs] = useState<string[]>([]);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [diffRecords, setDiffRecords] = useState<DiffRecord[]>([]);
  const [scorecard, setScorecard] = useState<DesignScorecard | null>(null);
  const [evidence, setEvidence] = useState<any>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 1. Load Flagship Missions on mount
  useEffect(() => {
    fetch("/api/coding/missions")
      .then((res) => res.json())
      .then((data: FlagshipMission[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setMissions(data);
          const first = data.find((m) => m.mission_id === "MISSION-01") || data[0];
          setSelectedMissionId(first.mission_id);
          setFiles(first.files);
          setPreviousFiles(first.files);
        }
      })
      .catch((err) => {
        console.warn("Failed to fetch missions, using fallback:", err);
      });
  }, []);

  // 2. SSE Event Stream subscription
  useEffect(() => {
    if (!taskId) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`/api/coding/tasks/${taskId}/events`);
    eventSourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        const time = new Date().toLocaleTimeString();
        setEventLogs((prev) => [`[${time}] ${ev.kind} (seq: ${ev.seq})`, ...prev.slice(0, 99)]);

        if (ev.kind === "file.patch.applied" && ev.payload?.diff) {
          setDiffRecords((prev) => [
            {
              timestamp: time,
              file: ev.file_path || "file",
              diff: ev.payload.diff,
              bytes: 0,
            },
            ...prev,
          ]);
        }

        if (ev.kind === "command.stdout" && ev.payload?.stdout) {
          setTerminalLogs((prev) => [...prev, ev.payload.stdout]);
        }

        if (ev.kind === "preview.ready" && ev.payload?.preview_url) {
          setPreviewUrl(ev.payload.preview_url);
        }

        if (ev.kind === "task.completed") {
          setIsRunning(false);
          setStatusText("Completed");
          refreshTaskDetails(taskId);
        }
      } catch (err) {
        console.error("Error parsing SSE event:", err);
      }
    };

    es.onerror = () => {
      // Reconnection handled automatically by browser EventSource
    };

    return () => {
      es.close();
    };
  }, [taskId]);

  const refreshTaskDetails = async (id: string) => {
    try {
      const res = await fetch(`/api/coding/tasks/${id}`);
      if (res.ok) {
        const t = await res.json();
        if (t.scorecard) setScorecard(t.scorecard);
        if (t.evidence_manifest) setEvidence(t.evidence_manifest);
        if (t.preview_url) setPreviewUrl(t.preview_url);
        if (t.diff_history) setDiffRecords(t.diff_history);
      }

      // Fetch file tree and load files
      const treeRes = await fetch(`/api/coding/tasks/${id}/tree`);
      if (treeRes.ok) {
        const tree: WorkspaceFile[] = await treeRes.json();
        const loaded: Record<string, string> = {};
        for (const item of tree) {
          const fRes = await fetch(`/api/coding/tasks/${id}/file?path=${encodeURIComponent(item.path)}`);
          if (fRes.ok) {
            const fData = await fRes.json();
            loaded[item.path] = fData.content;
          }
        }
        if (Object.keys(loaded).length > 0) {
          setFiles(loaded);
          setPreviousFiles(loaded);
        }
      }
    } catch (err) {
      console.error("Error refreshing task details:", err);
    }
  };

  // 3. Run Mission Autonomously
  const handleRunMission = async () => {
    setIsRunning(true);
    setStatusText("Executing...");
    setTerminalLogs([`> Starting autonomous mission ${selectedMissionId}...`]);
    setEventLogs([`[${new Date().toLocaleTimeString()}] Initiating flagship mission ${selectedMissionId}`]);
    setChangeCount(0);
    setModifiedFiles(new Set());

    try {
      const res = await fetch(`/api/coding/missions/${selectedMissionId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const task = await res.json();
      setTaskId(task.task_id);
      if (task.preview_url) setPreviewUrl(task.preview_url);
      if (task.scorecard) setScorecard(task.scorecard);
      await refreshTaskDetails(task.task_id);
      setStatusText("Ready");
      setIsRunning(false);
    } catch (err: any) {
      console.error("Mission failed:", err);
      setStatusText("Error: " + err.message);
      setIsRunning(false);
    }
  };

  // Phase 20: Compile Spec from prompt
  const handleCompileSpec = async () => {
    if (!promptInput.trim()) return;
    setIsCompilingSpec(true);
    setStatusText("Compiling Spec...");
    try {
      const res = await fetch("/api/coding/spec/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: promptInput }),
      });
      if (res.ok) {
        const spec = await res.json();
        setActiveSpec(spec);
        setTerminalLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] Compiled Spec: ${spec.title} (${spec.language_detected})`,
          `  Must-Haves: ${(spec.must_have_features || []).join(", ")}`,
          `  Entities: ${(spec.data_entities || []).map((e: any) => e.name).join(", ")}`,
          ...prev,
        ]);
        setStatusText("Spec Compiled");
      }
    } catch (err: any) {
      console.error("Failed to compile spec:", err);
      setStatusText("Compile Error");
    } finally {
      setIsCompilingSpec(false);
    }
  };

  // Phase 20: Build from Prompt
  const handleBuildFromPrompt = async (customPrompt?: string) => {
    const targetPrompt = customPrompt || promptInput;
    if (!targetPrompt.trim()) return;
    setIsRunning(true);
    setStatusText("Synthesizing...");
    setTerminalLogs([`> Starting Prompt-to-Production build for: "${targetPrompt}"...`]);
    setEventLogs([`[${new Date().toLocaleTimeString()}] Prompt-to-Production build initiated`]);
    setChangeCount(0);
    setModifiedFiles(new Set());

    try {
      const res = await fetch("/api/coding/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: targetPrompt }),
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const task = await res.json();
      setTaskId(task.task_id);
      if (task.specification) setActiveSpec(task.specification);
      if (task.preview_url) setPreviewUrl(task.preview_url);
      if (task.scorecard) setScorecard(task.scorecard);
      await refreshTaskDetails(task.task_id);
      setStatusText("Production Ready");
      setTerminalLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] Project synthesized successfully! Critic Score: ${task.scorecard?.overall_score || 95}/100`,
        ...prev,
      ]);
    } catch (err: any) {
      console.error("Build failed:", err);
      setStatusText("Build Error: " + err.message);
    } finally {
      setIsRunning(false);
    }
  };

  // Phase 21: Task Lifecycle & Midway Requirement Update Handlers
  const handleTogglePause = async () => {
    if (!taskId) return;
    try {
      const endpoint = isPaused ? `/api/coding/tasks/${taskId}/resume` : `/api/coding/tasks/${taskId}/pause`;
      const res = await fetch(endpoint, { method: "POST" });
      if (res.ok) {
        setIsPaused(!isPaused);
        setStatusText(isPaused ? "Running" : "Paused");
        setEventLogs((prev) => [`[${new Date().toLocaleTimeString()}] Task ${isPaused ? "resumed" : "paused"}`, ...prev]);
      }
    } catch (err) {
      console.error("Error toggling pause:", err);
    }
  };

  const handleApplyMidwayChange = async () => {
    if (!taskId || !midwayPrompt.trim()) return;
    setIsApplyingChange(true);
    setStatusText("Applying Change...");
    try {
      const res = await fetch(`/api/coding/tasks/${taskId}/change`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ change_prompt: midwayPrompt }),
      });
      if (res.ok) {
        const updated = await res.json();
        if (updated.specification) setActiveSpec(updated.specification);
        if (updated.scorecard) setScorecard(updated.scorecard);
        setTerminalLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] Applied midway change: "${midwayPrompt}"`,
          `  Plan version: ${updated.specification?.plan_version || 2}`,
          ...prev,
        ]);
        setMidwayPrompt("");
        await refreshTaskDetails(taskId);
        setStatusText("Change Applied");
      }
    } catch (err) {
      console.error("Error applying midway change:", err);
      setStatusText("Change Failed");
    } finally {
      setIsApplyingChange(false);
    }
  };

  // 4. Save file & trigger preview
  const handleSaveAndPreview = async () => {
    const currentCode = files[activeFile] || "";
    setStatusText("Saving...");

    if (taskId) {
      try {
        const res = await fetch(`/api/coding/tasks/${taskId}/file`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: activeFile, content: currentCode }),
        });
        if (res.ok) {
          const data = await res.json();
          setPreviousFiles((prev) => ({ ...prev, [activeFile]: currentCode }));
          setChangeCount((c) => c + 1);
          setModifiedFiles((s) => new Set(s).add(activeFile));
          setEventLogs((prev) => [
            `[${new Date().toLocaleTimeString()}] Saved ${activeFile} (${data.size_bytes} bytes)`,
            ...prev,
          ]);

          // Refresh critique
          const revRes = await fetch(`/api/coding/tasks/${taskId}/review`, { method: "POST" });
          if (revRes.ok) {
            const sc = await revRes.json();
            setScorecard(sc);
          }
          setStatusText("Ready");
        }
      } catch (err) {
        console.error("Failed to save to backend:", err);
        setStatusText("Save failed");
      }
    } else {
      // Local preview fallback if no task is active
      setPreviousFiles((prev) => ({ ...prev, [activeFile]: currentCode }));
      setChangeCount((c) => c + 1);
      setModifiedFiles((s) => new Set(s).add(activeFile));
      setStatusText("Ready");
    }
  };

  // 5. Reset to original files
  const handleReset = () => {
    const mission = missions.find((m) => m.mission_id === selectedMissionId);
    if (mission) {
      setFiles({ ...mission.files });
      setPreviousFiles({ ...mission.files });
      setModifiedFiles(new Set());
      setChangeCount(0);
      setEventLogs((prev) => [`[${new Date().toLocaleTimeString()}] Reset workspace to default mission files`, ...prev]);
    }
  };

  // 6. Handle code edit in textarea
  const handleCodeChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setFiles((prev) => ({ ...prev, [activeFile]: val }));
    setModifiedFiles((s) => new Set(s).add(activeFile));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "Enter" || e.key.toLowerCase() === "s")) {
      e.preventDefault();
      handleSaveAndPreview();
    }
  };

  // Download project ZIP
  const handleDownloadZip = () => {
    if (taskId) {
      window.open(`/api/coding/tasks/${taskId}/export`, "_blank");
    }
  };

  // Generate fallback srcdoc if no backend preview is loaded yet
  const generateLocalSrcDoc = () => {
    const html = files["index.html"] || "<h1>No index.html</h1>";
    const css = files["style.css"] || "";
    const js = files["app.js"] || "";
    return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style></head><body>${html}<script>${js}</script></body></html>`;
  };

  const currentCode = files[activeFile] || "";
  const lineCount = currentCode.split("\n").length;

  const viewportWidth =
    viewport === "desktop"
      ? "100%"
      : viewport === "tablet"
      ? "min(768px, calc(100% - 32px))"
      : "min(390px, calc(100% - 32px))";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#080d16", color: "#edf1f9", fontFamily: 'Inter, "Segoe UI", Arial, sans-serif' }}>
      {/* Top Header */}
      <header style={{ height: "64px", padding: "0 20px", background: "linear-gradient(90deg, #10192a, #0b111d)", borderBottom: "1px solid #253044", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ fontWeight: 800, fontSize: "19px", letterSpacing: "-0.02em" }}>
            <span style={{ color: "#67e9c0" }}>✦</span> HINAA <span style={{ fontWeight: 400, color: "#899bb1" }}>/ Developer Studio</span>
          </div>
          <span style={{ fontSize: "11px", padding: "4px 8px", background: "#142332", borderRadius: "6px", color: "#67e9c0", border: "1px solid #254354" }}>
            Phase 21 · Autonomous Product Engineering
          </span>
        </div>

        {/* Mission Switcher & Actions */}
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <select
            value={selectedMissionId}
            onChange={(e) => {
              setSelectedMissionId(e.target.value);
              const m = missions.find((x) => x.mission_id === e.target.value);
              if (m) {
                setFiles({ ...m.files });
                setPreviousFiles({ ...m.files });
                setActiveFile("index.html");
                setModifiedFiles(new Set());
              }
            }}
            style={{ background: "#141f30", color: "#edf1f9", border: "1px solid #2c3e55", borderRadius: "8px", padding: "7px 12px", fontSize: "12px", outline: "none", cursor: "pointer" }}
          >
            {missions.map((m) => (
              <option key={m.mission_id} value={m.mission_id}>
                {m.mission_id}: {m.title}
              </option>
            ))}
          </select>

          <button
            onClick={handleRunMission}
            disabled={isRunning}
            style={{ background: isRunning ? "#1a3a32" : "#67e9c0", border: "none", color: "#09211a", padding: "8px 14px", borderRadius: "8px", fontWeight: 700, fontSize: "12px", cursor: isRunning ? "wait" : "pointer", display: "flex", alignItems: "center", gap: "6px" }}
          >
            {isRunning ? "⚡ Building..." : "⚡ Run Mission"}
          </button>

          <button
            onClick={handleSaveAndPreview}
            style={{ background: "#243248", border: "1px solid #3b4a62", color: "#e6effe", padding: "8px 12px", borderRadius: "8px", fontWeight: 600, fontSize: "12px", cursor: "pointer" }}
          >
            ▶ Run preview
          </button>

          <button
            onClick={handleReset}
            style={{ background: "#182232", border: "1px solid #28374a", color: "#9cb1c9", padding: "8px 12px", borderRadius: "8px", fontSize: "12px", cursor: "pointer" }}
          >
            Reset
          </button>

          {taskId && (
            <>
              <button
                onClick={handleTogglePause}
                style={{
                  background: isPaused ? "#b45309" : "#1f293d",
                  border: "1px solid #3b4a62",
                  color: isPaused ? "#fef3c7" : "#e6effe",
                  padding: "8px 12px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  cursor: "pointer",
                }}
              >
                {isPaused ? "▶ Resume" : "⏸ Pause"}
              </button>

              <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                <input
                  type="text"
                  placeholder="Midway requirement update..."
                  value={midwayPrompt}
                  onChange={(e) => setMidwayPrompt(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleApplyMidwayChange(); }}
                  style={{
                    background: "#141f30",
                    border: "1px solid #2c3e55",
                    color: "#edf1f9",
                    padding: "6px 10px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    width: "180px",
                  }}
                />
                <button
                  onClick={handleApplyMidwayChange}
                  disabled={isApplyingChange || !midwayPrompt.trim()}
                  style={{
                    background: "#2563eb",
                    border: "none",
                    color: "#ffffff",
                    padding: "6px 10px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {isApplyingChange ? "..." : "Apply"}
                </button>
              </div>

              <button
                onClick={handleDownloadZip}
                style={{ background: "#1f334a", border: "1px solid #3d5875", color: "#93c5fd", padding: "8px 12px", borderRadius: "8px", fontSize: "12px", cursor: "pointer" }}
                title="Download project ZIP archive"
              >
                ⬇ Export ZIP
              </button>
            </>
          )}

          <div style={{ border: "1px solid #30564e", background: "#15362e", color: "#84ffcf", padding: "6px 10px", borderRadius: "999px", fontSize: "11px", display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#67e9c0" }}></span>
            {statusText}
          </div>
        </div>
      </header>

      {/* Phase 20: Prompt-to-Production Intelligence Bar */}
      <div style={{ background: "#0c1524", borderBottom: "1px solid #1f3147", padding: "10px 20px", display: "flex", flexDirection: "column", gap: "8px" }}>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <div style={{ flex: 1, position: "relative" }}>
            <input
              type="text"
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleBuildFromPrompt(); }}
              placeholder="Describe any custom website, dashboard or app in English or नेपाली (e.g. Kathmandu Dental Clinic, Pokhara Paragliding Roster)..."
              style={{
                width: "100%",
                background: "#142032",
                border: "1px solid #2e4460",
                color: "#f1f5f9",
                borderRadius: "8px",
                padding: "8px 14px",
                fontSize: "13px",
                outline: "none",
              }}
            />
          </div>
          <button
            onClick={() => handleBuildFromPrompt()}
            disabled={isRunning || !promptInput.trim()}
            style={{
              background: isRunning ? "#1a3a32" : "linear-gradient(135deg, #38bdf8, #818cf8)",
              border: "none",
              color: "#030712",
              padding: "8px 16px",
              borderRadius: "8px",
              fontWeight: 700,
              fontSize: "12px",
              cursor: isRunning ? "wait" : "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {isRunning ? "✦ Synthesizing..." : "✦ Build from Prompt"}
          </button>
          <button
            onClick={handleCompileSpec}
            disabled={isCompilingSpec || !promptInput.trim()}
            style={{
              background: "#1b2c44",
              border: "1px solid #355075",
              color: "#93c5fd",
              padding: "8px 12px",
              borderRadius: "8px",
              fontWeight: 600,
              fontSize: "12px",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {isCompilingSpec ? "Compiling..." : "Compile Spec"}
          </button>
        </div>

        {/* Quick Canonical Zero-Shot Presets */}
        <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", fontSize: "11px" }}>
          <span style={{ color: "#7c92a9", fontWeight: 600 }}>Zero-Shot Presets:</span>
          {[
            { code: "Z1", label: "Z1: Dental Wellness (Atomic Collision)", prompt: "Build a bilingual appointment booking system for a Kathmandu dental clinic with real SQLite collision prevention, admin dashboard, doctor slot scheduling, and role-based login." },
            { code: "Z2", label: "Z2: Civic Telemetry (Source Provenance)", prompt: "Build an environmental telemetry dashboard for Kathmandu valley monitoring Bagmati river water levels, Ratnapark air quality PM2.5, UV index with real source citations." },
            { code: "Z3", label: "Z3: Himalayan Khata (Integer NPR)", prompt: "Develop a small business operations and ledger system for a Nepali handicraft supplier with integer NPR accounting, customer balance ledger, inventory deduction, and tax invoice export." },
            { code: "Z4", label: "Z4: Vespera Kinetic Studio (60fps)", prompt: "Design an extraordinary, visually ambitious kinetic design studio landing page with 60fps CSS animations, dark aesthetic, reduced-motion accessibility support, and interactive portfolio." },
          ].map((preset) => (
            <button
              key={preset.code}
              onClick={() => {
                setPromptInput(preset.prompt);
                handleBuildFromPrompt(preset.prompt);
              }}
              style={{
                background: "#142032",
                border: "1px solid #283e57",
                color: "#67e9c0",
                borderRadius: "6px",
                padding: "3px 8px",
                fontSize: "11px",
                cursor: "pointer",
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main 3-Column Layout */}
      <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "220px minmax(400px, 1fr) minmax(420px, 1.15fr)", borderBottom: "1px solid #253044" }}>
        
        {/* Left Column: Project Explorer */}
        <aside style={{ background: "#0a111e", borderRight: "1px solid #253044", display: "flex", flexDirection: "column" }}>
          <div style={{ color: "#91a1b8", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 700, padding: "14px 16px 8px" }}>
            Project Explorer
          </div>

          <div style={{ flex: 1, padding: "6px 8px", display: "flex", flexDirection: "column", gap: "2px" }}>
            {Object.keys(files).map((name) => {
              const isActive = activeFile === name;
              const isModified = modifiedFiles.has(name);
              return (
                <button
                  key={name}
                  onClick={() => setActiveFile(name)}
                  style={{
                    border: "none",
                    textAlign: "left",
                    background: isActive ? "#1d2d3e" : "transparent",
                    color: isActive ? "#67e9c0" : "#aebbd0",
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "8px",
                    fontSize: "12.5px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: isModified ? "#5adcb9" : "#667186" }}></span>
                    {name}
                  </div>
                  <span style={{ fontSize: "10px", color: "#6e8299" }}>
                    {((files[name]?.length || 0) / 1024).toFixed(1)}k
                  </span>
                </button>
              );
            })}
          </div>

          {/* Mission Spec & Scorecard Card */}
          <div style={{ padding: "12px", margin: "12px", background: "#122132", border: "1px solid #284354", borderRadius: "10px", fontSize: "11px", color: "#93adc0" }}>
            <div style={{ fontWeight: 700, color: "#67e9c0", marginBottom: "4px" }}>
              {selectedMissionId}
            </div>
            <div style={{ marginBottom: "8px", color: "#cbd5e1" }}>
              {missions.find((m) => m.mission_id === selectedMissionId)?.title || "Custom Project"}
            </div>
            {scorecard ? (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid #1f3448", paddingTop: "6px", marginTop: "4px" }}>
                <span>Critic Score:</span>
                <span style={{ fontWeight: 800, color: scorecard.overall_score >= 85 ? "#67e9c0" : "#fbbf24" }}>
                  {scorecard.overall_score}/100
                </span>
              </div>
            ) : (
              <div style={{ fontSize: "10px", color: "#64748b" }}>Critic audit pending run</div>
            )}
          </div>
        </aside>

        {/* Middle Column: Source Editor */}
        <section style={{ borderRight: "1px solid #253044", display: "flex", flexDirection: "column", background: "#0d1421" }}>
          <div style={{ height: "46px", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", background: "#0f1725", borderBottom: "1px solid #253044", fontSize: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <b style={{ color: "#edf1f9" }}>{activeFile}</b>
              <span style={{ color: "#91edce", border: "1px solid #37685d", borderRadius: "5px", padding: "2px 6px", fontSize: "9.5px" }}>
                EDITABLE
              </span>
            </div>
            <div style={{ color: "#8fa6bd", fontSize: "11px" }}>Source editor</div>
          </div>

          <div style={{ flex: 1, position: "relative" }}>
            <textarea
              ref={textareaRef}
              value={currentCode}
              onChange={handleCodeChange}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              aria-label="Source code editor"
              style={{
                width: "100%",
                height: "100%",
                resize: "none",
                outline: "none",
                padding: "16px 20px",
                border: "none",
                background: "#0d1421",
                color: "#dbe4f7",
                fontFamily: 'Consolas, "Cascadia Code", monospace',
                fontSize: "13px",
                lineHeight: "1.65",
                tabSize: 2,
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ height: "34px", background: "#101b2b", borderTop: "1px solid #253044", padding: "8px 16px", fontSize: "11px", color: "#a9bbc9", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>{lineCount} lines · UTF-8</span>
            <span style={{ color: "#7a90a8" }}>Ctrl+Enter / Ctrl+S to save & preview</span>
          </div>
        </section>

        {/* Right Column: Live Rendered Website */}
        <section style={{ background: "#121a28", display: "flex", flexDirection: "column" }}>
          <div style={{ height: "46px", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", background: "#0f1725", borderBottom: "1px solid #253044", fontSize: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <b style={{ color: "#edf1f9" }}>Live website</b>
              <span style={{ color: "#91edce", border: "1px solid #37685d", borderRadius: "5px", padding: "2px 6px", fontSize: "9.5px" }}>
                {isRunning ? "BUILDING..." : "RENDERED"}
              </span>
            </div>

            {/* Viewport Toggles: Desktop (1440), Tablet (768), Mobile (390) */}
            <div style={{ display: "flex", gap: "4px" }}>
              {(["desktop", "tablet", "mobile"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setViewport(mode)}
                  style={{
                    borderRadius: "6px",
                    border: "1px solid #34445a",
                    background: viewport === mode ? "#3b4e70" : "#1d2a3f",
                    color: viewport === mode ? "white" : "#cfd9e6",
                    fontSize: "11px",
                    padding: "4px 8px",
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          {/* Viewport Frame Container */}
          <div style={{ flex: 1, padding: "16px", display: "flex", justifyContent: "center", alignItems: "center", background: "#0a111a", overflow: "hidden" }}>
            <div
              style={{
                width: viewportWidth,
                height: "100%",
                maxHeight: "680px",
                border: "1px solid #50627a",
                borderRadius: "10px",
                overflow: "hidden",
                background: "#ffffff",
                boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
                transition: "width 0.25s ease-in-out",
              }}
            >
              <iframe
                title="Isolated live website preview"
                sandbox="allow-scripts allow-forms allow-same-origin"
                src={previewUrl ? previewUrl : undefined}
                srcDoc={!previewUrl ? generateLocalSrcDoc() : undefined}
                style={{ border: "none", width: "100%", height: "100%", display: "block" }}
              />
            </div>
          </div>
        </section>
      </div>

      {/* Bottom Drawer: Tabs for Diffs, Terminal, Critic, Events, Evidence */}
      <div style={{ height: "180px", display: "flex", flexDirection: "column", background: "#0b1523", borderTop: "1px solid #253044" }}>
        <div style={{ display: "flex", gap: "6px", padding: "8px 16px", background: "#111b2b", borderBottom: "1px solid #253044" }}>
          {[
            { id: "changes", label: "Actual changes" },
            { id: "terminal", label: "Terminal & Build" },
            { id: "critic", label: "Design Critic" },
            { id: "events", label: "Event Stream" },
            { id: "evidence", label: "Cryptographic Evidence" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              style={{
                padding: "5px 10px",
                fontSize: "11px",
                border: "1px solid #394960",
                borderRadius: "6px",
                background: activeTab === t.id ? "#273f50" : "#202e44",
                color: activeTab === t.id ? "#67e9c0" : "#c7d4e7",
                cursor: "pointer",
                fontWeight: activeTab === t.id ? 700 : 500,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: "10px 16px", fontFamily: 'Consolas, "Cascadia Code", monospace', fontSize: "11.5px", lineHeight: "1.55", color: "#a8bad0" }}>
          {activeTab === "changes" && (
            <div>
              {diffRecords.length === 0 ? (
                <div style={{ color: "#64748b" }}>No differences in this file yet. Make edits and click "Run preview".</div>
              ) : (
                diffRecords.map((d, i) => (
                  <div key={i} style={{ marginBottom: "8px", borderBottom: "1px solid #1a2736", paddingBottom: "6px" }}>
                    <div style={{ color: "#67e9c0", fontWeight: 700 }}>
                      [{d.timestamp}] {d.file}
                    </div>
                    <pre style={{ margin: "4px 0", color: "#cbd5e1", whiteSpace: "pre-wrap" }}>{d.diff}</pre>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === "terminal" && (
            <div>
              {terminalLogs.length === 0 ? (
                <div style={{ color: "#64748b" }}>No terminal commands executed yet. Click "⚡ Run Mission".</div>
              ) : (
                terminalLogs.map((log, i) => (
                  <div key={i} style={{ color: log.includes("Cleanly") || log.includes("validated") ? "#67e9c0" : "#cbd5e1" }}>
                    {log}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === "critic" && (
            <div>
              {scorecard ? (
                <div>
                  <div style={{ display: "flex", gap: "16px", marginBottom: "8px", fontWeight: 700, color: "#edf1f9" }}>
                    <span>Overall: <b style={{ color: "#67e9c0" }}>{scorecard.overall_score}/100</b></span>
                    <span>Responsive: {scorecard.layout_responsiveness}/100</span>
                    <span>Typography: {scorecard.typography_hierarchy}/100</span>
                    <span>Contrast: {scorecard.color_contrast}/100</span>
                    <span>WCAG: {scorecard.accessibility_wcag}/100</span>
                    <span>Nepali: {scorecard.nepali_cultural_fidelity}/100</span>
                  </div>
                  <div>
                    {scorecard.findings.map((f, i) => (
                      <div key={i} style={{ color: f.severity === "CRITICAL" ? "#ef4444" : f.severity === "HIGH" ? "#f97316" : "#10b981", margin: "2px 0" }}>
                        • [{f.severity}] {f.rule_id}: {f.message}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ color: "#64748b" }}>No design audit scorecard available yet. Run a mission or save changes to trigger audit.</div>
              )}
            </div>
          )}

          {activeTab === "events" && (
            <div>
              {eventLogs.length === 0 ? (
                <div style={{ color: "#64748b" }}>Waiting for SSE events...</div>
              ) : (
                eventLogs.map((ev, i) => <div key={i}>{ev}</div>)
              )}
            </div>
          )}

          {activeTab === "evidence" && (
            <div>
              {evidence ? (
                <pre style={{ margin: 0, color: "#93c5fd" }}>
                  {JSON.stringify(evidence, null, 2)}
                </pre>
              ) : (
                <div style={{ color: "#64748b" }}>Run a mission to generate tamper-evident SHA256 artifact manifest.</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer Status Bar */}
      <footer style={{ height: "32px", background: "#0a111b", borderTop: "1px solid #253044", padding: "0 16px", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "#7d8da8" }}>
        <div>
          Connected to FastAPI Backend (127.0.0.1:8000) · <b style={{ color: "#d2dcfa" }}>.runtime/coding/workspaces</b>
        </div>
        <div>
          {changeCount} source changes · {eventLogs.length} events streamed
        </div>
      </footer>
    </div>
  );
};
