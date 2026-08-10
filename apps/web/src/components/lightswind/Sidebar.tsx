// Sidebar — adapted from lightswind.com (open-source)
// Premium collapsible sidebar with framer-motion sliding active indicator

import * as React from "react";
import { ChevronRight, ChevronLeft } from "lucide-react";
import { motion, AnimatePresence, LayoutGroup } from "framer-motion";

// ── Context ───────────────────────────────────────────────────────────────
interface SidebarCtx {
  expanded: boolean;
  setExpanded: (v: boolean) => void;
  activeItem: string | null;
  setActiveItem: (id: string | null) => void;
}
const SidebarContext = React.createContext<SidebarCtx | undefined>(undefined);

export function SidebarProvider({
  defaultExpanded = true,
  children,
}: {
  defaultExpanded?: boolean;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = React.useState(defaultExpanded);
  const [activeItem, setActiveItem] = React.useState<string | null>(null);

  // Collapse on mobile
  React.useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setExpanded(false);
    }
  }, []);

  return (
    <SidebarContext.Provider value={{ expanded, setExpanded, activeItem, setActiveItem }}>
      <LayoutGroup id="sidebar-layout">{children}</LayoutGroup>
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const ctx = React.useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar must be inside SidebarProvider");
  return ctx;
}

// ── Root ─────────────────────────────────────────────────────────────────
export function Sidebar({ className = "", children }: { className?: string; children: React.ReactNode }) {
  const { expanded } = useSidebar();
  return (
    <motion.aside
      className={`hinaa-sidebar ${expanded ? "sidebar-expanded" : "sidebar-collapsed"} ${className}`}
      animate={{ width: expanded ? 240 : 64 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
    >
      {children}
    </motion.aside>
  );
}

// ── Trigger ───────────────────────────────────────────────────────────────
export function SidebarTrigger({ className = "" }: { className?: string }) {
  const { expanded, setExpanded } = useSidebar();
  return (
    <motion.button
      type="button"
      className={`sidebar-trigger ${className}`}
      onClick={() => setExpanded(!expanded)}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={expanded ? "left" : "right"} initial={{ opacity: 0, rotate: -90 }} animate={{ opacity: 1, rotate: 0 }} exit={{ opacity: 0, rotate: 90 }} transition={{ duration: 0.2 }}>
          {expanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </motion.span>
      </AnimatePresence>
    </motion.button>
  );
}

// ── Header ────────────────────────────────────────────────────────────────
export function SidebarHeader({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  const { expanded } = useSidebar();
  return (
    <div className={`sidebar-section sidebar-header ${className}`}>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} transition={{ duration: 0.2 }}>
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Content ───────────────────────────────────────────────────────────────
export function SidebarContent({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const scrollRef = React.useRef<HTMLDivElement>(null);
  return (
    <div className={`sidebar-content-wrapper ${className}`}>
      <div ref={scrollRef} className="sidebar-scroll">
        {children}
      </div>
    </div>
  );
}

// ── Group ─────────────────────────────────────────────────────────────────
export function SidebarGroup({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`sidebar-group ${className}`}>{children}</div>;
}

export function SidebarGroupLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const { expanded } = useSidebar();
  return (
    <AnimatePresence>
      {expanded && (
        <motion.div
          className={`sidebar-group-label ${className}`}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function SidebarGroupContent({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`sidebar-group-content ${className}`}>{children}</div>;
}

// ── Menu ──────────────────────────────────────────────────────────────────
export function SidebarMenu({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`sidebar-menu ${className}`}>{children}</div>;
}

export function SidebarMenuItem({ children, value, className = "" }: { children: React.ReactNode; value?: string; className?: string }) {
  return <div className={`sidebar-menu-item ${className}`} data-value={value}>{children}</div>;
}

export const SidebarMenuButton = React.forwardRef<HTMLButtonElement, {
  children: React.ReactNode;
  value?: string;
  isActive?: boolean;
  onClick?: () => void;
  className?: string;
}>(({ children, value, isActive: propIsActive, onClick, className = "" }, ref) => {
  const { expanded, activeItem, setActiveItem } = useSidebar();
  const isActive = propIsActive ?? (activeItem === value);

  const handleClick = () => {
    if (value) setActiveItem(value);
    onClick?.();
  };

  return (
    <motion.button
      ref={ref}
      type="button"
      className={`sidebar-menu-btn ${isActive ? "active" : ""} ${!expanded ? "collapsed" : ""} ${className}`}
      onClick={handleClick}
      whileHover={{ x: expanded ? 2 : 0 }}
      whileTap={{ scale: 0.97 }}
    >
      {isActive && (
        <motion.div
          layoutId="sidebar-active-indicator"
          className="sidebar-active-bg"
          initial={false}
          transition={{ type: "spring", stiffness: 400, damping: 35 }}
        />
      )}
      <span className={`sidebar-btn-content ${expanded ? "expanded" : "collapsed"}`}>
        {children}
      </span>
    </motion.button>
  );
});
SidebarMenuButton.displayName = "SidebarMenuButton";

// ── Footer ────────────────────────────────────────────────────────────────
export function SidebarFooter({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`sidebar-footer ${className}`}>{children}</div>;
}
