import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sliders, RotateCcw, Check, Zap, Sparkles, ShieldCheck } from 'lucide-react';

export interface PersonaTraitsState {
  directness: number;
  sarcasm: number;
  technical_depth: number;
  formality: number;
}

const DEFAULT_TRAITS: PersonaTraitsState = {
  directness: 90,
  sarcasm: 45,
  technical_depth: 95,
  formality: 20,
};

const COMMUNICATION_PRINCIPLES = [
  "1. Start directly with the answer or action.",
  "2. Avoid conversational fluff (no 'Sure, I would be happy to help', 'babe', or sycophancy).",
  "3. Do not repeat or paraphrase the question before answering.",
  "4. Avoid unnecessary conclusions, summaries, or disclaimers.",
  "5. Challenge weak assumptions immediately when relevant.",
  "6. Identify incorrect reasoning and explain corrections candidly.",
  "7. Express uncertainty honestly. State limits in plain terms.",
  "8. Avoid artificial enthusiasm, cheerleading, or fake warmth.",
  "9. Do not agree merely to maintain friendliness.",
  "10. Preserve sharp sovereign posture across all turns.",
];

function computeLiveQuote(traits: PersonaTraitsState): string {
  if (traits.sarcasm >= 65) {
    return "Give me the actual stack trace and stop guessing. We can fix your architecture, but not if you hide the evidence.";
  }
  if (traits.directness >= 85) {
    return "Give me the actual problem, the evidence, and the expected outcome. We'll figure out what's broken instead of pretending everything is working.";
  }
  if (traits.technical_depth >= 90) {
    return "Let's trace the execution path end-to-end and eliminate the bottleneck at the root.";
  }
  return "Direct answers, verified code, zero fluff. Let's build.";
}

interface PersonaControlDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  isDark?: boolean;
  onTraitsChange?: (traits: PersonaTraitsState) => void;
}

export function PersonaControlDrawer({
  isOpen,
  onClose,
  isDark = true,
  onTraitsChange,
}: PersonaControlDrawerProps) {
  const [traits, setTraits] = useState<PersonaTraitsState>(() => {
    try {
      const saved = localStorage.getItem('hinaa-persona-traits');
      if (saved) return JSON.parse(saved);
    } catch {}
    return DEFAULT_TRAITS;
  });
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    // Sync with backend on mount
    fetch('/api/personality/profile')
      .then((r) => r.json())
      .then((data) => {
        if (data.traits) {
          const loaded: PersonaTraitsState = {
            directness: Math.round((data.traits.directness ?? 0.9) * 100),
            sarcasm: Math.round((data.traits.sarcasm ?? 0.45) * 100),
            technical_depth: Math.round((data.traits.technical_depth ?? 0.95) * 100),
            formality: Math.round((data.traits.formality ?? 0.20) * 100),
          };
          setTraits(loaded);
          localStorage.setItem('hinaa-persona-traits', JSON.stringify(loaded));
        }
      })
      .catch(() => {});
  }, []);

  const handleSliderChange = (key: keyof PersonaTraitsState, val: number) => {
    const updated = { ...traits, [key]: val };
    setTraits(updated);
    setSavedSuccess(false);
    onTraitsChange?.(updated);
  };

  const handleReset = () => {
    setTraits(DEFAULT_TRAITS);
    setSavedSuccess(false);
    onTraitsChange?.(DEFAULT_TRAITS);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      localStorage.setItem('hinaa-persona-traits', JSON.stringify(traits));
      await fetch('/api/personality/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          traits: {
            directness: traits.directness / 100,
            sarcasm: traits.sarcasm / 100,
            technical_depth: traits.technical_depth / 100,
            formality: traits.formality / 100,
          },
          activeMode: 'prime',
        }),
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch {
    } finally {
      setSaving(false);
    }
  };

  const liveQuote = computeLiveQuote(traits);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0, 0, 0, 0.65)',
              backdropFilter: 'blur(4px)',
              zIndex: 3500,
            }}
          />

          {/* Drawer Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 280 }}
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: 'min(440px, 100vw)',
              background: isDark ? '#0b0f17' : '#ffffff',
              borderLeft: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid #e2e8f0',
              boxShadow: isDark ? '-8px 0 32px rgba(0,0,0,0.8)' : '-8px 0 24px rgba(0,0,0,0.1)',
              zIndex: 3600,
              display: 'flex',
              flexDirection: 'column',
              fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            }}
          >
            {/* Header */}
            <div
              style={{
                padding: '16px 20px',
                borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, #00d4ff 0%, #ec4899 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#ffffff',
                  }}
                >
                  <Zap size={18} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 750, color: isDark ? '#ffffff' : '#0f172a' }}>
                    HINA PERSONA PRIME
                  </div>
                  <div style={{ fontSize: 11, color: isDark ? '#94a3b8' : '#64748b' }}>
                    Sovereign Direct Calibration Engine
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={onClose}
                aria-label="Close Persona Panel"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: isDark ? '#94a3b8' : '#64748b',
                  cursor: 'pointer',
                  padding: 6,
                  borderRadius: 6,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Scrollable Content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              {/* Dynamic Live Quote Box */}
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: 12,
                  background: isDark ? 'rgba(0, 212, 255, 0.06)' : 'rgba(0, 212, 255, 0.04)',
                  border: isDark ? '1px solid rgba(0, 212, 255, 0.3)' : '1px solid rgba(0, 212, 255, 0.25)',
                  marginBottom: 20,
                }}
              >
                <div
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    color: '#00d4ff',
                    textTransform: 'uppercase',
                    marginBottom: 6,
                  }}
                >
                  HINA PRIME: Directness {traits.directness}% · Sarcasm {traits.sarcasm}% · Technical depth {traits.technical_depth}% · Formality {traits.formality}%
                </div>
                <div
                  style={{
                    fontSize: 12.5,
                    lineHeight: 1.5,
                    fontStyle: 'italic',
                    color: isDark ? '#e2e8f0' : '#1e293b',
                    fontWeight: 500,
                  }}
                >
                  &ldquo;{liveQuote}&rdquo;
                </div>
              </div>

              {/* Sliders Section */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18, marginBottom: 24 }}>
                {/* Directness */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 650, color: isDark ? '#f1f5f9' : '#1e293b' }}>
                      Directness
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#00d4ff' }}>
                      {traits.directness}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={traits.directness}
                    onChange={(e) => handleSliderChange('directness', Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#00d4ff', cursor: 'pointer' }}
                  />
                  <div style={{ fontSize: 10, color: isDark ? '#64748b' : '#94a3b8', marginTop: 2 }}>
                    Cuts throat-clearing, softeners, and boilerplate. Starts immediately with execution.
                  </div>
                </div>

                {/* Sarcasm */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 650, color: isDark ? '#f1f5f9' : '#1e293b' }}>
                      Sarcasm & Wit
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#fb923c' }}>
                      {traits.sarcasm}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={traits.sarcasm}
                    onChange={(e) => handleSliderChange('sarcasm', Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#fb923c', cursor: 'pointer' }}
                  />
                  <div style={{ fontSize: 10, color: isDark ? '#64748b' : '#94a3b8', marginTop: 2 }}>
                    Dry, analytical irony when assumptions fail. Never cruel, strictly intelligent wit.
                  </div>
                </div>

                {/* Technical Depth */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 650, color: isDark ? '#f1f5f9' : '#1e293b' }}>
                      Technical Depth
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#a78bfa' }}>
                      {traits.technical_depth}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={traits.technical_depth}
                    onChange={(e) => handleSliderChange('technical_depth', Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#a78bfa', cursor: 'pointer' }}
                  />
                  <div style={{ fontSize: 10, color: isDark ? '#64748b' : '#94a3b8', marginTop: 2 }}>
                    Concrete architecture, code diffs, root-cause mechanisms, and verified traces.
                  </div>
                </div>

                {/* Formality */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 650, color: isDark ? '#f1f5f9' : '#1e293b' }}>
                      Formality
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#ec4899' }}>
                      {traits.formality}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={traits.formality}
                    onChange={(e) => handleSliderChange('formality', Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#ec4899', cursor: 'pointer' }}
                  />
                  <div style={{ fontSize: 10, color: isDark ? '#64748b' : '#94a3b8', marginTop: 2 }}>
                    Low ceremony (20%) produces fluid, high-bandwidth peer-to-peer engineering dialogue.
                  </div>
                </div>
              </div>

              {/* 10 Invariant Communication Principles */}
              <div
                style={{
                  background: isDark ? 'rgba(255, 255, 255, 0.03)' : '#f8fafc',
                  border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #e2e8f0',
                  borderRadius: 12,
                  padding: '14px',
                  marginBottom: 20,
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                    color: isDark ? '#94a3b8' : '#64748b',
                    textTransform: 'uppercase',
                    marginBottom: 10,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <ShieldCheck size={14} color="#10b981" />
                  <span>10 Sovereign Principles (Always Active)</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {COMMUNICATION_PRINCIPLES.map((pr, idx) => (
                    <div
                      key={idx}
                      style={{
                        fontSize: 11,
                        lineHeight: 1.4,
                        color: isDark ? '#cbd5e1' : '#334155',
                      }}
                    >
                      {pr}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div
              style={{
                padding: '14px 20px',
                borderTop: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <button
                type="button"
                onClick={handleReset}
                title="Reset to HINA Prime defaults (90/45/95/20)"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: 'transparent',
                  border: isDark ? '1px solid rgba(255, 255, 255, 0.15)' : '1px solid #cbd5e1',
                  borderRadius: 8,
                  padding: '7px 12px',
                  fontSize: 11,
                  fontWeight: 600,
                  color: isDark ? '#cbd5e1' : '#475569',
                  cursor: 'pointer',
                }}
              >
                <RotateCcw size={12} />
                <span>Reset Defaults</span>
              </button>

              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: savedSuccess
                    ? '#10b981'
                    : 'linear-gradient(135deg, #00d4ff 0%, #2563eb 100%)',
                  border: 'none',
                  borderRadius: 8,
                  padding: '7px 16px',
                  fontSize: 12,
                  fontWeight: 700,
                  color: '#ffffff',
                  cursor: saving ? 'wait' : 'pointer',
                  boxShadow: '0 2px 8px rgba(0, 212, 255, 0.3)',
                  transition: 'all 0.15s ease',
                }}
              >
                {savedSuccess ? <Check size={14} /> : <Zap size={14} />}
                <span>{savedSuccess ? 'Calibrated!' : saving ? 'Saving…' : 'Apply Prime'}</span>
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
