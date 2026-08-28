import { motion, AnimatePresence } from "framer-motion";
import { Brain, Image, Mail, Music, Search, Smartphone, Zap } from "lucide-react";
import type { ReactNode } from "react";

interface PowerWord {
  word: string;
  icon: ReactNode;
  color: string;
  description: string;
}

const POWER_WORDS: PowerWord[] = [
  { word: "play music", icon: <Music size={15} strokeWidth={1.9} />, color: "#ec4899", description: "Opens YouTube" },
  { word: "search web", icon: <Search size={15} strokeWidth={1.9} />, color: "#3b82f6", description: "Live web search" },
  { word: "show images", icon: <Image size={15} strokeWidth={1.9} />,  color: "#8b5cf6", description: "Fetch images" },
  { word: "deep think", icon: <Brain size={15} strokeWidth={1.9} />, color: "#f59e0b", description: "Extended reasoning" },
  { word: "open app", icon: <Smartphone size={15} strokeWidth={1.9} />, color: "#10b981", description: "Launch web app" },
  { word: "check mail", icon: <Mail size={15} strokeWidth={1.9} />, color: "#06b6d4", description: "Open Gmail" },
  { word: "plasma mode", icon: <Zap size={15} strokeWidth={1.9} />, color: "#a855f7", description: "Visual power mode" },
];

interface PowerWordBadgesProps {
  visible: boolean;
  onTrigger?: (word: string) => void;
}

export function PowerWordBadges({ visible, onTrigger }: PowerWordBadgesProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="power-badges-container"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.p
            className="power-badges-hint"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 0.6, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            ✦ Voice power words
          </motion.p>
          <div className="power-badges-grid">
            {POWER_WORDS.map((pw, i) => (
              <motion.button
                key={pw.word}
                className="power-badge"
                style={{ "--badge-color": pw.color } as React.CSSProperties}
                initial={{ opacity: 0, scale: 0.7, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.7 }}
                transition={{ delay: i * 0.05, type: "spring", stiffness: 300, damping: 20 }}
                whileHover={{ scale: 1.08, y: -2 }}
                whileTap={{ scale: 0.93 }}
                onClick={() => onTrigger?.(pw.word)}
                title={pw.description}
              >
                <span className="power-badge-icon">{pw.icon}</span>
                <span className="power-badge-word">{pw.word}</span>
              </motion.button>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
