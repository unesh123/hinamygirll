import { AutopilotDashboard } from "../../components/autopilot/AutopilotDashboard";
import { PageFrame } from "../ui";

export default function AutopilotPage() {
  return (
    <PageFrame title="Autopilot" subtitle="Scheduled jobs, notifications and runtime health.">
      <div className="shell-legacy-surface"><AutopilotDashboard /></div>
    </PageFrame>
  );
}
