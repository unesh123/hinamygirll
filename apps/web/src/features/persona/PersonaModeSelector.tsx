import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageCircle,
  Flame,
  Zap,
  Brain,
  Leaf,
  PartyPopper,
  Briefcase,
  ChevronDown,
} from 'lucide-react';

export type PersonaMode =
  | 'companion'
  | 'roast'
  | 'unfiltered'
  | 'deep'
  | 'sage'
  | 'playful'
  | 'professional';

interface PersonaConfig {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  label: string;
  emoji: string;
  color: string;
  bg: string;
  glow: string;
  description: string;
}

const PERSONA_CONFIG: Record<PersonaMode, PersonaConfig> = {
  companion: {
    icon: MessageCircle,
    label: 'Companion',
    emoji: '💕',
    color: '#f472b6',
    bg: 'rgba(244,114,182,0.12)',
    glow: 'rgba(244,114,182,0.3)',
    description: 'Sweet girlfriend warmth',
  },
  roast: {
    icon: Flame,
    label: 'Roast',
    emoji: '🔥',
    color: '#fb923c',
    bg: 'rgba(251,146,60,0.12)',
    glow: 'rgba(251,146,60,0.3)',
    description: 'Affectionate sharp wit',
  },
  unfiltered: {
    icon: Zap,
    label: 'Unfiltered',
    emoji: '💬',
    color: '#facc15',
    bg: 'rgba(250,204,21,0.12)',
    glow: 'rgba(250,204,21,0.3)',
    description: 'Raw zero-BS honesty',
  },
  deep: {
    icon: Brain,
    label: 'Deep',
    emoji: '🧠',
    color: '#a78bfa',
    bg: 'rgba(167,139,250,0.12)',
    glow: 'rgba(167,139,250,0.3)',
    description: 'Full cognitive power',
  },
  sage: {
    icon: Leaf,
    label: 'Sage',
    emoji: '🌿',
    color: '#34d399',
    bg: 'rgba(52,211,153,0.12)',
    glow: 'rgba(52,211,153,0.3)',
    description: 'Calm profound wisdom',
  },
  playful: {
    icon: PartyPopper,
    label: 'Playful',
    emoji: '🎉',
    color: '#22d3ee',
    bg: 'rgba(34,211,238,0.12)',
    glow: 'rgba(34,211,238,0.3)',
    description: 'Chaos gremlin energy',
  },
  professional: {
    icon: Briefcase,
    label: 'Pro',
    emoji: '💼',
    color: '#94a3b8',
    bg: 'rgba(148,163,184,0.12)',
    glow: 'rgba(148,163,184,0.3)',
    description: 'Executive precision',
  },
};

interface PersonaModeSelectorProps {
  value: PersonaMode;
  onChange: (mode: PersonaMode) => void;
  compact?: boolean;
  className?: string;
}

export function PersonaModeSelector({
  value,
  onChange,
  compact = false,
  className,
}: PersonaModeSelectorProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const cfg = PERSONA_CONFIG[value];
  const Icon = cfg.icon;

  /* close on outside click */
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ position: 'relative', display: 'inline-flex' }}
    >
      {/* Trigger pill */}
      <motion.button
        onClick={() => setOpen(o => !o)}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.96 }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          padding: compact ? '3px 9px' : '5px 12px',
          borderRadius: 20,
          border: `1px solid ${cfg.color}55`,
          background: cfg.bg,
          color: cfg.color,
          cursor: 'pointer',
          fontSize: compact ? 11 : 12,
          fontWeight: 600,
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          boxShadow: open ? `0 0 12px ${cfg.glow}` : 'none',
          transition: 'box-shadow 0.2s',
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ fontSize: compact ? 13 : 14 }}>{cfg.emoji}</span>
        {!compact && (
          <span style={{ letterSpacing: '-0.01em' }}>{cfg.label}</span>
        )}
        <ChevronDown
          size={10}
          strokeWidth={2.5}
          style={{
            opacity: 0.65,
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.18s',
          }}
        />
      </motion.button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}
            style={{
              position: 'absolute',
              top: 'calc(100% + 6px)',
              left: 0,
              zIndex: 9999,
              background: 'rgba(8,8,14,0.96)',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 18,
              padding: '6px 6px',
              minWidth: 232,
              boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 0 0.5px rgba(255,255,255,0.04)',
            }}
          >
            {/* Header */}
            <div
              style={{
                fontSize: 9,
                color: 'rgba(255,255,255,0.3)',
                padding: '3px 10px 7px',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                fontWeight: 600,
              }}
            >
              Hina's Persona Mode
            </div>

            {/* Mode rows */}
            {(Object.entries(PERSONA_CONFIG) as [PersonaMode, PersonaConfig][]).map(
              ([mode, c]) => {
                const ModeIcon = c.icon;
                const isActive = mode === value;
                return (
                  <motion.button
                    key={mode}
                    onClick={() => { onChange(mode); setOpen(false); }}
                    whileHover={{ x: 3, background: `${c.color}18` }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      width: '100%',
                      padding: '7px 10px',
                      borderRadius: 11,
                      border: 'none',
                      background: isActive ? c.bg : 'transparent',
                      color: isActive ? c.color : 'rgba(255,255,255,0.72)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'background 0.12s',
                      boxSizing: 'border-box',
                    }}
                  >
                    {/* Emoji badge */}
                    <span
                      style={{
                        fontSize: 17,
                        lineHeight: 1,
                        filter: isActive ? 'none' : 'grayscale(0.35)',
                      }}
                    >
                      {c.emoji}
                    </span>

                    {/* Text */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, fontWeight: isActive ? 700 : 500, lineHeight: 1.2 }}>
                        {c.label}
                      </div>
                      <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.38)', lineHeight: 1.2 }}>
                        {c.description}
                      </div>
                    </div>

                    {/* Active dot */}
                    {isActive && (
                      <motion.div
                        layoutId="persona-active-dot"
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: c.color,
                          boxShadow: `0 0 8px ${c.glow}`,
                          flexShrink: 0,
                        }}
                      />
                    )}
                  </motion.button>
                );
              }
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
