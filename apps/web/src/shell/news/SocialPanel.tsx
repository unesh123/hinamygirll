import { useState } from "react";
import { Badge, Button, Panel } from "../../design-system/hud";
import { useApiJson } from "../useApi";
import { ResourceState } from "../ui";
import { SOCIAL_BASE, call, type List, type SocialConnection } from "./api";

const TONE = { connected: "success", ready: "accent", requires_setup: "warning" } as const;
const LABEL = { connected: "Connected", ready: "Ready to connect", requires_setup: "Requires setup" } as const;

export function SocialPanel() {
  const conns = useApiJson<List<SocialConnection>>(`${SOCIAL_BASE}/connections`);
  const [error, setError] = useState<string | null>(null);
  const items = conns.data?.items ?? [];

  const connect = async () => {
    setError(null);
    try {
      const out = await call<{ authUrl: string }>("GET", `${SOCIAL_BASE}/youtube/connect`);
      if (out?.authUrl) window.open(out.authUrl, "_blank", "noopener");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the YouTube sign-in");
    }
  };

  const disconnect = async () => {
    setError(null);
    try {
      await call("POST", `${SOCIAL_BASE}/youtube/disconnect`);
      conns.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect");
    }
  };

  return (
    <Panel title="Social publishing">
      <p className="shell-card__meta">
        Publishing can’t be undone, so Hina always asks first and uploads as private unless you say public or unlisted.
      </p>
      {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}
      <ResourceState status={conns.status} error={conns.error} empty={items.length === 0} noun="connections" onRetry={conns.reload}>
        <ul className="shell-grid" aria-label="Social connections">
          {items.map((c) => (
            <li key={c.id} className="shell-card">
              <div className="shell-card__row">
                <strong>{c.name}</strong>
                <Badge tone={TONE[c.status]} dot>{LABEL[c.status]}</Badge>
              </div>
              {c.account && <span className="shell-card__meta">Channel: {c.account}</span>}
              {c.requirements && <span className="shell-card__meta">{c.requirements}</span>}
              {c.id === "youtube" && c.status === "ready" && <Button variant="primary" onClick={connect}>Connect YouTube</Button>}
              {c.id === "youtube" && c.connected && <Button onClick={disconnect}>Disconnect</Button>}
            </li>
          ))}
        </ul>
      </ResourceState>
    </Panel>
  );
}
