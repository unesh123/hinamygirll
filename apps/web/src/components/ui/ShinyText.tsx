import { motion } from "framer-motion";

interface ShinyTextProps {
  text: string;
  className?: string;
  speed?: number;
  color?: string;
  shineColor?: string;
}

export function ShinyText({
  text,
  className = "",
  speed = 3,
  color = "rgba(255,255,255,0.65)",
  shineColor = "rgba(255,255,255,1)",
}: ShinyTextProps) {
  return (
    <motion.span
      className={`shiny-text ${className}`}
      style={{
        backgroundImage: `linear-gradient(90deg, ${color} 0%, transparent 30%, ${shineColor} 50%, transparent 70%, ${color} 100%)`,
        backgroundSize: "200% 100%",
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        color: "transparent",
        display: "inline",
      }}
      animate={{ backgroundPosition: ["100% 0%", "-100% 0%"] }}
      transition={{ duration: speed, repeat: Infinity, ease: "linear" }}
    >
      {text}
    </motion.span>
  );
}
