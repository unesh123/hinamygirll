import { useState } from "react";
import { PageFrame } from "../ui";
import { DigestsPanel } from "../news/DigestsPanel";
import { SocialPanel } from "../news/SocialPanel";
import { WatchlistsPanel } from "../news/WatchlistsPanel";

export default function NewsPage() {
  const [reloadKey, setReloadKey] = useState(0);
  return (
    <PageFrame title="News" subtitle="Watch topics and feeds; every digest point links to the source it was read from.">
      <WatchlistsPanel onRan={() => setReloadKey((n) => n + 1)} />
      <DigestsPanel reloadKey={reloadKey} />
      <SocialPanel />
    </PageFrame>
  );
}
