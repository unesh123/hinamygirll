import { motion, AnimatePresence } from 'framer-motion';
import { X, Globe, Image as ImageIcon, Music, Mail } from 'lucide-react';
import type { IconComponent } from '../../shared/iconType';
import KnowledgeConvergence from '../lightswind/knowledge-convergence';
import { SourceCard, type SourceItem } from './SourceCard';

export type ContextMode = 'hidden' | 'research' | 'images' | 'music' | 'email' | 'browser';

interface ContextWorkspaceProps {
  mode: ContextMode;
  onClose: () => void;
  sources?: SourceItem[];
  isSearching?: boolean;
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

const MODE_ICONS: Record<ContextMode, IconComponent | null> = {
  hidden: null,
  research: Globe,
  images: ImageIcon,
  music: Music,
  email: Mail,
  browser: Globe,
};

export function ContextWorkspace({ mode, onClose, sources = [], isSearching = false, title }: ContextWorkspaceProps) {
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
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4, flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {ModeIcon && <ModeIcon size={15} style={{ color: '#0891b2' }} />}
                <span style={{ fontWeight: 700, fontSize: '0.88rem', color: '#1a1f2e' }}>{title ?? MODE_LABELS[mode]}</span>
              </div>
              <button
                onClick={onClose}
                style={{ width: 28, height: 28, borderRadius: 8, border: '1px solid rgba(255,255,255,0.7)', background: 'rgba(255,255,255,0.5)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}
              >
                <X size={13} />
              </button>
            </div>

            {/* Searching animation */}
            {isSearching && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ padding: '8px 0' }}>
                <KnowledgeConvergence title="HINAA Agent" badgeText="Searching" dotColor="#0891b2" showBadge />
              </motion.div>
            )}

            {/* Source cards */}
            {mode === 'research' && sources.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {sources.map((src, i) => (
                  <SourceCard key={src.id} source={src} index={i} />
                ))}
              </div>
            )}

            {mode === 'images' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[1,2,3,4].map(i => (
                  <div key={i} style={{ aspectRatio: '1', borderRadius: 12, background: `linear-gradient(135deg, hsl(${i*60},60%,88%), hsl(${i*60+40},60%,90%))`, border: '1px solid rgba(255,255,255,0.8)' }} />
                ))}
              </div>
            )}

            {/* Empty state */}
            {!isSearching && sources.length === 0 && mode !== 'images' && (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#94a3b8', fontSize: '0.82rem' }}>
                {ModeIcon && <ModeIcon size={32} style={{ marginBottom: 12, opacity: 0.4 }} />}
                <div>Results will appear here</div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default ContextWorkspace;
