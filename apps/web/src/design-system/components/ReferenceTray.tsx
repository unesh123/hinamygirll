import React from "react";
import { X, Plus, Image as ImageIcon, ChevronLeft, ChevronRight } from "lucide-react";
import type { MessageAttachment } from "../../features/companion/types";

export const REFERENCE_ROLES = [
  { id: "subject", label: "Subject" },
  { id: "face", label: "Face" },
  { id: "character", label: "Character" },
  { id: "style", label: "Style" },
  { id: "pose", label: "Pose" },
  { id: "lighting", label: "Lighting" },
  { id: "background", label: "Background" },
  { id: "product", label: "Product" },
] as const;

export type ReferenceRole = (typeof REFERENCE_ROLES)[number]["id"];

export interface ReferenceItem {
  id: string;
  url: string;
  role?: string;
  name?: string;
  assetId?: string;
  mimeType?: string;
}

export interface ReferenceTrayProps {
  references: MessageAttachment[];
  onUpdateRole: (index: number, role: string) => void;
  onRemove: (index: number) => void;
  onReorder?: (fromIndex: number, toIndex: number) => void;
  onAddClick?: () => void;
}

export function ReferenceTray({
  references,
  onUpdateRole,
  onRemove,
  onReorder,
  onAddClick,
}: ReferenceTrayProps) {
  if (!references || references.length === 0) return null;

  return (
    <div
      data-testid="reference-tray"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 8px",
        background: "rgba(243, 244, 246, 0.75)",
        backdropFilter: "blur(8px)",
        borderRadius: 12,
        border: "1px solid rgba(229, 231, 235, 0.8)",
        marginBottom: 8,
        overflowX: "auto",
        scrollbarWidth: "thin",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontSize: 11,
          fontWeight: 700,
          color: "var(--text-muted, #6b7280)",
          textTransform: "uppercase",
          letterSpacing: 0.5,
          paddingRight: 4,
          borderRight: "1px solid #e5e7eb",
        }}
      >
        <ImageIcon size={13} style={{ color: "#ec4899" }} />
        <span>Refs ({references.length})</span>
      </div>

      {references.map((item, idx) => {
        const isImage = !item.mime_type || item.mime_type.startsWith("image/");
        const currentRole = item.role || "subject";

        return (
          <div
            key={item.asset_id || item.url || idx}
            data-testid={`reference-card-${idx}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              padding: "3px 6px",
              boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
              flexShrink: 0,
            }}
          >
            {/* Ordinal Tag */}
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                background: "#f3f4f6",
                color: "#4b5563",
                padding: "2px 5px",
                borderRadius: 4,
              }}
            >
              #{idx + 1}
            </span>

            {/* Thumbnail */}
            {isImage && item.url ? (
              <img
                src={item.url}
                alt={item.filename || `Reference #${idx + 1}`}
                style={{
                  width: 28,
                  height: 28,
                  objectFit: "cover",
                  borderRadius: 4,
                  border: "1px solid #f3f4f6",
                }}
              />
            ) : (
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 4,
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 9,
                  fontWeight: 700,
                  color: "#166534",
                }}
              >
                DOC
              </div>
            )}

            {/* Role Dropdown */}
            <select
              data-testid={`role-select-${idx}`}
              value={currentRole}
              onChange={(e) => onUpdateRole(idx, e.target.value)}
              style={{
                fontSize: 11,
                fontWeight: 600,
                background: "rgba(236, 72, 153, 0.08)",
                color: "#be185d",
                border: "1px solid rgba(236, 72, 153, 0.2)",
                borderRadius: 6,
                padding: "2px 4px",
                cursor: "pointer",
                outline: "none",
              }}
            >
              {REFERENCE_ROLES.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>

            {/* Reorder Buttons if provided */}
            {onReorder && (
              <div style={{ display: "flex", gap: 2 }}>
                {idx > 0 && (
                  <button
                    type="button"
                    title="Move left"
                    onClick={() => onReorder(idx, idx - 1)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 1,
                      color: "#9ca3af",
                    }}
                  >
                    <ChevronLeft size={12} />
                  </button>
                )}
                {idx < references.length - 1 && (
                  <button
                    type="button"
                    title="Move right"
                    onClick={() => onReorder(idx, idx + 1)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 1,
                      color: "#9ca3af",
                    }}
                  >
                    <ChevronRight size={12} />
                  </button>
                )}
              </div>
            )}

            {/* Remove Button */}
            <button
              type="button"
              data-testid={`remove-reference-${idx}`}
              onClick={() => onRemove(idx)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 2,
                color: "#9ca3af",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 4,
              }}
              title="Remove reference"
            >
              <X size={12} />
            </button>
          </div>
        );
      })}

      {/* Add more reference button */}
      {onAddClick && (
        <button
          type="button"
          data-testid="add-reference-btn"
          onClick={onAddClick}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            background: "#ffffff",
            border: "1px dashed #d1d5db",
            borderRadius: 8,
            padding: "4px 8px",
            fontSize: 11,
            fontWeight: 600,
            color: "#4b5563",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          <Plus size={12} />
          <span>Add</span>
        </button>
      )}
    </div>
  );
}
