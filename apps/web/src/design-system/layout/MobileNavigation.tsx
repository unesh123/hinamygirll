import { motion } from "framer-motion";
import { MessageCircle, Sparkles, FolderKanban, ShieldCheck, MoreHorizontal } from "lucide-react";
import type { NavSection } from "./NavigationRail";

interface MobileNavigationProps {
  active: NavSection;
  onNavigate: (section: NavSection) => void;
  onOpenMore: () => void;
}

const TAB_ITEMS: Array<{
  id: NavSection;
  label: string;
  icon: React.ReactNode;
}> = [
  { id: "chat", label: "Chat", icon: <MessageCircle size={20} /> },
  { id: "studio", label: "Runway 3D", icon: <Sparkles size={20} /> },
  { id: "projects", label: "Projects", icon: <FolderKanban size={20} /> },
  { id: "vault", label: "VIP Vault", icon: <ShieldCheck size={20} /> },
];

export function MobileNavigation({
  active,
  onNavigate,
  onOpenMore,
}: MobileNavigationProps) {
  return (
    <nav
      className="sakura-mobile-nav"
      aria-label="HINAA mobile navigation"
    >
      {TAB_ITEMS.map((item) => (
        <motion.button
          key={item.id}
          type="button"
          onClick={() => onNavigate(item.id)}
          aria-label={item.label}
          aria-current={active === item.id ? "page" : undefined}
          whileTap={{ scale: 0.92 }}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 2,
            padding: "var(--space-1-5) var(--space-3)",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: active === item.id ? "var(--accent-pale)" : "transparent",
            color: active === item.id ? "var(--accent)" : "var(--text-tertiary)",
            cursor: "pointer",
            fontSize: "var(--text-xs)",
            fontWeight: active === item.id ? 600 : 500,
            fontFamily: "var(--font-body)",
            minWidth: 56,
            transition: "background var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard)",
          }}
        >
          <span style={{ display: "flex" }}>{item.icon}</span>
          <span>{item.label}</span>
        </motion.button>
      ))}

      <motion.button
        type="button"
        onClick={onOpenMore}
        aria-label="More options"
        whileTap={{ scale: 0.92 }}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 2,
          padding: "var(--space-1-5) var(--space-3)",
          borderRadius: "var(--radius-md)",
          border: "none",
          background: "transparent",
          color: "var(--text-tertiary)",
          cursor: "pointer",
          fontSize: "var(--text-xs)",
          fontWeight: 500,
          fontFamily: "var(--font-body)",
          minWidth: 56,
        }}
      >
        <MoreHorizontal size={20} />
        <span>More</span>
      </motion.button>

      <style>{`
        .sakura-mobile-nav {
          display: none;
          position: fixed;
          bottom: 0;
          left: 0;
          right: 0;
          background: var(--surface-overlay, rgba(15, 17, 23, 0.94));
          backdrop-filter: blur(24px) saturate(1.4);
          -webkit-backdrop-filter: blur(24px) saturate(1.4);
          border-top: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
          padding: 6px 12px;
          padding-bottom: max(8px, env(safe-area-inset-bottom, 8px));
          z-index: 1000;
          justify-content: space-around;
          align-items: center;
          gap: 4px;
          box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
        }

        @media (max-width: 768px) {
          .sakura-mobile-nav {
            display: flex;
          }
        }
      `}</style>
    </nav>
  );
}
