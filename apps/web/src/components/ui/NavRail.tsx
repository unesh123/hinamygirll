import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare, Mic, CheckSquare, FolderOpen, Brain, Wrench, Settings, Plus, ChevronRight, type LucideIcon
} from 'lucide-react';

export type NavSection = 'chat' | 'voice' | 'tasks' | 'files' | 'memory' | 'tools' | 'settings';

interface NavRailProps {
  active: NavSection;
  onNavigate: (s: NavSection) => void;
  onNewChat: () => void;
  onSettings: () => void;
  expanded?: boolean;
}

const ITEMS: Array<{ id: NavSection; icon: LucideIcon; label: string; tooltip: string }> = [
  { id: 'chat', icon: MessageSquare, label: 'Conversations', tooltip: 'Chat' },
  { id: 'voice', icon: Mic, label: 'Voice', tooltip: 'Voice' },
  { id: 'tasks', icon: CheckSquare, label: 'Tasks', tooltip: 'Tasks' },
  { id: 'files', icon: FolderOpen, label: 'Files', tooltip: 'Files' },
  { id: 'memory', icon: Brain, label: 'Memory', tooltip: 'Memory' },
  { id: 'tools', icon: Wrench, label: 'Tools', tooltip: 'Tools' },
];

export function NavRail({ active, onNavigate, onNewChat, onSettings, expanded = false }: NavRailProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <nav
      className={`workspace-nav-rail${expanded ? ' expanded' : ''}`}
      style={{ flexDirection: 'column', alignItems: expanded ? 'flex-start' : 'center' }}
      aria-label="HINAA Navigation"
    >
      {/* Logo */}
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: expanded ? 'flex-start' : 'center', width: '100%', paddingLeft: expanded ? 4 : 0 }}>
        <span style={{ fontSize: '1.3rem', filter: 'drop-shadow(0 0 6px rgba(16,185,129,0.4))' }}>◇</span>
        {expanded && <span style={{ fontWeight: 800, fontSize: '0.9rem', marginLeft: 8, letterSpacing: '-0.02em', color: '#1a1f2e' }}>HINAA</span>}
      </div>

      {/* New Chat */}
      <motion.button
        className="nav-rail-item"
        style={{ marginBottom: 8, background: 'linear-gradient(135deg, rgba(167,243,208,0.5), rgba(103,232,249,0.4))', color: '#059669', border: '1px solid rgba(255,255,255,0.8)', width: expanded ? '100%' : 44, justifyContent: expanded ? 'flex-start' : 'center', gap: 8, paddingLeft: expanded ? 12 : undefined }}
        onClick={onNewChat}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.96 }}
        title="New conversation"
        aria-label="New conversation"
      >
        <Plus size={16} />
        {expanded && <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>New chat</span>}
      </motion.button>

      {/* Nav Items */}
      {ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = active === item.id;
        return (
          <div key={item.id} style={{ position: 'relative', width: expanded ? '100%' : undefined }}>
            <motion.button
              className={`nav-rail-item${isActive ? ' active' : ''}`}
              style={{ width: expanded ? '100%' : 44, justifyContent: expanded ? 'flex-start' : 'center', gap: 8, paddingLeft: expanded ? 12 : undefined }}
              onClick={() => onNavigate(item.id)}
              aria-label={item.label}
              title={item.tooltip}
              onMouseEnter={() => setHovered(item.id)}
              onMouseLeave={() => setHovered(null)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
            >
              <Icon size={17} />
              {expanded && <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>{item.label}</span>}
            </motion.button>
            {/* Tooltip for collapsed state */}
            <AnimatePresence>
              {!expanded && hovered === item.id && (
                <motion.div
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -4 }}
                  style={{
                    position: 'absolute', left: 52, top: '50%', transform: 'translateY(-50%)',
                    background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(12px)',
                    border: '1px solid rgba(255,255,255,0.9)', borderRadius: 10,
                    padding: '5px 12px', fontSize: '0.78rem', fontWeight: 700,
                    color: '#1a1f2e', whiteSpace: 'nowrap', zIndex: 100,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.08)'
                  }}
                >
                  {item.tooltip}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Settings */}
      <motion.button
        className="nav-rail-item"
        style={{ width: expanded ? '100%' : 44, justifyContent: expanded ? 'flex-start' : 'center', gap: 8, paddingLeft: expanded ? 12 : undefined }}
        onClick={onSettings}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.96 }}
        title="Settings"
        aria-label="Settings"
      >
        <Settings size={17} />
        {expanded && <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Settings</span>}
      </motion.button>
    </nav>
  );
}

export default NavRail;
