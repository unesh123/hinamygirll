import React from 'react';
import { motion } from 'framer-motion';
import { Brain, Search, Code2, Sparkles, Database, Check, X, Loader2, Play } from 'lucide-react';
import type { BrainRunState, BrainSpecialist, SpecialistType, SpecialistStatus } from './types';

interface BrainOrchestrationPanelProps {
  brainState: BrainRunState;
  compact?: boolean;
  className?: string;
}

const ICONS: Record<SpecialistType, React.ElementType> = {
  planner: Brain,
  researcher: Search,
  coder: Code2,
  synthesizer: Sparkles,
  memory: Database,
};

const STATUS_COLORS: Record<SpecialistStatus, string> = {
  idle: 'text-gray-500 border-gray-700 bg-gray-800/50',
  queued: 'text-blue-400 border-blue-500/50 bg-blue-500/10',
  running: 'text-amber-400 border-amber-500/50 bg-amber-500/10',
  completed: 'text-emerald-400 border-emerald-500/50 bg-emerald-500/10',
  failed: 'text-red-400 border-red-500/50 bg-red-500/10',
  skipped: 'text-gray-400 border-gray-600/50 bg-gray-600/10',
};

const STATUS_ICONS: Record<SpecialistStatus, React.ReactNode> = {
  idle: null,
  queued: <Play className="w-3 h-3" />,
  running: <Loader2 className="w-3 h-3 animate-spin" />,
  completed: <Check className="w-3 h-3" />,
  failed: <X className="w-3 h-3" />,
  skipped: <X className="w-3 h-3" />,
};

function SpecialistNode({ specialist, isCompact }: { specialist: BrainSpecialist; isCompact: boolean }) {
  const Icon = ICONS[specialist.type];
  const colorClasses = STATUS_COLORS[specialist.status];
  const isRunning = specialist.status === 'running';

  return (
    <div className={`relative flex flex-col items-center gap-2 ${isCompact ? 'scale-90' : ''}`}>
      <motion.div
        layout
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`relative flex items-center justify-center w-12 h-12 rounded-xl border backdrop-blur-sm transition-colors duration-300 ${colorClasses}`}
      >
        <Icon className="w-6 h-6" />
        
        {isRunning && (
          <motion.div
            className="absolute inset-0 rounded-xl border border-amber-400"
            initial={{ scale: 1, opacity: 0.8 }}
            animate={{ scale: 1.5, opacity: 0 }}
            transition={{ repeat: Infinity, duration: 1.5, ease: 'easeOut' }}
          />
        )}
        
        <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-gray-900 border border-gray-700 flex items-center justify-center">
          {STATUS_ICONS[specialist.status]}
        </div>
      </motion.div>
      
      {!isCompact && (
        <div className="text-center w-24">
          <div className="text-xs font-semibold text-gray-200 truncate">{specialist.label}</div>
          {specialist.detail && (
            <div className="text-[10px] text-gray-500 truncate" title={specialist.detail}>{specialist.detail}</div>
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
}) => {
  return (
    <div className={`flex flex-col gap-4 p-4 rounded-2xl bg-gray-950/80 border border-gray-800/60 shadow-2xl backdrop-blur-xl overflow-hidden ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-bold text-gray-100 uppercase tracking-wider">Hina Brain</span>
        </div>
        <div className="text-xs text-gray-500">
          Status: <span className="text-gray-300 font-medium capitalize">{brainState.status}</span>
        </div>
      </div>

      <div className="relative flex items-center justify-center gap-4 sm:gap-8 py-2">
        {brainState.specialists.map((spec, i) => (
          <React.Fragment key={spec.type}>
            <SpecialistNode specialist={spec} isCompact={compact} />
            {i < brainState.specialists.length - 1 && (
              <div className="hidden sm:block h-px w-8 bg-gray-800 relative">
                <motion.div
                  className="absolute inset-0 bg-amber-400/50"
                  initial={{ scaleX: 0, transformOrigin: 'left' }}
                  animate={{ scaleX: spec.status === 'completed' || spec.status === 'running' ? 1 : 0 }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
      
      {!compact && brainState.status === 'running' && (
        <div className="flex justify-between items-center mt-2 px-2 border-t border-gray-800/50 pt-3">
          <div className="text-xs text-gray-400">
            {brainState.startedAt ? `${Math.floor((Date.now() - brainState.startedAt) / 1000)}s elapsed` : 'Live'}
          </div>
          <div className="text-xs text-gray-400">
            {brainState.sourcesFound ? `${brainState.sourcesFound} sources` : ''}
          </div>
        </div>
      )}
    </div>
  );
};
