import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface WorkTreeNode {
  id: string;
  status: 'pending' | 'active' | 'success' | 'error';
  title: string;
  detail?: React.ReactNode;
}

interface WorkTreeProps {
  title: string;
  icon?: React.ReactNode;
  nodes: WorkTreeNode[];
}

export function WorkTree({ title, icon, nodes }: WorkTreeProps) {
  return (
    <div style={{
      margin: '12px 0',
      padding: '16px',
      background: 'rgba(255, 255, 255, 0.03)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '12px' }}>
        {icon && <span style={{ color: 'var(--hinaa-accent, #14b8a6)' }}>{icon}</span>}
        <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#fff', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</h4>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '4px' }}>
        <AnimatePresence>
          {nodes.map((node, index) => (
            <motion.div 
              key={node.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              style={{ display: 'flex', gap: '12px', position: 'relative' }}
            >
              {/* Vertical connector line */}
              {index !== nodes.length - 1 && (
                <div style={{ position: 'absolute', left: '7px', top: '24px', bottom: '-16px', width: '2px', background: 'rgba(255, 255, 255, 0.1)' }} />
              )}
              
              <div style={{ 
                width: '16px', height: '16px', borderRadius: '50%', flexShrink: 0, marginTop: '2px',
                background: node.status === 'success' ? '#10b981' : node.status === 'active' ? '#3b82f6' : node.status === 'error' ? '#ef4444' : 'rgba(255, 255, 255, 0.2)',
                boxShadow: node.status === 'active' ? '0 0 10px rgba(59, 130, 246, 0.5)' : node.status === 'success' ? '0 0 10px rgba(16, 185, 129, 0.4)' : 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                {node.status === 'active' && <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#fff', animation: 'pulse 1s infinite' }} />}
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flexGrow: 1 }}>
                <span style={{ fontSize: '0.9rem', color: node.status === 'active' ? '#fff' : 'rgba(255, 255, 255, 0.8)', fontWeight: node.status === 'active' ? 600 : 400 }}>
                  {node.title}
                </span>
                {node.detail && (
                  <div style={{ fontSize: '0.85rem', color: 'rgba(255, 255, 255, 0.6)', background: 'rgba(0, 0, 0, 0.2)', padding: '8px', borderRadius: '6px', marginTop: '4px' }}>
                    {node.detail}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
