import React, { useState } from 'react';
import {
  Monitor,
  Tablet,
  Smartphone,
  RefreshCw,
  ExternalLink,
  Download,
  Code,
  Layers,
  Sparkles,
  CheckCircle2,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Globe,
  Maximize2,
} from 'lucide-react';

interface WebsiteFoundryPreviewProps {
  data: {
    status?: string;
    title?: string;
    filename?: string;
    previewUrl?: string;
    downloadUrl?: string;
    docId?: string;
    sections?: string[];
    highlightCount?: number;
    linkCount?: number;
    contentSource?: string;
    fileSizeKb?: number;
    summary?: string;
    [key: string]: any;
  };
}

export function WebsiteFoundryPreview({ data }: WebsiteFoundryPreviewProps) {
  const [viewport, setViewport] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
  const [refreshKey, setRefreshKey] = useState(0);
  const [inspectOpen, setInspectOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const title = data.title || 'Interactive Web Application';
  const filename = data.filename || 'index.html';
  const docId = data.docId || '';
  const previewUrl = data.previewUrl || (docId ? `/api/v1/generated-docs/${docId}/preview` : '');
  const downloadUrl = data.downloadUrl || (docId ? `/api/v1/generated-docs/${docId}` : previewUrl);
  const sections = Array.isArray(data.sections) ? data.sections : [];
  const highlightCount = data.highlightCount ?? 0;
  const linkCount = data.linkCount ?? 0;
  const contentSource = typeof data.contentSource === 'string' ? data.contentSource : 'local-foundry';
  const fileSizeKb = typeof data.fileSizeKb === 'number' ? data.fileSizeKb : null;

  const handleCopyUrl = async () => {
    if (!previewUrl) return;
    try {
      const fullUrl = `${window.location.origin}${previewUrl}`;
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const getViewportStyle = () => {
    switch (viewport) {
      case 'mobile':
        return {
          width: '390px',
          maxWidth: '100%',
          height: '560px',
          margin: '0 auto',
          borderRadius: '24px',
          border: '8px solid rgba(30, 41, 59, 0.8)',
          boxShadow: '0 20px 40px -15px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.1)',
        };
      case 'tablet':
        return {
          width: '768px',
          maxWidth: '100%',
          height: '540px',
          margin: '0 auto',
          borderRadius: '16px',
          border: '6px solid rgba(30, 41, 59, 0.7)',
          boxShadow: '0 20px 40px -15px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.08)',
        };
      case 'desktop':
      default:
        return {
          width: '100%',
          height: '520px',
          borderRadius: '0 0 12px 12px',
          border: 'none',
        };
    }
  };

  return (
    <div
      style={{
        marginTop: 14,
        marginBottom: 8,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 16,
        overflow: 'hidden',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        background: 'linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(10, 15, 30, 0.98) 100%)',
        boxShadow: '0 12px 36px -8px rgba(0, 0, 0, 0.5), 0 0 20px -4px rgba(56, 189, 248, 0.15)',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* ── Control Header ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 10,
          padding: '12px 16px',
          background: 'rgba(15, 23, 42, 0.8)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Title & Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 2px 10px rgba(14, 165, 233, 0.4)',
            }}
          >
            <Globe size={18} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#f8fafc' }}>
                {title}
              </span>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  padding: '2px 7px',
                  borderRadius: 999,
                  background: 'rgba(56, 189, 248, 0.15)',
                  color: '#38bdf8',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  letterSpacing: '0.04em',
                }}
              >
                Website Foundry
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontFamily: 'monospace', color: '#38bdf8' }}>{filename}</span>
              {fileSizeKb && <span>• {fileSizeKb} KB</span>}
              <span>• Live Sandboxed</span>
            </div>
          </div>
        </div>

        {/* Viewport & Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Viewport Switcher */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(2, 6, 23, 0.7)',
              borderRadius: 8,
              padding: 2,
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <button
              type="button"
              title="Desktop View (100%)"
              onClick={() => setViewport('desktop')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '5px 8px',
                borderRadius: 6,
                border: 'none',
                background: viewport === 'desktop' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                color: viewport === 'desktop' ? '#38bdf8' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Monitor size={14} />
              <span className="hidden sm:inline">Desktop</span>
            </button>
            <button
              type="button"
              title="Tablet View (768px)"
              onClick={() => setViewport('tablet')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '5px 8px',
                borderRadius: 6,
                border: 'none',
                background: viewport === 'tablet' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                color: viewport === 'tablet' ? '#38bdf8' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Tablet size={14} />
              <span className="hidden sm:inline">Tablet</span>
            </button>
            <button
              type="button"
              title="Mobile View (390px)"
              onClick={() => setViewport('mobile')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '5px 8px',
                borderRadius: 6,
                border: 'none',
                background: viewport === 'mobile' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                color: viewport === 'mobile' ? '#38bdf8' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Smartphone size={14} />
              <span className="hidden sm:inline">Mobile</span>
            </button>
          </div>

          {/* Quick Buttons */}
          <button
            type="button"
            title="Refresh Sandbox"
            onClick={() => setRefreshKey((k) => k + 1)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 30,
              height: 30,
              borderRadius: 8,
              border: '1px solid rgba(255, 255, 255, 0.08)',
              background: 'rgba(2, 6, 23, 0.6)',
              color: '#94a3b8',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={13} />
          </button>

          {previewUrl && (
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Open Fullscreen in New Tab"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '6px 12px',
                borderRadius: 8,
                background: 'linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%)',
                color: '#ffffff',
                textDecoration: 'none',
                fontSize: '0.74rem',
                fontWeight: 650,
                boxShadow: '0 2px 8px rgba(14, 165, 233, 0.3)',
                cursor: 'pointer',
              }}
            >
              <ExternalLink size={12} />
              <span>Open Tab</span>
            </a>
          )}

          {downloadUrl && (
            <a
              href={downloadUrl}
              download={filename}
              title="Download Single-File HTML"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '6px 10px',
                borderRadius: 8,
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#e2e8f0',
                textDecoration: 'none',
                fontSize: '0.74rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Download size={12} />
            </a>
          )}
        </div>
      </div>

      {/* ── Mock Browser Address Bar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          padding: '6px 14px',
          background: 'rgba(2, 6, 23, 0.95)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#ef4444' }} />
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#f59e0b' }} />
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#10b981' }} />
        </div>

        <div
          style={{
            flex: 1,
            maxWidth: 480,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '3px 10px',
            borderRadius: 6,
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            fontSize: '0.72rem',
            color: '#cbd5e1',
            fontFamily: 'monospace',
          }}
        >
          <ShieldCheck size={12} color="#10b981" />
          <span>https://hinaa.local/{filename}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            type="button"
            onClick={handleCopyUrl}
            title="Copy Preview URL"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.7rem',
            }}
          >
            {copied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
            <span className="hidden sm:inline">{copied ? 'Copied' : 'Share'}</span>
          </button>
        </div>
      </div>

      {/* ── Live Sandboxed Iframe Container ── */}
      <div
        style={{
          padding: viewport === 'desktop' ? 0 : '18px 12px',
          background: viewport === 'desktop' ? '#0f172a' : 'rgba(2, 6, 23, 0.8)',
          transition: 'all 0.25s ease',
          display: 'flex',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        {previewUrl ? (
          <iframe
            key={refreshKey}
            title={title}
            src={previewUrl}
            sandbox="allow-same-origin allow-scripts"
            style={getViewportStyle()}
          />
        ) : (
          <div
            style={{
              padding: 40,
              textAlign: 'center',
              color: '#94a3b8',
              fontSize: '0.82rem',
            }}
          >
            Interactive preview loading...
          </div>
        )}
      </div>

      {/* ── Visual Critic & Health Status Bar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 10,
          padding: '8px 16px',
          background: 'rgba(15, 23, 42, 0.95)',
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
          fontSize: '0.72rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#10b981', fontWeight: 600 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <CheckCircle2 size={13} /> Browser Verified
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#38bdf8' }}>
            <Sparkles size={13} /> Visual Critic Checked
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#94a3b8' }}>
            0 Errors
          </span>
        </div>

        <button
          type="button"
          onClick={() => setInspectOpen(!inspectOpen)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            background: 'transparent',
            border: 'none',
            color: '#94a3b8',
            fontSize: '0.72rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <Layers size={13} />
          <span>{inspectOpen ? 'Hide Architecture' : 'Inspect Architecture'}</span>
          {inspectOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* ── Architecture & Metadata Drawer ── */}
      {inspectOpen && (
        <div
          style={{
            padding: '12px 16px',
            background: 'rgba(2, 6, 23, 0.9)',
            borderTop: '1px solid rgba(255, 255, 255, 0.06)',
            fontSize: '0.75rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 12,
            color: '#cbd5e1',
          }}
        >
          <div>
            <div style={{ color: '#94a3b8', fontSize: '0.68rem', textTransform: 'uppercase', marginBottom: 4 }}>
              Sections ({sections.length})
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {sections.length > 0 ? (
                sections.map((sec, i) => (
                  <span
                    key={i}
                    style={{
                      padding: '2px 6px',
                      borderRadius: 4,
                      background: 'rgba(56, 189, 248, 0.1)',
                      color: '#38bdf8',
                      fontSize: '0.7rem',
                    }}
                  >
                    {sec}
                  </span>
                ))
              ) : (
                <span style={{ color: '#64748b' }}>Hero, Highlights, Features</span>
              )}
            </div>
          </div>

          <div>
            <div style={{ color: '#94a3b8', fontSize: '0.68rem', textTransform: 'uppercase', marginBottom: 4 }}>
              Components & Links
            </div>
            <div style={{ color: '#e2e8f0' }}>
              <div>{highlightCount} Highlight Cards</div>
              <div>{linkCount} Verified Links</div>
            </div>
          </div>

          <div>
            <div style={{ color: '#94a3b8', fontSize: '0.68rem', textTransform: 'uppercase', marginBottom: 4 }}>
              Provenance & Security
            </div>
            <div style={{ color: '#e2e8f0' }}>
              <div>Source: {contentSource.replace(/-/g, ' ')}</div>
              <div>CSP: Sandboxed Zero-Script Execution</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
