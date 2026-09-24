path = 'apps/web/src/design-system/modes/TalkMode.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
content = content.replace(
    'import { Suspense, lazy, useState } from "react";',
    'import { Suspense, lazy, useState } from "react";\nimport { motion, AnimatePresence } from "framer-motion";'
)
content = content.replace(
    '  Subtitles,\n} from "lucide-react";',
    '  Subtitles,\n  Send,\n} from "lucide-react";'
)

# 2. Props
content = content.replace(
    '  onTypeInstead: () => void;',
    '  onTypeInstead: () => void;\n  onSendText?: (text: string) => void;'
)

# 3. Component argument unpacking
content = content.replace(
    '  onTypeInstead,\n  isMuted,',
    '  onTypeInstead,\n  onSendText,\n  isMuted,'
)

# 4. State
content = content.replace(
    '  const [showCaptions, setShowCaptions] = useState(true);\n  const [isFullscreen, setIsFullscreen] = useState(false);',
    '  const [showCaptions, setShowCaptions] = useState(true);\n  const [isFullscreen, setIsFullscreen] = useState(false);\n  const [showAmbientInput, setShowAmbientInput] = useState(false);\n  const [ambientText, setAmbientText] = useState("");'
)

# 5. Keyboard dock button
content = content.replace(
    '''        {/* Keyboard input */}
        <DockButton
          onClick={onTypeInstead}
          title="Type instead"
          ariaLabel="Type instead"
        >
          <Keyboard size={18} />
        </DockButton>''',
    '''        {/* Keyboard input */}
        <DockButton
          onClick={() => setShowAmbientInput(!showAmbientInput)}
          active={showAmbientInput}
          title={showAmbientInput ? "Close input" : "Type to Hinaa"}
          ariaLabel={showAmbientInput ? "Close input" : "Type to Hinaa"}
        >
          <Keyboard size={18} />
        </DockButton>'''
)

# 6. Ambient input form right before the bottom dock
ambient_form = '''      {/* Ambient Quick Text Input Overlay */}
      <AnimatePresence>
        {showAmbientInput && (
          <motion.form
            initial={{ opacity: 0, y: 15, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 15, scale: 0.98 }}
            onSubmit={(e) => {
              e.preventDefault();
              if (ambientText.trim()) {
                if (onSendText) {
                  onSendText(ambientText.trim());
                } else {
                  onTypeInstead?.();
                }
                setAmbientText("");
                setShowAmbientInput(false);
              }
            }}
            style={{
              position: "fixed",
              bottom: 84,
              left: "50%",
              transform: "translateX(-50%)",
              width: "min(90vw, 560px)",
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 8px 6px 16px",
              borderRadius: 9999,
              background: "var(--bg-surface-raised, rgba(18,18,21,0.85))",
              backdropFilter: "blur(20px)",
              border: "1px solid var(--border-default, rgba(255,255,255,0.15))",
              boxShadow: "0 12px 35px rgba(0,0,0,0.35)",
              zIndex: 40,
            }}
          >
            <input
              type="text"
              autoFocus
              value={ambientText}
              onChange={(e) => setAmbientText(e.target.value)}
              placeholder={`Ask ${companionName} anything...`}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#fff",
                fontSize: 14,
              }}
            />
            <button
              type="submit"
              disabled={!ambientText.trim()}
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                border: "none",
                background: ambientText.trim() ? "var(--accent, #ec4899)" : "rgba(255,255,255,0.1)",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: ambientText.trim() ? "pointer" : "default",
                transition: "all 150ms ease",
              }}
            >
              <Send size={14} />
            </button>
          </motion.form>
        )}
      </AnimatePresence>

      {/* ── Bottom Dock Controls ──────────────────── */}'''

content = content.replace(
    '      {/* ── Bottom Dock Controls ──────────────────── */}',
    ambient_form
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated TalkMode.tsx successfully')
