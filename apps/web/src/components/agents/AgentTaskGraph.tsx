import React from "react";

export type AgentRole =
  | "supervisor"
  | "planner"
  | "researcher"
  | "engineer"
  | "qa"
  | "browser_operator"
  | "creative_operator"
  | "knowledge_curator"
  | "localization_specialist"
  | "security_reviewer";

export type TaskStatus =
  | "CREATED"
  | "PLANNING"
  | "READY"
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "RETRYING"
  | "RECOVERING"
  | "VERIFYING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "CANCELLED"
  | "TIMED_OUT"
  | "BLOCKED";

export interface TaskNodeData {
  node_id: string;
  task_id: string;
  title: string;
  specialist_role: AgentRole;
  dependencies: string[];
  allowed_tools: string[];
  permission_tier: string;
  status: TaskStatus;
  result_data?: Record<string, unknown> | null;
  error?: string | null;
  attempts: number;
}

interface AgentTaskGraphProps {
  nodes: TaskNodeData[];
  activeNodeId?: string | null;
  onSelectNode?: (node: TaskNodeData) => void;
}

export const AgentTaskGraph: React.FC<AgentTaskGraphProps> = ({
  nodes,
  activeNodeId,
  onSelectNode,
}) => {
  const getStatusBadge = (status: TaskStatus) => {
    switch (status) {
      case "COMPLETED":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
      case "RUNNING":
        return "bg-cyan-500/20 text-cyan-400 border-cyan-500/40 animate-pulse";
      case "WAITING_APPROVAL":
        return "bg-amber-500/20 text-amber-400 border-amber-500/40";
      case "FAILED":
        return "bg-rose-500/20 text-rose-400 border-rose-500/40";
      case "RETRYING":
      case "RECOVERING":
        return "bg-purple-500/20 text-purple-400 border-purple-500/40";
      default:
        return "bg-slate-700/40 text-slate-400 border-slate-600/40";
    }
  };

  const getRoleIcon = (role: AgentRole) => {
    switch (role) {
      case "supervisor":
        return "👑";
      case "planner":
        return "🗺️";
      case "researcher":
        return "🔍";
      case "engineer":
        return "⚡";
      case "qa":
        return "🛡️";
      case "browser_operator":
        return "🌐";
      case "creative_operator":
        return "🎨";
      case "knowledge_curator":
        return "🧠";
      case "localization_specialist":
        return "🇳🇵";
      case "security_reviewer":
        return "🔒";
      default:
        return "🤖";
    }
  };

  return (
    <div className="flex flex-col gap-3 p-4 bg-slate-900/60 rounded-xl border border-slate-800">
      <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
        <span className="font-semibold uppercase tracking-wider text-slate-300">
          Directed Acyclic Task Graph (DAG)
        </span>
        <span className="text-slate-500">{nodes.length} nodes scheduled</span>
      </div>

      <div className="flex flex-col gap-2 relative">
        {nodes.map((node, index) => {
          const isActive = activeNodeId === node.node_id;
          return (
            <div
              key={node.node_id}
              onClick={() => onSelectNode && onSelectNode(node)}
              className={`p-3 rounded-lg border transition-all cursor-pointer flex flex-col gap-2 ${
                isActive
                  ? "border-cyan-500/80 bg-slate-800/80 shadow-lg shadow-cyan-500/10"
                  : "border-slate-800/80 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-800/40"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">{getRoleIcon(node.specialist_role)}</span>
                  <span className="font-medium text-sm text-slate-200">
                    {index + 1}. {node.title}
                  </span>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-mono border ${getStatusBadge(
                    node.status
                  )}`}
                >
                  {node.status}
                </span>
              </div>

              <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                <span className="text-slate-500">role:</span>
                <span className="text-cyan-300">{node.specialist_role}</span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-500">tier:</span>
                <span className="text-slate-300">{node.permission_tier}</span>
                {node.dependencies.length > 0 && (
                  <>
                    <span className="text-slate-600">•</span>
                    <span className="text-slate-500">deps:</span>
                    <span className="text-amber-400">
                      {node.dependencies.map((d) => d.slice(-6)).join(", ")}
                    </span>
                  </>
                )}
              </div>

              {node.error && (
                <div className="text-xs text-rose-400 bg-rose-950/40 border border-rose-800/40 rounded p-1.5 mt-1 font-mono">
                  ⚠ {node.error}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
