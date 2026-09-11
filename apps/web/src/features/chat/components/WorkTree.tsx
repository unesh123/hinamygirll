import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, CircleDashed, AlertCircle, Sparkles } from 'lucide-react';

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
      margin: '14px 0',
      padding: '16px 20px',
      background: 'linear-gradient(135deg, rgba(255, 182, 193, 0.06) 0%, rgba(244, 114, 182, 0.03) 50%, rgba(18, 14, 26, 0.65) 100%)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      border: '1px solid rgba(244, 114, 182, 0.22)',
      borderRadius: 'var(--radius-lg, 18px)',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px',
      boxShadow: '0 8px 30px -4px rgba(244, 114, 182, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.06)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        borderBottom: '1px solid rgba(244, 114, 182, 0.15)',
        paddingBottom: '10px',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 26,
          height: 26,
          borderRadius: 8,
          background: 'rgba(244, 114, 182, 0.15)',
          color: 'var(--accent, #f472b6)',
          boxShadow: '0 0 10px rgba(244, 114, 182, 0.25)',
        }}>
          {icon || <Sparkles size={14} />}
        </div>
        <h4 style={{
          margin: 0,
          fontSize: '0.82rem',
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          fontFamily: 'var(--font-heading, inherit)',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}>
          {title}
        </h4>
      </div>
      
      {/* Node list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '2px' }}>
        <AnimatePresence>
          {nodes.map((node, index) => {
            const isLast = index === nodes.length - 1;
            const isActive = node.status === 'active';
            const isSuccess = node.status === 'success';
            const isError = node.status === 'error';

            return (
              <motion.div 
                key={node.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                style={{ display: 'flex', gap: '12px', position: 'relative' }}
              >
                {/* Vertical connector line */}
                {!isLast && (
                  <div style={{
                    position: 'absolute',
                    left: '10px',
                    top: '24px',
                    bottom: '-14px',
                    width: '2px',
                    background: isSuccess 
                      ? 'linear-gradient(to bottom, rgba(52, 211, 153, 0.5), rgba(244, 114, 182, 0.3))' 
                      : 'rgba(244, 114, 182, 0.12)',
                    transition: 'background 0.3s ease',
                  }} />
                )}
                
                {/* Status indicator */}
                <div style={{
                  width: '22px',
                  height: '22px',
                  borderRadius: '50%',
                  flexShrink: 0,
                  marginTop: '1px',
                  background: isSuccess
                    ? 'rgba(52, 211, 153, 0.16)'
                    : isActive
                      ? 'rgba(244, 114, 182, 0.20)'
                      : isError
                        ? 'rgba(244, 63, 94, 0.16)'
                        : 'rgba(255, 255, 255, 0.05)',
                  border: `1.5px solid ${
                    isSuccess
                      ? 'rgba(52, 211, 153, 0.75)'
                      : isActive
                        ? 'var(--accent, #f472b6)'
                        : isError
                          ? 'rgba(244, 63, 94, 0.75)'
                          : 'rgba(255, 255, 255, 0.12)'
                  }`,
                  boxShadow: isActive 
                    ? '0 0 12px rgba(244, 114, 182, 0.55)' 
                    : isSuccess 
                      ? '0 0 8px rgba(52, 211, 153, 0.25)' 
                      : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: isSuccess
                    ? '#34d399'
                    : isActive
                      ? 'var(--accent, #f472b6)'
                      : isError
                        ? '#fb7185'
                        : 'var(--text-tertiary)',
                  zIndex: 1,
                }}>
                  {isSuccess ? (
                    <CheckCircle2 size={13} strokeWidth={2.5} />
                  ) : isActive ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1.4, repeat: Infinity, ease: 'linear' }}
                      style={{ display: 'flex' }}
                    >
                      <CircleDashed size={13} strokeWidth={2.5} />
                    </motion.div>
                  ) : isError ? (
                    <AlertCircle size={13} strokeWidth={2.5} />
                  ) : (
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'rgba(255, 255, 255, 0.25)' }} />
                  )}
                </div>
                
                {/* Text and details */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flexGrow: 1 }}>
                  <span style={{
                    fontSize: '0.84rem',
                    color: isActive ? 'var(--text-primary)' : isSuccess ? 'var(--text-primary)' : 'var(--text-secondary)',
                    fontWeight: isActive ? 650 : 500,
                  }}>
                    {node.title}
                  </span>
                  {node.detail && (
                    <div style={{
                      fontSize: '0.78rem',
                      color: 'var(--text-secondary)',
                      background: 'rgba(255, 255, 255, 0.035)',
                      border: '1px solid rgba(244, 114, 182, 0.14)',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md, 10px)',
                      marginTop: '4px',
                      lineHeight: 1.5,
                      boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.04)',
                    }}>
                      {node.detail}
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
