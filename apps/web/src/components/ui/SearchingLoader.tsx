import { AnimatePresence, motion } from "framer-motion";
import { Search } from "lucide-react";

interface SearchingLoaderProps {
  visible: boolean;
}

/** A compact header status; detailed progress belongs in the workflow panel. */
export function SearchingLoader({ visible }: SearchingLoaderProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, width: 0, x: 4 }}
          animate={{ opacity: 1, width: "auto", x: 0 }}
          exit={{ opacity: 0, width: 0, x: 4 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          aria-label="Research workflow active"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            minWidth: 0,
            overflow: "hidden",
            padding: "5px 8px",
            border: "1px solid rgba(14,165,233,.20)",
            borderRadius: 999,
            color: "#0369a1",
            background: "rgba(224,242,254,.72)",
            fontSize: 11,
            fontWeight: 750,
            letterSpacing: ".01em",
            whiteSpace: "nowrap",
          }}
        >
          <motion.span
            animate={{ opacity: [0.5, 1, 0.5], scale: [0.94, 1.08, 0.94] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
            style={{ display: "grid", placeItems: "center" }}
          >
            <Search size={13} />
          </motion.span>
          <span>Research planning</span>
          <motion.span
            animate={{ opacity: [0.25, 1, 0.25] }}
            transition={{ duration: 1.15, repeat: Infinity }}
            style={{ display: "flex", gap: 2 }}
            aria-hidden="true"
          >
            {[0, 1, 2].map((dot) => <i key={dot} style={{ width: 3, height: 3, borderRadius: 99, background: "currentColor" }} />)}
          </motion.span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
