import { useState } from "react";
import { motion } from "framer-motion";
import {
  Globe,
  FolderOpen,
  Monitor,
  Terminal,
  Mail,
  Image,
  FileText,
  Shield,
  Settings,
  ExternalLink,
} from "lucide-react";

/* ── Tool Capability Registry ───────────────────────────── */
interface ToolCapability {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  category: "browser" | "files" | "desktop" | "system" | "external";
  status: "configured" | "unavailable" | "degraded" | "permission_needed";
  riskLevel: "read_only" | "local_mutation" | "external_mutation" | "high_impact";
  bridgeRequired: boolean;
}

const TOOL_REGISTRY: ToolCapability[] = [
  {
    id: "browser_navigate",
    name: "Browser Navigation",
    description: "Navigate websites, fill forms, extract data",
    icon: <Globe size={16} />,
    category: "browser",
    status: "configured",
    riskLevel: "external_mutation",
    bridgeRequired: false,
  },
  {
    id: "file_read",
    name: "File Access",
    description: "Read and write local files",
    icon: <FolderOpen size={16} />,
    category: "files",
    status: "configured",
    riskLevel: "local_mutation",
    bridgeRequired: true,
  },
  {
    id: "desktop_control",
    name: "Desktop Control",
    description: "Launch apps, control windows",
    icon: <Monitor size={16} />,
    category: "desktop",
    status: "unavailable",
    riskLevel: "high_impact",
    bridgeRequired: true,
  },
  {
    id: "shell_command",
    name: "Shell Commands",
    description: "Execute terminal commands",
    icon: <Terminal size={16} />,
    category: "system",
    status: "unavailable",
    riskLevel: "high_impact",
    bridgeRequired: true,
  },
  {
    id: "email_send",
    name: "Email",
    description: "Send and manage emails",
    icon: <Mail size={16} />,
    category: "external",
    status: "configured",
    riskLevel: "external_mutation",
    bridgeRequired: false,
  },
  {
    id: "image_generate",
    name: "Image Generation",
    description: "Generate images via ComfyUI",
    icon: <Image size={16} />,
    category: "external",
    status: "configured",
    riskLevel: "local_mutation",
    bridgeRequired: false,
  },
  {
    id: "document_create",
    name: "Document Creation",
    description: "Create PDFs, DOCX, PPTX",
    icon: <FileText size={16} />,
    category: "external",
    status: "configured",
    riskLevel: "local_mutation",
    bridgeRequired: false,
  },
];

/* ── Component ──────────────────────────────────────────── */
export function OperateMode() {
  const [selectedTool, setSelectedTool] = useState<string | null>(null);
  const selected = TOOL_REGISTRY.find((t) => t.id === selectedTool);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100%",
      overflow: "hidden",
      background: "var(--bg-canvas)",
    }}>
      {/* ── Header ──────────────────────────────── */}
      <header style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 var(--space-4)",
        borderBottom: "1px solid var(--border-subtle)",
        background: "var(--bg-surface)",
        flexShrink: 0,
        height: 48,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <Shield size={16} color="var(--accent)" />
          <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
            Operate
          </span>
        </div>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
          Supervised actions
        </span>
      </header>

      {/* ── Main Content ────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Capabilities list */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "var(--space-4)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
        }}>
          {/* Info banner */}
          <div style={{
            padding: "var(--space-3) var(--space-4)",
            background: "var(--info-bg)",
            border: "1px solid var(--info-border)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}>
            <Shield size={14} color="var(--info-text)" />
            <span style={{ fontSize: "var(--text-xs)", color: "var(--info-text)", fontWeight: 500 }}>
              All external actions require your approval before execution
            </span>
          </div>

          {/* Capabilities grid */}
          <section>
            <h3 style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "var(--space-2)",
            }}>
              Capabilities
            </h3>
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: "var(--space-2)",
            }}>
              {TOOL_REGISTRY.map((tool) => (
                <ToolCard
                  key={tool.id}
                  tool={tool}
                  isSelected={selectedTool === tool.id}
                  onSelect={() => setSelectedTool(selectedTool === tool.id ? null : tool.id)}
                />
              ))}
            </div>
          </section>

          {/* No executions yet — honest empty state */}
          <section>
            <h3 style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "var(--space-2)",
            }}>
              Recent Activity
            </h3>
            <div style={{
              padding: "var(--space-8) var(--space-4)",
              textAlign: "center",
              color: "var(--text-tertiary)",
              fontSize: "var(--text-sm)",
            }}>
              <Shield size={32} style={{ margin: "0 auto var(--space-2)", opacity: 0.3 }} />
              <p>No actions executed yet.</p>
              <p style={{ fontSize: "var(--text-xs)", marginTop: "var(--space-1)" }}>
                Execution receipts will appear here after tool actions are completed.
              </p>
            </div>
          </section>
        </div>

        {/* Selected tool detail panel */}
        {selected && (
          <div style={{
            width: 280,
            borderLeft: "1px solid var(--border-subtle)",
            background: "var(--bg-surface)",
            padding: "var(--space-4)",
            overflowY: "auto",
            flexShrink: 0,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
              <span style={{ color: "var(--accent)" }}>{selected.icon}</span>
              <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
                {selected.name}
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              <DetailRow label="Status" value={selected.status.replace(/_/g, " ")} />
              <DetailRow label="Risk" value={selected.riskLevel.replace(/_/g, " ")} />
              <DetailRow label="Category" value={selected.category} />
              <DetailRow label="Bridge" value={selected.bridgeRequired ? "Required" : "Not needed"} />

              <p style={{
                fontSize: "var(--text-xs)",
                color: "var(--text-secondary)",
                lineHeight: "var(--leading-relaxed)",
                marginTop: "var(--space-2)",
              }}>
                {selected.description}
              </p>

              {selected.status === "unavailable" && (
                <button style={{
                  padding: "var(--space-2) var(--space-3)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--accent)",
                  background: "var(--accent-pale)",
                  color: "var(--accent)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-1)",
                }}>
                  <Settings size={12} />
                  Set up bridge
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Tool Card ──────────────────────────────────────────── */
function ToolCard({ tool, isSelected, onSelect }: { tool: ToolCapability; isSelected: boolean; onSelect: () => void }) {
  const statusConfig = {
    configured: { color: "var(--success)", bg: "var(--success-bg)", border: "var(--success-border)", label: "Active" },
    unavailable: { color: "var(--text-disabled)", bg: "var(--bg-subtle)", border: "var(--border-subtle)", label: "Unavailable" },
    degraded: { color: "var(--warning-text)", bg: "var(--warning-bg)", border: "var(--warning-border)", label: "Degraded" },
    permission_needed: { color: "var(--info-text)", bg: "var(--info-bg)", border: "var(--info-border)", label: "Needs permission" },
  }[tool.status];

  return (
    <motion.button
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      onClick={onSelect}
      style={{
        padding: "var(--space-3)",
        background: "var(--bg-surface)",
        border: `1px solid ${isSelected ? "var(--accent)" : "var(--border-default)"}`,
        borderRadius: "var(--radius-md)",
        cursor: "pointer",
        textAlign: "left",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2)",
        transition: "border-color 150ms ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <span style={{ color: "var(--accent)" }}>{tool.icon}</span>
          <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
            {tool.name}
          </span>
        </div>
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "1px var(--space-1-5, 6px)",
          borderRadius: "var(--radius-pill)",
          background: statusConfig.bg,
          border: `1px solid ${statusConfig.border}`,
        }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: statusConfig.color }} />
          <span style={{ fontSize: "var(--text-xs, 11px)", fontWeight: 600, color: statusConfig.color }}>
            {statusConfig.label}
          </span>
        </div>
      </div>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)", lineHeight: "var(--leading-normal)" }}>
        {tool.description}
      </span>
    </motion.button>
  );
}

/* ── Detail Row ─────────────────────────────────────────── */
function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>{label}</span>
      <span style={{ fontSize: "var(--text-xs)", fontWeight: 500, color: "var(--text-primary)", textTransform: "capitalize" }}>
        {value}
      </span>
    </div>
  );
}
