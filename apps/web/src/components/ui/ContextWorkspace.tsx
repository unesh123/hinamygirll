import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Globe, Image as ImageIcon, Music, Mail, type LucideIcon } from 'lucide-react';
import { ActivityPanel, type AgentStep } from './ActivityPanel';
import { SourceCard, type SourceItem } from './SourceCard';

export type ContextMode = 'hidden' | 'research' | 'images' | 'music' | 'email' | 'browser';

interface ContextWorkspaceProps {
  mode: ContextMode;
  onClose: () => void;
  sources?: SourceItem[];
  isSearching?: boolean;
  steps?: AgentStep[];
  title?: string;
}

const MODE_LABELS: Record<ContextMode, string> = {
  hidden: '',
  research: 'Research',
  images: 'Images',
  music: 'Music',
  email: 'Email',
  browser: 'Browser',
};

const MODE_ICONS: Record<ContextMode, LucideIcon | null> = {
  hidden: null,
  research: Globe,
  images: ImageIcon,
  music: Music,
  email: Mail,
  browser: Globe,
};

const MODE_EMPTY_STATES: Record<Exclude<ContextMode, 'hidden'>, string> = {
  research: 'Ask HINAA to research a question. Attributed sources will appear here while the local workflow is active.',
  images: 'Open Image Studio to create locally. Finished images remain in the conversation and local generation history.',
  music: 'Music needs an explicit external request. HINAA will ask before opening or controlling a music service.',
  email: 'Email stays inactive until you configure a provider and explicitly approve an external action.',
  browser: 'Ask HINAA to open or research a link. Browser actions are proposed clearly before they run.',
};

export function ContextWorkspace({ mode, onClose, sources = [], isSearching = false, steps = [], title }: ContextWorkspaceProps) {
  const isOpen = mode !== 'hidden';
  const ModeIcon = mode !== 'hidden' ? MODE_ICONS[mode] : null;

  return (
    <div
      className={`workspace-context${isOpen ? ' open' : ''}`}
      aria-hidden={!isOpen}
    >
      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="context-workspace-inner"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexShrink: 0, borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {ModeIcon && <ModeIcon size={16} style={{ color: '#38bdf8' }} />}
                <span style={{ fontWeight: 750, fontSize: '0.9rem', color: '#f8fafc', letterSpacing: '.01em' }}>{title ?? MODE_LABELS[mode]}</span>
                {mode === 'research' && sources.length > 0 && (
                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', background: 'rgba(255,255,255,0.1)', color: '#cbd5e1', borderRadius: 12, fontWeight: 600 }}>
                    {sources.length} {sources.length === 1 ? 'source' : 'sources'}
                  </span>
                )}
              </div>
              <button
                type="button"
                aria-label={`Close ${MODE_LABELS[mode]} workspace`}
                onClick={onClose}
                style={{ width: 32, height: 32, borderRadius: 10, border: '1px solid rgba(255,255,255,.08)', background: 'rgba(255,255,255,.05)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', transition: 'all 0.2s' }}
                onFocus={(e) => (e.currentTarget.style.outline = '2px solid #38bdf8')}
                onBlur={(e) => (e.currentTarget.style.outline = 'none')}
              >
                <X size={14} />
              </button>
            </div>

            {/* Research progress uses HINAA's actual workflow state; it never
                invents external websites, source names, or completed fetches. */}
            {isSearching && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }} style={{ padding: '4px 0 16px' }}>
                <ActivityPanel
                  title="Research workflow"
                  mode="research"
                  steps={steps.length ? steps : [{ id: 'prepare', label: 'Prepare research workspace', detail: 'Waiting for the current search request', status: 'active' }]}
                />
              </motion.div>
            )}

            {/* Source cards */}
            {mode === 'research' && sources.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto', paddingRight: 4, paddingBottom: 16 }}>
                {sources.map((src, i) => (
                  <SourceCard key={src.id} source={src} index={i} />
                ))}
              </div>
            )}

            {/* Empty state */}
            {!isSearching && sources.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '48px 24px', opacity: 0.7 }}>
                <Globe size={32} style={{ color: '#64748b', marginBottom: 16 }} />
                <div style={{ fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.5, maxWidth: 280 }}>
                  {MODE_EMPTY_STATES[mode as Exclude<ContextMode, 'hidden'>]}
                </div>
              </div>
            )}

          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default ContextWorkspace;
