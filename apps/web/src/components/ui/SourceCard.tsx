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
}

export function SourceCard({ source, index = 0 }: SourceCardProps) {
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
          <div className="source-favicon" style={{ background: 'linear-gradient(135deg, #a7f3d0, #67e8f9)', borderRadius: 3 }} />
        )}
        <span className="source-domain">{source.domain}</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: '#94a3b8', fontWeight: 700 }}>#{(index + 1).toString().padStart(2, '0')}</span>
      </div>
      <div className="source-title">{source.title}</div>
      <div className="source-snippet">{source.snippet}</div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        <button
          onClick={() => window.open(source.url, '_blank', 'noopener,noreferrer')}
          style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.73rem', fontWeight: 600, color: '#0891b2', background: 'rgba(8,145,178,0.1)', border: '1px solid rgba(8,145,178,0.2)', borderRadius: 8, padding: '4px 10px', cursor: 'pointer' }}
        >
          <ExternalLink size={11} />
          Open
        </button>
        <button
          style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.73rem', fontWeight: 600, color: '#94a3b8', background: 'rgba(0,0,0,0.04)', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 8, padding: '4px 10px', cursor: 'pointer' }}
        >
          <BookmarkPlus size={11} />
          Save
        </button>
      </div>
    </motion.div>
  );
}

export default SourceCard;
