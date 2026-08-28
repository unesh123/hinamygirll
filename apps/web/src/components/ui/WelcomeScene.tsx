import React, { useRef } from 'react';
import { motion } from 'framer-motion';
import { useSpring, animated, config } from '@react-spring/web';
import { Search, Sparkles, Briefcase, Mic, type LucideIcon } from 'lucide-react';

interface WelcomeCard {
  icon: LucideIcon;
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

function WelcomeCardUI({ card, delay, onAction }: { card: WelcomeCard; delay: number; onAction?: (action: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [{ xys }, api] = useSpring(() => ({
    xys: [0, 0, 1], // rx, ry, scale
    config: config.wobbly,
  }));

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const rx = -(y - rect.height / 2) / 10;
    const ry = (x - rect.width / 2) / 10;
    
    api.start({ xys: [rx, ry, 1.02] });
  };
  
  const handlePointerDown = () => {
    api.start({ xys: [0, 0, 0.95], config: { mass: 1, tension: 500, friction: 30 } });
  };

  const handlePointerUp = () => {
    api.start({ xys: [0, 0, 1.02], config: config.wobbly });
  };

  const handlePointerLeave = () => {
    api.start({ xys: [0, 0, 1], config: config.wobbly });
  };

  const Icon = card.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
    >
      <animated.div
        ref={ref}
        className="welcome-card"
        style={{
          background: card.bgGradient + ', rgba(255,255,255,0.65)',
          transform: xys.to((x, y, s) => `perspective(600px) rotateX(${x}deg) rotateY(${y}deg) scale(${s})`),
          cursor: 'pointer',
          willChange: 'transform'
        }}
        onClick={() => onAction?.(card.action)}
        onPointerMove={handlePointerMove}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        onPointerCancel={handlePointerLeave}
      >
        <div className="welcome-card-icon">
          <Icon size={22} style={{ color: card.color }} />
        </div>
        <div className="welcome-card-title">{card.title}</div>
        <div className="welcome-card-desc">{card.desc}</div>
      </animated.div>
    </motion.div>
  );
}

interface WelcomeSceneProps {
  userName?: string;
  onAction?: (action: string) => void;
}

export function WelcomeScene({ userName, onAction }: WelcomeSceneProps) {
  const greeting = userName ? `Hello, ${userName}` : "Hello";
  const letters = greeting.split('');

  return (
    <div className="welcome-scene">
      {/* Animated greeting */}
      <div>
        <h1 className="welcome-greeting" aria-label={greeting}>
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
        {CARDS.map((card, i) => (
          <WelcomeCardUI key={card.action} card={card} delay={1.1 + i * 0.08} onAction={onAction} />
        ))}
      </motion.div>
    </div>
  );
}

export default WelcomeScene;
