import { Badge, Panel } from "../../design-system/hud";
import { useApiJson } from "../useApi";
import { ResourceState } from "../ui";
import { NEWS_BASE, formatWhen, hostOf, type Digest, type List } from "./api";

export function DigestsPanel({ reloadKey }: { reloadKey: number }) {
  // The key changes the URL so a finished run refetches without lifting state.
  const digests = useApiJson<List<Digest>>(`${NEWS_BASE}/digests?limit=10&r=${reloadKey}`);
  const items = digests.data?.items ?? [];
  return (
    <Panel title="Latest digests">
      <ResourceState status={digests.status} error={digests.error} empty={items.length === 0} noun="digests" onRetry={digests.reload}>
        <div className="news-digests">
          {items.map((d) => (
            <article key={d.id} className="shell-card" aria-label={d.title}>
              <div className="shell-card__row">
                <strong>{d.title}</strong>
                <Badge tone={d.generatedBy === "llm" ? "accent" : "neutral"}>{d.generatedBy === "llm" ? "AI summary" : "Extractive"}</Badge>
              </div>
              <span className="shell-card__meta">{formatWhen(d.createdAt)} · {d.articleCount} stories</span>
              <ul className="news-bullets">
                {d.items.map((item, i) => (
                  <li key={i}>
                    <span>{item.text}</span>{" "}
                    {item.urls.map((u) => (
                      <a key={u} className="news-link" href={u} target="_blank" rel="noopener noreferrer">{hostOf(u)}</a>
                    ))}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </ResourceState>
    </Panel>
  );
}
