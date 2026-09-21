import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Terminal, Image as ImageIcon, FileJson, ChevronDown, ChevronUp, AlertTriangle, Network, Globe, FileText, Download, ExternalLink } from 'lucide-react';
import { ImageGeneration } from '@/components/ui/image-generation';
import { SourceCard, type SourceItem } from '@/components/ui/SourceCard';
import { WorkTree } from './WorkTree';
import { downloadMarkdownPdf } from '@/features/documents/exportPdf';
import type { WorkTreeNode } from './WorkTree';

interface GenericResultRendererProps {
  toolName: string;
  result: any;
  conversationId?: string;
}

export function GenericResultRenderer({ toolName, result, conversationId }: GenericResultRendererProps) {
  const [expanded, setExpanded] = useState(false);
  const [sourceSaveState, setSourceSaveState] = useState<Record<string, string>>({});
  const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(null);
  const [selectionStatus, setSelectionStatus] = useState<string | null>(null);

  const saveSourceToProject = async (source: SourceItem) => {
    const projectId = localStorage.getItem("hinaa-active-project-id");
    if (!projectId) {
      setSourceSaveState((current) => ({ ...current, [source.id]: "Select a local project first to save this source." }));
      return;
    }
    setSourceSaveState((current) => ({ ...current, [source.id]: "Saving locally…" }));
    try {
      const response = await fetch(`/api/v1/projects/${encodeURIComponent(projectId)}/artifacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "research",
          title: source.title,
          content: source.snippet,
          sourceUrl: source.url,
          metadata: { sourceId: source.id, domain: source.domain },
        }),
      });
      if (!response.ok) throw new Error("save failed");
      setSourceSaveState((current) => ({ ...current, [source.id]: "Saved to the active local project." }));
    } catch {
      setSourceSaveState((current) => ({ ...current, [source.id]: "Could not save this source locally." }));
    }
  };
  
  if (!result) return null;

  // Extract from envelope if present
  const data = result.data !== undefined ? result.data : result;

  // Render Requires Approval
  if (result.status === 'RequiresApproval' || data.status === 'RequiresApproval') {
    const actionInfo = data.action ? `${data.action} ${data.args}` : JSON.stringify(data);
    return (
      <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
        <div style={{ fontSize: '0.75rem', color: '#854d0e', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <AlertTriangle size={14} /> Action Requires Approval
        </div>
        <div style={{ fontSize: '0.8rem', color: '#713f12', marginBottom: 12 }}>
          HINAA wants to perform a side-effect: <strong>{actionInfo}</strong>
        </div>
        <div style={{ fontSize: '0.75rem', color: '#a16207', lineHeight: 1.45 }}>
          This action remains blocked until you explicitly confirm it through Hinaa’s approved action flow. Nothing has been sent or changed yet.
        </div>
      </div>
    );
  }

  if (toolName === 'web_search' && Array.isArray(data.sources)) {
    if (data.error || result.status === 'error' || data.status === 'error') {
      const code = typeof data.code === 'string' ? data.code : 'RESEARCH_UNAVAILABLE';
      const recovery = code === 'YOUCOM_TIMEOUT'
        ? 'The configured research service exceeded its local response budget. Try a narrower query or retry shortly.'
        : code === 'YOUCOM_REQUEST_FAILED'
          ? 'Check the configured provider key and its account permissions, then retry the approved search.'
          : 'HINAA did not receive attributable results. Check the local provider status or try again later.';
      return (
        <section style={{ marginTop: 10, display: 'grid', gap: 8, padding: 12, border: '1px solid rgba(245,158,11,.30)', borderRadius: 14, background: 'rgba(245,158,11,.07)' }} aria-label="Research service recovery">
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#fde68a', fontSize: 12, fontWeight: 800 }}><AlertTriangle size={14} /> Research service needs attention</div>
          <p style={{ margin: 0, color: '#f1dfc7', fontSize: 12, lineHeight: 1.5 }}>{data.error}</p>
          <small style={{ color: '#cfb99d', fontSize: 11, lineHeight: 1.45 }}>{recovery} <code style={{ color: '#f2bf7a' }}>{code}</code></small>
        </section>
      );
    }
    const sources: SourceItem[] = data.sources
      .filter((source: any) => source && typeof source.url === 'string')
      .map((source: any, index: number) => {
        let domain = 'Source';
        try { domain = new URL(source.url).hostname.replace(/^www\./, ''); } catch {}
        return {
          id: source.id || `S${index + 1}`,
          title: source.title || 'Untitled source',
          url: source.url,
          snippet: source.snippet || 'No preview was provided.',
          domain,
          index,
        };
      });
    return (
      <section style={{ marginTop: 10, display: 'grid', gap: 8 }} aria-label="Research sources">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#f3e8dd', fontSize: 12, fontWeight: 750 }}>
          <span>Research sources</span><span style={{ color: '#cbbca8', fontWeight: 600 }}>{sources.length} attributed result{sources.length === 1 ? '' : 's'}</span>
        </div>
        {typeof data.notice === 'string' && data.notice ? (
          <div role="status" style={{ display: 'flex', gap: 7, alignItems: 'flex-start', padding: '9px 10px', border: '1px solid rgba(251,191,36,.24)', borderRadius: 11, background: 'rgba(251,191,36,.06)', color: '#e5d8c5', fontSize: 11, lineHeight: 1.45 }}>
            <Network size={14} style={{ flex: '0 0 auto', marginTop: 1, color: '#f2bf7a' }} />
            <span>{data.notice}</span>
          </div>
        ) : null}
        {sources.length ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 10,
            }}
          >
            {sources.map((source, index) => (
              <div key={source.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <SourceCard source={source} index={index} onSave={saveSourceToProject} />
                {sourceSaveState[source.id] && (
                  <small style={{ color: sourceSaveState[source.id].startsWith('Saved') ? '#86efac' : '#cbbca8', fontSize: 11 }}>
                    {sourceSaveState[source.id]}
                  </small>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: '#cbbca8', fontSize: 12 }}>No attributable sources were returned for this query.</div>
        )}
      </section>
    );
  }

  if (toolName === 'image_search') {
    const images = Array.isArray(data.images)
      ? data.images
          .map((image: any) => {
            const src = [image?.imageUrl, image?.thumbnailUrl, image?.url].find(
              (value: unknown) => typeof value === 'string' && value.length > 0,
            );
            return src ? { ...image, src } : null;
          })
          .filter(Boolean)
          .slice(0, 12)
      : [];
    if (data.error || result.status === 'error') {
      return (
        <section style={{ marginTop: 10, border: '1px solid rgba(251,191,36,.32)', borderRadius: 14, background: 'rgba(251,191,36,.07)', padding: 12 }} aria-label="Image search availability">
          <strong style={{ color: '#fde68a', fontSize: 12 }}>Image search needs attention</strong>
          <p style={{ color: '#e5d8c5', fontSize: 12, lineHeight: 1.5, margin: '6px 0 0' }}>{data.error}</p>
          <small style={{ display: 'block', marginTop: 6, color: '#cbbca8', lineHeight: 1.45 }}>
            {data.code === 'YOUCOM_IMAGE_ACCESS_REQUIRED'
              ? 'This You.com endpoint is beta and requires early-access permission for the configured key. Local ComfyUI remains HINAA’s private image-generation route.'
              : data.code === 'YOUCOM_UPSTREAM_UNAVAILABLE' || data.code === 'YOUCOM_REQUEST_FAILED' || /HTTP\s*502/i.test(String(data.error || ''))
                ? 'No public images were returned. The upstream beta image service is temporarily unavailable; retry later, use local ComfyUI generation, or run a normal web search for source pages.'
                : 'No public images were returned. Check provider availability, then retry the explicitly approved search.'}
          </small>
        </section>
      );
    }
    return (
      <section style={{ marginTop: 10, display: 'grid', gap: 9 }} aria-label="Public image search results">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, color: 'var(--text-primary)', fontSize: 12, fontWeight: 750 }}>
          <span>Public image results</span><span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{images.length} result{images.length === 1 ? '' : 's'}</span>
        </div>
        {selectionStatus && (
          <div role="status" style={{ fontSize: 11, color: 'var(--success, #10b981)', fontWeight: 600 }}>
            {selectionStatus}
          </div>
        )}
        {images.length ? <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 9 }}>
          {images.map((image: any, index: number) => (
            <div key={image.id || image.src || index} style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', border: '1px solid var(--border-subtle)', borderRadius: 12, background: 'var(--bg-surface-raised)', boxShadow: 'var(--shadow-xs)' }}>
              <motion.a href={image.pageUrl || image.src} target="_blank" rel="noopener noreferrer" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, delay: index * 0.025 }} whileHover={{ y: -2 }} style={{ overflow: 'hidden', color: 'var(--text-primary)', textDecoration: 'none' }}>
                <img src={image.src} alt={image.title || 'Public image result'} loading="lazy" referrerPolicy="no-referrer" style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block', background: 'var(--bg-secondary)' }} />
                <span style={{ display: 'block', padding: '7px 8px 4px', fontSize: 11, fontWeight: 650, lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{image.title || 'Open source page'}</span>
              </motion.a>
              <div style={{ padding: '0 8px 8px' }}>
                <button
                  type="button"
                  aria-label={`Select image ${index + 1}`}
                  aria-pressed={selectedImageIndex === index}
                  onClick={async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setSelectedImageIndex(index);
                    setSelectionStatus(`Selected image ${index + 1}.`);
                    if (conversationId) {
                      try {
                        await fetch(`/api/v1/conversations/${encodeURIComponent(conversationId)}/assets/select`, {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            assetId: image.id || image.src,
                            resultSetId: data.resultSet?.resultSetId,
                            canonicalSubject: data.canonicalSubject,
                          }),
                        });
                      } catch {}
                    }
                  }}
                  style={{
                    width: '100%',
                    padding: '4px 8px',
                    borderRadius: 6,
                    border: selectedImageIndex === index ? '1px solid var(--accent, #f472b6)' : '1px solid var(--border-default)',
                    background: selectedImageIndex === index ? 'var(--accent-pale, rgba(244, 114, 182, 0.15))' : 'var(--bg-surface)',
                    color: selectedImageIndex === index ? 'var(--accent, #f472b6)' : 'var(--text-secondary)',
                    fontSize: 10,
                    fontWeight: 650,
                    cursor: 'pointer',
                  }}
                >
                  {selectedImageIndex === index ? '✓ Selected' : `Select image ${index + 1}`}
                </button>
              </div>
            </div>
          ))}
        </div> : <p style={{ color: 'var(--text-tertiary)', fontSize: 12, margin: 0 }}>No public image links were returned for this query. Try a more specific search.</p>}
        {Array.isArray(data.boards) && data.boards.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 750, color: 'var(--text-secondary)' }}>📌 Pinterest Inspiration Boards:</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {data.boards.map((board: any, bIdx: number) => (
                <a
                  key={bIdx}
                  href={board.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '5px 12px',
                    borderRadius: 999,
                    background: 'rgba(244, 114, 182, 0.08)',
                    border: '1px solid rgba(244, 114, 182, 0.28)',
                    color: '#fbcfe8',
                    fontSize: 11,
                    fontWeight: 600,
                    textDecoration: 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span style={{ color: '#e11d48', fontWeight: 800 }}>📌</span>
                  <span>{board.title}</span>
                  {board.count ? <span style={{ opacity: 0.75, fontSize: 10 }}>({board.count})</span> : null}
                </a>
              ))}
            </div>
          </div>
        )}
        <small style={{ color: 'var(--text-tertiary)', fontSize: 11, lineHeight: 1.45 }}>Public web image links may have licensing restrictions. Open the source page before saving or reusing an image.</small>
      </section>
    );
  }

  const detailedResearchTools = new Set(['web_answer', 'web_research', 'web_research_status', 'web_extract', 'finance_research']);
  if (detailedResearchTools.has(toolName) && !data.error && result.status !== 'error') {
    const pages = Array.isArray(data.pages) ? data.pages : [];
    const content = typeof data.content === 'string'
      ? data.content.trim()
      : pages.map((page: any) => {
          const title = typeof page?.title === 'string' ? page.title : 'Selected page';
          const markdown = typeof page?.markdown === 'string' ? page.markdown : '';
          return markdown ? `## ${title}\n\n${markdown}` : '';
        }).filter(Boolean).join('\n\n');
    const detailSources: SourceItem[] = Array.isArray(data.sources)
      ? data.sources.filter((source: any) => source && typeof source.url === 'string').map((source: any, index: number) => {
          let domain = 'Source';
          try { domain = new URL(source.url).hostname.replace(/^www\./, ''); } catch {}
          return {
            id: source.id || `S${index + 1}`,
            title: source.title || 'Untitled source',
            url: source.url,
            snippet: source.snippet || 'No preview was provided.',
            domain,
            index,
          };
        })
      : [];
    const excerptLimit = 2_400;
    const compactContent = content.length > excerptLimit && !expanded
      ? `${content.slice(0, excerptLimit).trimEnd()}…`
      : content;
    const modeLabel = data.mode === 'contents' ? 'Selected page notes' : data.mode === 'answer' ? 'Cited answer' : 'Detailed research';
    if (content || detailSources.length) {
      return (
        <section style={{ marginTop: 10, display: 'grid', gap: 10, padding: 13, border: '1px solid rgba(255,219,231,.16)', borderRadius: 15, background: 'linear-gradient(145deg,rgba(46,29,44,.82),rgba(26,17,31,.84))' }} aria-label="Detailed research result">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, color: '#fff2f6' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12, fontWeight: 800 }}><Globe size={14} color="#f5a7bb" />{modeLabel}</span>
            <span style={{ color: '#cbbca8', fontSize: 11, fontWeight: 650 }}>{detailSources.length} attributed source{detailSources.length === 1 ? '' : 's'}</span>
          </div>
          {typeof data.notice === 'string' && data.notice ? <small style={{ color: '#dcc7b2', lineHeight: 1.45 }}>{data.notice}</small> : null}
          {content ? <div style={{ color: '#eee1e7', fontSize: 13, lineHeight: 1.65, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{compactContent}</div> : null}
          {content.length > excerptLimit ? <button type="button" onClick={() => setExpanded((value) => !value)} style={{ justifySelf: 'start', border: '1px solid rgba(255,219,231,.18)', borderRadius: 999, background: 'rgba(255,255,255,.045)', color: '#ffd2df', padding: '6px 10px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>{expanded ? 'Show concise view' : 'Read full research'}</button> : null}
          {Array.isArray(data.warnings) && data.warnings.length ? <div style={{ display: 'grid', gap: 4, padding: '8px 10px', borderLeft: '2px solid #f2bf7a', background: 'rgba(242,191,122,.06)', color: '#ead5b9', fontSize: 11, lineHeight: 1.45 }}>{data.warnings.slice(0, 3).map((warning: unknown, index: number) => <span key={index}>{String(warning)}</span>)}</div> : null}
          {detailSources.length ? <div style={{ display: 'grid', gap: 7, paddingTop: 2 }}>{detailSources.map((source, index) => <div key={source.id} style={{ display: 'grid', gap: 4 }}><SourceCard source={source} index={index} onSave={saveSourceToProject} />{sourceSaveState[source.id] && <small style={{ color: sourceSaveState[source.id].startsWith('Saved') ? '#86efac' : '#cbbca8', fontSize: 11 }}>{sourceSaveState[source.id]}</small>}</div>)}</div> : null}
        </section>
      );
    }
  }

  // Render browser_execute_task as WorkTree
  if (toolName === 'browser_execute_task') {
    const isError = Boolean(data?.error || result?.status === 'error');
    
    // Extract clean readable outcome
    let finalOutcome: React.ReactNode = null;
    if (typeof data === 'string') {
      finalOutcome = data;
    } else if (data && typeof data === 'object') {
      const candidate = data.details || data.result || data.summary || data.message || data.output;
      if (typeof candidate === 'string') {
        finalOutcome = candidate;
      } else if (data.error) {
        finalOutcome = String(data.error);
      } else if (data.imageCount || (Array.isArray(data.images) && data.images.length > 0)) {
        const count = data.imageCount || data.images?.length || 0;
        finalOutcome = (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
            <span style={{ 
              display: 'inline-block',
              padding: '2px 8px', 
              borderRadius: 6, 
              background: 'rgba(244, 114, 182, 0.15)', 
              color: 'var(--accent, #f472b6)', 
              fontWeight: 650, 
              fontSize: '0.75rem' 
            }}>
              {count} Results
            </span>
            <span>Retrieved {count} visual assets successfully ✨</span>
          </div>
        );
      } else {
        const entries = Object.entries(data).filter(([k]) => !['status', 'ok', 'provider', 'code', 'mode', 'sessionId'].includes(k));
        if (entries.length > 0) {
          finalOutcome = (
            <div style={{ display: 'grid', gap: 6 }}>
              {entries.map(([k, v]) => {
                const label = k.replace(/([A-Z])/g, ' $1').replace(/^./, (str) => str.toUpperCase());
                return (
                  <div key={k} style={{ fontSize: '0.78rem', display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{ fontWeight: 650, color: 'var(--accent, #f472b6)' }}>{label}:</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{typeof v === 'string' ? v : JSON.stringify(v)}</span>
                  </div>
                );
              })}
            </div>
          );
        } else {
          finalOutcome = isError ? 'Autonomous task stopped or encountered an error.' : 'Autonomous execution completed successfully ✨';
        }
      }
    } else {
      finalOutcome = isError ? 'Autonomous task stopped or encountered an error.' : 'Autonomous execution completed successfully ✨';
    }
    
    const nodes: WorkTreeNode[] = [
      { id: 'start', status: 'success', title: 'Initializing Autonomous Agent', detail: 'Agent spawned successfully.' },
      { id: 'work', status: isError ? 'error' : (data ? 'success' : 'active'), title: 'Deep Researching / Browsing', detail: 'Navigating, reading pages, and analyzing content.' },
    ];
    if (data || isError) {
      nodes.push({
        id: 'done',
        status: isError ? 'error' : 'success',
        title: isError ? 'Execution Interrupted' : 'Task Completed',
        detail: finalOutcome,
      });
    }

    return <WorkTree title="Autonomous Browser Task" icon={<Globe size={16} />} nodes={nodes} />;
  }

  // Render Document / PDF / DOCX Generation Result (ChatGPT Style with Download & Python Code Block)
  if (toolName === 'pdf_generate' || toolName === 'document_generate' || (data && (data.downloadUrl || data.format === 'docx' || data.format === 'pptx'))) {
    const isError = Boolean(data?.error || result?.status === 'error');
    if (isError) {
      return (
        <div style={{ marginTop: 12, padding: 12, borderRadius: 12, background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)' }}>
          <div style={{ color: '#ef4444', fontWeight: 650, fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={14} /> Document Compilation Failed
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', margin: '6px 0 0' }}>
            {data.error || 'Could not compile document.'}
          </p>
        </div>
      );
    }

    const title = data.title || 'Academic Document';
    const filename = data.filename || 'document.pdf';
    const docFormat = (data.format || (filename.endsWith('.docx') ? 'docx' : filename.endsWith('.pptx') ? 'pptx' : 'pdf')).toUpperCase();
    const isDocx = docFormat === 'DOCX';
    const isPptx = docFormat === 'PPTX';
    const badgeColor = isDocx
      ? 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)'
      : isPptx
      ? 'linear-gradient(135deg, #ea580c 0%, #c2410c 100%)'
      : 'linear-gradient(135deg, #ef4444 0%, #be123c 100%)';
    const badgeShadow = isDocx
      ? '0 4px 12px rgba(37, 99, 235, 0.35)'
      : isPptx
      ? '0 4px 12px rgba(234, 88, 12, 0.35)'
      : '0 4px 12px rgba(239, 68, 68, 0.35)';

    const baseDownloadUrl = data.downloadUrl || (data.docId ? `/api/v1/generated-docs/${data.docId}` : '');
    const downloadUrl = baseDownloadUrl
      ? `${baseDownloadUrl}${baseDownloadUrl.includes('?') ? '&' : '?'}filename=${encodeURIComponent(filename)}`
      : '#';
    const pageCount = data.pageCount;
    const fileSizeKb = data.fileSizeKb || 12;
    const pythonSnippet = data.pythonSnippet;

    return (
      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* ChatGPT Style Download Card */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 14,
          padding: '14px 18px',
          borderRadius: 14,
          background: 'linear-gradient(135deg, rgba(244, 114, 182, 0.08) 0%, rgba(20, 16, 28, 0.7) 100%)',
          border: '1px solid rgba(244, 114, 182, 0.3)',
          backdropFilter: 'blur(16px)',
          boxShadow: '0 8px 24px -4px rgba(244, 114, 182, 0.12)',
        }}>
          {/* File icon and info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
            <div style={{
              width: 42,
              height: 42,
              borderRadius: 10,
              background: badgeColor,
              color: '#ffffff',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: badgeShadow,
              flexShrink: 0,
            }}>
              <span style={{ fontSize: '0.62rem', fontWeight: 900, letterSpacing: '0.05em' }}>{docFormat}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
              <span style={{
                fontSize: '0.88rem',
                fontWeight: 650,
                color: 'var(--text-primary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {title}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                <span style={{ fontFamily: 'monospace', color: 'var(--accent, #f472b6)' }}>{filename}</span>
                {typeof pageCount === 'number' && (
                  <>
                    <span>•</span>
                    <span>{pageCount} Pages</span>
                  </>
                )}
                <span>•</span>
                <span>{fileSizeKb} KB</span>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <a
              href={downloadUrl}
              download={filename}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                borderRadius: 999,
                background: 'var(--accent, #f472b6)',
                color: '#ffffff',
                textDecoration: 'none',
                fontSize: '0.8rem',
                fontWeight: 700,
                boxShadow: '0 2px 10px rgba(244, 114, 182, 0.4)',
                cursor: 'pointer',
                transition: 'transform 0.15s ease',
              }}
            >
              <Download size={14} /> Download {docFormat}
            </a>
          </div>
        </div>

        {/* Collapsible Python Analysis / Code block (like ChatGPT) */}
        {pythonSnippet && (
          <div style={{
            borderRadius: 10,
            border: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(15, 12, 22, 0.6)',
            overflow: 'hidden',
          }}>
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              style={{
                width: '100%',
                padding: '7px 12px',
                background: 'transparent',
                border: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                color: 'var(--text-tertiary)',
                fontSize: '0.74rem',
                cursor: 'pointer',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'monospace' }}>
                <Terminal size={12} color="var(--accent, #f472b6)" /> Python Code Interpreter ({pageCount} pages generated)
              </span>
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {expanded && (
              <pre style={{
                margin: 0,
                padding: '10px 14px',
                background: 'rgba(0, 0, 0, 0.4)',
                borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                fontSize: '0.72rem',
                fontFamily: 'monospace',
                color: '#e2e8f0',
                overflowX: 'auto',
                lineHeight: 1.45,
              }}>
                {pythonSnippet}
              </pre>
            )}
          </div>
        )}
      </div>
    );
  }

  // Render images and processing state using WorkTree
  if (
    toolName === 'image_generate' ||
    toolName === 'comfy_ui' ||
    toolName === 'magnific_image_generate' ||
    toolName === 'freepik_image_generate' ||
    toolName === 'magnific_upscale'
  ) {
    const isProcessing = data.status === 'processing';
    
    // Extract image URLs safely from arrays of strings, objects ({url, file_path}), or single properties
    const rawList = Array.isArray(data.images)
      ? data.images
      : data.url
        ? [data.url]
        : data.imageUrl
          ? [data.imageUrl]
          : data.upscaled_path
            ? [data.url || data.upscaled_path]
            : [];

    const imageUrls: string[] = rawList
      .map((item: any) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') return item.url || item.file_path || '';
        return '';
      })
      .filter(Boolean);

    const hasImages = imageUrls.length > 0;
    
    // Determine workflow details
    const onMagnific = data.renderer === 'magnific-flux' || toolName.includes('magnific') || toolName.includes('freepik');
    let workflow = onMagnific ? "MAGNIFIC FLUX · FAST (768x768)" : "HINAA_ANIMA_FAST (768x768)";
    if (data.mode === 'quality') workflow = onMagnific ? "MAGNIFIC FLUX · QUALITY (1024x1024)" : "HINAA_ANIMA_QUALITY (1024x1024)";
    else if (data.mode === 'ultra') workflow = onMagnific ? "MAGNIFIC FLUX · ULTRA + UPSCALE (1024x1536)" : "HINAA_NEWBIE_ULTRA (1024x1536)";

    // Use prompt from params if available
    const promptText = data.prompt || data.details?.[0]?.prompt || "Generating amazing artwork...";

    const toolTitle = toolName === 'magnific_upscale'
      ? 'Magnific AI Upscaler'
      : toolName.includes('magnific')
        ? 'Magnific AI Creative Suite'
        : toolName.includes('freepik')
          ? 'Freepik AI Studio'
          : 'AI Image Generation';

    const workflowDetail = `Workflow: ${workflow} · Mode: ${data.mode || 'Quality'}${
      data.style && data.style !== 'custom' ? ` · Style: ${data.style}` : ''
    }${
      data.reference_applied
        ? data.upscale
          ? ' · Reference-guided · upscaled'
          : ' · Reference-guided'
        : ''
    }`;
    const promptDetail = data.enhanced_prompt
      ? `Enhanced prompt: ${data.enhanced_prompt}`
      : `Prompt: ${promptText}`;
    const errorDetail = data.error || data.message || data.detail || workflowDetail;

    const nodes: WorkTreeNode[] = [
      {
        id: 'prompt',
        status: 'success',
        title: 'Prompt sent to the image model',
        detail: promptDetail,
      },
      hasImages
        ? {
            id: 'image',
            status: 'success',
            title: imageUrls.length > 1 ? `${imageUrls.length} images ready` : 'Image ready',
            detail: workflowDetail,
          }
        : isProcessing
          ? {
              id: 'image',
              status: 'active',
              title: 'Generating the image',
              detail: workflowDetail,
            }
          : {
              id: 'image',
              status: 'error',
              title: 'No image came back',
              detail: errorDetail,
            },
    ];


    return (
      <div style={{ marginTop: 12 }}>
        <WorkTree title={toolTitle} icon={<ImageIcon size={16} />} nodes={nodes} />
        
        {(hasImages || isProcessing) && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12, padding: '0 16px' }}>
            {hasImages && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
                {imageUrls.map((url: string, i: number) => (
                  <motion.a 
                    key={i} 
                    href={url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    style={{ display: 'block', borderRadius: 8, overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                  >
                    <img src={url} alt={`Generated ${i+1}`} style={{ width: '100%', height: 'auto', display: 'block' }} />
                  </motion.a>
                ))}
              </div>
            )}
            
            {isProcessing && (
              <div style={{ display: 'flex', justifyContent: 'center', width: '100%', padding: '10px 0' }}>
                 <ImageGeneration prompt={promptText} resolution={workflow.split(' ')[1]?.replace(/[()]/g, '') || '1024x1024'} />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  if (toolName === 'deep_research') {
    const sources: any[] = Array.isArray(data.sources) ? data.sources : [];
    const items: any[] = Array.isArray(data.items) ? data.items : [];
    const reportHtml: string = typeof data.report === 'string' ? data.report : '';
    const isWorking = sources.length === 0 && !data.error && result.status !== 'error' && !reportHtml;
    const nodes: WorkTreeNode[] = [
      { id: 'fan', status: 'success', title: 'Fanning out research probes', detail: `${sources.length || 6} independent sources queried in parallel${data.depth ? ` · depth ${data.depth}` : ''}` },
      ...(sources.length ? sources.map((source: any) => ({
        id: `src-${source.id}`,
        status: (source.status === 'ok' ? 'success' : source.status === 'failed' ? 'error' : undefined) as WorkTreeNode['status'],
        title: `${source.label} — ${source.count} finding${source.count === 1 ? '' : 's'}`,
        detail: source.error ? `Source did not answer: ${source.error}` : (source.count ? 'Merged into the cited brief.' : 'No relevant results returned.'),
      })) : [{ id: 'wait', status: 'active' as const, title: 'Gathering cited findings', detail: isWorking ? 'Each source answers on its own timer; failures are never fatal.' : 'Sources reported back.' }]),
      ...(items.length ? [{ id: 'merge', status: 'success' as const, title: `Brief ready · ${items.length} findings`, detail: `${Math.round((data.elapsedMs ?? 0) / 100) / 10}s across all sources.` }] : []),
    ];

    return (
      <div style={{ marginTop: 12 }}>
        <WorkTree title={data.topic ? `Deep research · ${data.topic}` : 'Deep research'} icon={<Network size={16} />} nodes={nodes} />
        {items.length > 0 && (
          <div style={{ display: 'grid', gap: 8, marginTop: 12, padding: '0 16px' }}>
            {items.slice(0, 8).map((item: any, index: number) => (
              <motion.a
                key={item.url || index}
                href={item.url || undefined}
                target="_blank"
                rel="noopener noreferrer"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.24, delay: index * 0.03 }}
                whileHover={{ y: -1 }}
                style={{ display: 'grid', gap: 3, padding: '9px 11px', borderRadius: 11, border: '1px solid rgba(255,255,255,.1)', background: 'rgba(255,255,255,.03)', color: '#f4e9df', textDecoration: 'none' }}
              >
                <span style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.4 }}>{item.title || item.url || 'Untitled finding'}</span>
                {item.snippet ? <span style={{ fontSize: 11.5, color: '#cbbca8', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{item.snippet}</span> : null}
                <span style={{ fontSize: 10.5, color: '#a99a8b', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{item.source}{item.stars ? ` · ${item.stars}★` : ''}{item.points ? ` · ${item.points} pts` : ''}{item.published ? ` · ${item.published}` : ''}</span>
              </motion.a>
            ))}
          </div>
        )}
        {reportHtml && (
          <details style={{ margin: '12px 16px 0' }}>
            <summary style={{ cursor: 'pointer', fontSize: 11.5, fontWeight: 750, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#cbbca8' }}>Full cited brief</summary>
          <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '6px 0 0' }}>
            <button
              type="button"
              onClick={() => { void downloadMarkdownPdf(`HINAA research — ${data.topic || 'dossier'}`, reportHtml, 'Deep research dossier').catch(() => undefined); }}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 999, border: '1px solid rgba(255,255,255,.18)', background: 'rgba(255,255,255,.05)', color: '#e9def1', fontSize: 10.5, fontWeight: 750, letterSpacing: '0.04em', cursor: 'pointer' }}
            >
              <Download size={11} /> Download PDF
            </button>
          </div>
            <div className="hinaa-markdown" style={{ marginTop: 8, fontSize: 12.5, lineHeight: 1.65, color: '#e5d8c5' }} dangerouslySetInnerHTML={{ __html: reportHtml }} />
          </details>
        )}
      </div>
    );
  }

  // Render error
  if (data.error || result.status === 'error' || data.status === 'error') {
    const errorMsg = data.error || data.details || "An error occurred";
    return (
      <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: 'rgba(220, 38, 38, 0.08)', border: '1px solid rgba(220, 38, 38, 0.2)' }}>
        <div style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <AlertTriangle size={14} /> Tool Execution Failed ({toolName})
        </div>
        <div style={{ fontSize: '0.8rem', color: '#7f1d1d', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
          {errorMsg}
        </div>
      </div>
    );
  }

  // Generic JSON renderer
  return (
    <div style={{ marginTop: 12, borderRadius: 'var(--radius-md, 10px)', overflow: 'hidden', border: '1px solid var(--border-subtle)', background: 'var(--bg-surface-raised)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{ width: '100%', padding: '9px 14px', background: 'var(--bg-surface)', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
      >
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileJson size={14} color="var(--accent)" /> {toolName} result
        </span>
        {expanded ? <ChevronUp size={14} color="var(--text-tertiary)" /> : <ChevronDown size={14} color="var(--text-tertiary)" />}
      </button>
      
      {expanded && (
        <div style={{ padding: 12, background: 'var(--bg-surface-raised)', borderTop: '1px solid var(--border-subtle)', maxHeight: 300, overflowY: 'auto' }}>
          <pre style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: 'monospace' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
