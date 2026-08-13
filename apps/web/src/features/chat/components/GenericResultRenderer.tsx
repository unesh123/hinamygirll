import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Terminal, Image as ImageIcon, FileJson, ChevronDown, ChevronUp, AlertTriangle, Network, Globe } from 'lucide-react';
import { ImageGeneration } from '@/components/ui/image-generation';
import { SourceCard, type SourceItem } from '@/components/ui/SourceCard';
import { WorkTree } from './WorkTree';
import type { WorkTreeNode } from './WorkTree';

interface GenericResultRendererProps {
  toolName: string;
  result: any;
}

export function GenericResultRenderer({ toolName, result }: GenericResultRendererProps) {
  const [expanded, setExpanded] = useState(false);
  const [sourceSaveState, setSourceSaveState] = useState<Record<string, string>>({});

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
        {sources.length ? sources.map((source, index) => <div key={source.id} style={{ display: 'grid', gap: 4 }}><SourceCard source={source} index={index} onSave={saveSourceToProject} />{sourceSaveState[source.id] && <small style={{ color: sourceSaveState[source.id].startsWith('Saved') ? '#86efac' : '#cbbca8', fontSize: 11 }}>{sourceSaveState[source.id]}</small>}</div>) : <div style={{ color: '#cbbca8', fontSize: 12 }}>No attributable sources were returned for this query.</div>}
      </section>
    );
  }

  if (toolName === 'image_search') {
    const images = Array.isArray(data.images) ? data.images.filter((image: any) => image && typeof image.imageUrl === 'string').slice(0, 12) : [];
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
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, color: '#f3e8dd', fontSize: 12, fontWeight: 750 }}>
          <span>Public image results</span><span style={{ color: '#cbbca8', fontWeight: 600 }}>{images.length} result{images.length === 1 ? '' : 's'} · beta</span>
        </div>
        {images.length ? <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 9 }}>
          {images.map((image: any, index: number) => (
            <motion.a key={image.id || image.imageUrl || index} href={image.pageUrl || image.imageUrl} target="_blank" rel="noopener noreferrer" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, delay: index * 0.025 }} whileHover={{ y: -2 }} style={{ overflow: 'hidden', border: '1px solid rgba(255,255,255,.12)', borderRadius: 12, background: '#211823', color: '#f4e9df', textDecoration: 'none' }}>
              <img src={image.imageUrl} alt={image.title || 'Public image result'} loading="lazy" referrerPolicy="no-referrer" style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block', background: '#130d15' }} />
              <span style={{ display: 'block', padding: '7px 8px 8px', fontSize: 11, fontWeight: 650, lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{image.title || 'Open source page'}</span>
            </motion.a>
          ))}
        </div> : <p style={{ color: '#cbbca8', fontSize: 12, margin: 0 }}>No public image links were returned for this query. Try a more specific search.</p>}
        <small style={{ color: '#a99a8b', fontSize: 11, lineHeight: 1.45 }}>Public web image links may have licensing restrictions. Open the source page before saving or reusing an image.</small>
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
    const effortLabel = typeof data.effort === 'string' ? `${data.effort[0].toUpperCase()}${data.effort.slice(1)} research` : null;
    const isBackgroundTask = data.mode === 'research-task' && typeof data.status === 'string' && data.status !== 'completed';
    if (content || detailSources.length || isBackgroundTask) {
      return (
        <section style={{ marginTop: 10, display: 'grid', gap: 10, padding: 13, border: '1px solid rgba(255,219,231,.16)', borderRadius: 15, background: 'linear-gradient(145deg,rgba(46,29,44,.82),rgba(26,17,31,.84))' }} aria-label="Detailed research result">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, color: '#fff2f6' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12, fontWeight: 800 }}><Globe size={14} color="#f5a7bb" />{modeLabel}</span>
            <span style={{ color: '#cbbca8', fontSize: 11, fontWeight: 650 }}>{detailSources.length} attributed source{detailSources.length === 1 ? '' : 's'}</span>
          </div>
          {(effortLabel || isBackgroundTask) ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {effortLabel ? <span style={{ border: '1px solid rgba(238,145,173,.28)', borderRadius: 999, padding: '4px 7px', background: 'rgba(238,145,173,.08)', color: '#ffd4e1', fontSize: 10, fontWeight: 750 }}>{effortLabel}</span> : null}
            {isBackgroundTask ? <span style={{ border: '1px solid rgba(207,184,214,.28)', borderRadius: 999, padding: '4px 7px', background: 'rgba(207,184,214,.08)', color: '#e5d8ff', fontSize: 10, fontWeight: 750 }}>Research task {data.status}</span> : null}
          </div> : null}
          {typeof data.notice === 'string' && data.notice ? <small style={{ color: '#dcc7b2', lineHeight: 1.45 }}>{data.notice}</small> : null}
          {isBackgroundTask && !content ? <p style={{ margin: 0, color: '#e5d7df', fontSize: 12, lineHeight: 1.5 }}>HINAA has a research task in progress. Check its progress after approval to retrieve the cited result.</p> : null}
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
    const isError = data.error || result.status === 'error';
    const isProcessing = !data && result.status !== 'success' && !isError;
    const finalOutcome = typeof data === 'string' ? data : (data.details || JSON.stringify(data));
    
    const nodes: WorkTreeNode[] = [
      { id: 'start', status: 'success', title: 'Initializing Autonomous Agent', detail: 'Agent spawned successfully.' },
      { id: 'work', status: isError ? 'error' : (data ? 'success' : 'active'), title: 'Deep Researching / Browsing', detail: 'Navigating, reading pages, and analyzing content.' },
    ];
    if (data || isError) {
      nodes.push({ id: 'done', status: isError ? 'error' : 'success', title: 'Task Completed', detail: finalOutcome });
    }

    return <WorkTree title="Autonomous Browser Task" icon={<Globe size={16} />} nodes={nodes} />;
  }

  // Render images and processing state using WorkTree
  if (toolName === 'image_generate' || toolName === 'comfy_ui') {
    const isProcessing = data.status === 'processing';
    const hasImages = data.images && Array.isArray(data.images) && data.images.length > 0;
    
    // Determine workflow details
    let workflow = "HINAA_ANIMA_FAST (768x768)";
    if (data.mode === 'quality') workflow = "HINAA_ANIMA_QUALITY (1024x1024)";
    else if (data.mode === 'ultra') workflow = "HINAA_NEWBIE_ULTRA (1024x1536)";

    // Use prompt from params if available
    const promptText = data.prompt || data.details?.[0]?.prompt || "Generating amazing artwork...";

    const nodes: WorkTreeNode[] = [
      { id: '1', status: 'success', title: 'Connecting to AI Canvas', detail: `Workflow: ${workflow} | Mode: ${data.mode || 'Fast'}` },
      { id: '2', status: hasImages ? 'success' : 'active', title: 'Rendering Image(s)', detail: `Prompt: ${promptText}` }
    ];

    return (
      <div style={{ marginTop: 12 }}>
        <WorkTree title="AI Image Generation" icon={<ImageIcon size={16} />} nodes={nodes} />
        
        {(hasImages || isProcessing) && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12, padding: '0 16px' }}>
            {hasImages && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
                {data.images.map((url: string, i: number) => (
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
                 <ImageGeneration prompt={promptText} resolution={workflow.split(' ')[1].replace(/[()]/g, '')} />
              </div>
            )}
          </div>
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
    <div style={{ marginTop: 12, borderRadius: 8, overflow: 'hidden', border: '1px solid rgba(0,0,0,0.1)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{ width: '100%', padding: '8px 12px', background: 'rgba(241, 245, 249, 0.5)', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
      >
        <span style={{ fontSize: '0.75rem', color: '#475569', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileJson size={14} /> {toolName} result
        </span>
        {expanded ? <ChevronUp size={14} color="#64748b" /> : <ChevronDown size={14} color="#64748b" />}
      </button>
      
      {expanded && (
        <div style={{ padding: 12, background: 'rgba(255,255,255,0.8)', borderTop: '1px solid rgba(0,0,0,0.05)', maxHeight: 300, overflowY: 'auto' }}>
          <pre style={{ margin: 0, fontSize: '0.75rem', color: '#334155', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
