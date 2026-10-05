import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Search,
  Code2,
  Sparkles,
  Database,
  Check,
  X,
  Loader2,
  ChevronDown,
  ChevronUp,
  FileText,
  Clock,
  Layers,
  ArrowRight,
} from 'lucide-react';
import type { BrainRunState, BrainSpecialist, SpecialistType, SpecialistStatus } from './types';

export interface BrainOrchestrationPanelProps {
  brainState: BrainRunState;
  compact?: boolean;
  className?: string;
  onOpenReceipts?: () => void;
}

const SPECIALIST_CONFIG: Record<
  SpecialistType,
  {
    icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
    title: string;
    subtitle: string;
    color: string;
    glow: string;
  }
> = {
  planner: {
    icon: Brain,
    title: 'Planning',
    subtitle: 'Strategy',
    color: '#f59e0b',
    glow: 'rgba(245, 158, 11, 0.4)',
  },
  researcher: {
    icon: Search,
    title: 'Research',
    subtitle: 'Exa & Web',
    color: '#06b6d4',
    glow: 'rgba(6, 182, 212, 0.4)',
  },
  coder: {
    icon: Code2,
    title: 'Coding',
    subtitle: 'Generation',
    color: '#8b5cf6',
    glow: 'rgba(139, 92, 246, 0.4)',
  },
  synthesizer: {
    icon: Sparkles,
    title: 'Synthesis',
    subtitle: 'Assembly',
    color: '#ec4899',
    glow: 'rgba(236, 72, 153, 0.4)',
  },
  memory: {
    icon: Database,
    title: 'Memory',
    subtitle: 'Context',
    color: '#3b82f6',
    glow: 'rgba(59, 130, 246, 0.4)',
  },
};

function SpecialistNode({
  specialist,
  isLast,
}: {
  specialist: BrainSpecialist;
  isLast: boolean;
}) {
  const cfg = SPECIALIST_CONFIG[specialist.type];
  const Icon = cfg.icon;
  const isRunning = specialist.status === 'running';
  const isDone = specialist.status === 'completed';
  const isFailed = specialist.status === 'failed';

  return (
    <div className="flex items-center flex-1 min-w-0">
      <div className="flex flex-col items-center flex-1 min-w-0 px-1">
        {/* Node Icon Box */}
        <motion.div
          layout
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          className="relative flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-300"
          style={{
            background: isRunning
              ? 'rgba(245, 158, 11, 0.12)'
              : isDone
              ? 'rgba(16, 185, 129, 0.12)'
              : isFailed
              ? 'rgba(239, 68, 68, 0.12)'
              : 'rgba(255, 255, 255, 0.04)',
            border: isRunning
              ? '1.5px solid #f59e0b'
              : isDone
              ? '1.5px solid #10b981'
              : isFailed
              ? '1.5px solid #ef4444'
              : '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: isRunning
              ? `0 0 16px ${cfg.glow}, inset 0 0 8px ${cfg.glow}`
              : isDone
              ? '0 0 10px rgba(16, 185, 129, 0.25)'
              : 'none',
          }}
        >
          <Icon
            className="w-5 h-5 transition-colors"
            style={{
              color: isRunning ? cfg.color : isDone ? '#10b981' : isFailed ? '#ef4444' : '#64748b',
            }}
          />

          {/* Pulse Ripple when running */}
          {isRunning && (
            <motion.div
              className="absolute inset-0 rounded-xl"
              style={{ border: `1.5px solid ${cfg.color}` }}
              initial={{ scale: 1, opacity: 0.8 }}
              animate={{ scale: 1.45, opacity: 0 }}
              transition={{ repeat: Infinity, duration: 1.5, ease: 'easeOut' }}
            />
          )}

          {/* Micro Status Badge */}
          <div
            className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full flex items-center justify-center text-[9px]"
            style={{
              background: isRunning ? '#f59e0b' : isDone ? '#10b981' : isFailed ? '#ef4444' : '#1e293b',
              color: '#ffffff',
              boxShadow: '0 1px 4px rgba(0,0,0,0.5)',
            }}
          >
            {isRunning ? (
              <Loader2 className="w-2.5 h-2.5 animate-spin" />
            ) : isDone ? (
              <Check className="w-2.5 h-2.5 stroke-[3]" />
            ) : isFailed ? (
              <X className="w-2.5 h-2.5 stroke-[3]" />
            ) : (
              <span className="w-1.5 h-1.5 rounded-full bg-gray-500" />
            )}
          </div>
        </motion.div>

        {/* Node Labels: Title & Subtitle (No truncation!) */}
        <div className="flex flex-col items-center mt-2 text-center w-full">
          <span
            className="text-[11px] font-bold tracking-tight whitespace-nowrap"
            style={{
              color: isRunning ? '#f8fafc' : isDone ? '#e2e8f0' : isFailed ? '#fca5a5' : '#64748b',
            }}
          >
            {cfg.title}
          </span>
          <span
            className="text-[9px] font-medium tracking-normal whitespace-nowrap mt-0.5"
            style={{
              color: isRunning ? cfg.color : isDone ? '#6ee7b7' : '#475569',
            }}
          >
            {cfg.subtitle}
          </span>
        </div>
      </div>

      {/* Circuit Connector Line to Next Node */}
      {!isLast && (
        <div className="relative flex-1 h-[2px] mx-1 bg-gray-800/80 overflow-hidden rounded-full">
          {/* Active laser beam passing through when current node is completed or running */}
          {(isDone || isRunning) && (
            <motion.div
              className="absolute inset-y-0 w-full"
              style={{
                background: isDone
                  ? 'linear-gradient(90deg, #10b981, #06b6d4)'
                  : 'linear-gradient(90deg, #f59e0b, #ec4899)',
              }}
              initial={{ scaleX: 0, transformOrigin: 'left' }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.4 }}
            />
          )}
        </div>
      )}
    </div>
  );
}

export const BrainOrchestrationPanel: React.FC<BrainOrchestrationPanelProps> = ({
  brainState,
  compact = false,
  className = '',
  onOpenReceipts,
}) => {
  const [isExpanded, setIsExpanded] = useState(!compact);

  // Derive active specialist and detailed status
  const activeSpecialist = brainState.specialists.find((s) => s.status === 'running');
  const completedCount = brainState.specialists.filter((s) => s.status === 'completed').length;
  const totalCount = brainState.specialists.length;

  const elapsedSec = brainState.startedAt
    ? ((Date.now() - brainState.startedAt) / 1000).toFixed(1)
    : '0.0';

  // Detail message for bottom telemetry strip
  const telemetryMessage = activeSpecialist?.detail
    ? activeSpecialist.detail
    : activeSpecialist?.type === 'planner'
    ? 'Formulating task breakdown & reasoning matrix...'
    : activeSpecialist?.type === 'researcher'
    ? 'Querying Exa neural search & verifying web sources...'
    : activeSpecialist?.type === 'coder'
    ? 'Synthesizing code structures & AST repair...'
    : activeSpecialist?.type === 'synthesizer'
    ? 'Unifying specialist outputs into final executive response...'
    : activeSpecialist?.type === 'memory'
    ? 'Extracting relevant conversation history & workspace context...'
    : brainState.status === 'completed'
    ? 'All 5 specialists completed successfully'
    : 'Orchestrating multi-agent cognitive mesh';

  return (
    <div
      className={`relative w-full max-w-3xl rounded-2xl border transition-all duration-300 overflow-hidden ${className}`}
      style={{
        background: 'linear-gradient(135deg, rgba(13, 17, 28, 0.94) 0%, rgba(8, 10, 18, 0.98) 100%)',
        borderColor: brainState.status === 'running' ? 'rgba(245, 158, 11, 0.28)' : 'rgba(255, 255, 255, 0.1)',
        boxShadow:
          brainState.status === 'running'
            ? '0 12px 36px rgba(0, 0, 0, 0.6), 0 0 20px rgba(245, 158, 11, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.1)'
            : '0 8px 28px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
      }}
    >
      {/* ── Top Header Bar ────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.06]">
        {/* Left: Brand & Status */}
        <div className="flex items-center gap-2.5">
          <div className="relative flex items-center justify-center w-6 h-6 rounded-lg bg-gradient-to-tr from-purple-500/20 to-pink-500/20 border border-purple-400/30">
            <Brain className="w-3.5 h-3.5 text-purple-400" />
            {brainState.status === 'running' && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            )}
          </div>
          <span className="text-xs font-extrabold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-pink-300 to-amber-200 uppercase">
            Hina Brain
          </span>

          {/* Active status pill */}
          <span
            className="text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1.5"
            style={{
              background:
                brainState.status === 'running'
                  ? 'rgba(245, 158, 11, 0.15)'
                  : brainState.status === 'completed'
                  ? 'rgba(16, 185, 129, 0.15)'
                  : 'rgba(255, 255, 255, 0.06)',
              color:
                brainState.status === 'running'
                  ? '#fbbf24'
                  : brainState.status === 'completed'
                  ? '#34d399'
                  : '#94a3b8',
              border:
                brainState.status === 'running'
                  ? '1px solid rgba(245, 158, 11, 0.3)'
                  : '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background:
                  brainState.status === 'running'
                    ? '#fbbf24'
                    : brainState.status === 'completed'
                    ? '#34d399'
                    : '#94a3b8',
              }}
            />
            <span className="capitalize">
              {brainState.status === 'running'
                ? activeSpecialist
                  ? `${SPECIALIST_CONFIG[activeSpecialist.type].title}`
                  : 'Orchestrating'
                : brainState.status}
            </span>
          </span>
        </div>

        {/* Right: Telemetry & Actions */}
        <div className="flex items-center gap-2">
          {/* Elapsed Time Chip */}
          <div className="hidden sm:flex items-center gap-1 text-[10px] font-medium text-gray-400 bg-white/[0.04] border border-white/[0.06] rounded-md px-2 py-0.5">
            <Clock className="w-2.5 h-2.5 text-gray-400" />
            <span>{elapsedSec}s</span>
          </div>

          {/* Audit Receipts Button */}
          {onOpenReceipts && (
            <button
              type="button"
              onClick={onOpenReceipts}
              title="Inspect verifiable cryptographic execution receipts & token audit"
              className="inline-flex items-center gap-1.5 text-[10px] font-bold text-purple-300 hover:text-white bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 hover:border-purple-400/50 rounded-lg px-2.5 py-1 transition-all cursor-pointer shadow-sm"
            >
              <Layers className="w-3 h-3 text-purple-400" />
              <span>Audit Receipts</span>
            </button>
          )}

          {/* Expand / Collapse Button */}
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            title={isExpanded ? 'Collapse brain pipeline' : 'Expand brain pipeline'}
            className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* ── Collapsible Body: Neural Specialist Pipeline ─────────── */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            {/* Visual Node Graph */}
            <div className="px-4 py-3.5">
              <div className="flex items-center justify-between gap-1 sm:gap-2">
                {brainState.specialists.map((spec, i) => (
                  <SpecialistNode
                    key={spec.type}
                    specialist={spec}
                    isLast={i === brainState.specialists.length - 1}
                  />
                ))}
              </div>
            </div>

            {/* Bottom Live Activity Telemetry Bar */}
            <div className="flex items-center justify-between px-4 py-2 bg-black/30 border-t border-white/[0.04] text-[11px]">
              <div className="flex items-center gap-2 text-gray-300 min-w-0 pr-2">
                {activeSpecialist ? (
                  <Loader2 className="w-3 h-3 text-amber-400 animate-spin shrink-0" />
                ) : (
                  <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                )}
                <span className="truncate text-gray-300 font-medium">
                  {telemetryMessage}
                </span>
              </div>

              {/* Progress Count */}
              <div className="text-[10px] font-semibold text-gray-400 shrink-0">
                <span>{completedCount}</span>
                <span className="text-gray-600">/</span>
                <span>{totalCount} specialists</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
