import React from 'react';
import { motion } from 'framer-motion';
import { Search, Sparkles, Briefcase, Mic } from 'lucide-react';

interface WelcomeCard {
  icon: React.ElementType;
  title: string;
  desc: string;
  action: string;
  color: string;
  bgGradient: string;
}

const CARDS: WelcomeCard[] = [
  { icon: Search, title: 'Research something', desc: 'Search the web with sources and analysis', action: 'research', color: '#0891b2', bgGradient: 'linear-gradient(135deg, rgba(103,232,249,0.2), rgba(167,243,208,0.2))' },
  { icon: Sparkles, title: 'Create something', desc: 'Images, documents, plans and ideas', action: 'create', color: '#7c3aed', bgGradient: 'linear-gradient(135deg, rgba(196,181,253,0.2), rgba(103,232,249,0.15))' },
  { icon: Briefcase, title: 'Continue my work', desc: 'Projects, files and tasks', action: 'work', color: '#059669', bgGradient: 'linear-gradient(135deg, rgba(167,243,208,0.2), rgba(103,232,249,0.15))' },
  { icon: Mic, title: 'Talk with HINAA', desc: 'Start a natural live conversation', action: 'voice', color: '#d97706', bgGradient: 'linear-gradient(135deg, rgba(253,230,138,0.2), rgba(167,243,208,0.15))' },
];

interface WelcomeSceneProps {
  userName?: string;
  onAction?: (action: string) => void;
}

export function WelcomeScene({ userName = 'Unesh', onAction }: WelcomeSceneProps) {
  const letters = `Hello, ${userName}`.split('');

  return (
    <div className="welcome-scene">
      {/* Animated greeting */}
      <div>
        <h1 className="welcome-greeting" aria-label={`Hello, ${userName}`}>
          {letters.map((char, i) => (
            <motion.span
              key={i}
              style={{ display: 'inline-block', position: 'relative' }}
              initial={{ opacity: 0, y: 16, filter: 'blur(6px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ delay: i * 0.04 + 0.2, duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
            >
              {char === ' ' ? '\u00A0' : char}
            </motion.span>
          ))}
          {/* Shimmer light pass */}
          <motion.span
            aria-hidden
            style={{
              position: 'absolute', inset: 0, pointerEvents: 'none',
              background: 'linear-gradient(90deg, transparent 0%, rgba(103,232,249,0.4) 50%, transparent 100%)',
              backgroundSize: '200% 100%',
            }}
            initial={{ backgroundPosition: '-100% 0' }}
            animate={{ backgroundPosition: '200% 0' }}
            transition={{ delay: letters.length * 0.04 + 0.6, duration: 0.8, ease: 'easeOut' }}
          />
        </h1>
        <motion.p
          className="welcome-subtitle"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.5 }}
        >
          Main tumhare liye ready hoon. What would you like to do?
        </motion.p>
      </div>

      {/* Capability cards */}
      <motion.div
        className="welcome-cards"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.0, duration: 0.5 }}
      >
        {CARDS.map((card, i) => {
          const Icon = card.icon;
          return (
            <motion.div
              key={card.action}
              className="welcome-card"
              style={{ background: card.bgGradient + ', rgba(255,255,255,0.65)' }}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.1 + i * 0.08 }}
              onClick={() => onAction?.(card.action)}
              whileHover={{ y: -3, scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
            >
              <div className="welcome-card-icon">
                <Icon size={22} style={{ color: card.color }} />
              </div>
              <div className="welcome-card-title">{card.title}</div>
              <div className="welcome-card-desc">{card.desc}</div>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}

export default WelcomeScene;
