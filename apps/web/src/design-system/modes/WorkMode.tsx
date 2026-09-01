import { Suspense, lazy, useCallback, useEffect, useRef, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Wand2,
  Brain,
  ListChecks,
  AudioLines,
  Mic,
  Paperclip,
  Send,
  Square,
  Sparkles,
  Globe,
  FileText,
  Image,
  Bot,
  Slash,
  AtSign,
} from "lucide-react";
import type { CompanionState, TranscriptMessage } from "../../features/companion/types";
import type { PowerUp, PowerUpId } from "../chat/ChatComposer";
import { PowerUpMentions, type ContextItem, type CommandItem } from "../../components/ui/PowerUpMentions";
import { SourceCard, type SourceItem } from "../../components/ui/SourceCard";

const ActivityPanel = lazy(() =>
  import("../../components/ui/ActivityPanel").then((m) => ({
    default: m.ActivityPanel,
  }))
);


/* Local command registry fallback - used when /api/v1/commands is unavailable.
 * The capability field carries the frontend action routed through onCommand. */
const DEFAULT_COMMANDS: CommandItem[] = [
  { name: "search", aliases: ["web", "research"], label: "Web Search", description: "Research a question with attributed sources", descriptionShort: "Research with sources", icon: Search, color: "#4FB989", group: "research", inputSchema: {}, capability: "search-web", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/search best coffee in Kathmandu"] },
  { name: "image", aliases: ["draw", "generate"], label: "Generate Image", description: "Open Image Studio to create an image locally", descriptionShort: "Create an image", icon: Sparkles, color: "#F36F9C", group: "creative", inputSchema: {}, capability: "generate-image", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "browser", examples: ["/image a sakura sunset"] },
  { name: "humanize", aliases: ["rewrite", "tone"], label: "Humanizer", description: "Open Humanizer Studio to rewrite text naturally", descriptionShort: "Rewrite text naturally", icon: Wand2, color: "#5B9DCF", group: "writing", inputSchema: {}, capability: "open-humanizer", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "browser", examples: ["/humanize"] },
  { name: "memory", aliases: ["remember"], label: "Memory", description: "Open your saved memories", descriptionShort: "Open memories", icon: Brain, color: "#B8A7F2", group: "personal", inputSchema: {}, capability: "remember-this", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/memory"] },



];

interface WorkModeProps {
  companionState: CompanionState;
  messages: TranscriptMessage[];
  streamingText: string;
  partialTranscript: string;
  isThinking: boolean;
  input: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  disabled: boolean;
  isVoiceActive: boolean;
  onStartVoice: () => void;
  onStopVoice: () => void;
  voiceFeedback: { kind: string; label: string; detail?: string };
  powerUps: PowerUp[];
  onPowerUpToggle: (id: PowerUpId) => void;
  onCommand?: (action: string) => void;
  onResolveTool: (messageId: string, request: any, approved: boolean) => Promise<void>;
  autoRunTools: boolean;
  agentSteps: Array<{
    id: string;
    label: string;
    detail?: string;
    status: "pending" | "active" | "done" | "error" | "cancelled";
  }>;
  onWelcomeAction: (action: string) => void;
  attachedImage: string | null;
  onImageAttach: (image: string | null) => void;
}

export function WorkMode({
  companionState,
  messages,
  streamingText,
  partialTranscript,
  isThinking,
  input,
  onInputChange,
  onSend,
  onStop,
  disabled,
  isVoiceActive,
  onStartVoice,
  onStopVoice,
  onResolveTool,
  agentSteps,
  onWelcomeAction,
  powerUps,
  onPowerUpToggle,
  onCommand,
  attachedImage,
  onImageAttach,
}: WorkModeProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [inputHeight, setInputHeight] = useState(44);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState("");
  const [mentionCursorPos, setMentionCursorPos] = useState(0);
  const [trigger, setTrigger] = useState<"@" | "/">("@");
  const [commands, setCommands] = useState<CommandItem[]>([]);
  const [contexts, setContexts] = useState<ContextItem[]>([]);
  const [commandRegistryLoaded, setCommandRegistryLoaded] = useState(false);
  const showWelcome =
    messages.length <= 1 &&
    !streamingText &&
    !partialTranscript &&
    companionState === "idle" &&
    !isVoiceActive;

  // Fetch command registry on mount
  useEffect(() => {
    async function fetchCommands() {
      try {
        const res = await fetch("/api/v1/commands");
        const data = await res.json();
        const fetched: CommandItem[] = data.commands || [];
        setCommands(fetched.length > 0 ? fetched : DEFAULT_COMMANDS);
        setCommandRegistryLoaded(true);
      } catch (e) {
        console.warn("Failed to load command registry, using local commands:", e);
        setCommands(DEFAULT_COMMANDS);
        setCommandRegistryLoaded(true);
      }
    }
    fetchCommands();
  }, []);

  // Build context items from available data
  const availableContexts = useMemo((): ContextItem[] => {
    const items: ContextItem[] = [
      { id: "project", kind: "project", label: "Current Project", description: "Reference the active project", icon: AtSign, color: "#7c3aed", sourceId: "current", access: "read" },
      { id: "conversation", kind: "conversation", label: "This Conversation", description: "Reference recent messages", icon: AtSign, color: "#14b8a6", sourceId: "current", access: "read" },
      { id: "memory", kind: "memory", label: "Saved Memories", description: "Reference your saved memories", icon: AtSign, color: "#ec4899", sourceId: "memories", access: "read" },
    ];
    // Add project files if available
    if (messages.some(m => m.text?.includes(".py") || m.text?.includes(".ts"))) {
      items.push({ id: "files", kind: "file", label: "Project Files", description: "Reference project files", icon: AtSign, color: "#0891b2", sourceId: "files", access: "read" });
    }
    return items;
  }, [messages]);

  // contexts are driven by the useMemo above; no separate state copy needed

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText]);

  // Auto-resize textarea
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value;
      onInputChange(val);
      // Detect @ context picker or / command palette at cursor
      const cursorPos = e.target.selectionStart ?? val.length;
      const beforeCursor = val.slice(0, cursorPos);
      const mentionMatch = beforeCursor.match(/@(\S*)$/);
      // "/" only triggers a command palette at the start of a word,
      // so URLs (example.com/x) and dates (12/08) never pop the palette.
      const commandMatch = /^\/(\S*)$/.test(beforeCursor.trim()) || /\s\/(\S*)$/.test(beforeCursor)
        ? beforeCursor.match(/\/(\S*)$/)
        : null;
      if (mentionMatch) {
        setTrigger("@");
        setShowMentions(true);
        setMentionFilter(mentionMatch[1]);
        setMentionCursorPos(cursorPos - mentionMatch[1].length - 1);
      } else if (commandMatch) {
        setTrigger("/");
        setShowMentions(true);
        setMentionFilter(commandMatch[1]);
        setMentionCursorPos(cursorPos - commandMatch[1].length - 1);
      } else {
        setShowMentions(false);
        setMentionFilter("");
      }
      const el = e.target;
      el.style.height = "auto";
      const newHeight = Math.min(Math.max(44, el.scrollHeight), 160);
      el.style.height = `${newHeight}px`;
      setInputHeight(newHeight);
    },
    [onInputChange]
  );

  const handleSubmit = useCallback(() => {
    if (!input.trim() && !attachedImage) return;
    onSend();
    if (inputRef.current) {
      inputRef.current.style.height = "44px";
      setInputHeight(44);
    }
  }, [input, attachedImage, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (showMentions && (e.key === "Escape")) {
        setShowMentions(false);
        setMentionFilter("");
        return;
      }
      if (showMentions && (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter")) {
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const handleContextSelect = useCallback(
    (context: ContextItem) => {
      if (!inputRef.current) return;
      const el = inputRef.current;
      const val = el.value;
      const before = val.slice(0, mentionCursorPos);
      const after = val.slice(el.selectionStart ?? val.length);
      // Replace @trigger with a context chip reference
      const newVal = before + `@${context.kind}:${context.sourceId} ` + after;
      onInputChange(newVal);
      setShowMentions(false);
      setMentionFilter("");
    },
    [mentionCursorPos, onInputChange],
  );

  const handleCommandSelect = useCallback(
    (command: CommandItem) => {
      setShowMentions(false);
      setMentionFilter("");
      // Commands with a capability action run immediately through the app
      // dispatcher (opens the matching workspace/studio), matching @context
      // behavior. The /trigger text is stripped from the input.
      const action = command.capability;
      if (onCommand && action) {
        if (inputRef.current) {
          const el = inputRef.current;
          const before = el.value.slice(0, mentionCursorPos);
          const after = el.value.slice(el.selectionStart ?? el.value.length);
          onInputChange((before + after).replace(/^\s+/, ""));
        }
        onCommand(action);
        return;
      }
      // Fallback: insert the command text for the model to interpret.
      if (!inputRef.current) return;
      const el = inputRef.current;
      const val = el.value;
      const before = val.slice(0, mentionCursorPos);
      const after = val.slice(el.selectionStart ?? val.length);
      const newVal = before + `/${command.name} ` + after;
      onInputChange(newVal);
    },
    [mentionCursorPos, onInputChange, onCommand],
  );

  // Find tool approval requests
  const toolApprovals: Array<{
    messageId: string;
    request: any;
    status: string;
  }> = [];
  for (const msg of messages) {
    if (msg.toolActivity) {
      for (const activity of msg.toolActivity) {
        if (activity.status === "pending") {
          const plan = msg.plan;
          const toolReq = plan?.toolRequests?.find(
            (t: any) => t.toolName === activity.id
          );
          if (toolReq) {
            toolApprovals.push({
              messageId: msg.id,
              request: {
                id: activity.id,
                toolName: toolReq.toolName,
                action: (toolReq as any).description || toolReq.toolName,
                description: `Proposed: ${toolReq.toolName}`,
                parameters: toolReq.parameters,
                riskLevel: "local" as const,
                requiresApproval: true,
              },
              status: activity.status,
            });
          }
        }
      }
    }
  }

  return (
    <div
      data-testid="work-mode"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        background: "var(--bg-canvas)",
      }}
    >
      {/* ── Header ─────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 var(--space-4)",
          borderBottom: "1px solid var(--border-subtle)",
          background: "var(--bg-surface)",
          flexShrink: 0,
          height: 48,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <Sparkles size={16} color="var(--accent)" />
          <span
            style={{
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              color: "var(--text-primary)",
            }}
          >
            Work
          </span>
          {messages.length > 0 && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
              · {messages.length} messages
            </span>
          )}
        </div>
        <StatusDot state={companionState} />
      </header>

      {/* ── Main Area ───────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Transcript column — centered, readable width */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: "auto",
            overflowX: "hidden",
            padding: "var(--space-4) var(--space-6) var(--space-2)",
            display: "flex",
            flexDirection: "column",
            maxWidth: 860,
            width: "100%",
            margin: "0 auto",
          }}
        >
          {/* Activity */}
          {agentSteps.length > 0 && (
            <Suspense fallback={null}>
              <ActivityPanel
                steps={agentSteps}
                title="Execution"
                mode="execution"
              />
            </Suspense>
          )}

          {/* Welcome */}
          {showWelcome && <WorkWelcome onAction={onWelcomeAction} />}

          {/* Messages */}
          {!showWelcome &&
            messages.map((msg) => (
              <WorkMessage key={msg.id} message={msg} />
            ))}

          {/* Streaming */}
          {streamingText && (
            <WorkMessage
              message={
                {
                  id: "streaming",
                  role: "assistant",
                  text: streamingText,
                  createdAt: new Date().toISOString(),
                } as TranscriptMessage
              }
              isStreaming
            />
          )}

          {/* Tool approvals */}
          {toolApprovals.map((ta) => (
            <div
              key={`${ta.messageId}-${ta.request.id}`}
              data-testid="tool-approval"
              style={{
                padding: "var(--space-3) var(--space-4)",
                background: "var(--warning-bg)",
                border: "1px solid var(--warning-border)",
                borderRadius: "var(--radius-md)",
                marginBottom: "var(--space-3)",
              }}
            >
              <div
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: 600,
                  color: "var(--warning-text)",
                  marginBottom: "var(--space-1)",
                }}
              >
                Tool approval: {ta.request.toolName}
              </div>
              <div
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--text-secondary)",
                  marginBottom: "var(--space-2)",
                }}
              >
                {ta.request.description}
              </div>
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <button
                  onClick={() => onResolveTool(ta.messageId, ta.request, true)}
                  style={{
                    padding: "var(--space-1) var(--space-3)",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--success-border)",
                    background: "var(--success-bg)",
                    color: "var(--success-text)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Approve
                </button>
                <button
                  onClick={() => onResolveTool(ta.messageId, ta.request, false)}
                  style={{
                    padding: "var(--space-1) var(--space-3)",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-default)",
                    background: "var(--bg-surface)",
                    color: "var(--text-secondary)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}

          {/* Spacer for composer */}
          <div style={{ height: "var(--space-2)", flexShrink: 0 }} />
        </div>
      </div>

      {/* ── Composer (attached to bottom) ─────────── */}
      <div
        data-testid="work-composer"
        style={{
          padding: "var(--space-2) var(--space-4) var(--space-3)",
          maxWidth: 860,
          width: "100%",
          margin: "0 auto",
          flexShrink: 0,
          borderTop: "1px solid var(--border-subtle)",
          background: "var(--bg-surface)",
        }}
      >
        {/* Image preview */}
        {attachedImage && (
          <div
            style={{
              marginBottom: "var(--space-2)",
              padding: "var(--space-2)",
              background: "var(--bg-subtle)",
              borderRadius: "var(--radius-md)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
            }}
          >
            <img
              src={attachedImage}
              alt="Attached"
              style={{ height: 48, borderRadius: "var(--radius-sm)" }}
            />
            <button
              onClick={() => onImageAttach(null)}
              style={{
                fontSize: "var(--text-xs)",
                color: "var(--danger-text)",
                background: "none",
                border: "none",
                cursor: "pointer",
              }}
            >
              Remove
            </button>
          </div>
        )}

        {/* @-mention dropdown / command palette */}
        {showMentions && (
          <div style={{ position: "relative", marginBottom: "var(--space-1)" }}>
            <PowerUpMentions
              visible={true}
              filter={mentionFilter}
              onSelectContext={handleContextSelect}
              onSelectCommand={handleCommandSelect}
              onClose={() => { setShowMentions(false); setMentionFilter(""); }}
              trigger={trigger}
              contexts={availableContexts}
              commands={commands}
            />
          </div>
        )}

        {/* Input area */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: "var(--space-2)",
            padding: "var(--space-2) var(--space-3)",
            background: "var(--bg-surface-raised)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-xl)",
            boxShadow: "var(--shadow-sm)",
            transition: "border-color 150ms ease, box-shadow 150ms ease",
          }}
        >
          {/* Attach */}
          <button
            title="Attach image"
            aria-label="Attach image"
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "transparent",
              color: "var(--text-tertiary)",
              cursor: "pointer",
            }}
          >
            <Paperclip size={16} />
          </button>

          {/* Textarea */}
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask HINAA anything..."
            rows={1}
            data-testid="chat-input"
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              color: "var(--text-primary)",
              fontSize: "var(--text-sm)",
              fontFamily: "var(--font-body)",
              lineHeight: "var(--leading-normal)",
              resize: "none",
              height: inputHeight,
              maxHeight: 160,
              padding: "var(--space-1) 0",
            }}
          />

          {/* Voice */}
          <button
            onClick={isVoiceActive ? onStopVoice : onStartVoice}
            title={isVoiceActive ? "Stop voice" : "Start voice"}
            aria-label={isVoiceActive ? "Stop voice" : "Start voice"}
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: isVoiceActive ? "var(--danger-bg)" : "transparent",
              color: isVoiceActive ? "var(--danger-text)" : "var(--text-tertiary)",
              cursor: "pointer",
            }}
          >
            <Mic size={16} />
          </button>

          {/* Send / Stop */}
          {isThinking || companionState === "thinking" ? (
            <button
              onClick={onStop}
              title="Stop generation"
              aria-label="Stop generation"
              style={{
                flexShrink: 0,
                width: 32,
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "var(--danger-bg)",
                color: "var(--danger-text)",
                cursor: "pointer",
              }}
            >
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!input.trim() && !attachedImage}
              title="Send message"
              aria-label="Send message"
              data-testid="send-button"
              style={{
                flexShrink: 0,
                width: 32,
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background:
                  input.trim() || attachedImage
                    ? "var(--accent)"
                    : "var(--bg-subtle)",
                color:
                  input.trim() || attachedImage
                    ? "var(--text-on-accent)"
                    : "var(--text-disabled)",
                cursor:
                  input.trim() || attachedImage ? "pointer" : "default",
                transition: "background 150ms ease",
              }}
            >
              <Send size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Message Component ───────────────────────────────────── */
function WorkMessage({
  message,
  isStreaming,
}: {
  message: TranscriptMessage;
  isStreaming?: boolean;
}) {
  const isUser = message.role === "user";

  // Convert tool results to SourceItem format for SourceCard
  const renderToolResults = () => {
    if (!message.toolResults || message.toolResults.length === 0) return null;
    
    return (
      <div style={{ marginTop: "var(--space-2)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {message.toolResults.map((tr, idx) => {
          const result = tr.result;
          if (!result || !result.sources) return null;
          
          const sources: SourceItem[] = result.sources.map((s: any, i: number) => ({
            id: s.id || `${tr.toolName}-${i}`,
            title: s.title || s.url || "Untitled",
            domain: new URL(s.url).hostname || "unknown",
            snippet: s.snippet || "",
            url: s.url,
            index: i,
          }));
          
          if (sources.length === 0) return null;
          
          return (
            <div key={`${tr.toolName}-${idx}`} style={{ marginTop: "var(--space-2)" }}>
              <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--accent)", marginBottom: "var(--space-1)" }}>
                Sources from {tr.toolName}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {sources.map((source) => (
                  <SourceCard key={source.id} source={source} index={source.index || 0} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div
      style={{
        marginBottom: "var(--space-3)",
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
      }}
    >
      {/* Role label */}
      {!isUser && (
        <div
          style={{
            fontSize: "var(--text-xs)",
            fontWeight: 600,
            color: "var(--accent)",
            marginBottom: "var(--space-1)",
            paddingLeft: "var(--space-1)",
          }}
        >
          HINAA
        </div>
      )}

      {/* Message bubble */}
      <div
        style={{
          maxWidth: "85%",
          padding: "var(--space-3) var(--space-4)",
          borderRadius: isUser
            ? "18px 18px 6px 18px"
            : "6px 18px 18px 18px",
          background: isUser ? "var(--accent-pale)" : "var(--bg-surface)",
          border: isUser
            ? "1px solid var(--accent-soft)"
            : "1px solid var(--border-subtle)",
          color: "var(--text-primary)",
          fontSize: "var(--text-sm)",
          lineHeight: "var(--leading-relaxed)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {message.text}
        {isStreaming && (
          <span
            style={{
              display: "inline-block",
              width: 2,
              height: "1em",
              background: "var(--accent)",
              marginLeft: 2,
              animation: "blink 1s step-end infinite",
            }}
          />
        )}
      </div>

      {/* Tool Results with Source Cards */}
      {!isUser && renderToolResults()}

      {/* Timestamp */}
      {message.createdAt && (
        <div
          style={{
            fontSize: "var(--text-xs)",
            color: "var(--text-tertiary)",
            marginTop: "var(--space-1)",
            paddingLeft: isUser ? 0 : "var(--space-1)",
            paddingRight: isUser ? "var(--space-1)" : 0,
          }}
        >
          {new Date(message.createdAt).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      )}

      {/* Blink animation — inject once */}
      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
    </div>
  );
}

/* ── Welcome Screen ──────────────────────────────────────── */
function WorkWelcome({
  onAction,
}: {
  onAction: (action: string) => void;
}) {
  const items = [
    {
      icon: <Search size={18} />,
      title: "Research",
      desc: "Search with sources",
      action: "research",
    },
    {
      icon: <Wand2 size={18} />,
      title: "Create",
      desc: "Images, documents, ideas",
      action: "create",
    },
    {
      icon: <ListChecks size={18} />,
      title: "Continue work",
      desc: "Projects & tasks",
      action: "work",
    },
    {
      icon: <AudioLines size={18} />,
      title: "Talk to HINAA",
      desc: "Voice conversation",
      action: "voice",
    },
  ];

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "var(--space-6)",
        padding: "var(--space-12) 0",
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ textAlign: "center" }}
      >
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--text-3xl)",
            fontWeight: 800,
            color: "var(--text-primary)",
            marginBottom: "var(--space-2)",
          }}
        >
          Hello
        </h1>
        <p
          style={{
            fontSize: "var(--text-base)",
            color: "var(--text-secondary)",
            fontWeight: 500,
          }}
        >
          What would you like to work on?
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: "var(--space-3)",
          maxWidth: 420,
          width: "100%",
        }}
      >
        {items.map((item, i) => (
          <motion.button
            key={item.action}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 + i * 0.08 }}
            whileHover={{ y: -2, boxShadow: "var(--shadow-md)" }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onAction(item.action)}
            style={{
              padding: "var(--space-4)",
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              cursor: "pointer",
              textAlign: "left",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
              transition: "box-shadow 150ms ease",
            }}
          >
            <span style={{ color: "var(--accent)", display: "flex" }}>
              {item.icon}
            </span>
            <span
              style={{
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                color: "var(--text-primary)",
              }}
            >
              {item.title}
            </span>
            <span
              style={{
                fontSize: "var(--text-xs)",
                color: "var(--text-tertiary)",
              }}
            >
              {item.desc}
            </span>
          </motion.button>
        ))}
      </motion.div>
    </div>
  );
}

/* ── Status Dot ──────────────────────────────────────────── */
function StatusDot({ state }: { state: CompanionState }) {
  const color =
    state === "error"
      ? "var(--danger)"
      : state === "idle"
        ? "var(--success)"
        : "var(--accent)";
  return (
    <div
      style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: color,
        boxShadow: `0 0 6px ${color}60`,
      }}
    />
  );
}
