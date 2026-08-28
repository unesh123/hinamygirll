import React from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, BookmarkPlus } from 'lucide-react';

export interface SourceItem {
  id: string;
  title: string;
  domain: string;
  snippet: string;
  favicon?: string;
  url: string;
  index?: number;
}

interface SourceCardProps {
  source: SourceItem;
  index?: number;
  onSave?: (source: SourceItem) => void;
}

export function SourceCard({ source, index = 0, onSave }: SourceCardProps) {
  // Use a media query hook or just CSS for prefers-reduced-motion. We'll rely on framer-motion's default reduced motion handling or CSS.
  // Actually, framer-motion handles it automatically if we don't override too heavily, but we can also use CSS.
  return (
    <motion.div
      className="source-card"
      initial={{ opacity: 0, y: 12, filter: 'blur(3px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ delay: index * 0.05, duration: 0.3, ease: 'easeOut' }}
      style={{
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: 12,
        padding: 14,
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div className="source-card-header" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {source.favicon ? (
          <img src={source.favicon} alt="" className="source-favicon" style={{ width: 16, height: 16, borderRadius: 4 }} onError={e => (e.currentTarget.style.display = 'none')} />
        ) : (
          <div className="source-favicon" style={{ width: 16, height: 16, background: 'linear-gradient(135deg, #a7f3d0, #67e8f9)', borderRadius: 4 }} />
        )}
        <span className="source-domain" style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e2e8f0' }}>{source.domain}</span>
        {source.id.startsWith('tinyfish') && (
          <span style={{ fontSize: '0.65rem', padding: '2px 6px', background: 'rgba(14, 165, 233, 0.15)', color: '#38bdf8', borderRadius: 4, fontWeight: 700 }}>TinyFish</span>
        )}
        <span style={{ marginLeft: 'auto', fontSize: '0.7rem', color: '#64748b', fontWeight: 700 }}>#{(index + 1).toString().padStart(2, '0')}</span>
      </div>
      
      <div className="source-title" style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f8fafc', lineHeight: 1.3 }}>{source.title}</div>
      <div className="source-snippet" style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{source.snippet}</div>
      
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button
          type="button"
          aria-label={`Open external source: ${source.title}`}
          onClick={() => window.open(source.url, '_blank', 'noopener,noreferrer')}
          className="source-action-btn"
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 600, color: '#0ea5e9', background: 'rgba(14, 165, 233, 0.1)', border: '1px solid rgba(14, 165, 233, 0.2)', borderRadius: 8, padding: '6px 12px', cursor: 'pointer', transition: 'background 0.2s, outline 0.2s' }}
          onFocus={(e) => (e.currentTarget.style.outline = '2px solid #0ea5e9')}
          onBlur={(e) => (e.currentTarget.style.outline = 'none')}
        >
          <ExternalLink size={13} />
          Open
        </button>
        {onSave && (
          <button
            type="button"
            aria-label={`Save source to local project: ${source.title}`}
            onClick={() => onSave(source)}
            className="source-action-btn"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: 8, padding: '6px 12px', cursor: 'pointer', transition: 'background 0.2s, outline 0.2s' }}
            onFocus={(e) => (e.currentTarget.style.outline = '2px solid #94a3b8')}
            onBlur={(e) => (e.currentTarget.style.outline = 'none')}
          >
            <BookmarkPlus size={13} />
            Save locally
          </button>
        )}
      </div>
    </motion.div>
  );
}

export default SourceCard;
