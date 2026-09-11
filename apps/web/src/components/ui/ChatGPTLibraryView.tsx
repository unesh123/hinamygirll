import { useState, useMemo, useEffect } from "react";
import { Search, FileText, Image as ImageIcon, Presentation, Download, ExternalLink, LayoutGrid, List, MoreVertical, Loader2 } from "lucide-react";

interface LibraryItem {
  id: string;
  name: string;
  type: "image" | "document" | "presentation";
  modified: string;
  size: string;
  url?: string;
}

const DEMO_LIBRARY_ITEMS: LibraryItem[] = [
  {
    id: "lib-1",
    name: "Sakura_OS_Architecture_Overview.pptx",
    type: "presentation",
    modified: "Yesterday",
    size: "152 KB",
  },
  {
    id: "lib-2",
    name: "hinaa_cyberpunk_neon_portrait.png",
    type: "image",
    modified: "Yesterday",
    size: "1.76 MB",
  },
  {
    id: "lib-3",
    name: "mikasa_ackerman_hd_fanart.png",
    type: "image",
    modified: "Today",
    size: "2.25 MB",
  },
  {
    id: "lib-4",
    name: "hinata_hyuga_aesthetic_wallpaper.png",
    type: "image",
    modified: "Today",
    size: "1.42 MB",
  },
  {
    id: "lib-5",
    name: "Quantum_AI_Research_Report.pdf",
    type: "document",
    modified: "Aug 28",
    size: "410 KB",
  },
  {
    id: "lib-6",
    name: "HINAA_Companion_Design_System.md",
    type: "document",
    modified: "Aug 25",
    size: "54.4 KB",
  },
];

interface Props {
  onOpenChat: (initialPrompt?: string) => void;
}

export function ChatGPTLibraryView({ onOpenChat }: Props) {
  const [items, setItems] = useState<LibraryItem[]>(DEMO_LIBRARY_ITEMS);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "images" | "documents">("all");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadLibrary() {
      setLoading(true);
      try {
        const realItems: LibraryItem[] = [];
        const imgRes = await fetch("/api/v1/generated-images?limit=50", {
          headers: { "X-HINAA-Dev-User": "local-web-user" },
        });
        if (imgRes.ok) {
          const imgData = await imgRes.json();
          if (Array.isArray(imgData.images)) {
            for (const img of imgData.images) {
              const cleanPrompt = (img.prompt || "hinaa_creation")
                .slice(0, 30)
                .trim()
                .replace(/[^a-zA-Z0-9_-]/g, "_");
              realItems.push({
                id: `img-${img.id}`,
                name: `${cleanPrompt}.png`,
                type: "image",
                modified: img.created_at ? new Date(img.created_at).toLocaleDateString() : "Today",
                size: "1.2 MB",
                url: img.url,
              });
            }
          }
        }
        if (realItems.length > 0) {
          setItems([...realItems, ...DEMO_LIBRARY_ITEMS]);
        }
      } catch {
        // fallback to demo items
      } finally {
        setLoading(false);
      }
    }
    loadLibrary();
  }, []);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesQuery = item.name.toLowerCase().includes(query.toLowerCase());
      if (!matchesQuery) return false;
      if (filter === "images") return item.type === "image";
      if (filter === "documents") return item.type === "document" || item.type === "presentation";
      return true;
    });
  }, [items, query, filter]);

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "var(--space-6) var(--space-6)",
        background: "var(--bg-canvas)",
        color: "var(--text-primary)",
        minHeight: "100%",
      }}
    >
      <div style={{ maxWidth: 960, width: "100%", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        {/* Header Bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: "1.6rem", fontWeight: 800, fontFamily: "var(--font-heading)" }}>Library</span>
          
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "var(--bg-surface-raised)",
                border: "1px solid var(--border-default)",
                borderRadius: 20,
                padding: "6px 14px",
                width: 240,
              }}
            >
              <Search size={14} color="var(--text-tertiary)" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search..."
                style={{
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  color: "var(--text-primary)",
                  fontSize: "0.85rem",
                  width: "100%",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: 4, background: "var(--bg-secondary)", padding: 3, borderRadius: 8 }}>
              <button
                type="button"
                onClick={() => setViewMode("list")}
                style={{
                  padding: 6,
                  borderRadius: 6,
                  background: viewMode === "list" ? "var(--bg-surface)" : "transparent",
                  border: "none",
                  color: viewMode === "list" ? "var(--accent)" : "var(--text-tertiary)",
                  cursor: "pointer",
                }}
              >
                <List size={16} />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("grid")}
                style={{
                  padding: 6,
                  borderRadius: 6,
                  background: viewMode === "grid" ? "var(--bg-surface)" : "transparent",
                  border: "none",
                  color: viewMode === "grid" ? "var(--accent)" : "var(--text-tertiary)",
                  cursor: "pointer",
                }}
              >
                <LayoutGrid size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Filter Pills (All, Images, Documents matching screenshot 3) */}
        <div style={{ display: "flex", gap: 8, margin: "8px 0" }}>
          {(["all", "images", "documents"] as const).map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setFilter(cat)}
              style={{
                padding: "6px 16px",
                borderRadius: 20,
                border: "1px solid",
                borderColor: filter === cat ? "var(--accent)" : "var(--border-default)",
                background: filter === cat ? "var(--accent-pale)" : "var(--bg-surface-raised)",
                color: filter === cat ? "var(--accent)" : "var(--text-secondary)",
                fontSize: "0.8rem",
                fontWeight: 600,
                cursor: "pointer",
                textTransform: "capitalize",
                transition: "all 0.15s ease",
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Table / List View */}
        {viewMode === "list" ? (
          <div
            style={{
              background: "var(--bg-surface-raised)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg, 14px)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 140px 100px 48px",
                padding: "10px 16px",
                borderBottom: "1px solid var(--border-subtle)",
                fontSize: "0.75rem",
                fontWeight: 700,
                color: "var(--text-tertiary)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              <span>Name</span>
              <span>Modified</span>
              <span>Size</span>
              <span></span>
            </div>

            {filteredItems.map((item) => {
              const Icon =
                item.type === "image"
                  ? ImageIcon
                  : item.type === "presentation"
                    ? Presentation
                    : FileText;
              const iconColor =
                item.type === "image"
                  ? "#ec4899"
                  : item.type === "presentation"
                    ? "#f97316"
                    : "#38bdf8";

              return (
                <div
                  key={item.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 140px 100px 48px",
                    alignItems: "center",
                    padding: "12px 16px",
                    borderBottom: "1px solid var(--border-subtle)",
                    fontSize: "0.85rem",
                    transition: "background 0.12s ease",
                    cursor: "pointer",
                  }}
                  onClick={() => onOpenChat(`tell me about my file ${item.name}`)}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        background: `${iconColor}16`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Icon size={16} color={iconColor} />
                    </div>
                    <span style={{ fontWeight: 600, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.name}
                    </span>
                  </div>

                  <span style={{ color: "var(--text-tertiary)", fontSize: "0.8rem" }}>
                    {item.modified}
                  </span>

                  <span style={{ color: "var(--text-tertiary)", fontSize: "0.8rem" }}>
                    {item.size}
                  </span>

                  <button
                    type="button"
                    title="Options"
                    style={{
                      border: "none",
                      background: "transparent",
                      color: "var(--text-tertiary)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <MoreVertical size={16} />
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          /* Grid View */
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
            {filteredItems.map((item) => (
              <div
                key={item.id}
                onClick={() => onOpenChat(`tell me about my file ${item.name}`)}
                style={{
                  background: "var(--bg-surface-raised)",
                  border: "1px solid var(--border-default)",
                  borderRadius: 14,
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                  cursor: "pointer",
                }}
              >
                <div style={{ height: 100, borderRadius: 8, background: "var(--bg-secondary)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {item.type === "image" ? <ImageIcon size={32} color="#ec4899" /> : <FileText size={32} color="#38bdf8" />}
                </div>
                <div style={{ fontWeight: 650, fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.name}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
                  <span>{item.modified}</span>
                  <span>{item.size}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
