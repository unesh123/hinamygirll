import { useRef, useMemo } from "react";
import { motion, useInView, type Variants } from "framer-motion";

interface ScrollRevealTextProps {
  text: string;
  className?: string;
  staggerDelay?: number;
  baseOpacity?: number;
  blurStrength?: number;
}

export function ScrollRevealText({
  text,
  className = "",
  staggerDelay = 0.04,
  baseOpacity = 0.15,
  blurStrength = 3,
}: ScrollRevealTextProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(containerRef, { amount: 0.2, once: false });

  const words = useMemo(() => {
    return text.split(/(\s+)/).filter(Boolean);
  }, [text]);

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: staggerDelay, delayChildren: 0.05 } as never,
    },
  };

  const wordVariants: Variants = {
    hidden: {
      opacity: baseOpacity,
      filter: `blur(${blurStrength}px)`,
      y: 8,
    },
    visible: {
      opacity: 1,
      filter: "blur(0px)",
      y: 0,
    },
  };

  return (
    <div ref={containerRef} className={`scroll-reveal-text ${className}`}>
      <motion.span
        variants={containerVariants}
        initial="hidden"
        animate={isInView ? "visible" : "hidden"}
        className="scroll-reveal-inner"
      >
        {words.map((word, i) =>
          /^\s+$/.test(word) ? (
            <span key={i}>{word}</span>
          ) : (
            <motion.span
              key={i}
              variants={wordVariants}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="scroll-reveal-word"
              style={{ display: "inline-block" }}
            >
              {word}
            </motion.span>
          )
        )}
      </motion.span>
    </div>
  );
}
