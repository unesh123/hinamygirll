import { useState } from "react";
import { Badge, Button, Panel } from "../../design-system/hud";
import { ResourceState } from "../ui";
import { useApiJson } from "../useApi";
import { ORG_BASE, call, when, type AuditPage, type AuditVerdict } from "./api";

const PAGE = 20;

export function AuditPanel() {
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState("");
  const [verdict, setVerdict] = useState<AuditVerdict | null>(null);
  const [error, setError] = useState<string | null>(null);
  const query = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
  if (action.trim()) query.set("action", action.trim());
  const page = useApiJson<AuditPage>(`${ORG_BASE}/audit?${query}`);
  const items = page.data?.items ?? [];
  const total = page.data?.total ?? 0;

  const verify = async () => {
    setError(null);
    try {
      setVerdict(await call<AuditVerdict>("GET", `${ORG_BASE}/audit/verify`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    }
  };

  return (
    <Panel title="Audit log">
      <div className="prod-quick">
        <label className="prod-field"><span>Filter by action</span>
          <input className="shell-input" value={action} onChange={(e) => { setOffset(0); setAction(e.target.value); }} placeholder="e.g. apikey.create" />
        </label>
        <Button onClick={() => void verify()}>Verify chain</Button>
        {verdict && (
          <Badge tone={verdict.ok ? "success" : "danger"} dot>
            {verdict.ok ? `Chain intact (${verdict.checked} entries)` : `Tampering detected at entry ${verdict.firstInvalidSeq}`}
          </Badge>
        )}
      </div>
      {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}
      <ResourceState status={page.status} error={page.error} empty={items.length === 0} noun="audit entries" onRetry={page.reload}>
        <table className="prod-table" aria-label="Audit log">
          <thead><tr><th>#</th><th>When</th><th>Action</th><th>Target</th><th>Outcome</th></tr></thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.seq}>
                <td>{r.seq}</td>
                <td>{when(r.timestamp)}</td>
                <td>{r.action}</td>
                <td>{r.target}</td>
                <td><Badge tone={r.outcome === "denied" ? "danger" : "neutral"}>{r.outcome}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="org-actions">
          <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
          <span className="org-page">{offset + 1}–{Math.min(offset + PAGE, total)} of {total}</span>
          <Button disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
        </div>
      </ResourceState>
    </Panel>
  );
}
