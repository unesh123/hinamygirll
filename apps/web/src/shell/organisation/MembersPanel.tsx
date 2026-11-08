import { useState, type FormEvent } from "react";
import { Badge, Button, Panel } from "../../design-system/hud";
import { ResourceState } from "../ui";
import { useApiJson } from "../useApi";
import { ORG_BASE, call, can, type Member, type OrgMe, type Role } from "./api";

export function MembersPanel({ me }: { me: OrgMe }) {
  const list = useApiJson<{ items: Member[] }>(`${ORG_BASE}/members`);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<Role>("member");
  const manage = can(me, "members:manage");
  const items = list.data?.items ?? [];
  // Only owners may touch the owner tier; mirror the server so the UI never offers a doomed action.
  const roleOptions = me.roles.filter((r) => r !== "owner" || me.role === "owner");

  const run = async (work: () => Promise<unknown>) => {
    setError(null);
    try {
      await work();
      list.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    }
  };

  const invite = (e: FormEvent) => {
    e.preventDefault();
    if (!userId.trim()) return setError("Enter the user id to add.");
    void run(async () => {
      await call("POST", `${ORG_BASE}/members`, { userId: userId.trim(), role });
      setUserId("");
    });
  };

  return (
    <Panel title="Members">
      {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}
      {manage && (
        <form className="prod-quick" onSubmit={invite} aria-label="Add member">
          <label className="prod-field prod-field--grow"><span>User id</span>
            <input className="shell-input" value={userId} onChange={(e) => setUserId(e.target.value)} />
          </label>
          <label className="prod-field"><span>Role</span>
            <select className="shell-input" value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {roleOptions.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <Button type="submit" variant="primary">Add member</Button>
        </form>
      )}
      <ResourceState status={list.status} error={list.error} empty={items.length === 0} noun="members" onRetry={list.reload}>
        <table className="prod-table" aria-label="Members">
          <thead><tr><th>Member</th><th>Role</th>{manage && <th><span className="org-sr">Actions</span></th>}</tr></thead>
          <tbody>
            {items.map((m) => {
              const label = m.authSubject ?? m.userId;
              const locked = m.role === "owner" && me.role !== "owner";
              return (
                <tr key={m.userId}>
                  <td>{label}{m.userId === me.user.id && <Badge tone="accent">you</Badge>}</td>
                  <td>
                    {manage && !locked ? (
                      <select
                        className="shell-input"
                        aria-label={`Role for ${label}`}
                        value={m.role}
                        onChange={(e) => void run(() => call("PATCH", `${ORG_BASE}/members/${m.userId}`, { role: e.target.value }))}
                      >
                        {roleOptions.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    ) : <Badge tone="neutral">{m.role}</Badge>}
                  </td>
                  {manage && (
                    <td>
                      {!locked && (
                        <Button variant="danger" aria-label={`Remove ${label}`} onClick={() => void run(() => call("DELETE", `${ORG_BASE}/members/${m.userId}`))}>Remove</Button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </ResourceState>
    </Panel>
  );
}
