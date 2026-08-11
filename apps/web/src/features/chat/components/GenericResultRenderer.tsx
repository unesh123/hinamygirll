import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Terminal, Image as ImageIcon, FileJson, ChevronDown, ChevronUp, AlertTriangle, Network, Globe } from 'lucide-react';
import { ImageGeneration } from '@/components/ui/image-generation';
import { WorkTree, WorkTreeNode } from './WorkTree';

interface GenericResultRendererProps {
  toolName: string;
  result: any;
}

export function GenericResultRenderer({ toolName, result }: GenericResultRendererProps) {
  const [expanded, setExpanded] = useState(false);
  
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
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{ padding: '6px 12px', background: '#059669', color: 'white', border: 'none', borderRadius: 4, fontSize: '0.75rem', cursor: 'pointer' }}>Allow</button>
          <button style={{ padding: '6px 12px', background: 'transparent', color: '#475569', border: '1px solid #cbd5e1', borderRadius: 4, fontSize: '0.75rem', cursor: 'pointer' }}>Deny</button>
        </div>
      </div>
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
