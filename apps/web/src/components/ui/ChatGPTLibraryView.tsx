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

function formatSize(sizeKb: number | null | undefined): string {
  if (typeof sizeKb !== "number" || !Number.isFinite(sizeKb)) return "—";
  return sizeKb >= 1024 ? `${(sizeKb / 1024).toFixed(2)} MB` : `${Math.round(sizeKb)} KB`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleDateString();
}

interface Props {
  onOpenChat: (initialPrompt?: string) => void;
}

export function ChatGPTLibraryView({ onOpenChat }: Props) {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "images" | "documents">("all");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    async function loadLibrary() {
      setLoading(true);
      setLoadFailed(false);
      const headers = { "X-HINAA-Dev-User": "local-web-user" };
      try {
        const [imgRes, docRes] = await Promise.all([
          fetch("/api/v1/generated-images?limit=50", { headers }),
          fetch("/api/v1/generated-docs", { headers }),
        ]);
        const loaded: LibraryItem[] = [];
        if (imgRes.ok) {
          const data = await imgRes.json();
          for (const img of Array.isArray(data?.images) ? data.images : []) {
            loaded.push({
              id: `img-${img.id}`,
              name: img.filename || img.id,
              type: "image",
              modified: formatDate(img.created_at),
              size: formatSize(img.sizeKb),
              url: img.url,
            });
          }
        }
        if (docRes.ok) {
          const data = await docRes.json();
          for (const doc of Array.isArray(data?.documents) ? data.documents : []) {
            loaded.push({
              id: `doc-${doc.docId}`,
              name: doc.filename || doc.title || doc.docId,
              type: doc.format === "pptx" ? "presentation" : "document",
              modified: formatDate(doc.createdAt),
              size: formatSize(doc.fileSizeKb),
              url: doc.downloadUrl,
            });
          }
        }
        setItems(loaded);
        setLoadFailed(!imgRes.ok || !docRes.ok);
      } catch {
        // A failed request must read as failed, not as an empty library.
        setItems([]);
        setLoadFailed(true);
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

        {!loading && filteredItems.length === 0 && (
          <div
            data-testid="library-empty-state"
            style={{
              padding: "var(--space-8) var(--space-6)",
              textAlign: "center",
              border: "1px dashed var(--border-default)",
              borderRadius: 14,
              color: "var(--text-secondary)",
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            <span style={{ fontWeight: 650, color: "var(--text-primary)" }}>
              {loadFailed
                ? "Library unavailable"
                : items.length === 0
                  ? "Nothing generated yet"
                  : "No files match this filter"}
            </span>
            <span style={{ fontSize: "0.82rem" }}>
              {loadFailed
                ? "HINAA could not read the generated-files endpoints, so this list is empty rather than fake."
                : items.length === 0
                  ? "Images and documents Hina actually produces will appear here."
                  : "Try clearing the search box or switching back to All."}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
