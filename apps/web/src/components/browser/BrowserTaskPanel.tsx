import React, { useState } from "react";
import {
  Globe,
  ShieldCheck,
  ShieldAlert,
  StopCircle,
  RefreshCw,
  ExternalLink,
  Layers,
  AlertTriangle,
  Check,
  X,
} from "lucide-react";
import { BrowserActionTimeline, BrowserActionItem } from "./BrowserActionTimeline";

export interface TabData {
  tab_id: string;
  url: string;
  title: string;
  origin: string;
  is_active: boolean;
}

export interface ApprovalRequestData {
  approval_id: string;
  task_id: string;
  action_type: string;
  target_origin: string;
  destination_url: string;
  summary: string;
  proposed_payload: Record<string, any>;
  risk_level: "HIGH" | "CRITICAL";
}

export interface BrowserTaskPanelProps {
  taskId: string;
  objective: string;
  state: "CREATED" | "RUNNING" | "WAITING_FOR_USER" | "COMPLETED" | "FAILED" | "CANCELLED";
  currentUrl?: string;
  tabs?: TabData[];
  actions?: BrowserActionItem[];
  pendingApproval?: ApprovalRequestData | null;
  onCancelTask?: (taskId: string) => void;
  onApproveAction?: (taskId: string, approvalId: string, token: string) => void;
  onDenyAction?: (taskId: string, approvalId: string) => void;
  onSwitchTab?: (tabId: string) => void;
}

export function BrowserTaskPanel({
  taskId,
  objective,
  state,
  currentUrl,
  tabs = [],
  actions = [],
  pendingApproval = null,
  onCancelTask,
  onApproveAction,
  onDenyAction,
  onSwitchTab,
}: BrowserTaskPanelProps) {
  const isRunning = state === "RUNNING";
  const isWaiting = state === "WAITING_FOR_USER";
  const isCompleted = state === "COMPLETED";
  const isFailed = state === "FAILED";
  const isCancelled = state === "CANCELLED";

  const stateBadgeClass = isRunning
    ? "bg-blue-500/10 text-blue-600 border-blue-500/20 animate-pulse"
    : isWaiting
    ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
    : isCompleted
    ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
    : isFailed
    ? "bg-rose-500/10 text-rose-600 border-rose-500/20"
    : "bg-slate-500/10 text-slate-600 border-slate-500/20";

  return (
    <div
      className="p-3 bg-frost/90 backdrop-blur-sm border border-glass-border rounded-xl shadow-xs text-xs font-sans flex flex-col gap-3 min-w-0"
      role="region"
      aria-label="Browser Task Execution Panel"
    >
      {/* ── Top Bar: Task Objective & Global Controls ── */}
      <div className="flex items-center justify-between gap-2 min-w-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <Globe size={14} className="text-brand-600 flex-shrink-0" />
          <div className="flex flex-col min-w-0">
            <span className="font-semibold text-text-primary truncate">{objective}</span>
            <span className="text-[10px] text-text-muted font-mono truncate">{taskId}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold tracking-wide ${stateBadgeClass}`}
          >
            {state}
          </span>

          {(isRunning || isWaiting) && onCancelTask && (
            <button
              type="button"
              onClick={() => onCancelTask(taskId)}
              className="flex items-center gap-1 px-2 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 text-[11px] font-medium transition-colors cursor-pointer"
              aria-label="Cancel active browser task"
            >
              <StopCircle size={12} />
              <span>Cancel</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Browser Address Bar & Security Pill ── */}
      {currentUrl && (
        <div className="flex items-center gap-2 p-1.5 bg-surface/80 border border-glass-border rounded-lg min-w-0">
          <div className="flex items-center gap-1 text-[10px] text-emerald-600 flex-shrink-0 pl-1 font-medium">
            <ShieldCheck size={12} />
            <span>SSRF-Safe</span>
          </div>
          <span className="text-text-muted text-[10px]">|</span>
          <span className="truncate font-mono text-[11px] text-text-secondary select-all">
            {currentUrl}
          </span>
        </div>
      )}

      {/* ── Tabs Bar (if multiple tabs exist) ── */}
      {tabs.length > 1 && (
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {tabs.map((tab) => (
            <button
              key={tab.tab_id}
              type="button"
              onClick={() => onSwitchTab && onSwitchTab(tab.tab_id)}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all max-w-[140px] truncate ${
                tab.is_active
                  ? "bg-brand-50 text-brand-700 border border-brand-200"
                  : "bg-surface/50 text-text-muted hover:bg-surface border border-glass-border"
              }`}
            >
              <Layers size={10} className="flex-shrink-0" />
              <span className="truncate">{tab.title || tab.origin}</span>
            </button>
          ))}
        </div>
      )}

      {/* ── Tier C Human Authorization Banner ── */}
      {pendingApproval && (
        <div
          className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex flex-col gap-2 animate-in fade-in duration-200"
          role="alertdialog"
          aria-labelledby="approval-title"
        >
          <div className="flex items-center gap-1.5 text-amber-700 font-semibold text-[11px]">
            <AlertTriangle size={13} className="text-amber-600" />
            <span id="approval-title">Human Authorization Required (Tier C Consequential Action)</span>
          </div>

          <p className="text-[11px] text-text-secondary leading-relaxed">
            {pendingApproval.summary}
          </p>

          <div className="text-[10px] font-mono text-text-muted bg-white/50 p-1.5 rounded border border-amber-200/50 break-words">
            <span>Destination: {pendingApproval.destination_url}</span>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            {onDenyAction && (
              <button
                type="button"
                onClick={() => onDenyAction(taskId, pendingApproval.approval_id)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-white hover:bg-slate-100 text-text-secondary border border-glass-border font-medium text-[11px] transition-colors cursor-pointer"
              >
                <X size={12} />
                <span>Deny Action</span>
              </button>
            )}

            {onApproveAction && (
              <button
                type="button"
                onClick={() =>
                  onApproveAction(
                    taskId,
                    pendingApproval.approval_id,
                    pendingApproval.proposed_payload.token
                  )
                }
                className="flex items-center gap-1 px-3 py-1 rounded-md bg-brand-600 hover:bg-brand-700 text-white font-medium text-[11px] shadow-xs transition-colors cursor-pointer"
              >
                <Check size={12} />
                <span>Authorize & Execute</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Action Timeline ── */}
      <div className="flex flex-col gap-1.5 pt-1 border-t border-glass-border">
        <div className="flex items-center justify-between text-[11px] font-semibold text-text-secondary px-0.5">
          <span>Action Timeline ({actions.length})</span>
          {isRunning && (
            <span className="flex items-center gap-1 text-brand-600 text-[10px]">
              <RefreshCw size={10} className="animate-spin" />
              Executing live...
            </span>
          )}
        </div>

        <BrowserActionTimeline actions={actions} />
      </div>
    </div>
  );
}
