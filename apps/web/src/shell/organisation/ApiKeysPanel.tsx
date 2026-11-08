import { useState, type FormEvent } from "react";
import { Badge, Button, Panel } from "../../design-system/hud";
import { ResourceState } from "../ui";
import { useApiJson } from "../useApi";
import { ORG_BASE, call, when, type ApiKeyRow, type CreatedKey, type OrgMe } from "./api";

export function ApiKeysPanel({ me }: { me: OrgMe }) {
  const list = useApiJson<{ items: ApiKeyRow[] }>(`${ORG_BASE}/api-keys`);
  const [name, setName] = useState("");
  const [days, setDays] = useState("");
  const [scopes, setScopes] = useState<string[]>(["data:read"]);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<CreatedKey | null>(null);
  const [copied, setCopied] = useState(false);
  const items = list.data?.items ?? [];

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return setError("Give the key a name.");
    if (scopes.length === 0) return setError("Pick at least one scope.");
    try {
      const created = await call<CreatedKey>("POST", `${ORG_BASE}/api-keys`, {
        name: name.trim(),
        scopes,
        expiresInDays: days ? Number(days) : null,
      });
      setRevealed(created);
      setCopied(false);
      setName("");
      list.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the key");
    }
  };

  const revoke = async (k: ApiKeyRow) => {
    setError(null);
    try {
      await call("DELETE", `${ORG_BASE}/api-keys/${k.id}`);
      list.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke the key");
    }
  };

  const copy = async () => {
    if (!revealed) return;
    try {
      await navigator.clipboard.writeText(revealed.key);
      setCopied(true);
    } catch {
      setError("Copy failed — select the key and copy it manually.");
    }
  };

  const toggle = (scope: string) =>
    setScopes((s) => (s.includes(scope) ? s.filter((x) => x !== scope) : [...s, scope]));

  return (
    <Panel title="API keys">
      {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}
      {revealed && (
        <div className="org-reveal" role="status" aria-label="New API key">
          <p>Copy this key now. It is shown once and cannot be retrieved later.</p>
          <code className="org-reveal__key">{revealed.key}</code>
          <div className="org-actions">
            <Button variant="primary" onClick={() => void copy()}>{copied ? "Copied" : "Copy key"}</Button>
            <Button onClick={() => setRevealed(null)}>Done</Button>
          </div>
        </div>
      )}
      <form className="prod-quick" onSubmit={create} aria-label="New API key form">
        <label className="prod-field"><span>Name</span><input className="shell-input" value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="prod-field"><span>Expires in (days)</span><input className="shell-input" inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))} placeholder="never" /></label>
        <fieldset className="org-scopes">
          <legend>Scopes</legend>
          {me.permissions.map((p) => (
            <label key={p} className="org-scope"><input type="checkbox" checked={scopes.includes(p)} onChange={() => toggle(p)} /> {p}</label>
          ))}
        </fieldset>
        <Button type="submit" variant="primary">Create key</Button>
      </form>
      <ResourceState status={list.status} error={list.error} empty={items.length === 0} noun="API keys" onRetry={list.reload}>
        <table className="prod-table" aria-label="API keys">
          <thead><tr><th>Name</th><th>Prefix</th><th>Scopes</th><th>Last used</th><th>Status</th><th><span className="org-sr">Actions</span></th></tr></thead>
          <tbody>
            {items.map((k) => (
              <tr key={k.id}>
                <td>{k.name}</td>
                <td><code>{k.prefix}…</code></td>
                <td>{k.scopes.join(", ")}</td>
                <td>{when(k.lastUsedAt)}</td>
                <td><Badge tone={k.active ? "success" : "neutral"}>{k.revokedAt ? "revoked" : k.active ? "active" : "expired"}</Badge></td>
                <td>{k.active && <Button variant="danger" aria-label={`Revoke ${k.name}`} onClick={() => void revoke(k)}>Revoke</Button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ResourceState>
    </Panel>
  );
}
