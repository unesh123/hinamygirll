import { useMemo } from "react";
import { GlowOrb, Panel, StatTile } from "../../design-system/hud";
import { groupMemory, useMemoryItems, type MemoryGroup, type MemoryItem } from "../data";
import { PageFrame, ResourceState } from "../ui";

const GROUPS: { id: MemoryGroup; title: string; empty: string }[] = [
  { id: "about", title: "About me", empty: "Nothing remembered about you yet." },
  { id: "projects", title: "Projects", empty: "No project memories yet." },
  { id: "preferences", title: "Preferences", empty: "No preferences saved yet." },
];

function MemoryNode({ item }: { item: MemoryItem }) {
  return (
    <li className="shell-card">
      <span>{item.content}</span>
      <span className="shell-card__meta">{item.type} · {Math.round(item.confidence * 100)}% confidence</span>
    </li>
  );
}

export default function MemoryPage() {
  const memory = useMemoryItems();
  const grouped = useMemo(() => groupMemory(memory.items), [memory.items]);

  return (
    <PageFrame title="Real Memory" subtitle="What Hina has actually stored, grouped by what it is about.">
      <div className="shell-memory-core">
        <GlowOrb size={120} state={memory.status === "loading" ? "thinking" : "idle"} label="Memory core" />
        <div className="shell-stats">
          <StatTile label="Memories" value={memory.items.length} />
          {GROUPS.map((g) => <StatTile key={g.id} label={g.title} value={grouped[g.id].length} />)}
        </div>
      </div>
      <ResourceState status={memory.status} error={memory.error} noun="memories" onRetry={memory.reload}>
        <div className="shell-columns">
          {GROUPS.map((g) => (
            <Panel key={g.id} title={g.title} aria-label={g.title}>
              {grouped[g.id].length === 0 ? (
                <p className="shell-state" data-kind="empty">{g.empty}</p>
              ) : (
                <ul className="shell-list">{grouped[g.id].map((item) => <MemoryNode key={item.id} item={item} />)}</ul>
              )}
            </Panel>
          ))}
        </div>
      </ResourceState>
    </PageFrame>
  );
}
