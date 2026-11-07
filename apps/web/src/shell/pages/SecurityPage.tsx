import { SecurityCenterPanel } from "../../components/security/SecurityCenterPanel";
import { PageFrame } from "../ui";

export default function SecurityPage() {
  return (
    <PageFrame title="Security" subtitle="Posture, permissions, approvals and the audit trail.">
      <div className="shell-legacy-surface"><SecurityCenterPanel /></div>
    </PageFrame>
  );
}
