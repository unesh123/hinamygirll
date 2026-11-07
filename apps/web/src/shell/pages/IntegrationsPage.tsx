import { useMemo, useState } from "react";
import { Badge, Panel } from "../../design-system/hud";
import { useConnectors, useMcpServers, useSkills, useTools } from "../data";
import { PageFrame, ResourceState } from "../ui";

export default function IntegrationsPage() {
  const connectors = useConnectors();
  const skills = useSkills();
  const tools = useTools();
  const mcp = useMcpServers();
  const [query, setQuery] = useState("");

  const visibleSkills = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return skills.items;
    return skills.items.filter((s) => `${s.name} ${s.description} ${s.category}`.toLowerCase().includes(q));
  }, [skills.items, query]);

  const configuredCount = connectors.items.filter((c) => c.configured).length;

  return (
    <PageFrame title="Integrations" subtitle="Connectors, skills, tools and MCP servers Hina can use.">
      <Panel title={`Connectors${connectors.items.length ? ` · ${configuredCount}/${connectors.items.length} configured` : ""}`}>
        <ResourceState status={connectors.status} error={connectors.error} empty={connectors.items.length === 0} noun="connectors" onRetry={connectors.reload}>
          <ul className="shell-grid" aria-label="Connectors">
            {connectors.items.map((c) => (
              <li key={c.id} className="shell-card">
                <div className="shell-card__row">
                  <strong>{c.name}</strong>
                  <Badge tone={c.configured ? "success" : "neutral"} dot>{c.configured ? "Configured" : "Not configured"}</Badge>
                </div>
                <span className="shell-card__meta">{c.category}{c.statusText ? ` · ${c.statusText}` : ""}</span>
                {c.capabilities.length > 0 && <span className="shell-card__meta">{c.capabilities.slice(0, 4).join(", ")}</span>}
              </li>
            ))}
          </ul>
        </ResourceState>
      </Panel>

      <Panel title="Skills" actions={
        <input
          className="shell-input"
          type="search"
          aria-label="Search skills"
          placeholder="Search skills…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      }>
        <ResourceState status={skills.status} error={skills.error} empty={skills.items.length === 0} noun="skills" onRetry={skills.reload}>
          {visibleSkills.length === 0 ? (
            <p className="shell-state" data-kind="empty">No skills match “{query}”.</p>
          ) : (
            <ul className="shell-grid" aria-label="Skills">
              {visibleSkills.map((s) => (
                <li key={s.id} className="shell-card">
                  <div className="shell-card__row"><strong>{s.name}</strong><Badge>{s.category}</Badge></div>
                  {s.description && <span className="shell-card__meta">{s.description}</span>}
                </li>
              ))}
            </ul>
          )}
        </ResourceState>
      </Panel>

      <Panel title="MCP servers">
        <ResourceState status={mcp.status} error={mcp.error} empty={mcp.items.length === 0} noun="MCP servers" onRetry={mcp.reload}>
          <ul className="shell-list" aria-label="MCP servers">
            {mcp.items.map((m) => (
              <li key={m.id} className="shell-card__row">
                <span><strong>{m.name}</strong>{m.transport && <span className="shell-card__meta"> · {m.transport}</span>}</span>
                <span>
                  {m.toolCount !== null && <span className="shell-card__meta">{m.toolCount} tools </span>}
                  <Badge tone={m.status === "connected" ? "success" : "neutral"} dot>{m.status}</Badge>
                </span>
              </li>
            ))}
          </ul>
        </ResourceState>
      </Panel>

      <Panel title={`Tools${tools.items.length ? ` · ${tools.items.length}` : ""}`}>
        <ResourceState status={tools.status} error={tools.error} empty={tools.items.length === 0} noun="tools" onRetry={tools.reload}>
          <ul className="shell-list" aria-label="Tools">
            {tools.items.map((t) => (
              <li key={t.name} className="shell-card__row">
                <span><strong>{t.displayName}</strong><span className="shell-card__meta"> {t.description}</span></span>
                <span>
                  {t.requiresConfirmation && <Badge tone="warning">Needs approval</Badge>}{" "}
                  <Badge tone={t.riskLevel === "high" ? "danger" : "neutral"}>{t.riskLevel}</Badge>
                </span>
              </li>
            ))}
          </ul>
        </ResourceState>
      </Panel>
    </PageFrame>
  );
}
