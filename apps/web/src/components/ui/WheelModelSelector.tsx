import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface WheelOption {
  id: string;
  num: string;
  label: string;
}

interface WheelModelSelectorProps {
  options: WheelOption[];
  selectedId: string;
  onChange: (id: string) => void;
}

export function WheelModelSelector({ options, selectedId, onChange }: WheelModelSelectorProps) {
  const [spinning, setSpinning] = useState(false);

  const selectedIndex = options.findIndex((o) => o.id === selectedId);

  const spin = () => {
    if (spinning) return;
    setSpinning(true);
    const next = (selectedIndex + 1) % options.length;
    setTimeout(() => {
      onChange(options[next].id);
      setSpinning(false);
    }, 500);
  };

  const prevIndex = (selectedIndex - 1 + options.length) % options.length;
  const nextIndex = (selectedIndex + 1) % options.length;

  return (
    <div className="wheel-selector-wrapper" onClick={spin} title="Tap to cycle models">
      <div className="wheel-hint-pop">TAP TO SPIN</div>
      <div className="wheel-panel">
        {/* Decorative dot */}
        <div className="wheel-dot" />
        <div className="glass-overlay" />

        {/* Previous item (blurred top) */}
        <AnimatePresence mode="popLayout">
          <motion.div
            key={`prev-${prevIndex}`}
            className="wheel-item wheel-item-prev"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 0.12, y: 0, filter: "blur(2px)" }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.4, ease: [0.19, 1, 0.22, 1] }}
          >
            <span className="wheel-item-num">{options[prevIndex]?.num}</span>
            <span className="wheel-item-label">{options[prevIndex]?.label}</span>
          </motion.div>
        </AnimatePresence>

        {/* Selected item (sharp center) */}
        <AnimatePresence mode="popLayout">
          <motion.div
            key={`sel-${selectedIndex}`}
            className="wheel-item wheel-item-selected"
            initial={{ opacity: 0, scale: 0.85, filter: "blur(4px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)", x: 10 }}
            exit={{ opacity: 0, scale: 0.85, filter: "blur(4px)" }}
            transition={{ duration: 0.55, ease: [0.19, 1, 0.22, 1] }}
          >
            <span className="wheel-item-num">{options[selectedIndex]?.num}</span>
            <span className="wheel-item-label">{options[selectedIndex]?.label}</span>
          </motion.div>
        </AnimatePresence>

        {/* Next item (blurred bottom) */}
        <AnimatePresence mode="popLayout">
          <motion.div
            key={`next-${nextIndex}`}
            className="wheel-item wheel-item-next"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 0.12, y: 0, filter: "blur(2px)" }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.4, ease: [0.19, 1, 0.22, 1] }}
          >
            <span className="wheel-item-num">{options[nextIndex]?.num}</span>
            <span className="wheel-item-label">{options[nextIndex]?.label}</span>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
