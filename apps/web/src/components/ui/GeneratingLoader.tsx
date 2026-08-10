import { motion, AnimatePresence } from "framer-motion";

interface GeneratingLoaderProps {
  visible: boolean;
  label?: string;
}

const letters = ["G", "e", "n", "e", "r", "a", "t", "i", "n", "g"];

export function GeneratingLoader({ visible, label }: GeneratingLoaderProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="generating-loader-wrapper"
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.6 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        >
          <div className="gl-orb" />
          <div className="gl-letters">
            {(label ? label.split("") : letters).map((char, i) => (
              <motion.span
                key={i}
                className="gl-letter"
                animate={{ opacity: [0.3, 1, 0.5, 0.3], scale: [1, 1.18, 1, 1] }}
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
            <span className="gl-letter">…</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
