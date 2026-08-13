import { useEffect, useState } from "react";
import { CheckCircle2, Download, FileSearch, FolderPlus, FileText, ListTodo, Loader2, Pause, Play, Plus, RefreshCw, RotateCcw, ShieldCheck, Sparkles, Upload, XCircle } from "lucide-react";

type TaskStatus = "pending" | "active" | "success" | "error" | "cancelled" | "waiting_approval";

interface ProjectTask {
  id: string;
  title: string;
  detail: string;
  parentTaskId?: string | null;
  status: TaskStatus;
  requiresApproval: boolean;
}

interface ProjectFile {
  id: string;
  name: string;
  mediaType?: string;
  sizeBytes: number;
}

interface ProjectArtifact {
  id: string;
  kind: string;
  title: string;
  sourceUrl?: string | null;
}

type RunStatus = "queued" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";

interface AgentRunEvent {
  id: string;
  label: string;
  detail: string;
  status: RunStatus;
}

interface AgentRun {
  id: string;
  goal: string;
  status: RunStatus;
  summary: string;
  events: AgentRunEvent[];
}

interface ProjectSummary {
  id: string;
  title: string;
  description: string;
}

interface ProjectDetail extends ProjectSummary {
  tasks: ProjectTask[];
  files: ProjectFile[];
  artifacts: ProjectArtifact[];
  runs: AgentRun[];
}

const API = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) throw new Error(`Workspace request failed (${response.status})`);
  return response.json() as Promise<T>;
}

function statusColor(status: TaskStatus): string {
  return {
    pending: "#94a3b8",
    active: "#38bdf8",
    success: "#34d399",
    error: "#fb7185",
    cancelled: "#64748b",
    waiting_approval: "#fbbf24",
  }[status];
}

export function LocalProjectWorkspace({ active }: { active: boolean }) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selected, setSelected] = useState<ProjectDetail | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [planGoal, setPlanGoal] = useState("");
  const [siteBrief, setSiteBrief] = useState("");
  const [siteBusy, setSiteBusy] = useState(false);
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [runGoal, setRunGoal] = useState("");
  const [runBusy, setRunBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fileBusy, setFileBusy] = useState(false);

  const loadProjects = async (selectId?: string) => {
    setLoading(true);
    setError("");
    try {
      const items = await request<ProjectSummary[]>("/projects");
      setProjects(items);
      const id = selectId || selected?.id || items[0]?.id;
      if (id) {
        const detail = await request<ProjectDetail>(`/projects/${id}`);
        setSelected(detail);
        localStorage.setItem("hinaa-active-project-id", detail.id);
      } else {
        setSelected(null);
        localStorage.removeItem("hinaa-active-project-id");
      }
    } catch {
      setError("Local workspace is unavailable. Start Hinaa’s API to access projects.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (active) void loadProjects();
    // Refresh only when the panel is opened; do not poll the local API.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const createProject = async () => {
    const clean = title.trim();
    if (!clean) return;
    setCreating(true);
    try {
      const project = await request<ProjectSummary>("/projects", {
        method: "POST",
        body: JSON.stringify({ title: clean }),
      });
      setTitle("");
      await loadProjects(project.id);
    } catch {
      setError("Could not create the local project.");
    } finally {
      setCreating(false);
    }
  };

  const createPlan = async () => {
    const goal = planGoal.trim();
    if (!selected || !goal) return;
    try {
      await request(`/projects/${selected.id}/plans`, {
        method: "POST",
        body: JSON.stringify({ goal }),
      });
      setPlanGoal("");
      await loadProjects(selected.id);
    } catch {
      setError("Could not create the local work plan.");
    }
  };

  const createWebsiteBlueprint = async () => {
    const brief = siteBrief.trim();
    if (!selected || brief.length < 10) {
      setError("Describe the website in at least 10 characters before creating its local blueprint.");
      return;
    }
    setSiteBusy(true);
    setError("");
    try {
      await request(`/projects/${selected.id}/website-blueprint`, {
        method: "POST",
        body: JSON.stringify({ brief, stack: "React + TypeScript" }),
      });
      setSiteBrief("");
      await loadProjects(selected.id);
    } catch {
      setError("Could not create the local website blueprint.");
    } finally {
      setSiteBusy(false);
    }
  };

  const updateTaskStatus = async (task: ProjectTask, status: TaskStatus) => {
    if (!selected || status === task.status) return;
    try {
      await request(`/projects/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await loadProjects(selected.id);
    } catch {
      setError("Could not update the task status.");
    }
  };

  const saveSource = async () => {
    const title = sourceTitle.trim();
    const url = sourceUrl.trim();
    if (!selected || !title || !/^https?:\/\//i.test(url)) {
      setError("Enter a source title and a complete http(s) URL.");
      return;
    }
    try {
      await request(`/projects/${selected.id}/artifacts`, {
        method: "POST",
        body: JSON.stringify({ kind: "research", title, sourceUrl: url, content: "Saved local research source" }),
      });
      setSourceTitle("");
      setSourceUrl("");
      await loadProjects(selected.id);
    } catch {
      setError("Could not save that local research source.");
    }
  };

  const startRun = async () => {
    const goal = runGoal.trim();
    if (!selected || !goal) return;
    setRunBusy(true);
    try {
      await request(`/projects/${selected.id}/runs`, {
        method: "POST",
        body: JSON.stringify({ goal }),
      });
      setRunGoal("");
      await loadProjects(selected.id);
    } catch {
      setError("Could not start the local agent run.");
    } finally {
      setRunBusy(false);
    }
  };

  const updateRun = async (run: AgentRun, status: RunStatus) => {
    if (!selected || run.status === status) return;
    setRunBusy(true);
    try {
      await request(`/projects/runs/${run.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await loadProjects(selected.id);
    } catch {
      setError("Could not update the local agent run.");
    } finally {
      setRunBusy(false);
    }
  };

  const uploadFile = async (file: File | undefined) => {
    if (!selected || !file) return;
    if (file.size > 25 * 1024 * 1024) {
      setError("Files are limited to 25 MB.");
      return;
    }
    setFileBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API}/projects/${selected.id}/files`, { method: "POST", body: form });
      if (!response.ok) throw new Error(`Upload failed (${response.status})`);
      await loadProjects(selected.id);
    } catch {
      setError("Could not save that file to the local project.");
    } finally {
      setFileBusy(false);
    }
  };

  const analyzeFile = async (file: ProjectFile) => {
    if (!selected) return;
    setFileBusy(true);
    setError("");
    try {
      await request(`/projects/files/${file.id}/analyze`, { method: "POST" });
      await loadProjects(selected.id);
    } catch {
      setError("HINAA could not read that file locally. Supported formats: TXT, Markdown, CSV, JSON, PDF, DOCX, and PPTX.");
    } finally {
      setFileBusy(false);
    }
  };

  const addTask = async () => {
    const clean = taskTitle.trim();
    if (!selected || !clean) return;
    try {
      await request(`/projects/${selected.id}/tasks`, {
        method: "POST",
        body: JSON.stringify({ title: clean, requiresApproval: false }),
      });
      setTaskTitle("");
      await loadProjects(selected.id);
    } catch {
      setError("Could not add the task.");
    }
  };

  if (!active) return null;

  return (
    <aside
      aria-label="Local project workspace"
      style={{
        width: 300,
        minWidth: 260,
        borderRight: "1px solid rgba(148,163,184,0.18)",
        background: "rgba(15,23,42,0.76)",
        color: "#e2e8f0",
        padding: 14,
        overflowY: "auto",
        zIndex: 2,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <div>
          <p style={{ margin: 0, color: "#5eead4", fontSize: 11, fontWeight: 800, letterSpacing: "0.1em" }}>LOCAL WORKSPACE</p>
          <h2 style={{ margin: "3px 0 0", fontSize: 17 }}>Projects & tasks</h2>
        </div>
        <button type="button" aria-label="Refresh projects" onClick={() => void loadProjects()} style={iconButtonStyle}>
          {loading ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}
        </button>
      </div>

      <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
        <input value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void createProject()} placeholder="New project name" aria-label="New project name" style={inputStyle} />
        <button type="button" disabled={creating} onClick={() => void createProject()} style={primaryButtonStyle} title="Create project"><FolderPlus size={16} /></button>
      </div>

      {error && <p style={{ color: "#fda4af", fontSize: 12, lineHeight: 1.4 }}>{error}</p>}

      <div style={{ display: "grid", gap: 5, marginTop: 14 }}>
        {projects.map((project) => (
          <button key={project.id} type="button" onClick={() => void loadProjects(project.id)} style={{ ...projectButtonStyle, borderColor: selected?.id === project.id ? "#2dd4bf" : "rgba(148,163,184,0.18)", background: selected?.id === project.id ? "rgba(20,184,166,0.13)" : "rgba(15,23,42,0.38)" }}>
            <strong>{project.title}</strong>
            {project.description && <span>{project.description}</span>}
          </button>
        ))}
      </div>

      {!loading && projects.length === 0 && <p style={{ color: "#94a3b8", fontSize: 13, lineHeight: 1.5 }}>Create a private project to organize Hinaa’s files, plans, research, and generated assets.</p>}

      {selected && (
        <div style={{ marginTop: 18, display: "grid", gap: 16 }}>
          <section>
            <label style={sectionLabelStyle}><ListTodo size={14} /> TASK TREE</label>
                          <div style={{ display: "grid", gap: 6, marginTop: 7 }}>
                <div style={{ display: "flex", gap: 6 }}>
                  <input value={planGoal} onChange={(event) => setPlanGoal(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void createPlan()} placeholder="What should Hinaa plan?" aria-label="Project goal for plan" style={inputStyle} />
                  <button type="button" onClick={() => void createPlan()} style={primaryButtonStyle} title="Create plan"><Sparkles size={16} /></button>
                </div>
                <div style={{ display: "grid", gap: 5, padding: "8px", borderRadius: 9, border: "1px solid rgba(245,167,187,.18)", background: "rgba(245,167,187,.045)" }}>
                  <small style={{ color: "#ffd4df", fontWeight: 750 }}>WEBSITE BUILD BLUEPRINT</small>
                  <input value={siteBrief} onChange={(event) => setSiteBrief(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void createWebsiteBlueprint()} placeholder="Describe the site, audience, pages, and style" aria-label="Website build brief" style={inputStyle} />
                  <button type="button" disabled={siteBusy || siteBrief.trim().length < 10} onClick={() => void createWebsiteBlueprint()} style={{ ...miniButtonStyle, justifyContent: "center", opacity: siteBusy || siteBrief.trim().length < 10 ? .55 : 1 }}><FileText size={12} />{siteBusy ? "Creating blueprint…" : "Create local blueprint"}</button>
                  <small style={{ color: "#94a3b8", lineHeight: 1.35 }}>Creates tasks and a private brief only. HINAA will request approval before writing, running, or publishing a site.</small>
                </div>

              <div style={{ display: "flex", gap: 6 }}>
                <input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void addTask()} placeholder="Add a task" aria-label="Add project task" style={inputStyle} />
                <button type="button" onClick={() => void addTask()} style={primaryButtonStyle} title="Add task"><Plus size={16} /></button>
              </div>
            </div>
            <div style={{ display: "grid", gap: 7, marginTop: 10 }}>
              {selected.tasks.map((task) => <div key={task.id} style={{ ...rowStyle, marginLeft: task.parentTaskId ? 14 : 0, borderLeft: task.parentTaskId ? "2px solid rgba(45,212,191,.35)" : "2px solid transparent" }}>
                <span style={{ width: 8, height: 8, borderRadius: 99, background: statusColor(task.status), flexShrink: 0, marginTop: 5 }} />
                <div style={{ minWidth: 0, flex: 1 }}><strong>{task.title}</strong>{task.detail && <small>{task.detail}</small>}{task.requiresApproval && <em><ShieldCheck size={11} /> Approval required</em>}</div>
                <select aria-label={`Status for ${task.title}`} value={task.status} onChange={(event) => void updateTaskStatus(task, event.target.value as TaskStatus)} style={statusSelectStyle}>
                  <option value="pending">Queued</option><option value="active">Active</option><option value="waiting_approval">Approve</option><option value="success">Done</option><option value="error">Blocked</option><option value="cancelled">Stopped</option>
                </select>
              </div>)}
              {selected.tasks.length === 0 && <small style={{ color: "#94a3b8" }}>Add a goal to generate a visible, editable local work plan.</small>}
            </div>
          </section>

          <section>
            <label style={sectionLabelStyle}><Sparkles size={14} /> AGENT RUNS</label>
            <p style={{ color: "#cbd5e1", fontSize: 12, lineHeight: 1.45, margin: "7px 0" }}>Persistent local run context. Hinaa records each state, but still waits for your approval before consequential actions.</p>
            <div style={{ display: "flex", gap: 6 }}>
              <input value={runGoal} onChange={(event) => setRunGoal(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void startRun()} placeholder="Start a focused agent run" aria-label="Agent run goal" style={inputStyle} />
              <button type="button" disabled={runBusy} onClick={() => void startRun()} style={primaryButtonStyle} title="Start local agent run"><Play size={15} /></button>
            </div>
            <div style={{ display: "grid", gap: 7, marginTop: 9 }}>
              {selected.runs.slice(0, 4).map((run) => {
                const latest = run.events[run.events.length - 1];
                const color = run.status === "completed" ? "#34d399" : run.status === "waiting_approval" ? "#fbbf24" : run.status === "failed" ? "#fb7185" : run.status === "running" ? "#38bdf8" : "#94a3b8";
                return <div key={run.id} style={{ ...rowStyle, display: "grid", gap: 6, borderLeft: `2px solid ${color}` }}>
                  <div style={{ display: "flex", gap: 7, alignItems: "flex-start" }}><span style={{ width: 8, height: 8, marginTop: 4, borderRadius: 99, background: color }} /><div style={{ minWidth: 0, flex: 1 }}><strong>{run.goal}</strong><small>{latest?.label || "Run created"}{latest?.detail ? ` · ${latest.detail}` : ""}</small></div></div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, paddingLeft: 15 }}><span style={{ color, fontSize: 10, fontWeight: 800, letterSpacing: ".05em" }}>{run.status.replace("_", " ").toUpperCase()}</span><span style={{ display: "flex", gap: 5, flexWrap: "wrap", justifyContent: "flex-end" }}>{run.status === "waiting_approval" && <><button type="button" disabled={runBusy} onClick={() => void updateRun(run, "running")} style={miniButtonStyle}><Play size={11} /> Resume</button><button type="button" disabled={runBusy} onClick={() => void updateRun(run, "cancelled")} style={miniButtonStyle}><XCircle size={11} /> Cancel</button></>}{run.status === "running" && <><button type="button" disabled={runBusy} onClick={() => void updateRun(run, "waiting_approval")} style={miniButtonStyle}><Pause size={11} /> Pause</button><button type="button" disabled={runBusy} onClick={() => void updateRun(run, "completed")} style={miniButtonStyle}><CheckCircle2 size={11} /> Finish</button><button type="button" disabled={runBusy} onClick={() => void updateRun(run, "cancelled")} style={miniButtonStyle}><XCircle size={11} /> Cancel</button></>}{(run.status === "failed" || run.status === "cancelled" || run.status === "completed") && <button type="button" disabled={runBusy} onClick={() => void updateRun(run, "running")} style={miniButtonStyle}><RotateCcw size={11} /> Resume context</button>}</span></div>
                </div>;
              })}
              {selected.runs.length === 0 && <small style={{ color: "#94a3b8" }}>Start a run to preserve a focused execution context and inspect its event history later.</small>}
            </div>
          </section>

          <section>
            <label style={sectionLabelStyle}><FileText size={14} /> LOCAL CONTENT</label>
            <p style={{ color: "#cbd5e1", fontSize: 12, margin: "8px 0" }}>{selected.files.length} file{selected.files.length === 1 ? "" : "s"} · {selected.artifacts.length} saved artifact{selected.artifacts.length === 1 ? "" : "s"}</p>
            <label style={{ ...miniButtonStyle, width: "fit-content", opacity: fileBusy ? .6 : 1 }} title="Upload a local document">
              {fileBusy ? <Loader2 size={11} className="spin" /> : <Upload size={11} />} Upload file
              <input aria-label="Upload local project file" type="file" hidden disabled={fileBusy} accept=".txt,.md,.markdown,.csv,.json,.pdf,.docx,.pptx" onChange={(event) => { void uploadFile(event.target.files?.[0]); event.currentTarget.value = ""; }} />
            </label>
            <p style={{ color: "#94a3b8", fontSize: 11, lineHeight: 1.4, margin: "7px 0" }}>Files remain local. Analyze supported files to create a private text artifact HINAA can reference and export.</p>
            <div style={{ display: "grid", gap: 5 }}>
              {selected.artifacts.slice(0, 4).map((item) => <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, color: "#94a3b8", fontSize: 12 }}><span style={{ minWidth: 0, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.kind}: {item.title}</span><a href={`${API}/projects/artifacts/${item.id}/export`} title={`Export ${item.title} as Markdown`} aria-label={`Export ${item.title} as Markdown`} style={{ color: "#7dd3fc", display: "grid" }}><Download size={13} /></a></div>)}
              {selected.files.slice(0, 6).map((item) => <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, color: "#94a3b8", fontSize: 12, padding: "2px 0" }}><span style={{ minWidth: 0, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>file: {item.name}</span><a href={`${API}/projects/files/${item.id}`} title={`Download ${item.name}`} aria-label={`Download ${item.name}`} style={{ color: "#7dd3fc", display: "grid" }}><Download size={13} /></a><button type="button" disabled={fileBusy} onClick={() => void analyzeFile(item)} title={`Analyze ${item.name} locally`} style={miniButtonStyle}><FileSearch size={11} /> Analyze</button></div>)}
            </div>
          </section>

          <section>
            <label style={sectionLabelStyle}>SAVED SOURCES</label>
            <input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} placeholder="Source title" aria-label="Source title" style={{ ...inputStyle, width: "100%", marginTop: 7 }} />
            <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
              <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void saveSource()} placeholder="https://source.example" aria-label="Source URL" style={inputStyle} />
              <button type="button" onClick={() => void saveSource()} style={primaryButtonStyle} title="Save source"><Plus size={16} /></button>
            </div>
            <div style={{ display: "grid", gap: 5, marginTop: 8 }}>
              {selected.artifacts.filter((item) => item.sourceUrl).slice(0, 4).map((item) => <a key={item.id} href={item.sourceUrl || "#"} target="_blank" rel="noreferrer" style={{ color: "#7dd3fc", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>[Source] {item.title}</a>)}
            </div>
          </section>
        </div>
      )}
    </aside>
  );
}

const inputStyle = { minWidth: 0, flex: 1, border: "1px solid rgba(148,163,184,0.26)", borderRadius: 8, background: "rgba(15,23,42,0.72)", color: "#f8fafc", padding: "8px 9px", fontSize: 12 } as const;
const primaryButtonStyle = { border: 0, borderRadius: 8, background: "linear-gradient(135deg,#14b8a6,#0ea5e9)", color: "white", width: 34, display: "grid", placeItems: "center", cursor: "pointer" } as const;
const iconButtonStyle = { border: "1px solid rgba(148,163,184,0.25)", borderRadius: 8, background: "transparent", color: "#cbd5e1", padding: 7, cursor: "pointer" } as const;
const projectButtonStyle = { textAlign: "left", display: "grid", gap: 3, padding: "9px 10px", border: "1px solid", borderRadius: 9, color: "#e2e8f0", cursor: "pointer" } as const;
const sectionLabelStyle = { display: "flex", alignItems: "center", gap: 6, color: "#5eead4", fontSize: 11, fontWeight: 800, letterSpacing: "0.08em" } as const;
const rowStyle = { display: "flex", alignItems: "flex-start", gap: 8, padding: 8, background: "rgba(15,23,42,0.42)", borderRadius: 8, fontSize: 12 } as const;
const statusSelectStyle = { width: 76, border: "1px solid rgba(148,163,184,.28)", background: "rgba(2,6,23,.7)", borderRadius: 6, color: "#cbd5e1", fontSize: 10, padding: "4px" } as const;
const miniButtonStyle = { display: "inline-flex", alignItems: "center", gap: 3, border: "1px solid rgba(148,163,184,.30)", borderRadius: 6, background: "rgba(15,23,42,.66)", color: "#cbd5e1", padding: "4px 6px", cursor: "pointer", fontSize: 10, fontWeight: 700 } as const;
