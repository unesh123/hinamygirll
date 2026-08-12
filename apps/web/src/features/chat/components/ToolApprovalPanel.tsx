import { Check, Loader2, ShieldAlert, X } from "lucide-react";
import type { AssistantTurnPlan } from "../../../contracts/assistantTurnPlan";

interface ToolActivity {
  id: string;
  status: string;
  label: string;
}

interface ToolApprovalPanelProps {
  messageId: string;
  requests: AssistantTurnPlan["toolRequests"];
  activity?: ToolActivity[];
  onResolve: (
    messageId: string,
    request: AssistantTurnPlan["toolRequests"][number],
    approved: boolean,
  ) => void | Promise<void>;
}

function summary(request: AssistantTurnPlan["toolRequests"][number]): string {
  const values = Object.entries(request.parameters || {})
    .filter(([, value]) => typeof value === "string" || typeof value === "number")
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${String(value)}`);
  return values.length ? values.join(" · ") : "Review the proposed action before continuing.";
}

export function ToolApprovalPanel({ messageId, requests, activity = [], onResolve }: ToolApprovalPanelProps) {
  if (!requests.length) return null;

  return (
    <section aria-label="Proposed agent actions" style={{ display: "grid", gap: 8, marginTop: 10 }}>
      {requests.map((request, index) => {
        const state = activity.find((item) => item.id === request.toolName);
        const pending = !state || state.status === "pending";
        const running = state?.status === "running";
        const complete = state?.status === "complete";
        const declined = state?.status === "cancelled";
        const failed = state?.status === "error";
        const tone = complete ? "#34d399" : declined ? "#94a3b8" : failed ? "#fda4af" : "#fbbf24";

        return (
          <div key={`${request.toolName}-${index}`} style={{ border: `1px solid ${tone}44`, borderRadius: 10, background: "rgba(15,23,42,.58)", padding: "10px 11px" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
              <span style={{ display: "grid", placeItems: "center", width: 25, height: 25, flexShrink: 0, borderRadius: 8, color: tone, background: `${tone}1a` }}>
                {running ? <Loader2 size={14} className="spin" /> : complete ? <Check size={14} /> : <ShieldAlert size={14} />}
              </span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <strong style={{ display: "block", color: "#f8fafc", fontSize: 12 }}>Approval required · {request.toolName}</strong>
                <span style={{ display: "block", marginTop: 3, overflow: "hidden", color: "#94a3b8", fontSize: 11, lineHeight: 1.4, textOverflow: "ellipsis" }}>{state?.label || summary(request)}</span>
              </div>
            </div>
            {pending && (
              <div style={{ display: "flex", gap: 7, marginTop: 9, paddingLeft: 33 }}>
                <button type="button" onClick={() => void onResolve(messageId, request, true)} style={{ ...buttonStyle, color: "#052e2b", background: "linear-gradient(135deg,#5eead4,#7dd3fc)", border: 0 }}>Allow once</button>
                <button type="button" onClick={() => void onResolve(messageId, request, false)} style={{ ...buttonStyle, color: "#cbd5e1", background: "transparent", border: "1px solid rgba(148,163,184,.30)" }}><X size={12} /> Decline</button>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}

const buttonStyle = { display: "inline-flex", alignItems: "center", gap: 5, borderRadius: 7, padding: "6px 9px", cursor: "pointer", fontSize: 11, fontWeight: 800 } as const;
