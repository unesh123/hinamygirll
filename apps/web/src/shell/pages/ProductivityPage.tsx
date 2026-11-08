import { PageFrame } from "../ui";
import { ContentPanel } from "../productivity/ContentPanel";
import { ProjectsPanel } from "../productivity/ProjectsPanel";
import { SalesPanel } from "../productivity/SalesPanel";

export default function ProductivityPage() {
  return (
    <PageFrame title="Productivity" subtitle="Content calendar, sales and projects — ask Hina to plan, log or update any of it.">
      <ContentPanel />
      <div className="prod-split">
        <SalesPanel />
        <ProjectsPanel />
      </div>
    </PageFrame>
  );
}
