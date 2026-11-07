import { GoalsDashboard } from "../../components/goals/GoalsDashboard";
import { PageFrame } from "../ui";

export default function GoalsPage() {
  return (
    <PageFrame title="Goals" subtitle="Plans, milestones and evidence for long-running objectives.">
      <div className="shell-legacy-surface"><GoalsDashboard /></div>
    </PageFrame>
  );
}
