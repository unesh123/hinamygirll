import React, { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';

type ActionMode = 'humanize' | 'review';
type Mode = 'natural' | 'warm' | 'professional' | 'concise';

interface ReviewMetrics {
  wordCount: number;
  englishWordCount: number;
  sentenceCount: number;
  longEnglishSentences: number;
  denseParagraphs: number;
}

interface HumanizeResponse {
  originalText: string;
  humanizedText: string;
  protectedSpans: number;
  externalTextTransfer: boolean;
  mode: string;
  reviewMetrics?: ReviewMetrics;
  reviewIdeas?: string[];
}

export function HumanizerStudio({ onClose }: { onClose?: () => void }) {
  const [inputText, setInputText] = useState('');
  const [outputText, setOutputText] = useState('');
  const [actionMode, setActionMode] = useState<ActionMode>('humanize');
  const [mode, setMode] = useState<Mode>('natural');
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<{ protected: number; external: boolean } | null>(null);
  const [metrics, setMetrics] = useState<ReviewMetrics | null>(null);
  const [ideas, setIdeas] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    if (!inputText.trim()) return;
    
    setIsLoading(true);
    setError(null);
    setStats(null);
    setMetrics(null);
    setIdeas([]);
    setOutputText('');
    
    try {
      const response = await fetch('/api/v1/text/humanize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: inputText,
          mode: mode,
          providerMode: 'local',
          action: actionMode,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to process text');
      }
      
      const data: HumanizeResponse = await response.json();
      
      if (actionMode === 'humanize') {
        setOutputText(data.humanizedText);
      } else {
        if (data.reviewMetrics) setMetrics(data.reviewMetrics);
        if (data.reviewIdeas) setIdeas(data.reviewIdeas);
      }
      
      setStats({
        protected: data.protectedSpans,
        external: data.externalTextTransfer
      });
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', color: '#e2d5e5', display: 'flex', flexDirection: 'column', gap: '20px', height: '100%', background: 'rgba(24, 18, 27, 0.4)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#fdf8ff', margin: 0 }}>Polish & Review Draft</h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#a89eb0' }}>Local-first structure, clarity, and prose improvements</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#a89eb0',
              cursor: 'pointer',
              fontSize: '1.5rem',
              lineHeight: 1
            }}
          >
            &times;
          </button>
        )}
      </div>
      
      {/* Tab Switcher */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '12px' }}>
        {(['humanize', 'review'] as ActionMode[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActionMode(tab)}
            style={{
              padding: '8px 20px',
              borderRadius: '8px',
              border: 'none',
              background: actionMode === tab ? 'rgba(236, 72, 153, 0.15)' : 'transparent',
              color: actionMode === tab ? '#ec4899' : '#a89eb0',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.9rem',
              transition: 'all 0.2s'
            }}
          >
            {tab === 'humanize' ? 'Polish Draft' : 'Review Draft'}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', flex: 1, minHeight: '400px' }}>
        
        {/* Left Column: Input */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label style={{ fontSize: '0.85rem', color: '#a89eb0', fontWeight: 500 }}>Original Draft</label>
            {actionMode === 'humanize' && (
              <div style={{ display: 'flex', gap: '4px' }}>
                {(['natural', 'warm', 'professional', 'concise'] as Mode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '12px',
                      border: '1px solid',
                      borderColor: mode === m ? 'rgba(236, 72, 153, 0.4)' : 'transparent',
                      background: mode === m ? 'rgba(236, 72, 153, 0.1)' : 'transparent',
                      color: mode === m ? '#ec4899' : '#a89eb0',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      textTransform: 'capitalize'
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}
          </div>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Paste your draft here..."
            style={{
              flex: 1,
              background: 'rgba(0, 0, 0, 0.2)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '16px',
              color: '#fdf8ff',
              fontFamily: 'inherit',
              fontSize: '0.9rem',
              resize: 'none',
              outline: 'none',
              lineHeight: 1.5,
            }}
          />
        </div>
        
        {/* Right Column: Output */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <label style={{ fontSize: '0.85rem', color: '#a89eb0', fontWeight: 500 }}>
            {actionMode === 'humanize' ? 'Polished Output' : 'Review Report'}
          </label>
          
          <div style={{
            flex: 1,
            background: 'rgba(0, 0, 0, 0.2)',
            border: '1px solid rgba(236, 72, 153, 0.2)',
            borderRadius: '12px',
            padding: '16px',
            color: '#fdf8ff',
            overflowY: 'auto',
            fontSize: '0.9rem',
            lineHeight: 1.5,
          }}>
            {isLoading ? (
              <div style={{ color: '#a89eb0', fontStyle: 'italic', display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                {actionMode === 'humanize' ? 'Polishing text...' : 'Analyzing draft...'}
              </div>
            ) : actionMode === 'humanize' ? (
              outputText ? outputText : <div style={{ color: '#64748b' }}>Result will appear here</div>
            ) : (
              metrics ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div style={{ background: 'rgba(255,255,255,0.05)', padding: '12px', borderRadius: '8px' }}>
                      <div style={{ fontSize: '1.2rem', fontWeight: 600, color: '#fdf8ff' }}>{metrics.wordCount}</div>
                      <div style={{ fontSize: '0.75rem', color: '#a89eb0' }}>Total Words</div>
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.05)', padding: '12px', borderRadius: '8px' }}>
                      <div style={{ fontSize: '1.2rem', fontWeight: 600, color: '#fdf8ff' }}>{metrics.sentenceCount}</div>
                      <div style={{ fontSize: '0.75rem', color: '#a89eb0' }}>Sentences</div>
                    </div>
                  </div>
                  
                  <div>
                    <h3 style={{ fontSize: '0.9rem', color: '#ec4899', margin: '0 0 8px 0' }}>Revision Ideas</h3>
                    {ideas.length > 0 ? (
                      <ul style={{ margin: 0, paddingLeft: '20px', color: '#fdf8ff', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {ideas.map((idea, idx) => (
                          <li key={idx} style={{ lineHeight: 1.4 }}>{idea}</li>
                        ))}
                      </ul>
                    ) : (
                      <div style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <CheckCircle2 size={18} style={{ color: '#34d399', flexShrink: 0 }} /> Looking good! No major structural flaws detected.
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ color: '#64748b' }}>Report will appear here</div>
              )
            )}
          </div>
        </div>
      </div>
      
      {/* Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ display: 'flex', gap: '16px', fontSize: '0.8rem', color: '#a89eb0' }}>
          {stats && (
            <>
              <span>Protected spans: <strong style={{ color: '#fdf8ff' }}>{stats.protected}</strong></span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                Privacy: <strong style={{ color: '#10b981' }}>{stats.external ? 'Cloud' : 'Local Only'}</strong>
              </span>
            </>
          )}
          {error && <span style={{ color: '#ef4444' }}>{error}</span>}
        </div>
        
        <button
          onClick={handleProcess}
          disabled={isLoading || !inputText.trim()}
          style={{
            padding: '10px 24px',
            borderRadius: '8px',
            border: 'none',
            background: '#ec4899',
            color: '#fff',
            fontWeight: 600,
            cursor: isLoading || !inputText.trim() ? 'not-allowed' : 'pointer',
            opacity: isLoading || !inputText.trim() ? 0.5 : 1,
            transition: 'background 0.2s'
          }}
        >
          {isLoading ? 'Processing...' : (actionMode === 'humanize' ? 'Polish Draft' : 'Review Draft')}
        </button>
      </div>
    </div>
  );
}

export default HumanizerStudio;
