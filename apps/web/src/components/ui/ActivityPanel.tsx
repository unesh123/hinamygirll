import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Circle, XCircle, ChevronDown, ChevronUp, Zap } from 'lucide-react';

export type StepStatus = 'pending' | 'active' | 'done' | 'error' | 'cancelled';

export interface AgentStep {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

interface ActivityPanelProps {
  steps: AgentStep[];
  title?: string;
  collapsed?: boolean;
}

const StatusIcon = ({ status }: { status: StepStatus }) => {
  switch (status) {
    case 'done': return <CheckCircle2 size={14} style={{ color: '#059669' }} />;
    case 'active': return (
      <motion.div
        style={{ width: 14, height: 14, border: '2px solid #0891b2', borderTopColor: 'transparent', borderRadius: '50%' }}
        animate={{ rotate: 360 }}
        transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
      />
    );
    case 'error': return <XCircle size={14} style={{ color: '#dc2626' }} />;
    case 'cancelled': return <XCircle size={14} style={{ color: '#94a3b8' }} />;
    default: return <Circle size={14} style={{ color: '#cbd5e1' }} />;
  }
};

export function ActivityPanel({ steps, title = 'Working on your request', collapsed: initialCollapsed = false }: ActivityPanelProps) {
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const doneCount = steps.filter(s => s.status === 'done').length;

  if (steps.length === 0) return null;

  return (
    <motion.div
      className="activity-panel"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <button
        className="activity-header"
        onClick={() => setCollapsed(v => !v)}
        style={{ background: 'none', border: 'none', width: '100%', textAlign: 'left', cursor: 'pointer' }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Zap size={13} style={{ color: '#0891b2' }} />
          <span>{title}</span>
          <span style={{ marginLeft: 4, padding: '1px 8px', borderRadius: 8, background: 'rgba(8,145,178,0.1)', color: '#0891b2', fontSize: '0.7rem', fontWeight: 700 }}>
            {steps.length} steps
          </span>
        </span>
        {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>

      <AnimatePresence>
        {!collapsed && (
          <motion.div
            className="activity-steps"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            style={{ overflow: 'hidden' }}
          >
            {/* Progress bar */}
            <div style={{ height: 2, borderRadius: 1, background: 'rgba(0,0,0,0.06)', margin: '0 0 10px', overflow: 'hidden' }}>
              <motion.div
                style={{ height: '100%', borderRadius: 1, background: 'linear-gradient(90deg, #10b981, #0891b2)' }}
                initial={{ width: 0 }}
                animate={{ width: `${(doneCount / steps.length) * 100}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>

            {steps.map((step, i) => (
              <motion.div
                key={step.id}
                className={`activity-step ${step.status}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <div className="activity-step-icon">
                  <StatusIcon status={step.status} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: step.status === 'active' ? 600 : 400 }}>{step.label}</div>
                  {step.detail && step.status === 'active' && (
                    <div style={{ fontSize: '0.72rem', opacity: 0.7, marginTop: 2 }}>{step.detail}</div>
                  )}
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default ActivityPanel;
