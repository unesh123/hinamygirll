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
  return (
    <motion.div
      className="source-card"
      initial={{ opacity: 0, y: 16, filter: 'blur(4px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ delay: index * 0.06, duration: 0.4 }}
    >
      <div className="source-card-header">
        {source.favicon ? (
          <img src={source.favicon} alt="" className="source-favicon" onError={e => (e.currentTarget.style.display = 'none')} />
        ) : (
          <div className="source-favicon" style={{ background: 'linear-gradient(135deg, #f5a7bb, #b78ee5)', borderRadius: 4, boxShadow: '0 0 0 1px rgba(255,224,236,.12)' }} />
        )}
        <span className="source-domain">{source.domain}</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: '#94a3b8', fontWeight: 700 }}>#{(index + 1).toString().padStart(2, '0')}</span>
      </div>
      <div className="source-title">{source.title}</div>
      <div className="source-snippet">{source.snippet}</div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        <button
          onClick={() => window.open(source.url, '_blank', 'noopener,noreferrer')}
          style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.73rem', fontWeight: 700, color: '#ffd7e2', background: 'rgba(238,145,173,0.12)', border: '1px solid rgba(238,145,173,0.30)', borderRadius: 8, padding: '5px 10px', cursor: 'pointer', transition: 'transform 160ms var(--ease-out-expo), background 160ms var(--ease-out-expo)' }}
        >
          <ExternalLink size={11} />
          Open
        </button>
        {onSave && (
          <button
            type="button"
            onClick={() => onSave(source)}
            style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.73rem', fontWeight: 700, color: '#eadce2', background: 'rgba(255,255,255,0.045)', border: '1px solid rgba(255,219,231,.16)', borderRadius: 8, padding: '5px 10px', cursor: 'pointer', transition: 'transform 160ms var(--ease-out-expo), background 160ms var(--ease-out-expo)' }}
          >
            <BookmarkPlus size={11} />
            Save
          </button>
        )}
      </div>
    </motion.div>
  );
}

export default SourceCard;
