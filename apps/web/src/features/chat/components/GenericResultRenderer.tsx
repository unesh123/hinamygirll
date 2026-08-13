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
          {data.code === 'YOUCOM_IMAGE_ACCESS_REQUIRED' ? <small style={{ display: 'block', marginTop: 6, color: '#cbbca8' }}>This You.com image endpoint is beta and requires early-access permission for the configured key. Local ComfyUI remains HINAA’s private image-generation route.</small> : null}
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
