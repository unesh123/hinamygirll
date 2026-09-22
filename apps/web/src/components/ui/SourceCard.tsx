import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, BookmarkPlus, Globe } from 'lucide-react';

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
  /**
   * Phone shape: the reply is what the user asked for, so the evidence behind it
   * has to stay scannable. A full card measured ~200px tall, and 17 of them in a
   * single column pushed the actual answer off the screen.
   */
  compact?: boolean;
}

export function SourceCard({ source, index = 0, onSave, compact = false }: SourceCardProps) {
  const [imgError, setImgError] = useState(false);

  const parsedDomain = React.useMemo(() => {
    if (source.domain) return source.domain.replace(/^https?:\/\//, '').split('/')[0];
    if (source.url) {
      try {
        return new URL(source.url).hostname;
      } catch {
        return 'web';
      }
    }
    return 'web';
  }, [source.domain, source.url]);

  const faviconUrl = source.favicon || `https://www.google.com/s2/favicons?domain=${encodeURIComponent(parsedDomain)}&sz=64`;

  const handleCardClick = () => {
    if (source.url) {
      window.open(source.url, '_blank', 'noopener,noreferrer');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleCardClick();
    }
  };

  return (
    <motion.div
      role="link"
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      className="source-card group"
      initial={{ opacity: 0, y: 8, filter: 'blur(2px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      whileHover={{ y: -2 }}
      transition={{ delay: index * 0.04, duration: 0.25, ease: 'easeOut' }}
      style={{
        background: 'linear-gradient(145deg, rgba(28, 22, 34, 0.75), rgba(18, 16, 24, 0.85))',
        border: '1px solid rgba(244, 114, 182, 0.16)',
        borderRadius: 14,
        padding: compact ? '9px 11px' : '12px 14px',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.25)',
        backdropFilter: 'blur(12px)',
        display: 'flex',
        flexDirection: 'column',
        gap: compact ? 4 : 8,
        cursor: 'pointer',
        transition: 'border-color 0.2s, box-shadow 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'rgba(244, 114, 182, 0.45)';
        e.currentTarget.style.boxShadow = '0 8px 24px -4px rgba(0, 0, 0, 0.4), 0 0 16px -2px rgba(244, 114, 182, 0.18)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'rgba(244, 114, 182, 0.16)';
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.25)';
      }}
    >
      <div className="source-card-header" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: 6,
            background: 'rgba(255, 255, 255, 0.06)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            flexShrink: 0,
          }}
        >
          {!imgError ? (
            <img
              src={faviconUrl}
              alt=""
              className="source-favicon"
              style={{ width: 14, height: 14, objectFit: 'contain' }}
              onError={() => setImgError(true)}
            />
          ) : (
            <Globe size={12} color="#f472b6" />
          )}
        </div>

        <span
          className="source-domain"
          style={{
            fontSize: '0.75rem',
            fontWeight: 600,
            color: '#cbd5e1',
            letterSpacing: '0.02em',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {parsedDomain}
        </span>

        {source.id.startsWith('tinyfish') && (
          <span
            style={{
              fontSize: '0.65rem',
              padding: '2px 6px',
              background: 'rgba(244, 114, 182, 0.15)',
              color: '#f472b6',
              borderRadius: 4,
              fontWeight: 700,
            }}
          >
            TinyFish
          </span>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              fontSize: '0.68rem',
              color: '#f472b6',
              fontWeight: 700,
              background: 'rgba(244, 114, 182, 0.1)',
              padding: '1px 6px',
              borderRadius: 6,
            }}
          >
            #{(index + 1).toString().padStart(2, '0')}
          </span>
          <ExternalLink
            size={13}
            style={{ color: '#94a3b8', transition: 'color 0.2s, transform 0.2s' }}
            className="group-hover:text-pink-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
          />
        </div>
      </div>

      <div
        className="source-title"
        style={{
          fontSize: '0.88rem',
          fontWeight: 700,
          color: '#f8fafc',
          lineHeight: 1.35,
          display: '-webkit-box',
          WebkitLineClamp: compact ? 1 : 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {source.title}
      </div>

      {!compact && (
        <div
          className="source-snippet"
          style={{
            fontSize: '0.78rem',
            color: '#94a3b8',
            lineHeight: 1.45,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {source.snippet}
        </div>
      )}

      {onSave && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 2 }}>
          <button
            type="button"
            aria-label={`Save source: ${source.title}`}
            onClick={(e) => {
              e.stopPropagation();
              onSave(source);
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              fontSize: '0.72rem',
              fontWeight: 600,
              color: '#f472b6',
              background: 'rgba(244, 114, 182, 0.08)',
              border: '1px solid rgba(244, 114, 182, 0.2)',
              borderRadius: 6,
              padding: compact ? '3px 6px' : '4px 9px',
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(244, 114, 182, 0.18)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(244, 114, 182, 0.08)')}
          >
            <BookmarkPlus size={12} />
            {!compact && 'Save source'}
          </button>
        </div>
      )}
    </motion.div>
  );
}

export default SourceCard;

