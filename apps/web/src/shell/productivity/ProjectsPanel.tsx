import { useState, type FormEvent } from "react";
import { Badge, Button, Panel } from "../../design-system/hud";
import { useApiJson } from "../useApi";
import { ResourceState } from "../ui";
import { Dialog } from "./Dialog";
import { PRIORITIES, PROJECT_STATUSES, PRODUCTIVITY_BASE, formatDay, send, toIsoDate, type Page, type Project } from "./api";

const STATUS_TONE = { planning: "neutral", active: "accent", blocked: "danger", done: "success" } as const;
const PRIORITY_TONE = { low: "neutral", medium: "warning", high: "danger" } as const;

interface Draft {
  id: string | null;
  name: string;
  status: string;
  priority: string;
  dueDate: string;
  progress: string;
  nextAction: string;
  notes: string;
}

const blank: Draft = { id: null, name: "", status: "planning", priority: "medium", dueDate: "", progress: "0", nextAction: "", notes: "" };

function draftFrom(p: Project): Draft {
  return { id: p.id, name: p.name, status: p.status, priority: p.priority, dueDate: p.dueDate ?? "", progress: String(p.progress), nextAction: p.nextAction, notes: p.notes };
}

function ProjectDialog({ initial, onClose, onSaved }: { initial: Draft; onClose: () => void; onSaved: () => void }) {
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const set = (key: keyof Draft) => (e: { target: { value: string } }) => setDraft((d) => ({ ...d, [key]: e.target.value }));

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const progress = Number(draft.progress);
    if (!draft.name.trim()) return setError("A project needs a name.");
    if (!Number.isInteger(progress) || progress < 0 || progress > 100) return setError("Progress must be a whole number from 0 to 100.");
    const body = {
      name: draft.name.trim(),
      status: draft.status,
      priority: draft.priority,
      progress,
      dueDate: draft.dueDate || null,
      nextAction: draft.nextAction,
      notes: draft.notes,
    };
    void run(() => (draft.id ? send("PATCH", `/projects/${draft.id}`, body) : send("POST", "/projects", body)));
  };

  return (
    <Dialog title={draft.id ? "Edit project" : "Add project"} onClose={onClose}>
      <form className="prod-form" onSubmit={submit} noValidate>
        <label className="prod-field">Name<input className="shell-input" value={draft.name} onChange={set("name")} maxLength={160} required /></label>
        <div className="prod-form__row">
          <label className="prod-field">Status
            <select className="shell-input" value={draft.status} onChange={set("status")}>{PROJECT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
          </label>
          <label className="prod-field">Priority
            <select className="shell-input" value={draft.priority} onChange={set("priority")}>{PRIORITIES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
          </label>
        </div>
        <div className="prod-form__row">
          <label className="prod-field">Due date<input className="shell-input" type="date" value={draft.dueDate} onChange={set("dueDate")} /></label>
          <label className="prod-field">Progress (%)<input className="shell-input" type="number" min={0} max={100} value={draft.progress} onChange={set("progress")} /></label>
        </div>
        <label className="prod-field">Next action<input className="shell-input" value={draft.nextAction} onChange={set("nextAction")} maxLength={1000} /></label>
        <label className="prod-field">Notes<textarea className="shell-input prod-textarea" rows={3} value={draft.notes} onChange={set("notes")} /></label>
        {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}
        <div className="prod-form__actions">
          {draft.id && (
            confirmDelete
              ? <Button variant="danger" disabled={busy} onClick={() => void run(() => send("DELETE", `/projects/${draft.id}`))}>Confirm delete</Button>
              : <Button variant="danger" disabled={busy} onClick={() => setConfirmDelete(true)}>Delete</Button>
          )}
          <span className="prod-spacer" />
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" disabled={busy}>{draft.id ? "Save project" : "Add project"}</Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ProjectsPanel() {
  const projects = useApiJson<Page<Project>>(`${PRODUCTIVITY_BASE}/projects?limit=100`);
  const [editing, setEditing] = useState<Draft | null>(null);
  const [quick, setQuick] = useState("");
  const [quickError, setQuickError] = useState<string | null>(null);
  const items = projects.data?.items ?? [];
  const today = toIsoDate(new Date());

  const quickAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!quick.trim()) return setQuickError("A project needs a name.");
    setQuickError(null);
    try {
      await send("POST", "/projects", { name: quick.trim() });
      setQuick("");
      projects.reload();
    } catch (err) {
      setQuickError(err instanceof Error ? err.message : "Could not add the project");
    }
  };

  return (
    <Panel title={`Projects${items.length ? ` · ${items.length}` : ""}`} actions={<Button variant="secondary" onClick={() => setEditing({ ...blank })}>Detailed add</Button>}>
      <form className="prod-quick" onSubmit={(e) => void quickAdd(e)} noValidate aria-label="Quick add project">
        <label className="prod-field prod-field--grow">New project<input className="shell-input" value={quick} onChange={(e) => setQuick(e.target.value)} maxLength={160} /></label>
        <Button variant="primary" type="submit">Add project</Button>
      </form>
      {quickError && <p className="shell-state" data-kind="error" role="alert">{quickError}</p>}
      <ResourceState status={projects.status} error={projects.error} empty={items.length === 0} noun="projects" onRetry={projects.reload}>
        <ul className="shell-grid prod-projects" aria-label="Projects">
          {items.map((p) => {
            const overdue = p.dueDate != null && p.status !== "done" && p.dueDate < today;
            return (
              <li key={p.id} className="shell-card prod-project">
                <div className="shell-card__row">
                  <strong>{p.name}</strong>
                  <Badge tone={STATUS_TONE[p.status]} dot>{p.status}</Badge>
                </div>
                <div className="prod-project__meta">
                  <Badge tone={PRIORITY_TONE[p.priority]}>{p.priority} priority</Badge>
                  {p.dueDate && <Badge tone={overdue ? "danger" : "neutral"}>{overdue ? "Overdue · " : "Due "}{formatDay(p.dueDate)}</Badge>}
                </div>
                <div className="prod-progress" role="progressbar" aria-label={`${p.name} progress`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={p.progress}>
                  <span className="prod-progress__bar" style={{ width: `${p.progress}%` }} />
                </div>
                <span className="shell-card__meta">{p.progress}% complete</span>
                {p.nextAction && <span className="prod-project__next"><span className="shell-card__meta">Next:</span> {p.nextAction}</span>}
                <Button variant="ghost" aria-label={`Edit ${p.name}`} onClick={() => setEditing(draftFrom(p))}>Edit</Button>
              </li>
            );
          })}
        </ul>
      </ResourceState>
      {editing && <ProjectDialog initial={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); projects.reload(); }} />}
    </Panel>
  );
}
