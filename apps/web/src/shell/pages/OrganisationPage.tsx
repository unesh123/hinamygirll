import { Badge } from "../../design-system/hud";
import { ApiKeysPanel } from "../organisation/ApiKeysPanel";
import { AuditPanel } from "../organisation/AuditPanel";
import { MembersPanel } from "../organisation/MembersPanel";
import { ORG_BASE, can, type OrgMe } from "../organisation/api";
import { PageFrame, ResourceState } from "../ui";
import { useApiJson } from "../useApi";

export default function OrganisationPage() {
  const me = useApiJson<OrgMe>(`${ORG_BASE}/me`);
  return (
    <PageFrame title="Organisation" subtitle="Members, roles, API keys and the tamper-evident audit log.">
      <ResourceState status={me.status} error={me.error} noun="organisation" onRetry={me.reload}>
        {me.data && (
          <>
            <p className="org-summary">
              <strong>{me.data.org?.name ?? "Organisation"}</strong>
              <Badge tone="accent">{me.data.role}</Badge>
              {me.data.org?.isPersonal && <Badge tone="neutral">personal</Badge>}
            </p>
            <MembersPanel me={me.data} />
            {can(me.data, "apikeys:manage") && <ApiKeysPanel me={me.data} />}
            {can(me.data, "audit:read") && <AuditPanel />}
          </>
        )}
      </ResourceState>
    </PageFrame>
  );
}
