/**
 * PremiumComposer — floating crystal input bar with:
 * - Auto-resize textarea
 * - @ Power-up mention system
 * - Smart suggestions as you type
 * - Image attachment preview
 * - Voice mic toggle
 * - Send / Stop controls
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Send, Mic, MicOff, RotateCcw, Volume2, VolumeX, X } from "lucide-react";
import { SmartSuggestions, type Suggestion } from "./SmartSuggestions";
import { PowerUpMentions, type PowerUp, type ContextItem, type CommandItem } from "./PowerUpMentions";

interface PremiumComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onVoiceStart?: () => void;
  onVoiceStop?: () => void;
  onPowerUp?: (powerUp: PowerUp) => void;
  onImageAttach?: (dataUrl: string | null) => void;
  imagePreview?: string | null;
  isVoiceActive?: boolean;
  isGenerating?: boolean;
  disabled?: boolean;
  companionName?: string;
  placeholder?: string;
  voiceFeedback?: {
    kind: "idle" | "cloud" | "browser" | "unavailable";
    label: string;
    detail?: string;
  };
  hasReplay?: boolean;
  muted?: boolean;
  onReplay?: () => void;
  onToggleMute?: () => void;
  /** Optional pre-loaded commands/contexts. If not provided, will fetch from /v1/commands */
  commands?: CommandItem[];
  contexts?: ContextItem[];
}

export function PremiumComposer({
  value,
  onChange,
  onSend,
  onVoiceStart,
  onVoiceStop,
  onPowerUp,
  onImageAttach,
  imagePreview: controlledPreview,
  isVoiceActive = false,
  isGenerating = false,
  disabled = false,
  companionName = "HINAA",
  placeholder,
  voiceFeedback,
  hasReplay = false,
  muted = false,
  onReplay,
  onToggleMute,
  commands: providedCommands = [],
  contexts: providedContexts = [],
}: PremiumComposerProps) {
  const textRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [localPreview, setLocalPreview] = useState<string | null>(null);
  const imagePreview = controlledPreview !== undefined ? controlledPreview : localPreview;
  const setImagePreview = onImageAttach || setLocalPreview;
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState("");
  const [trigger, setTrigger] = useState<"@" | "/">("@");
  const [commands, setCommands] = useState<CommandItem[]>(providedCommands);
  const [contexts, setContexts] = useState<ContextItem[]>(providedContexts);
  const [commandsLoaded, setCommandsLoaded] = useState(providedCommands.length > 0);

  // Fetch commands from API if not provided
  useEffect(() => {
    if (providedCommands.length > 0) return;
    let cancelled = false;
    fetch("/api/v1/commands")
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled && data.commands) {
          setCommands(data.commands);
          setCommandsLoaded(true);
        }
      })
      .catch(() => {
        setCommandsLoaded(true);
      });
    return () => { cancelled = true; };
  }, [providedCommands]);

  /* ─── Detect @ power-ups and / commands at the cursor ─── */
  const detectComposerTrigger = useCallback((text: string) => {
    const cursorPos = textRef.current?.selectionStart ?? text.length;
    const beforeCursor = text.slice(0, cursorPos);
    const mention = beforeCursor.match(/@(\S*)$/);
    const command = beforeCursor.match(/\/(\S*)$/);
    if (mention) {
      setTrigger("@");
      setShowMentions(true);
      setMentionFilter(mention[1]);
    } else if (command && (beforeCursor.length === command[0].length || /\s\/(\S*)$/.test(beforeCursor))) {
      setTrigger("/");
      setShowMentions(true);
      setMentionFilter(command[1]);
    } else {
      setShowMentions(false);
      setMentionFilter("");
    }
  }, []);

  /* ─── Auto-resize ──────────────────────────────────── */
  useLayoutEffect(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  const canSend = (value.trim().length > 0 || imagePreview != null) && !disabled && !isGenerating;

  const handleKey = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (showMentions && (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === "Escape" || e.key === "Tab")) {
        e.preventDefault();
        return; // Let the active command menu handle it
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (canSend) onSend();
      }
    },
    [canSend, onSend, showMentions],
  );

  const handleChange = useCallback(
    (text: string) => {
      onChange(text);
      detectComposerTrigger(text);
    },
    [onChange, detectComposerTrigger],
  );

  const handlePowerUpSelect = useCallback(
    (item: ContextItem | CommandItem) => {
      const cursorPos = textRef.current?.selectionStart ?? value.length;
      const triggerPattern = trigger === "@" ? /@\S*$/ : /\/\S*$/;
      const beforeTrigger = value.slice(0, cursorPos).replace(triggerPattern, "");
      const afterCursor = value.slice(cursorPos);
      // @ tags are HINAA's durable intent syntax. Slash commands are a faster
      // entry path but resolve to the same safe, visible operation tag.
      const isContextItem = (item: ContextItem | CommandItem): item is ContextItem => 
        "kind" in item && "sourceId" in item;
      const shortcut = isContextItem(item) ? `@${item.kind}:${item.sourceId}` : `/${item.name}`;
      const newValue = `${beforeTrigger}${shortcut} ${afterCursor}`;
      onChange(newValue);
      setShowMentions(false);
      setMentionFilter("");
      onPowerUp?.(item as any);
      requestAnimationFrame(() => {
        textRef.current?.focus();
        const newPos = beforeTrigger.length + shortcut.length + 1;
        textRef.current?.setSelectionRange(newPos, newPos);
      });
    },
    [value, onChange, onPowerUp, trigger],
  );

  const handleSuggestionSelect = useCallback(
    (suggestion: Suggestion) => {
      onChange(suggestion.prefix || suggestion.label + ": ");
      setShowMentions(false);
      textRef.current?.focus();
    },
    [onChange],
  );

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f?.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onloadend = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(f);
    e.target.value = "";
  };

  return (
    <div className="premium-composer-shell">
      {/* @ Power-up mention popup */}
      <PowerUpMentions
        visible={showMentions}
        filter={mentionFilter}
        onSelectContext={handlePowerUpSelect}
        onSelectCommand={handlePowerUpSelect}
        onClose={() => setShowMentions(false)}
        trigger={trigger}
        contexts={contexts}
        commands={commands}
      />

      {/* Smart suggestions */}
      <SmartSuggestions
        input={value}
        visible={!showMentions && value.trim().length > 1}
        onSelect={handleSuggestionSelect}
      />

      <div className={`premium-composer ${isVoiceActive ? "voice-active" : ""}`}>
        {/* Image preview */}
        <AnimatePresence>
          {imagePreview && (
            <motion.div
              className="composer-image-preview"
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85 }}
            >
              <img src={imagePreview} alt="Preview" />
              <button className="composer-img-remove" onClick={() => setImagePreview(null)} aria-label="Remove image">
                <X size={12} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Text input */}
        <textarea
          ref={textRef}
          className="composer-textarea"
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder ?? `Message ${companionName}… (type @ or / for tools)`}
          disabled={disabled || isVoiceActive}
          rows={1}
          spellCheck
          autoComplete="off"
          aria-label={`Message ${companionName}`}
        />

        {voiceFeedback && voiceFeedback.kind !== "idle" && (
          <div
            className={`composer-voice-feedback composer-voice-feedback--${voiceFeedback.kind}`}
            role="status"
            aria-live="polite"
          >
            <span className="composer-voice-feedback-dot" aria-hidden="true" />
            <span>
              <strong>{voiceFeedback.label}</strong>
              {voiceFeedback.detail ? <small>{voiceFeedback.detail}</small> : null}
            </span>
          </div>
        )}

        {/* Toolbar */}
        <div className="composer-toolbar">
          <div className="composer-tools-left">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="sr-only"
              onChange={handleFile}
              aria-label="Attach image"
            />
            <motion.button
              type="button"
              className="composer-tool-btn"
              onClick={() => fileRef.current?.click()}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.92 }}
              title="Attach image"
              aria-label="Attach image"
            >
              <Plus size={17} />
            </motion.button>
          </div>

          <div className="composer-tools-right">
            {hasReplay && onReplay ? (
              <motion.button
                type="button"
                className="composer-voice-btn"
                onClick={onReplay}
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.94 }}
                title="Replay Hinaa's last spoken reply"
                aria-label="Replay Hinaa voice reply"
              >
                <RotateCcw size={15} />
              </motion.button>
            ) : null}
            {onToggleMute ? (
              <motion.button
                type="button"
                className={`composer-voice-btn ${muted ? "muted" : ""}`}
                onClick={onToggleMute}
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.94 }}
                title={muted ? "Unmute Hinaa voice" : "Mute Hinaa voice"}
                aria-label={muted ? "Unmute Hinaa voice" : "Mute Hinaa voice"}
                aria-pressed={muted}
              >
                {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
              </motion.button>
            ) : null}
            {/* Voice mic */}
            <motion.button
              type="button"
              className={`composer-mic-btn ${isVoiceActive ? "active" : ""}`}
              onClick={isVoiceActive ? onVoiceStop : onVoiceStart}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              title={isVoiceActive ? "Stop listening" : "Start voice"}
              aria-label={isVoiceActive ? "Stop microphone" : "Start microphone"}
            >
              {isVoiceActive ? <MicOff size={17} /> : <Mic size={17} />}
            </motion.button>

            {/* Send / Stop */}
            <motion.button
              type="button"
              className={`composer-send-btn ${canSend ? "can-send" : ""}`}
              onClick={() => canSend && onSend()}
              disabled={!canSend}
              whileHover={canSend ? { scale: 1.08 } : undefined}
              whileTap={canSend ? { scale: 0.92 } : undefined}
              title={isGenerating ? "Generating…" : "Send"}
              aria-label={isGenerating ? "Generating" : "Send message"}
            >
              {isGenerating ? (
                <motion.span
                  className="composer-spinner"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                />
              ) : (
                <Send size={16} />
              )}
            </motion.button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PremiumComposer;
