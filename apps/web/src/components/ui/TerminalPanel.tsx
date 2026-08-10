import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface TerminalLine {
  type: "cmd" | "output" | "info" | "success" | "error";
  text: string;
  timestamp?: number;
}

interface TerminalPanelProps {
  visible: boolean;
  lines: TerminalLine[];
  title?: string;
}

export function TerminalPanel({ visible, lines, title = "hinaa.agent" }: TerminalPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="terminal-panel"
          initial={{ opacity: 0, y: 20, scaleY: 0.85 }}
          animate={{ opacity: 1, y: 0, scaleY: 1 }}
          exit={{ opacity: 0, y: 20, scaleY: 0.85 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Terminal header */}
          <div className="terminal-header">
            <div className="terminal-dots">
              <span className="td td-red" />
              <span className="td td-yellow" />
              <span className="td td-green" />
            </div>
            <span className="terminal-title">⚡ {title}</span>
            <span className="terminal-live">LIVE</span>
          </div>

          {/* Terminal body */}
          <div className="terminal-body" ref={scrollRef}>
            <AnimatePresence initial={false}>
              {lines.map((line, i) => (
                <motion.div
                  key={i}
                  className={`terminal-line terminal-${line.type}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25, delay: 0.02 }}
                >
                  {line.type === "cmd" && <span className="terminal-prompt">❯ </span>}
                  {line.type === "success" && <span className="terminal-success-dot">✓ </span>}
                  {line.type === "error" && <span className="terminal-error-dot">✗ </span>}
                  {line.type === "info" && <span className="terminal-info-dot">· </span>}
                  <span className="terminal-text">{line.text}</span>
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Blinking cursor */}
            <div className="terminal-cursor-line">
              <span className="terminal-prompt">❯ </span>
              <motion.span
                className="terminal-cursor"
                animate={{ opacity: [1, 0, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
              >
                █
              </motion.span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
