import { useState, type FormEvent } from "react";
import { Badge, Button, Panel } from "../../design-system/hud";
import { useApiJson } from "../useApi";
import { ResourceState } from "../ui";
import { Dialog } from "./Dialog";
import {
  PLATFORMS,
  POST_STATUSES,
  PRODUCTIVITY_BASE,
  addDays,
  formatDay,
  mondayOf,
  parseIsoDate,
  send,
  toIsoDate,
  type ContentPost,
  type WeekView,
} from "./api";

interface Draft {
  id: string | null;
  title: string;
  platform: string;
  status: string;
  date: string;
  time: string;
  caption: string;
  tags: string;
  notes: string;
}

function blankDraft(date = ""): Draft {
  return { id: null, title: "", platform: "instagram", status: date ? "scheduled" : "idea", date, time: "09:00", caption: "", tags: "", notes: "" };
}

function draftFrom(post: ContentPost): Draft {
  const [date = "", time = ""] = (post.scheduledFor ?? "").split("T");
  return { id: post.id, title: post.title, platform: post.platform, status: post.status, date, time: time || "09:00", caption: post.caption, tags: post.tags.join(", "), notes: post.notes };
}

function PostDialog({ initial, onClose, onSaved }: { initial: Draft; onClose: () => void; onSaved: () => void }) {
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
    if (!draft.title.trim()) {
      setError("A post needs a title.");
      return;
    }
    const body = {
      title: draft.title.trim(),
      platform: draft.platform,
      status: draft.status,
      caption: draft.caption,
      notes: draft.notes,
      tags: draft.tags.split(",").map((t) => t.trim()).filter(Boolean),
      scheduledFor: draft.date ? `${draft.date}T${draft.time || "09:00"}` : null,
    };
    void run(() => (draft.id ? send("PATCH", `/content/posts/${draft.id}`, body) : send("POST", "/content/posts", body)));
  };

  return (
    <Dialog title={draft.id ? "Edit post" : "Add post"} onClose={onClose}>
      <form className="prod-form" onSubmit={submit} noValidate>
        <label className="prod-field">Title<input className="shell-input" value={draft.title} onChange={set("title")} maxLength={200} required /></label>
        <div className="prod-form__row">
          <label className="prod-field">Platform
            <select className="shell-input" value={draft.platform} onChange={set("platform")}>{PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}</select>
          </label>
          <label className="prod-field">Status
            <select className="shell-input" value={draft.status} onChange={set("status")}>{POST_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
          </label>
        </div>
        <div className="prod-form__row">
          <label className="prod-field">Date<input className="shell-input" type="date" value={draft.date} onChange={set("date")} /></label>
          <label className="prod-field">Time<input className="shell-input" type="time" value={draft.time} onChange={set("time")} /></label>
        </div>
        <label className="prod-field">Caption<textarea className="shell-input prod-textarea" rows={3} value={draft.caption} onChange={set("caption")} /></label>
        <label className="prod-field">Tags (comma separated)<input className="shell-input" value={draft.tags} onChange={set("tags")} /></label>
        <label className="prod-field">Notes<textarea className="shell-input prod-textarea" rows={2} value={draft.notes} onChange={set("notes")} /></label>
        {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}
        <div className="prod-form__actions">
          {draft.id && (
            confirmDelete
              ? <Button variant="danger" disabled={busy} onClick={() => void run(() => send("DELETE", `/content/posts/${draft.id}`))}>Confirm delete</Button>
              : <Button variant="danger" disabled={busy} onClick={() => setConfirmDelete(true)}>Delete</Button>
          )}
          <span className="prod-spacer" />
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" disabled={busy}>{draft.id ? "Save post" : "Add post"}</Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ContentPanel() {
  const [weekStart, setWeekStart] = useState(() => toIsoDate(mondayOf(new Date())));
  const [editing, setEditing] = useState<Draft | null>(null);
  const week = useApiJson<WeekView>(`${PRODUCTIVITY_BASE}/content/week?week_start=${weekStart}`);
  const todayIso = toIsoDate(new Date());
  const weekEnd = addDays(weekStart, 6);

  return (
    <Panel
      title={`Content calendar · ${formatDay(weekStart)} – ${formatDay(weekEnd)}`}
      actions={
        <span className="prod-toolbar">
          <Button variant="ghost" aria-label="Previous week" onClick={() => setWeekStart(addDays(weekStart, -7))}>‹</Button>
          <Button variant="ghost" onClick={() => setWeekStart(toIsoDate(mondayOf(new Date())))}>This week</Button>
          <Button variant="ghost" aria-label="Next week" onClick={() => setWeekStart(addDays(weekStart, 7))}>›</Button>
          <Button variant="primary" onClick={() => setEditing(blankDraft())}>Add post</Button>
        </span>
      }
    >
      <ResourceState status={week.status} error={week.error} noun="content calendar" onRetry={week.reload}>
        {week.data && (
          <>
            {week.data.total === 0 && <p className="shell-state" data-kind="empty">No posts planned this week yet.</p>}
            <ol className="prod-week" aria-label={`Week of ${formatDay(week.data.weekStart)}`}>
              {week.data.days.map((day) => (
                <li key={day.date} className="prod-day" data-today={day.date === todayIso}>
                  <div className="prod-day__head">
                    <strong>{parseIsoDate(day.date).toLocaleDateString("en-US", { weekday: "short" })}</strong>
                    <span className="shell-card__meta">{formatDay(day.date)}</span>
                  </div>
                  <ul className="shell-list" aria-label={`Posts on ${day.weekday}`}>
                    {day.posts.map((post) => (
                      <li key={post.id}>
                        <button type="button" className="prod-post" data-status={post.status} onClick={() => setEditing(draftFrom(post))}>
                          <span className="prod-post__top">
                            <Badge tone="accent">{post.platform}</Badge>
                            <span className="shell-card__meta">{(post.scheduledFor ?? "").split("T")[1] ?? ""}</span>
                          </span>
                          <span className="prod-post__title">{post.title}</span>
                          <span className="prod-post__status">{post.status}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  <button type="button" className="prod-day__add" aria-label={`Add post on ${day.weekday}`} onClick={() => setEditing(blankDraft(day.date))}>+</button>
                </li>
              ))}
            </ol>
          </>
        )}
      </ResourceState>
      {editing && (
        <PostDialog
          initial={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); week.reload(); }}
        />
      )}
    </Panel>
  );
}
