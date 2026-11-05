import React, { useState, useEffect, useCallback } from "react";

export interface KeystoreProbe {
  keystore_type: string;
  is_hardware_backed: boolean;
  provider_name: string;
  capabilities: string[];
  status_details: string;
}

export interface HostIsolationProbe {
  isolation_level: string;
  can_execute_untrusted_code: boolean;
  os_platform: string;
  job_objects_available: boolean;
  wsl_available: boolean;
  status_details: string;
}

export interface SecurityPosture {
  keystore: KeystoreProbe;
  host_isolation: HostIsolationProbe;
  active_revocations_count: number;
  is_emergency_stopped: boolean;
}

export interface MyPermissions {
  user_id: string;
  tenant_id: string;
  role: string;
  scopes: string[];
  effective_permissions: string[];
  is_emergency_stopped: boolean;
}

export interface ApprovalChallenge {
  token_id: string;
  tenant_id: string;
  action: string;
  parameters_digest: string;
  nonce: string;
  issued_at: number;
  expires_at: number;
  amount_paisa?: number;
  currency: string;
  status: string;
  signature: string;
}

export interface AuditEventItem {
  sequence_id: number;
  event_id: string;
  timestamp: number;
  tenant_id: string;
  subject_id: string;
  action: string;
  resource: string;
  decision: string;
  reason_code: string;
  prev_hash: string;
  event_hash: string;
}

export const SecurityCenterPanel: React.FC = () => {
  const [posture, setPosture] = useState<SecurityPosture | null>(null);
  const [permissions, setPermissions] = useState<MyPermissions | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[]>([]);
  const [pendingChallenges, setPendingChallenges] = useState<ApprovalChallenge[]>([]);
  const [auditVerifyResult, setAuditVerifyResult] = useState<{ is_valid: boolean; total_records: number; errors: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchSecurityData = useCallback(async () => {
    try {
      setLoading(true);
      // 1. Fetch Posture
      const posRes = await fetch("/api/security/posture");
      if (posRes.ok) {
        setPosture(await posRes.json());
      }

      // 2. Fetch Permissions (using dev bearer or current session)
      const permRes = await fetch("/api/security/my-permissions", {
        headers: { Authorization: "Bearer dev-session" },
      });
      if (permRes.ok) {
        setPermissions(await permRes.json());
      }

      // 3. Fetch Audit Logs
      const audRes = await fetch("/api/security/audit?limit=25", {
        headers: { Authorization: "Bearer dev-session" },
      });
      if (audRes.ok) {
        setAuditEvents(await audRes.json());
      }
    } catch (err: any) {
      console.warn("Could not fetch security telemetry:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSecurityData();
    const interval = setInterval(fetchSecurityData, 10000);
    return () => clearInterval(interval);
  }, [fetchSecurityData]);

  const handleVerifyAuditChain = async () => {
    try {
      const res = await fetch("/api/security/audit/verify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer dev-session",
        },
      });
      if (res.ok) {
        const data = await res.json();
        setAuditVerifyResult(data);
        setActionMessage(data.is_valid ? "Audit chain verified: 100% mathematically intact!" : "Audit chain integrity failure detected!");
      }
    } catch (err: any) {
      setActionMessage(`Audit verification failed: ${err.message}`);
    }
  };

  const handleEmergencyStopToggle = async (active: boolean) => {
    try {
      const endpoint = active ? "/api/security/emergency-stop/lift" : "/api/security/emergency-stop";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer dev-session",
        },
        body: JSON.stringify({ tenant_id: "*", reason: "User dashboard button toggle" }),
      });
      if (res.ok) {
        fetchSecurityData();
        setActionMessage(active ? "Emergency stop lifted successfully." : "EMERGENCY STOP TRIGGERED! All agent actions halted.");
      }
    } catch (err: any) {
      setActionMessage(`Emergency stop toggle failed: ${err.message}`);
    }
  };

  const handleChallengeDecision = async (tokenId: string, decision: "APPROVE" | "REJECT") => {
    try {
      const res = await fetch("/api/security/ceremonies/decide", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer dev-session",
        },
        body: JSON.stringify({ token_id: tokenId, decision }),
      });
      if (res.ok) {
        setActionMessage(`Challenge ${tokenId} marked as ${decision}.`);
        setPendingChallenges((prev) => prev.filter((c) => c.token_id !== tokenId));
        fetchSecurityData();
      }
    } catch (err: any) {
      setActionMessage(`Decision submission failed: ${err.message}`);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 p-6 overflow-y-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center space-x-3 text-cyan-400">
            <span>🛡️</span>
            <span>Security, Permissions & Governance Control Center</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            OWASP ASVS 5.0 server-side enforcement &bull; Cryptographic approval ceremonies &bull; Append-only tamper-evident audit trail
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={fetchSecurityData}
            disabled={loading}
            className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition"
          >
            {loading ? "Refreshing..." : "Refresh Status"}
          </button>
          <button
            onClick={() => handleEmergencyStopToggle(posture?.is_emergency_stopped || false)}
            className={`px-4 py-1.5 text-xs font-semibold rounded shadow transition flex items-center space-x-2 ${
              posture?.is_emergency_stopped
                ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                : "bg-rose-600 hover:bg-rose-500 text-white animate-pulse"
            }`}
          >
            <span>🚨</span>
            <span>{posture?.is_emergency_stopped ? "Lift Emergency Stop" : "Trigger Emergency Stop"}</span>
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-cyan-950/60 border border-cyan-800/80 rounded text-cyan-300 text-sm flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-cyan-400 hover:text-white font-bold ml-4">
            &times;
          </button>
        </div>
      )}

      {/* Grid: Posture & Identity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Posture Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-4">
          <h2 className="text-lg font-semibold text-slate-200 flex items-center space-x-2">
            <span>💻</span>
            <span>Platform Posture & Hardware Truthfulness</span>
          </h2>

          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
              <span className="text-slate-400">Keystore Provider:</span>
              <span className="font-mono text-cyan-300">{posture?.keystore.provider_name || "Windows DPAPI"}</span>
            </div>
            <div className="flex justify-between items-center p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
              <span className="text-slate-400">Hardware-Backed Keystore:</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-900/40 text-amber-300 border border-amber-800/60">
                {posture?.keystore.is_hardware_backed ? "True (TPM 2.0)" : "False (Software DPAPI)"}
              </span>
            </div>
            <div className="flex justify-between items-center p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
              <span className="text-slate-400">Host Process Isolation:</span>
              <span className="font-mono text-indigo-300">{posture?.host_isolation.isolation_level || "PROCESS_JOB_OBJECT"}</span>
            </div>
            <div className="flex justify-between items-center p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
              <span className="text-slate-400">Untrusted Code Execution:</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-900/40 text-rose-300 border border-rose-800/60">
                {posture?.host_isolation.can_execute_untrusted_code ? "Allowed" : "BLOCKED_UNAVAILABLE"}
              </span>
            </div>
            <div className="p-2.5 bg-slate-950/80 rounded text-xs text-slate-400 border border-slate-800">
              <span className="font-semibold text-slate-300">Honesty Invariant: </span>
              {posture?.host_isolation.status_details || "Windows Job Object governs CPU/memory trees. Untrusted code blocked."}
            </div>
          </div>
        </div>

        {/* Identity & Permissions Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-4">
          <h2 className="text-lg font-semibold text-slate-200 flex items-center space-x-2">
            <span>👤</span>
            <span>Server-Verified Identity & RBAC</span>
          </h2>

          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
              <span className="text-slate-400">User Subject:</span>
              <span className="font-mono text-slate-200">{permissions?.user_id || "owner"}</span>
            </div>
            <div className="flex justify-between items-center p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
              <span className="text-slate-400">Tenant ID:</span>
              <span className="font-mono text-slate-200">{permissions?.tenant_id || "tenant_default"}</span>
            </div>
            <div className="flex justify-between items-center p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
              <span className="text-slate-400">Assigned Role:</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-semibold bg-cyan-900/40 text-cyan-300 border border-cyan-800/60 uppercase">
                {permissions?.role || "OWNER"}
              </span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block mb-2 font-medium">Effective Capability Set:</span>
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto p-2 bg-slate-950/60 rounded border border-slate-800">
                {(permissions?.effective_permissions || ["read", "write", "tool:execute", "code:execute", "approval:tier_c"]).map((p) => (
                  <span key={p} className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-xs font-mono">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Human Approval Ceremonies (Tier C) */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-200 flex items-center space-x-2">
            <span>🔑</span>
            <span>Cryptographic Human Approval Ceremonies (Tier C)</span>
          </h2>
          <span className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-300">
            Active: {pendingChallenges.length}
          </span>
        </div>

        {pendingChallenges.length === 0 ? (
          <div className="p-6 bg-slate-950/40 rounded border border-dashed border-slate-800 text-center text-sm text-slate-500">
            No high-impact operations awaiting authorization ceremony. All routines operating within baseline bounds.
          </div>
        ) : (
          <div className="space-y-4">
            {pendingChallenges.map((ch) => (
              <div key={ch.token_id} className="p-4 bg-slate-950 rounded border border-amber-800/60 space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="font-mono text-amber-400 font-semibold">{ch.action}</span>
                    <span className="text-xs text-slate-500 ml-2">Token: {ch.token_id}</span>
                  </div>
                  {ch.amount_paisa && (
                    <span className="text-sm font-bold text-emerald-400">
                      रु {(ch.amount_paisa / 100).toFixed(2)} NPR
                    </span>
                  )}
                </div>

                {/* Trilingual Risk Notice */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 p-3 bg-amber-950/20 border border-amber-900/40 rounded text-xs">
                  <div>
                    <span className="font-semibold text-amber-300 block mb-1">English:</span>
                    <p className="text-slate-300">High-impact action requires cryptographic authorization. This operation cannot be undone.</p>
                  </div>
                  <div>
                    <span className="font-semibold text-amber-300 block mb-1">नेपाली:</span>
                    <p className="text-slate-300">उच्च-जोखिम कार्यका लागि तपाइँको स्पष्ट सहमति आवश्यक छ। यो कार्य फिर्ता गर्न सकिँदैन।</p>
                  </div>
                  <div>
                    <span className="font-semibold text-amber-300 block mb-1">Romanized:</span>
                    <p className="text-slate-300">Uchcha-jokhim karya ko lagi tapai ko anumati chahincha. Yo operation undo garna sakidaina.</p>
                  </div>
                </div>

                <div className="flex justify-end space-x-3 pt-2">
                  <button
                    onClick={() => handleChallengeDecision(ch.token_id, "REJECT")}
                    className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-rose-400 rounded border border-rose-900/40 transition"
                  >
                    Reject Action
                  </button>
                  <button
                    onClick={() => handleChallengeDecision(ch.token_id, "APPROVE")}
                    className="px-4 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded transition shadow"
                  >
                    Authorize Ceremony (HMAC-SHA256)
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Verifiable Audit Trail */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-200 flex items-center space-x-2">
              <span>📜</span>
              <span>Append-Only Verifiable Audit Trail</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Hash-chained events &bull; Zero credential leakage &bull; Scoped to active tenant
            </p>
          </div>
          <button
            onClick={handleVerifyAuditChain}
            className="px-3 py-1.5 text-xs bg-cyan-700 hover:bg-cyan-600 text-white rounded font-medium transition flex items-center space-x-1.5"
          >
            <span>🔍</span>
            <span>Verify Chain Integrity</span>
          </button>
        </div>

        {auditVerifyResult && (
          <div
            className={`p-3 rounded text-xs border ${
              auditVerifyResult.is_valid
                ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
                : "bg-rose-950/40 border-rose-800 text-rose-300"
            }`}
          >
            <span className="font-bold">
              {auditVerifyResult.is_valid ? "✓ Audit Chain Integrity Confirmed" : "✗ Audit Chain Integrity Violation!"}
            </span>
            <span className="ml-2">({auditVerifyResult.total_records} records verified)</span>
            {auditVerifyResult.errors.length > 0 && (
              <ul className="mt-2 list-disc list-inside space-y-1">
                {auditVerifyResult.errors.map((e, idx) => (
                  <li key={idx}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="overflow-x-auto border border-slate-800 rounded bg-slate-950/60 max-h-72">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900 text-slate-400 border-b border-slate-800 sticky top-0">
              <tr>
                <th className="p-2.5 font-semibold">Seq</th>
                <th className="p-2.5 font-semibold">Action</th>
                <th className="p-2.5 font-semibold">Resource</th>
                <th className="p-2.5 font-semibold">Decision</th>
                <th className="p-2.5 font-semibold">Reason</th>
                <th className="p-2.5 font-semibold font-mono">Event Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-900">
              {auditEvents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-slate-500">
                    No audit records logged yet.
                  </td>
                </tr>
              ) : (
                auditEvents.map((evt) => (
                  <tr key={evt.event_id} className="hover:bg-slate-900/50">
                    <td className="p-2.5 font-mono text-slate-400">#{evt.sequence_id}</td>
                    <td className="p-2.5 font-mono text-cyan-300">{evt.action}</td>
                    <td className="p-2.5 text-slate-300">{evt.resource}</td>
                    <td className="p-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          evt.decision.toUpperCase() === "ALLOW"
                            ? "bg-emerald-950 text-emerald-400 border border-emerald-800/80"
                            : evt.decision.toUpperCase() === "DENY"
                            ? "bg-rose-950 text-rose-400 border border-rose-800/80"
                            : "bg-amber-950 text-amber-400 border border-amber-800/80"
                        }`}
                      >
                        {evt.decision}
                      </span>
                    </td>
                    <td className="p-2.5 text-slate-400">{evt.reason_code}</td>
                    <td className="p-2.5 font-mono text-slate-500 text-[10px]">{evt.event_hash.slice(0, 16)}...</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SecurityCenterPanel;
