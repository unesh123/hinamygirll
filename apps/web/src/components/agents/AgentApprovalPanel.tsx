import React, { useState } from "react";

export interface ApprovalRequestData {
  approval_id: string;
  task_id: string;
  node_id: string;
  action: string;
  argument_digest: string;
  amount_paisa: number;
  currency: string;
  expires_at: string;
  nonce: string;
  team_id?: string | null;
  ancestry?: string[];
}

interface AgentApprovalPanelProps {
  request: ApprovalRequestData;
  onApprove: (approvalId: string, signature: string) => Promise<void>;
  onReject: (approvalId: string) => Promise<void>;
}

export const AgentApprovalPanel: React.FC<AgentApprovalPanelProps> = ({
  request,
  onApprove,
  onReject,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nprAmount = (request.amount_paisa / 100).toFixed(2);

  const handleApprove = async () => {
    setLoading(true);
    setError(null);
    try {
      // Client-side signed approval token
      const mockSignature = `sig_${request.approval_id}_${Date.now()}`;
      await onApprove(request.approval_id, mockSignature);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to approve action");
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    try {
      await onReject(request.approval_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reject action");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-slate-900 border border-amber-500/50 rounded-2xl p-6 shadow-2xl flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center text-xl font-bold border border-amber-500/30">
            🛡️
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-100">
              Tier C Action Approval Required
            </h3>
            <p className="text-xs text-slate-400">
              Autonomous agent paused waiting for explicit human authorization.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-2.5 text-xs font-mono bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
          <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
            <span className="text-slate-500">Action:</span>
            <span className="text-amber-300 font-semibold">{request.action}</span>
          </div>

          <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
            <span className="text-slate-500">Node ID:</span>
            <span className="text-slate-300">{request.node_id}</span>
          </div>

          {request.team_id && (
            <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
              <span className="text-slate-500">Team:</span>
              <span className="text-cyan-300">{request.team_id}</span>
            </div>
          )}

          {request.ancestry && request.ancestry.length > 0 && (
            <div className="flex flex-col gap-1 py-1 border-b border-slate-800/60">
              <span className="text-slate-500">Ancestry Chain:</span>
              <span className="text-purple-300 text-[11px] break-all">
                {request.ancestry.join(" ➔ ")}
              </span>
            </div>
          )}

          <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
            <span className="text-slate-500">Argument Digest:</span>
            <span className="text-slate-400 text-[11px] truncate max-w-[240px]">
              {request.argument_digest}
            </span>
          </div>

          <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
            <span className="text-slate-500">Cost / Authorization:</span>
            <span className="text-emerald-400 font-bold text-sm">
              NPR {nprAmount} ({request.amount_paisa} paisa)
            </span>
          </div>

          <div className="flex justify-between items-center py-1">
            <span className="text-slate-500">Token Nonce:</span>
            <span className="text-slate-400 text-[11px]">{request.nonce.slice(0, 16)}...</span>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={handleReject}
            disabled={loading}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition disabled:opacity-50"
          >
            Deny & Abort
          </button>
          <button
            onClick={handleApprove}
            disabled={loading}
            className="px-5 py-2 rounded-xl text-xs font-semibold text-slate-950 bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 shadow-lg shadow-amber-500/20 transition disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? "Signing Token..." : "Sign & Authorize (Tier C)"}
          </button>
        </div>
      </div>
    </div>
  );
};
