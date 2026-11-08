import { useState, type FormEvent } from "react";
import { Badge, Button, Panel } from "../../design-system/hud";
import { useApiJson } from "../useApi";
import { ResourceState } from "../ui";
import { CADENCES, NEWS_BASE, call, formatWhen, splitList, type List, type RunResult, type Watchlist } from "./api";

const blank = { name: "", topics: "", keywords: "", sources: "", cadence: "daily", dailyHour: "8" };

export function WatchlistsPanel({ onRan }: { onRan: () => void }) {
  const lists = useApiJson<List<Watchlist>>(`${NEWS_BASE}/watchlists`);
  const [form, setForm] = useState(blank);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const items = lists.data?.items ?? [];

  const bind = (key: keyof typeof blank) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value })),
  });

  const act = async (id: string, work: () => Promise<void>, fallback: string) => {
    setBusy(id);
    setError(null);
    try {
      await work();
    } catch (err) {
      setError(err instanceof Error ? err.message : fallback);
    } finally {
      setBusy(null);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const topics = splitList(form.topics);
    const keywords = splitList(form.keywords);
    const sources = splitList(form.sources);
    if (!form.name.trim()) return setError("Give the watchlist a name.");
    if (!topics.length && !keywords.length && !sources.length) return setError("Add at least one topic, keyword or feed URL.");
    await act("create", async () => {
      await call("POST", `${NEWS_BASE}/watchlists`, { name: form.name.trim(), topics, keywords, sources, cadence: form.cadence, dailyHour: Number(form.dailyHour) });
      setForm(blank);
      lists.reload();
    }, "Could not create the watchlist");
  };

  const runNow = (w: Watchlist) =>
    act(w.id, async () => {
      setNote(null);
      const result = await call<RunResult>("POST", `${NEWS_BASE}/watchlists/${w.id}/run`);
      const warnings = result?.warnings ?? [];
      const head = result?.digest ? `Digest ready: ${result.digest.items.length} cited stories.` : "No new stories found — nothing was invented.";
      setNote([head, ...warnings].join(" "));
      lists.reload();
      onRan();
    }, "Run failed");

  const toggle = (w: Watchlist) =>
    act(w.id, async () => {
      await call("PATCH", `${NEWS_BASE}/watchlists/${w.id}`, { enabled: !w.enabled });
      lists.reload();
    }, "Could not update the watchlist");

  const remove = (w: Watchlist) =>
    act(w.id, async () => {
      await call("DELETE", `${NEWS_BASE}/watchlists/${w.id}`);
      lists.reload();
      onRan();
    }, "Could not delete the watchlist");

  return (
    <Panel title="Watchlists">
      <form className="prod-quick" onSubmit={submit} aria-label="New watchlist">
        <label className="prod-field"><span>Name</span><input className="shell-input" {...bind("name")} /></label>
        <label className="prod-field"><span>Topics (comma separated)</span><input className="shell-input" {...bind("topics")} /></label>
        <label className="prod-field"><span>Keywords</span><input className="shell-input" {...bind("keywords")} /></label>
        <label className="prod-field prod-field--grow"><span>RSS / Atom feed URLs</span><input className="shell-input" {...bind("sources")} /></label>
        <label className="prod-field">
          <span>Cadence</span>
          <select className="shell-input" {...bind("cadence")}>{CADENCES.map((c) => <option key={c} value={c}>{c}</option>)}</select>
        </label>
        <label className="prod-field"><span>Daily hour (Nepal)</span><input className="shell-input" type="number" min={0} max={23} {...bind("dailyHour")} /></label>
        <Button type="submit" variant="primary" disabled={busy === "create"}>Add watchlist</Button>
      </form>
      {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}
      {note && <p className="shell-state" role="status">{note}</p>}
      <ResourceState status={lists.status} error={lists.error} empty={items.length === 0} noun="watchlists" onRetry={lists.reload}>
        <ul className="shell-grid" aria-label="Watchlists">
          {items.map((w) => (
            <li key={w.id} className="shell-card">
              <div className="shell-card__row">
                <strong>{w.name}</strong>
                <Badge tone={w.enabled ? "success" : "neutral"} dot>{w.enabled ? w.cadence : "paused"}</Badge>
              </div>
              <span className="shell-card__meta">{[...w.topics, ...w.keywords].join(", ") || "feeds only"}{w.sources.length ? ` · ${w.sources.length} feed(s)` : ""}</span>
              <span className="shell-card__meta">Last run {formatWhen(w.lastRunAt)} · next {formatWhen(w.nextRunAt)}</span>
              <div className="prod-toolbar">
                <Button variant="primary" disabled={busy === w.id} onClick={() => runNow(w)} aria-label={`Run ${w.name} now`}>
                  {busy === w.id ? "Running…" : "Run now"}
                </Button>
                <Button onClick={() => toggle(w)} disabled={busy === w.id}>{w.enabled ? "Pause" : "Resume"}</Button>
                <Button variant="danger" onClick={() => remove(w)} disabled={busy === w.id} aria-label={`Delete ${w.name}`}>Delete</Button>
              </div>
            </li>
          ))}
        </ul>
      </ResourceState>
    </Panel>
  );
}
