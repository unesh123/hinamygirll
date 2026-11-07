import { X } from "lucide-react";
import { Badge, Button } from "../design-system/hud";
import { groupMemory, useConnectors, useMemoryItems, useTools } from "./data";
import { shell, useShell, type InspectorTab } from "./store";
import { ResourceState } from "./ui";

const TABS: { id: InspectorTab; label: string }[] = [
  { id: "plan", label: "Plan" },
  { id: "tools", label: "Tools" },
  { id: "memory", label: "Memory" },
  { id: "integrations", label: "Integrations" },
];

function stepTone(status: string): "success" | "danger" | "accent" | "neutral" {
  if (status === "done" || status === "complete" || status === "completed") return "success";
  if (status === "error" || status === "failed") return "danger";
  if (status === "running" || status === "active") return "accent";
  return "neutral";
}

function PlanTab() {
  const steps = useShell((s) => s.agent.steps);
  const state = useShell((s) => s.agent.state);
  if (steps.length === 0) {
    return <p className="shell-state" data-kind="empty">No run in progress. Agent steps appear here as Hina plans and acts{state !== "idle" ? ` (${state}…)` : ""}.</p>;
  }
  return (
    <ol className="shell-timeline" aria-label="Run timeline">
      {steps.map((step) => (
        <li key={step.id} className="shell-timeline__item">
          <span>{step.label}</span>
          <Badge tone={stepTone(step.status)} dot>{step.status}</Badge>
        </li>
      ))}
    </ol>
  );
}

function ToolsTab() {
  const tools = useTools();
  return (
    <ResourceState status={tools.status} error={tools.error} empty={tools.items.length === 0} noun="tools" onRetry={tools.reload}>
      <ul className="shell-list">
        {tools.items.slice(0, 30).map((t) => (
          <li key={t.name} className="shell-card__row">
            <span>{t.displayName}</span>
            <Badge tone={t.requiresConfirmation ? "warning" : "neutral"}>{t.requiresConfirmation ? "approval" : t.riskLevel}</Badge>
          </li>
        ))}
      </ul>
    </ResourceState>
  );
}

function MemoryTab() {
  const memory = useMemoryItems(30);
  const grouped = groupMemory(memory.items);
  return (
    <ResourceState status={memory.status} error={memory.error} empty={memory.items.length === 0} noun="memories" onRetry={memory.reload}>
      {(["about", "projects", "preferences"] as const).map((g) => (
        <section key={g} aria-label={g}>
          <h3 className="shell-inspector__h">{g === "about" ? "About me" : g === "projects" ? "Projects" : "Preferences"}</h3>
          <ul className="shell-list">
            {grouped[g].slice(0, 5).map((m) => <li key={m.id} className="shell-card">{m.content}</li>)}
            {grouped[g].length === 0 && <li className="shell-card__meta">Nothing yet</li>}
          </ul>
        </section>
      ))}
    </ResourceState>
  );
}

function IntegrationsTab() {
  const connectors = useConnectors();
  return (
    <ResourceState status={connectors.status} error={connectors.error} empty={connectors.items.length === 0} noun="connectors" onRetry={connectors.reload}>
      <ul className="shell-list">
        {connectors.items.map((c) => (
          <li key={c.id} className="shell-card__row">
            <span>{c.name}</span>
            <Badge tone={c.configured ? "success" : "neutral"} dot>{c.configured ? "On" : "Off"}</Badge>
          </li>
        ))}
      </ul>
    </ResourceState>
  );
}

export function Inspector() {
  const open = useShell((s) => s.inspectorOpen);
  const tab = useShell((s) => s.inspectorTab);
  if (!open) return null;
  return (
    <aside className="shell-inspector" aria-label="Inspector">
      <div className="shell-inspector__head">
        <div role="tablist" aria-label="Inspector sections" className="shell-tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              id={`inspector-tab-${t.id}`}
              role="tab"
              type="button"
              aria-selected={tab === t.id}
              aria-controls="inspector-panel"
              tabIndex={tab === t.id ? 0 : -1}
              className="shell-tabs__tab ds-focusable"
              onClick={() => shell.setInspector(true, t.id)}
              onKeyDown={(e) => {
                const i = TABS.findIndex((x) => x.id === tab);
                if (e.key === "ArrowRight") shell.setInspector(true, TABS[(i + 1) % TABS.length].id);
                if (e.key === "ArrowLeft") shell.setInspector(true, TABS[(i + TABS.length - 1) % TABS.length].id);
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Button variant="ghost" icon aria-label="Close inspector" onClick={() => shell.setInspector(false)}><X size={16} aria-hidden="true" /></Button>
      </div>
      <div id="inspector-panel" role="tabpanel" aria-labelledby={`inspector-tab-${tab}`} className="shell-inspector__body">
        {tab === "plan" && <PlanTab />}
        {tab === "tools" && <ToolsTab />}
        {tab === "memory" && <MemoryTab />}
        {tab === "integrations" && <IntegrationsTab />}
      </div>
    </aside>
  );
}
