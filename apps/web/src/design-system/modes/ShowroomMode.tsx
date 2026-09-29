import React, { useState, useEffect, useRef, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  ArrowRight,
  Shield,
  Zap,
  Terminal,
  Cpu,
  Layers,
  ChevronRight,
  Eye,
  Radio,
  ExternalLink,
  Code,
  Compass,
  Check,
} from "lucide-react";
import { VRMAvatar } from "../../features/avatar/VRMAvatar";
import { CipherDecoderText, GyroOrbLoader } from "../../components/ui/HinaCyberLoaders";

export interface ShowroomModeProps {
  onEnterWorkspace?: () => void;
  onEnterTalk?: () => void;
  selectedAvatarModel?: string;
  onSelectAvatarModel?: (modelUrl: string) => void;
}

interface FashionCollectionItem {
  id: string;
  index: string;
  name: string;
  modelUrl: string;
  subtitle: string;
  tagline: string;
  energyPulse: string;
  styleDna: string;
  codeEssence: string;
  accentColor: string;
  bgGradient: string;
  description: string;
  badge: string;
}

const COLLECTIONS: FashionCollectionItem[] = [
  {
    id: "oraniths",
    index: ".01",
    name: "ORANITHS",
    modelUrl: "/models/hinaa-original.vrm",
    subtitle: "Future-Playful Cyber Floral",
    tagline: "Radiant rebels of light, dancing fearlessly at creation's edge.",
    energyPulse: "VIBRANT ORANGE",
    styleDna: "FUTURE-PLAYFUL",
    codeEssence: "CREATIVE CHAOS",
    accentColor: "#ff7a00",
    bgGradient: "radial-gradient(circle at center, rgba(255, 122, 0, 0.15), transparent 70%)",
    description: "Their electric essence shapes the future through bold neural innovation and generative vision.",
    badge: "COLLECTION 01",
  },
  {
    id: "anturax",
    index: ".02",
    name: "ANTURAX",
    modelUrl: "/models/model_6164.vrm",
    subtitle: "Haute-Couture Kimono Neon",
    tagline: "Fiber-optic silk woven with ancient Japanese elegance.",
    energyPulse: "CRIMSON LASER",
    styleDna: "AVANT-GARDE TRADITION",
    codeEssence: "NEURO-HARMONY",
    accentColor: "#ff2a5f",
    bgGradient: "radial-gradient(circle at center, rgba(255, 42, 95, 0.16), transparent 70%)",
    description: "Traditional silhouettes reconstructed through laser-cut organza and bio-luminescent thread.",
    badge: "COLLECTION 02",
  },
  {
    id: "cybersphere",
    index: ".03",
    name: "CYBERSPHERE",
    modelUrl: "/models/model_5447.vrm",
    subtitle: "Streetwear Cyberpunk Casual",
    tagline: "High-frequency urban mobility engineered for augmented reality.",
    energyPulse: "ULTRA VIOLET",
    styleDna: "TACTICAL CASUAL",
    codeEssence: "QUANTUM EFFICIENCY",
    accentColor: "#8b5cf6",
    bgGradient: "radial-gradient(circle at center, rgba(139, 92, 246, 0.16), transparent 70%)",
    description: "Modular techwear tailored for hackers, terminal operators, and deep-space researchers.",
    badge: "COLLECTION 03",
  },
  {
    id: "scholastic",
    index: ".04",
    name: "AKADEMIA",
    modelUrl: "/models/AvatarSample_E.vrm",
    subtitle: "Collegiate VIP Deep Vault",
    tagline: "Institutional academic precision paired with elite cognitive models.",
    energyPulse: "EMERALD SYNAPSE",
    styleDna: "OXFORD RESEARCH",
    codeEssence: "PROVABLE REASONING",
    accentColor: "#10b981",
    bgGradient: "radial-gradient(circle at center, rgba(16, 185, 129, 0.16), transparent 70%)",
    description: "Designed for university faculty, campus researchers, and students mastering defensive cybersecurity.",
    badge: "VIP VAULT",
  },
];

export const ShowroomMode: React.FC<ShowroomModeProps> = memo(({
  onEnterWorkspace,
  onEnterTalk,
  selectedAvatarModel = "/models/hinaa-original.vrm",
  onSelectAvatarModel,
}) => {
  const [activeItem, setActiveItem] = useState<FashionCollectionItem>(COLLECTIONS[0]);
  const [mouseCoords, setMouseCoords] = useState({ x: 0.0412, y: 0.0306 });
  const [viewMode, setViewMode] = useState<"lookbook" | "runway" | "steep_analytics">("lookbook");
  const [searchQuery, setSearchQuery] = useState("");

  // Track mouse coordinates for the cyber HUD telemetry
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width).toFixed(4);
    const y = ((e.clientY - rect.top) / rect.height).toFixed(4);
    setMouseCoords({ x: parseFloat(x), y: parseFloat(y) });
  };

  const handleSelectItem = (item: FashionCollectionItem) => {
    setActiveItem(item);
    if (onSelectAvatarModel) {
      onSelectAvatarModel(item.modelUrl);
    }
  };

  return (
    <div
      className="dich-showroom-root"
      onMouseMove={handleMouseMove}
      style={{
        position: "relative",
        width: "100%",
        minHeight: "calc(100vh - 56px)",
        background: "#fbf6f0",
        color: "#17191c",
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        overflowY: "auto",
        overflowX: "hidden",
        boxSizing: "border-box",
        padding: "16px 24px 60px 24px",
      }}
    >
      {/* ── Outer HUD Framing ──────────────────────────────── */}
      <div
        className="dich-outer-frame"
        style={{
          position: "relative",
          maxWidth: 1360,
          margin: "0 auto",
          border: "1.5px solid rgba(23, 25, 28, 0.12)",
          borderRadius: 24,
          background: "#f7efe4",
          boxShadow: "0 20px 48px -8px rgba(0, 0, 0, 0.08)",
          overflow: "hidden",
        }}
      >
        {/* Corner HUD Brackets */}
        <div className="dich-corner-bracket dich-corner-tl" />
        <div className="dich-corner-bracket dich-corner-tr" />
        <div className="dich-corner-bracket dich-corner-bl" />
        <div className="dich-corner-bracket dich-corner-br" />

        {/* ── Top Cyber HUD Bar ────────────────────────────── */}
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 24px",
            borderBottom: "1px solid rgba(23, 25, 28, 0.08)",
            background: "rgba(255, 255, 255, 0.4)",
            backdropFilter: "blur(12px)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div className="dich-pulse-wave">
              <span>/\/\/\-</span>
              <span>LIVE</span>
            </div>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                letterSpacing: "0.08em",
                color: "#5d2a1a",
                fontWeight: 600,
              }}
            >
              HINAA // OMEGA HAUTE-COUTURE
            </span>
          </div>

          {/* Navigation Pill Switcher */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              background: "rgba(23, 25, 28, 0.06)",
              padding: "3px 4px",
              borderRadius: 9999,
            }}
          >
            <button
              type="button"
              onClick={() => setViewMode("lookbook")}
              style={{
                border: "none",
                background: viewMode === "lookbook" ? "#17191c" : "transparent",
                color: viewMode === "lookbook" ? "#ffffff" : "#5d2a1a",
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 14px",
                borderRadius: 9999,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              LOOKBOOK .01
            </button>
            <button
              type="button"
              onClick={() => setViewMode("runway")}
              style={{
                border: "none",
                background: viewMode === "runway" ? "#17191c" : "transparent",
                color: viewMode === "runway" ? "#ffffff" : "#5d2a1a",
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 14px",
                borderRadius: 9999,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              RUNWAY GALLERY
            </button>
            <button
              type="button"
              onClick={() => setViewMode("steep_analytics")}
              style={{
                border: "none",
                background: viewMode === "steep_analytics" ? "#17191c" : "transparent",
                color: viewMode === "steep_analytics" ? "#ffffff" : "#5d2a1a",
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 14px",
                borderRadius: 9999,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              EDITORIAL ANALYTICS
            </button>
          </div>

          {/* Right Telemetry */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: "#787574",
            }}
          >
            <span>X .0{Math.floor(mouseCoords.x * 1000)} // Y .0{Math.floor(mouseCoords.y * 1000)}</span>
            <button
              type="button"
              onClick={onEnterWorkspace}
              style={{
                background: "#17191c",
                color: "#ffffff",
                border: "none",
                padding: "5px 14px",
                borderRadius: 9999,
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              WORKSPACE →
            </button>
          </div>
        </header>

        {/* ── VIEW 1: DICH FASHION LOOKBOOK HERO (Screenshot 1) ── */}
        {viewMode === "lookbook" && (
          <div
            style={{
              padding: "36px 32px 48px 32px",
              display: "grid",
              gridTemplateColumns: "1.1fr 1.6fr 1.1fr",
              gap: 24,
              alignItems: "center",
              minHeight: 580,
            }}
          >
            {/* Left Column: Cyber Code Metadata & Micro Ticks */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 20,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                lineHeight: 1.65,
                color: "#332f2d",
              }}
            >
              <div style={{ color: "#787574", letterSpacing: "0.08em" }}>
                +++ <br />
                DARE_TO_DISRUPT <br />
                &lt;META CHARSET=UTF-8&gt;
              </div>

              <div
                style={{
                  background: "rgba(255, 255, 255, 0.6)",
                  padding: "16px 18px",
                  borderRadius: 16,
                  border: "1px solid rgba(23, 25, 28, 0.08)",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.03)",
                }}
              >
                <div style={{ color: activeItem.accentColor, fontWeight: 700, marginBottom: 4 }}>
                  &lt;BODY (
                </div>
                <div>SERIE#OMEGA_V2</div>
                <div>ENERGY-PULSE: {activeItem.energyPulse}</div>
                <div style={{ margin: "6px 0", opacity: 0.4 }}>+++</div>
                <div>STYLE-DNA: {activeItem.styleDna}</div>
                <div>CODE-ESSENCE: {activeItem.codeEssence}</div>
                <div style={{ marginTop: 8, fontWeight: 700, color: "#17191c" }}>
                  DISRUPT. CREATE. DOMINATE )
                </div>
              </div>

              {/* Reticle Crosshair */}
              <div style={{ display: "flex", alignItems: "center", gap: 10, opacity: 0.6 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    border: "1px dashed #17191c",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <div style={{ width: 6, height: 6, background: activeItem.accentColor }} />
                </div>
                <span>STYLE=UTF-1 // LIVE</span>
              </div>
            </div>

            {/* Center Column: Iconic Circular Cyber-Fashion Viewport */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                position: "relative",
              }}
            >
              <div
                className="dich-circular-lens"
                style={{
                  position: "relative",
                  width: 380,
                  height: 380,
                  borderRadius: "50%",
                  border: "2px solid #17191c",
                  boxShadow: `0 0 0 10px rgba(255,255,255,0.7), 0 20px 48px -10px ${activeItem.accentColor}33`,
                  background: activeItem.bgGradient,
                  overflow: "hidden",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {/* Real 3D VRM Model Loaded in the circular lens */}
                <div style={{ width: "100%", height: "100%", transform: "scale(1.15)" }}>
                  <VRMAvatar
                    companionId="hinaa"
                    state="idle"
                    modelUrl={activeItem.modelUrl}
                    reducedMotion={false}
                    textOnly={false}
                    closeUp={true}
                  />
                </div>

                {/* Subtitle Badge */}
                <div
                  style={{
                    position: "absolute",
                    bottom: 24,
                    background: "rgba(23, 25, 28, 0.85)",
                    color: "#ffffff",
                    backdropFilter: "blur(8px)",
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: "0.08em",
                    padding: "4px 12px",
                    borderRadius: 9999,
                  }}
                >
                  {activeItem.badge}
                </div>
              </div>

              {/* Massive Geometric Title below the Lens */}
              <div
                style={{
                  marginTop: 20,
                  fontFamily: "'Signifier', Georgia, ui-serif, serif",
                  fontSize: 52,
                  fontWeight: 400,
                  letterSpacing: "-0.03em",
                  color: "#17191c",
                  textAlign: "center",
                  lineHeight: 1,
                }}
              >
                {activeItem.name}
              </div>
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  color: "#787574",
                  marginTop: 4,
                  letterSpacing: "0.1em",
                }}
              >
                X .0412 // Y .0306 // 3D_VRM_LIVE
              </div>
            </div>

            {/* Right Column: Collection Metric, Discover CTA, and Carousel Thumbnails */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 20,
              }}
            >
              {/* Giant Index Number */}
              <div
                style={{
                  fontSize: 76,
                  fontFamily: "'Signifier', Georgia, serif",
                  lineHeight: 0.9,
                  fontWeight: 400,
                  color: "#17191c",
                }}
              >
                {activeItem.index}
              </div>

              {/* Discover Pill Button */}
              <div>
                <button
                  type="button"
                  onClick={onEnterTalk || onEnterWorkspace}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 12,
                    background: "#17191c",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: 9999,
                    padding: "10px 22px",
                    fontSize: 13,
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    cursor: "pointer",
                    boxShadow: "0 6px 16px rgba(0,0,0,0.15)",
                    transition: "transform 0.15s ease",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-1px)")}
                  onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
                >
                  <span>COMMUNICATE</span>
                  <span
                    style={{
                      background: activeItem.accentColor,
                      color: "#17191c",
                      width: 22,
                      height: 22,
                      borderRadius: 9999,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 800,
                      fontSize: 11,
                    }}
                  >
                    &gt;&gt;
                  </span>
                </button>
              </div>

              {/* Editorial Description */}
              <div
                style={{
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: "#5d2a1a",
                  maxWidth: 280,
                }}
              >
                {activeItem.tagline} {activeItem.description}
              </div>

              {/* Collection Carousel Thumbnails */}
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#787574", marginBottom: 8 }}>
                  HAUTE-COUTURE SELECTION
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {COLLECTIONS.map((c) => {
                    const isSelected = c.id === activeItem.id;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => handleSelectItem(c)}
                        style={{
                          width: 48,
                          height: 56,
                          borderRadius: 8,
                          border: isSelected ? `2px solid ${c.accentColor}` : "1px solid rgba(23, 25, 28, 0.15)",
                          background: isSelected ? "#ffffff" : "rgba(255,255,255,0.5)",
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 2,
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                          boxShadow: isSelected ? `0 4px 12px ${c.accentColor}44` : "none",
                        }}
                      >
                        <span style={{ fontSize: 10, fontWeight: 700, color: "#17191c" }}>{c.index}</span>
                        <div
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: c.accentColor,
                          }}
                        />
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── VIEW 2: DICH RUNWAY GALLERY (Screenshot 2 ANTURAX) ── */}
        {viewMode === "runway" && (
          <div
            className="dich-hud-dark-matrix"
            style={{
              padding: "48px 32px 64px 32px",
              background: "#0e100f",
              color: "#fffce1",
              minHeight: 580,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                letterSpacing: "0.15em",
                color: "#ff8709",
                marginBottom: 16,
              }}
            >
              &#123; DICH // RUNWAY GALLERY &#125;
            </div>

            {/* Horizontal Runway Cards */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 24,
                width: "100%",
                overflowX: "auto",
                padding: "20px 0",
              }}
            >
              {COLLECTIONS.map((c, i) => {
                const isSelected = c.id === activeItem.id;
                return (
                  <motion.div
                    key={c.id}
                    whileHover={{ scale: 1.03 }}
                    onClick={() => handleSelectItem(c)}
                    style={{
                      width: 220,
                      minHeight: 340,
                      borderRadius: 24,
                      background: isSelected ? "rgba(255, 252, 225, 0.08)" : "rgba(255, 252, 225, 0.03)",
                      border: isSelected ? `2px solid ${c.accentColor}` : "1px solid #42433d",
                      boxShadow: isSelected ? `0 0 24px ${c.accentColor}66` : "none",
                      padding: 16,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      cursor: "pointer",
                      position: "relative",
                      backdropFilter: "blur(8px)",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: c.accentColor }}>
                          {c.index}
                        </span>
                        {isSelected && (
                          <span
                            style={{
                              fontSize: 9,
                              background: c.accentColor,
                              color: "#0e100f",
                              fontWeight: 700,
                              padding: "2px 6px",
                              borderRadius: 9999,
                            }}
                          >
                            SELECTED
                          </span>
                        )}
                      </div>

                      {/* Small avatar circular preview */}
                      <div
                        style={{
                          width: 140,
                          height: 140,
                          borderRadius: "50%",
                          margin: "16px auto",
                          border: `1.5px solid ${c.accentColor}`,
                          background: c.bgGradient,
                          overflow: "hidden",
                        }}
                      >
                        <VRMAvatar
                          companionId="hinaa"
                          state="idle"
                          modelUrl={c.modelUrl}
                          reducedMotion={true}
                          textOnly={false}
                          closeUp={true}
                        />
                      </div>

                      <div style={{ fontSize: 18, fontWeight: 600, color: "#fffce1", textAlign: "center" }}>
                        {c.name}
                      </div>
                      <div style={{ fontSize: 11, color: "#7c7c6f", textAlign: "center", marginTop: 4 }}>
                        {c.subtitle}
                      </div>
                    </div>

                    <button
                      type="button"
                      style={{
                        width: "100%",
                        padding: "8px 0",
                        borderRadius: 100,
                        background: isSelected ? c.accentColor : "transparent",
                        color: isSelected ? "#0e100f" : "#fffce1",
                        border: `1px solid ${c.accentColor}`,
                        fontSize: 11,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      {isSelected ? "ACTIVE VRM MODEL" : "SELECT MODEL"}
                    </button>
                  </motion.div>
                );
              })}
            </div>

            {/* Bottom Title Bar */}
            <div
              style={{
                marginTop: 24,
                fontFamily: "'Signifier', Georgia, serif",
                fontSize: 38,
                letterSpacing: "0.1em",
                color: "#fffce1",
              }}
            >
              A N T U R A X
            </div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                color: "#7c7c6f",
                marginTop: 4,
              }}
            >
              X .0852 // Y .0370 // FIBER_OPTIC_HAUTE_COUTURE
            </div>
          </div>
        )}

        {/* ── VIEW 3: STEEP & SHOP STYLE EDITORIAL ARTIFACTS ── */}
        {viewMode === "steep_analytics" && (
          <div
            style={{
              padding: "40px 32px 56px 32px",
              background: "#ffffff",
              minHeight: 580,
            }}
          >
            {/* Steep Serif Headline on White Canvas */}
            <div style={{ maxWidth: 880, margin: "0 auto 40px auto", textAlign: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", color: "#777b86", textTransform: "uppercase" }}>
                EDITORIAL ARTIFACTS & TELEMETRY
              </div>
              <h1
                style={{
                  fontFamily: "'Signifier', Georgia, ui-serif, serif",
                  fontSize: 48,
                  fontWeight: 400,
                  lineHeight: 1.25,
                  letterSpacing: "-0.96px",
                  color: "#17191c",
                  marginTop: 12,
                }}
              >
                Serif analytics floating on <em>warm editorial paper</em>.
              </h1>
              <p
                style={{
                  fontSize: 17,
                  lineHeight: 1.5,
                  color: "#777b86",
                  marginTop: 12,
                  maxWidth: 640,
                  margin: "12px auto 0 auto",
                }}
              >
                HINAA unifies university infrastructure, deep dual-path cognitive routing, and private college knowledge bases into one seamless executive canvas.
              </p>
            </div>

            {/* Grid of Steep & Shop Floating Artifact Cards */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: 24,
                maxWidth: 1180,
                margin: "0 auto",
              }}
            >
              {/* Card 1: Steep Signature Blush Peach Card */}
              <div
                style={{
                  background: "#fbe1d1",
                  color: "#5d2a1a",
                  borderRadius: 24,
                  padding: "32px 24px",
                  border: "none",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.05em", opacity: 0.8 }}>
                    COLLEGE VIP DEEP VAULT
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 500, marginTop: 8, letterSpacing: "-0.01em" }}>
                    Verified Student ID Portal
                  </div>
                  <p style={{ fontSize: 15, lineHeight: 1.5, marginTop: 12, opacity: 0.9 }}>
                    Curated playbooks on Ethical Hacking, production AI agent scripts, and 4-hour systems architecture lectures locked under campus credentials.
                  </p>
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginTop: 20,
                    fontWeight: 600,
                    fontSize: 14,
                  }}
                >
                  <Shield size={16} />
                  <span>100% On-Premise Data Sovereignty</span>
                </div>
              </div>

              {/* Card 2: Neutral Metric Artifact Card */}
              <div
                style={{
                  background: "#ffffff",
                  borderRadius: 20,
                  padding: 24,
                  border: "1px solid rgba(4, 23, 43, 0.05)",
                  boxShadow: "0 20px 25px -5px rgba(0,0,0,0.06), 0 8px 10px -6px rgba(0,0,0,0.04)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, color: "#777b86", fontWeight: 500 }}>
                    Cognitive Response Latency
                  </div>
                  <div style={{ fontSize: 36, fontWeight: 600, color: "#17191c", marginTop: 4 }}>
                    142ms
                  </div>
                  <div style={{ fontSize: 13, color: "#10b981", fontWeight: 600, marginTop: 2 }}>
                    ↑ 5.5x faster with Casual Fast-Path
                  </div>

                  {/* Gestural line simulation */}
                  <div
                    style={{
                      height: 48,
                      width: "100%",
                      marginTop: 20,
                      background: "linear-gradient(90deg, #f2f2f3 0%, rgba(220, 95, 139, 0.2) 100%)",
                      borderRadius: 8,
                      position: "relative",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: 2,
                        background: "#5d2a1a",
                      }}
                    />
                  </div>
                </div>

                <div style={{ fontSize: 12, color: "#979799", marginTop: 16 }}>
                  Active Engine: OmniRoute (Claude 3.5 Sonnet + Gemini 2.5 Flash)
                </div>
              </div>

              {/* Card 3: Shop Style Discovery Pill Card */}
              <div
                style={{
                  background: "#f2f4f5",
                  borderRadius: 28,
                  padding: 24,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#5433eb" }}>
                    SHOP CONSTELLATION
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 600, color: "#000000", marginTop: 6 }}>
                    Hands & Automation
                  </div>
                  <p style={{ fontSize: 14, color: "#787574", marginTop: 8, lineHeight: 1.45 }}>
                    Execute terminal shell commands, manage git branches, and send Office 365 Outlook emails directly.
                  </p>
                </div>

                {/* Shop Violet Action Pill */}
                <div style={{ marginTop: 24 }}>
                  <button
                    type="button"
                    onClick={onEnterWorkspace}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 16px",
                      borderRadius: 9999,
                      background: "#ffffff",
                      border: "1px solid rgba(5,41,77,0.1)",
                      cursor: "pointer",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                    }}
                  >
                    <span style={{ fontSize: 13, fontWeight: 500, color: "#000000" }}>
                      Launch Terminal Hands
                    </span>
                    <span
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: "50%",
                        background: "#5433eb",
                        color: "#ffffff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        boxShadow: "0 4px 16px rgba(69,36,219,0.34)",
                      }}
                    >
                      <ArrowRight size={14} />
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
