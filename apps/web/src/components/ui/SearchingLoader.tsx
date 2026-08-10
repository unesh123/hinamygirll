import { motion, AnimatePresence } from "framer-motion";

interface SearchingLoaderProps {
  visible: boolean;
}

const letters = ["S", "e", "a", "r", "c", "h", "i", "n", "g"];

export function SearchingLoader({ visible }: SearchingLoaderProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="searching-loader-wrapper"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.3 }}
        >
          <div className="sl-orb" />
          <div className="sl-letters">
            {letters.map((char, i) => (
              <motion.span
                key={i}
                className="sl-letter"
                animate={{ opacity: [0.35, 1, 0.5, 0.35], scale: [1, 1.18, 1, 1] }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  delay: i * 0.1,
                  ease: "easeInOut",
                }}
              >
                {char}
              </motion.span>
            ))}
            <span className="sl-letter">…</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
