import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Volume2, Loader2, Square } from 'lucide-react';
export type CompanionState = 'idle' | 'listening' | 'speaking' | 'thinking';

interface HinaaVoiceOrbProps {
  state: CompanionState;
  onStop?: () => void;
  waveform?: number[];
}

export function HinaaVoiceOrb({ state, onStop, waveform = [] }: HinaaVoiceOrbProps) {
  const isActive = state === 'listening' || state === 'speaking' || state === 'thinking';

  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          className="voice-bean-wrapper"
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.9 }}
          transition={{ type: 'spring', stiffness: 400, damping: 28 }}
          style={{
            display: 'flex',
            justifyContent: 'center',
            padding: '16px 20px',
            position: 'absolute',
            bottom: '120px',
            left: 0,
            right: 0,
            zIndex: 50,
            pointerEvents: 'none',
          }}
        >
          {/* Main bean/capsule */}
          <div 
            className={`voice-bean ${state}`} 
            style={{ 
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '10px 20px',
              borderRadius: '30px',
              background: 'rgba(255, 255, 255, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255,255,255,0.9)',
              boxShadow: '0 8px 32px rgba(8, 145, 178, 0.15), 0 2px 8px rgba(0,0,0,0.05)',
              pointerEvents: 'auto',
              minWidth: '180px',
            }}
          >
            {/* Inner animated glow layer based on state */}
            <div style={{
              position: 'absolute', inset: 0, borderRadius: '30px',
              background: state === 'listening' ? 'linear-gradient(90deg, rgba(16,185,129,0.1), rgba(8,145,178,0.1))' :
                          state === 'speaking' ? 'linear-gradient(90deg, rgba(8,145,178,0.15), rgba(167,243,208,0.2))' :
                          'linear-gradient(90deg, rgba(124,58,237,0.1), rgba(8,145,178,0.1))',
              opacity: 0.8,
              pointerEvents: 'none',
              animation: state === 'listening' ? 'bean-breathe 1.5s ease-in-out infinite alternate' : 
                         state === 'speaking' ? 'bean-speak 0.4s ease-in-out infinite alternate' : 'none'
            }} />

            {/* Icon */}
            <motion.div 
              animate={{ scale: state === 'speaking' ? [1, 1.15, 1] : 1 }} 
              transition={{ duration: 0.5, repeat: state === 'speaking' ? Infinity : 0 }}
              style={{ zIndex: 2 }}
            >
              {state === 'listening' && <Mic size={20} style={{ color: '#0891b2' }} />}
              {state === 'thinking' && <Loader2 size={20} style={{ color: '#7c3aed' }} className="animate-spin" />}
              {state === 'speaking' && <Volume2 size={20} style={{ color: '#059669' }} />}
            </motion.div>

            {/* State label & Waveform */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, zIndex: 2 }}>
              <motion.span
                style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1e293b' }}
                key={state}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
              >
                {state === 'listening' ? 'Listening' : state === 'thinking' ? 'Thinking' : 'Speaking'}
              </motion.span>

              {/* Waveform */}
              {waveform.length > 0 && state !== 'thinking' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 24, marginLeft: 'auto' }}>
                  {waveform.slice(0, 10).map((amp, i) => (
                    <motion.div
                      key={i}
                      style={{
                        width: 3, borderRadius: 2,
                        background: state === 'speaking' ? '#10b981' : '#0891b2'
                      }}
                      animate={{ height: Math.max(4, amp * 20) }}
                      transition={{ duration: 0.08 }}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Stop button inside the bean */}
            {onStop && (
              <motion.button
                onClick={onStop}
                style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'rgba(239,68,68,0.1)',
                  color: '#ef4444', border: 'none',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  zIndex: 2, marginLeft: 8
                }}
                whileHover={{ scale: 1.1, background: 'rgba(239,68,68,0.15)' }}
                whileTap={{ scale: 0.9 }}
                title="Stop"
              >
                <Square size={12} fill="currentColor" />
              </motion.button>
            )}
            
            <style>{`
              @keyframes bean-breathe {
                0% { opacity: 0.4; }
                100% { opacity: 0.8; }
              }
              @keyframes bean-speak {
                0% { opacity: 0.5; }
                100% { opacity: 1; }
              }
            `}</style>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default HinaaVoiceOrb;
