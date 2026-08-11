import { useEffect, useState } from "react";
import { FolderPlus, FileText, ListTodo, Loader2, Plus, RefreshCw } from "lucide-react";

type TaskStatus = "pending" | "active" | "success" | "error" | "cancelled" | "waiting_approval";

interface ProjectTask {
  id: string;
  title: string;
  detail: string;
  status: TaskStatus;
  requiresApproval: boolean;
}

interface ProjectFile {
  id: string;
  name: string;
  sizeBytes: number;
}

interface ProjectArtifact {
  id: string;
  kind: string;
  title: string;
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadProjects = async (selectId?: string) => {
    setLoading(true);
    setError("");
    try {
      const items = await request<ProjectSummary[]>("/projects");
      setProjects(items);
      const id = selectId || selected?.id || items[0]?.id;
      if (id) setSelected(await request<ProjectDetail>(`/projects/${id}`));
      else setSelected(null);
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
            <div style={{ display: "flex", gap: 6, marginTop: 7 }}>
              <input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void addTask()} placeholder="Add a task" aria-label="Add project task" style={inputStyle} />
              <button type="button" onClick={() => void addTask()} style={primaryButtonStyle}><Plus size={16} /></button>
            </div>
            <div style={{ display: "grid", gap: 7, marginTop: 10 }}>
              {selected.tasks.map((task) => <div key={task.id} style={rowStyle}><span style={{ width: 8, height: 8, borderRadius: 99, background: statusColor(task.status), flexShrink: 0 }} /><div><strong>{task.title}</strong>{task.detail && <small>{task.detail}</small>}{task.requiresApproval && <em>Approval required</em>}</div></div>)}
              {selected.tasks.length === 0 && <small style={{ color: "#94a3b8" }}>No tasks yet. Hinaa can turn your next goal into a plan.</small>}
            </div>
          </section>

          <section>
            <label style={sectionLabelStyle}><FileText size={14} /> LOCAL CONTENT</label>
            <p style={{ color: "#cbd5e1", fontSize: 12, margin: "8px 0" }}>{selected.files.length} file{selected.files.length === 1 ? "" : "s"} · {selected.artifacts.length} saved artifact{selected.artifacts.length === 1 ? "" : "s"}</p>
            {[...selected.artifacts.slice(0, 3).map((item) => `${item.kind}: ${item.title}`), ...selected.files.slice(0, 3).map((item) => `file: ${item.name}`)].map((label) => <div key={label} style={{ color: "#94a3b8", fontSize: 12, padding: "4px 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</div>)}
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
