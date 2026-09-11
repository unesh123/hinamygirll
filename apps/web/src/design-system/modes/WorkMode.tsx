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
import type { CompanionId, CompanionState, TranscriptMessage } from "../../features/companion/types";
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

import { GenericResultRenderer } from "../../features/chat/components/GenericResultRenderer";
import { AgentActivityCard, type ActivityStep } from "../../features/chat/components/AgentActivityCard";
import { AvatarModelPicker } from "../../features/avatar/AvatarModelPicker";
import { AVATAR_REGISTRY, DEFAULT_AVATAR_FILE } from "../../features/avatar/avatarRegistry";
import { VRMAvatar } from "../../features/avatar/VRMAvatar";
import { ModelControlBar } from "../layout/ModelControlBar";
import type { PresenceMode } from "../../components/ui/AvatarPresence";

function getProviderDisplayName(mode?: string): string {
  if (!mode) return "Provider";
  switch (mode) {
    case "cx-gateway": return "CX Gateway";
    case "anthropic-direct": return "Claude Direct";
    case "groq": return "Groq";
    case "real": return "Gemini";
    case "custom": return "Custom Gateway";
    case "agent-router": return "Agent Router";
    default:
      return mode.charAt(0).toUpperCase() + mode.slice(1);
  }
}

interface WorkModeProps {
  companionId?: CompanionId;
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
  currentAgentRunId?: string;
  currentAgentConfirmationStepId?: string;
  onCancelAgentRun?: () => void;
  onResumeAgentRun?: () => void;
  onConfirmAgentStep?: (approved: boolean) => void;
  onRecoverAgentRun?: () => void;
  onWelcomeAction: (action: string) => void;
  attachedImage: string | null;
  onImageAttach: (image: string | null) => void;
  // Companion & Avatar Props
  avatarModel?: string;
  avatarMode?: PresenceMode;
  onChangeAvatarMode?: (mode: PresenceMode) => void;
  avatarPresentation?: any;
  onOpenAvatarLab?: () => void;
  onSelectModel?: (modelUrl: string) => void;
  companionName?: string;
  jawEnergy?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEvents?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  // Provider micro-status & fallback props
  activeProviderMode?: string;
  activeProviderModel?: string | null;
  providerHealth?: string;
  providerLatencyMs?: number | null;
  onSelectProvider?: (mode: string, modelId?: string) => void;
  onRetry?: () => void;
  attachedAttachments?: any[];
  onUpdateAttachmentRole?: any;
  onRemoveAttachment?: any;
  onReorderAttachment?: any;
  onReuseAsReference?: any;
  onOpenLibrary?: () => void;
  onOpenImages?: () => void;
  providerOptions?: any[];
  getModelOptions?: (mode: any) => Array<{ id: string; label: string; isDefault: boolean }>;
  imageEngine?: string;
  onSelectImageEngine?: (engine: string) => void;
  voiceEngine?: string;
  onSelectVoiceEngine?: (engine: string) => void;
  onOpenSettings?: () => void;
}

export function WorkMode({
  companionId = "hinaa",
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
  currentAgentRunId,
  currentAgentConfirmationStepId,
  onCancelAgentRun,
  onResumeAgentRun,
  onConfirmAgentStep,
  onRecoverAgentRun,
  onWelcomeAction,
  powerUps,
  onPowerUpToggle,
  onCommand,
  attachedImage,
  onImageAttach,
  avatarModel = DEFAULT_AVATAR_FILE,
  avatarMode = "portrait",
  onChangeAvatarMode,
  avatarPresentation,
  onOpenAvatarLab,
  onSelectModel,
  companionName = "HINAA",
  jawEnergy,
  speakingRef,
  visemeEvents,
  audioStartTimeRef,
  activeProviderMode,
  activeProviderModel,
  providerHealth = "healthy",
  providerLatencyMs,
  onSelectProvider,
  onRetry,
  providerOptions,
  getModelOptions,
  imageEngine,
  onSelectImageEngine,
  voiceEngine,
  onSelectVoiceEngine,
  onOpenSettings,
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
  const [dockPosition, setDockPosition] = useState<"right" | "left" | "floating">("right");
  const [companionVisible, setCompanionVisible] = useState<boolean>(true);
  const [showModelPicker, setShowModelPicker] = useState<boolean>(false);
  const modelPickerTriggerRef = useRef<HTMLButtonElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  const handleImageFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === "string") {
          onImageAttach(reader.result);
        }
      };
      reader.readAsDataURL(file);
    }
    e.target.value = "";
  }, [onImageAttach]);

  const handlePaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (items) {
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith("image/")) {
          const file = items[i].getAsFile();
          if (file) {
            const reader = new FileReader();
            reader.onload = () => {
              if (typeof reader.result === "string") {
                onImageAttach(reader.result);
              }
            };
            reader.readAsDataURL(file);
            e.preventDefault();
            break;
          }
        }
      }
    }
  }, [onImageAttach]);

  const [isMobile, setIsMobile] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth <= 768;
    }
    return false;
  });
  const [mobileTab, setMobileTab] = useState<"chat" | "avatar">("chat");

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const [internalImageEngine, setInternalImageEngine] = useState<string>(() => {
    try {
      const prefs = localStorage.getItem("hinaa-model-prefs");
      return prefs ? JSON.parse(prefs).imageEngine || "auto" : "auto";
    } catch { return "auto"; }
  });
  const [internalVoiceEngine, setInternalVoiceEngine] = useState<string>(() => {
    try {
      const prefs = localStorage.getItem("hinaa-model-prefs");
      return prefs ? JSON.parse(prefs).voiceEngine || "auto" : "auto";
    } catch { return "auto"; }
  });

  const currentAvatarDef = AVATAR_REGISTRY.find((a) => a.fileUrl === avatarModel);
  const currentModelName = currentAvatarDef?.name || "Hinaa (Original)";

  const convertedActivitySteps: ActivityStep[] = useMemo(() => {
    // Only inspect the assistant message of the current active turn to avoid leaking previous turns' completed tools
    const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
    if (isThinking && lastMessage && lastMessage.role === "assistant" && lastMessage.toolActivity && lastMessage.toolActivity.length > 0) {
      return lastMessage.toolActivity.map((act, index, arr) => ({
        id: act.id,
        toolName: act.id,
        title: act.label || `Running ${act.id}`,
        status: act.status === "complete" || act.status === "completed" ? ("completed" as const) : act.status === "error" || act.status === "failed" ? ("failed" as const) : ("running" as const),
        message: act.label,
        stepNumber: index + 1,
        totalSteps: arr.length,
      }));
    }

    if (agentSteps.length > 0) {
      return agentSteps.map((step, index, arr) => ({
        id: step.id,
        title: step.label,
        status: step.status === "done"
          ? ("completed" as const)
          : step.status === "error"
            ? ("failed" as const)
            : step.status === "cancelled"
              ? ("cancelled" as const)
              : step.status === "pending"
                ? ("pending" as const)
                : ("running" as const),
        message: step.detail,
        stepNumber: index + 1,
        totalSteps: arr.length,
      }));
    }

    return [];
  }, [isThinking, messages, agentSteps]);

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
        const raw: any[] = data.commands || [];
        const fetched: CommandItem[] = raw.map((cmd) => ({
          name: cmd.name || "",
          aliases: cmd.aliases || [],
          label: cmd.label || (cmd.name ? cmd.name.charAt(0).toUpperCase() + cmd.name.slice(1) : "Command"),
          description: cmd.description || "",
          descriptionShort: cmd.descriptionShort || cmd.description || "",
          icon: cmd.name === "search" || cmd.name === "web" ? Search : (cmd.name === "memory" ? Brain : Sparkles),
          color: cmd.color || (cmd.name === "search" ? "#0891b2" : "#F36F9C"),
          group: cmd.group || "Commands",
          inputSchema: cmd.inputSchema || {},
          capability: cmd.capability || "",
          riskLevel: cmd.riskLevel || "read",
          approvalPolicy: cmd.approvalPolicy || "automatic",
          availability: cmd.availability || "available",
          executionLocation: cmd.executionLocation || "api",
          examples: cmd.examples || [],
        }));
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
      if (e.key === "Escape") {
        if (isThinking || companionState === "thinking" || companionState === "speaking") {
          e.preventDefault();
          onStop();
          return;
        }
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit, isThinking, companionState, onStop, showMentions]
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
      if (!inputRef.current) return;
      const el = inputRef.current;
      const val = el.value;
      const before = val.slice(0, mentionCursorPos);
      const after = val.slice(el.selectionStart ?? val.length);
      const cmdText = `/${command.name} `;
      const newVal = before + cmdText + after;
      onInputChange(newVal);
      // Position cursor immediately after the inserted command
      window.requestAnimationFrame(() => {
        if (inputRef.current) {
          inputRef.current.focus();
          const targetPos = before.length + cmdText.length;
          inputRef.current.setSelectionRange(targetPos, targetPos);
        }
      });
    },
    [mentionCursorPos, onInputChange],
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

  const renderCompanionPanel = () => {
    const isFloating = dockPosition === "floating";
    const isLeft = dockPosition === "left";

    let panelStyle: React.CSSProperties = {
      display: "flex",
      flexDirection: "column",
      background: "var(--bg-surface)",
      borderLeft: dockPosition === "right" ? "1px solid var(--border-subtle)" : undefined,
      borderRight: dockPosition === "left" ? "1px solid var(--border-subtle)" : undefined,
      zIndex: isFloating ? 50 : 10,
      flexShrink: 0,
      overflow: "hidden",
    };

    if (isFloating) {
      panelStyle = {
        ...panelStyle,
        position: "absolute",
        top: 16,
        right: 16,
        width: "320px",
        height: "440px",
        borderRadius: "var(--radius-xl, 16px)",
        border: "1px solid var(--border-default)",
        boxShadow: "0 10px 25px rgba(0,0,0,0.3)",
      };
    } else if (isLeft) {
      panelStyle = {
        ...panelStyle,
        position: "relative",
        width: 320,
        left: "0px",
        order: -1,
        height: "100%",
      };
    } else {
      panelStyle = {
        ...panelStyle,
        position: "relative",
        width: 320,
        right: "0px",
        order: 1,
        height: "100%",
      };
    }

    return (
      <aside
        data-testid="work-companion-panel"
        style={panelStyle}
        aria-label="Companion avatar panel"
      >
        {/* Companion Panel Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            borderBottom: "1px solid var(--border-subtle)",
            background: "var(--bg-surface-raised)",
            flexShrink: 0,
          }}
        >
          {/* Model Switcher Button */}
          <div style={{ position: "relative" }}>
            <button
              ref={modelPickerTriggerRef}
              type="button"
              aria-label="Switch 3D Avatar Model"
              onClick={() => setShowModelPicker((prev) => !prev)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 8px",
                borderRadius: "var(--radius-sm, 6px)",
                border: "1px solid var(--border-default)",
                background: "var(--bg-surface)",
                color: "var(--text-primary)",
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Sparkles size={12} color="var(--accent)" />
              <span>{currentModelName}</span>
            </button>
            <AvatarModelPicker
              isOpen={showModelPicker}
              onClose={() => setShowModelPicker(false)}
              triggerRef={modelPickerTriggerRef}
              currentModel={avatarModel}
              onSelectModel={(url) => {
                onSelectModel?.(url);
                setShowModelPicker(false);
              }}
              onOpenAvatarLab={onOpenAvatarLab}
            />
          </div>

          {/* Dock and Close controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <button
              type="button"
              aria-label="Dock Left"
              title="Dock Left"
              onClick={() => setDockPosition("left")}
              style={{
                padding: "4px 6px",
                borderRadius: 4,
                border: "none",
                background: dockPosition === "left" ? "var(--accent-pale)" : "transparent",
                color: dockPosition === "left" ? "var(--accent)" : "var(--text-tertiary)",
                cursor: "pointer",
                fontSize: "0.7rem",
              }}
            >
              Dock Left
            </button>
            <button
              type="button"
              aria-label="Float Companion"
              title="Float Companion"
              onClick={() => setDockPosition("floating")}
              style={{
                padding: "4px 6px",
                borderRadius: 4,
                border: "none",
                background: dockPosition === "floating" ? "var(--accent-pale)" : "transparent",
                color: dockPosition === "floating" ? "var(--accent)" : "var(--text-tertiary)",
                cursor: "pointer",
                fontSize: "0.7rem",
              }}
            >
              Float Companion
            </button>
            <button
              type="button"
              aria-label="Dock Right"
              title="Dock Right"
              onClick={() => setDockPosition("right")}
              style={{
                padding: "4px 6px",
                borderRadius: 4,
                border: "none",
                background: dockPosition === "right" ? "var(--accent-pale)" : "transparent",
                color: dockPosition === "right" ? "var(--accent)" : "var(--text-tertiary)",
                cursor: "pointer",
                fontSize: "0.7rem",
              }}
            >
              Dock Right
            </button>
            <button
              type="button"
              aria-label="Hide Companion"
              title="Hide Companion"
              onClick={() => setCompanionVisible(false)}
              style={{
                padding: "4px 6px",
                borderRadius: 4,
                border: "none",
                background: "transparent",
                color: "var(--text-tertiary)",
                cursor: "pointer",
                fontSize: "0.7rem",
              }}
            >
              Hide Companion
            </button>
          </div>
        </div>

        {/* Companion Avatar View Container */}
        <div style={{ flex: 1, position: "relative", minHeight: 240, overflow: "hidden" }}>
          <VRMAvatar
            companionId={companionId}
            state={companionState}
            reducedMotion={false}
            textOnly={false}
            jawEnergy={jawEnergy}
            speakingRef={speakingRef}
            visemeEvents={visemeEvents}
            audioStartTimeRef={audioStartTimeRef}
            modelUrl={avatarModel ?? null}
            closeUp={avatarMode !== "full"}
          />
        </div>
      </aside>
    );
  };

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
          gap: 8,
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
          {messages.length > 0 && !isMobile && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
              · {messages.length} {messages.length === 1 ? "message" : "messages"}
            </span>
          )}
        </div>

        {/* Mobile View Switcher: [💬 Chat] [🌸 3D Avatar] */}
        {isMobile && avatarModel && (
          <div
            data-testid="mobile-mode-switcher"
            style={{
              display: "flex",
              alignItems: "center",
              background: "var(--bg-surface-raised, rgba(0,0,0,0.05))",
              padding: "2px",
              borderRadius: "20px",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <button
              type="button"
              data-testid="mobile-tab-chat"
              onClick={() => setMobileTab("chat")}
              style={{
                padding: "3px 10px",
                borderRadius: "16px",
                border: "none",
                background: mobileTab === "chat" ? "var(--accent)" : "transparent",
                color: mobileTab === "chat" ? "#ffffff" : "var(--text-secondary)",
                fontSize: "0.72rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 150ms ease",
              }}
            >
              💬 Chat
            </button>
            <button
              type="button"
              data-testid="mobile-tab-avatar"
              onClick={() => setMobileTab("avatar")}
              style={{
                padding: "3px 10px",
                borderRadius: "16px",
                border: "none",
                background: mobileTab === "avatar" ? "var(--accent)" : "transparent",
                color: mobileTab === "avatar" ? "#ffffff" : "var(--text-secondary)",
                fontSize: "0.72rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 150ms ease",
              }}
            >
              🌸 3D Avatar
            </button>
          </div>
        )}

        {/* Desktop Model Control Bar */}
        {!isMobile && (
          <div style={{ display: "flex", alignItems: "center" }}>
            <ModelControlBar
              currentMode={(activeProviderMode as any) || "auto"}
              currentModel={activeProviderModel}
              providerOptions={providerOptions || []}
              getModelOptions={getModelOptions || (() => [])}
              onSelectProvider={(mode, modelId) => onSelectProvider?.(mode, modelId ?? undefined)}
              imageEngine={imageEngine || internalImageEngine}
              onSelectImageEngine={(engine) => {
                onSelectImageEngine?.(engine);
                setInternalImageEngine(engine);
              }}
              voiceEngine={voiceEngine || internalVoiceEngine}
              onSelectVoiceEngine={(engine) => {
                onSelectVoiceEngine?.(engine);
                setInternalVoiceEngine(engine);
              }}
              onOpenSettings={onOpenSettings}
            />
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {!isMobile && avatarModel && !companionVisible && (
            <button
              type="button"
              aria-label="Show companion panel"
              onClick={() => setCompanionVisible(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 10px",
                borderRadius: "var(--radius-sm, 6px)",
                border: "1px solid var(--border-default)",
                background: "var(--bg-surface-raised)",
                color: "var(--text-secondary)",
                fontSize: "var(--text-xs)",
                cursor: "pointer",
              }}
            >
              <Bot size={14} color="var(--accent)" />
              <span>Show companion panel</span>
            </button>
          )}
          <StatusDot state={companionState} />
        </div>
      </header>

      {/* ── Voice Active Banner ───────────────────────── */}
      {isVoiceActive && (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 16px",
            background: "var(--accent-pale, rgba(235, 111, 146, 0.12))",
            borderBottom: "1px solid var(--border-subtle)",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-xs)", color: "var(--text-primary)" }}>
            <AudioLines size={16} color="var(--accent)" />
            <span>HINAA Live Voice is active — speaking & listening</span>
          </div>
          <button
            type="button"
            aria-label="Done"
            onClick={onStopVoice}
            style={{
              padding: "4px 14px",
              borderRadius: 999,
              background: "var(--accent)",
              color: "#ffffff",
              border: "none",
              cursor: "pointer",
              fontWeight: 700,
              fontSize: "var(--text-xs)",
            }}
          >
            Done
          </button>
        </div>
      )}

      {/* ── Main Area ───────────────────────────────── */}
      {isMobile && mobileTab === "avatar" && avatarModel ? (
        <div
          data-testid="mobile-avatar-screen"
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            position: "relative",
            width: "100%",
            height: "100%",
            overflow: "hidden",
            background: "var(--bg-canvas)",
          }}
        >
          {/* Top Floating Bar: Avatar Picker & Model Name */}
          <div
            style={{
              position: "absolute",
              top: 12,
              left: 12,
              right: 12,
              zIndex: 30,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "6px 12px",
              borderRadius: 24,
              background: "var(--bg-surface-raised, rgba(255, 255, 255, 0.9))",
              backdropFilter: "blur(12px)",
              boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <div style={{ position: "relative" }}>
              <button
                ref={modelPickerTriggerRef}
                type="button"
                aria-label="Switch Avatar Model"
                onClick={() => setShowModelPicker((prev) => !prev)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 10px",
                  borderRadius: "16px",
                  border: "1px solid var(--border-default)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 650,
                  cursor: "pointer",
                }}
              >
                <Sparkles size={13} color="var(--accent)" />
                <span>{currentModelName}</span>
              </button>
              <AvatarModelPicker
                isOpen={showModelPicker}
                onClose={() => setShowModelPicker(false)}
                triggerRef={modelPickerTriggerRef}
                currentModel={avatarModel}
                onSelectModel={(url) => {
                  onSelectModel?.(url);
                  setShowModelPicker(false);
                }}
                onOpenAvatarLab={onOpenAvatarLab}
              />
            </div>

            <button
              type="button"
              data-testid="mobile-back-to-chat"
              onClick={() => setMobileTab("chat")}
              style={{
                padding: "4px 12px",
                borderRadius: "16px",
                border: "none",
                background: "var(--accent-pale)",
                color: "var(--accent)",
                fontSize: "var(--text-xs)",
                fontWeight: 650,
                cursor: "pointer",
              }}
            >
              Open Chat 💬
            </button>
          </div>

          {/* Dedicated Full Portrait 3D VRM Canvas */}
          <div style={{ flex: 1, position: "relative", width: "100%", height: "100%" }}>
            <VRMAvatar
              companionId={companionId}
              state={companionState}
              reducedMotion={false}
              textOnly={false}
              jawEnergy={jawEnergy}
              speakingRef={speakingRef}
              visemeEvents={visemeEvents}
              audioStartTimeRef={audioStartTimeRef}
              modelUrl={avatarModel ?? null}
              closeUp={avatarMode !== "full"}
            />
          </div>

          {/* Bottom Floating Card: Live Speech Subtitle & Push to Talk */}
          <div
            style={{
              position: "absolute",
              bottom: 16,
              left: 16,
              right: 16,
              zIndex: 30,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            {(streamingText || partialTranscript || (messages.length > 0 && messages[messages.length - 1].role === "assistant")) && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  padding: "12px 16px",
                  borderRadius: "18px",
                  background: "var(--bg-surface-raised, rgba(255, 255, 255, 0.9))",
                  backdropFilter: "blur(16px)",
                  boxShadow: "0 8px 30px rgba(0,0,0,0.15)",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "0.85rem",
                  lineHeight: 1.4,
                  color: "var(--text-primary)",
                  maxHeight: 120,
                  overflowY: "auto",
                }}
              >
                <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--accent)", marginBottom: 4 }}>
                  {companionName}
                </div>
                <div>{streamingText || partialTranscript || messages[messages.length - 1]?.text}</div>
              </motion.div>
            )}

            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 12 }}>
              <button
                type="button"
                onClick={isVoiceActive ? onStopVoice : onStartVoice}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 24px",
                  borderRadius: "30px",
                  background: isVoiceActive ? "var(--danger, #ef4444)" : "var(--accent)",
                  color: "#ffffff",
                  border: "none",
                  boxShadow: "0 4px 16px rgba(0,0,0,0.2)",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  cursor: "pointer",
                }}
              >
                {isVoiceActive ? <Square size={16} fill="#fff" /> : <Mic size={16} />}
                <span>{isVoiceActive ? "Stop Voice" : "Talk Live"}</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
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
          {/* Rate limit recovery card if message contains rate limit error */}
          {messages.some((m) => m.role === "assistant" && /rate\s*limit/i.test(m.text || "")) && (
            <div
              data-testid="rate-limit-recovery-card"
              style={{
                padding: "var(--space-3) var(--space-4)",
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
                borderRadius: "var(--radius-md, 10px)",
                marginBottom: "var(--space-3)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              <div style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--danger, #ef4444)" }}>
                Brain Model Rate Limit / Cooldown Active
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)" }}>
                The selected brain model is temporarily rate limited. Please wait a moment or switch to Gemini.
              </div>
              <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-1)" }}>
                <button
                  type="button"
                  onClick={() => onSelectProvider?.("real", "gemini-2.5-flash")}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: "var(--accent)",
                    color: "#ffffff",
                    border: "none",
                    fontWeight: 600,
                    fontSize: "var(--text-xs)",
                    cursor: "pointer",
                  }}
                >
                  Switch to Gemini 2.5 Flash
                </button>
                <button
                  type="button"
                  onClick={() => onRetry?.()}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: "var(--bg-surface-raised)",
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-default)",
                    fontWeight: 600,
                    fontSize: "var(--text-xs)",
                    cursor: "pointer",
                  }}
                >
                  Retry Prompt
                </button>
              </div>
            </div>
          )}

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

        {/* Mobile floating 3D avatar jump button */}
        {isMobile && avatarModel && (
          <motion.button
            type="button"
            data-testid="mobile-floating-avatar-pill"
            whileTap={{ scale: 0.94 }}
            onClick={() => setMobileTab("avatar")}
            aria-label="Switch to 3D Avatar Screen"
            style={{
              position: "fixed",
              bottom: 84,
              right: 16,
              zIndex: 40,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 14px",
              borderRadius: "24px",
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              boxShadow: "0 6px 20px rgba(0,0,0,0.18)",
              color: "var(--text-primary)",
              fontSize: "0.78rem",
              fontWeight: 650,
              cursor: "pointer",
            }}
          >
            <Sparkles size={14} color="var(--accent)" />
            <span>3D Hinaa</span>
            <StatusDot state={companionState} />
          </motion.button>
        )}

        {/* Desktop Companion Panel */}
        {!isMobile && avatarModel && companionVisible && renderCompanionPanel()}
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
        {/* Agent Activity Card (Pulsing multi-stage progress, animated spinner, elapsed timer) */}
        <AgentActivityCard
          isActive={isThinking}
          steps={convertedActivitySteps}
          onCancel={currentAgentRunId ? onCancelAgentRun : onStop}
          onResume={currentAgentRunId ? onResumeAgentRun : undefined}
          onConfirm={currentAgentRunId && currentAgentConfirmationStepId ? () => onConfirmAgentStep?.(true) : undefined}
          onReject={currentAgentRunId && currentAgentConfirmationStepId ? () => onConfirmAgentStep?.(false) : undefined}
          onRecover={currentAgentRunId ? onRecoverAgentRun : undefined}
        />

        {/* Provider micro-status */}
        {(activeProviderMode || activeProviderModel) && (
          <div
            data-testid="provider-micro-status"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "4px 8px 6px",
              fontSize: "0.72rem",
              color: "var(--text-tertiary)",
            }}
          >
            <div
              role="button"
              tabIndex={0}
              onClick={() => onOpenSettings?.()}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onOpenSettings?.(); }}
              title="Click to switch brain models or configure provider settings"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                cursor: onOpenSettings ? "pointer" : "default",
                padding: "2px 6px",
                borderRadius: 4,
                transition: "background 0.15s ease",
              }}
              onMouseEnter={(e) => {
                if (onOpenSettings) (e.currentTarget as HTMLElement).style.background = "var(--bg-surface-hover, rgba(255,255,255,0.06))";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = "transparent";
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: providerHealth === "unavailable" ? "var(--danger, #ef4444)" : "var(--success, #10b981)",
                }}
              />
              <span style={{ fontWeight: 650, color: "var(--text-secondary)" }}>
                {getProviderDisplayName(activeProviderMode)}
              </span>
              {activeProviderModel && (
                <span
                  style={{
                    padding: "1px 6px",
                    borderRadius: 4,
                    background: "var(--bg-surface-raised)",
                    border: "1px solid var(--border-subtle)",
                    fontFamily: "monospace",
                    fontSize: "0.68rem",
                  }}
                >
                  {activeProviderModel}
                </span>
              )}
              <span>·</span>
              <span>
                {providerHealth === "unavailable"
                  ? "Offline"
                  : `Ready${providerLatencyMs ? ` · ${providerLatencyMs}ms` : ""}`}
              </span>
            </div>

            {providerHealth === "unavailable" && (
              <button
                type="button"
                onClick={() => onSelectProvider?.("real", "gemini-2.5-flash")}
                style={{
                  padding: "2px 8px",
                  borderRadius: 4,
                  background: "var(--accent)",
                  color: "#ffffff",
                  border: "none",
                  fontSize: "0.7rem",
                  fontWeight: 650,
                  cursor: "pointer",
                }}
              >
                Switch to Gemini
              </button>
            )}
          </div>
        )}

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
          {/* Hidden file input */}
          <input
            ref={imageInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleImageFile}
            data-testid="image-file-input"
          />

          {/* Attach */}
          <button
            type="button"
            title="Attach image"
            aria-label="Attach image"
            data-testid="attach-image-button"
            onClick={() => imageInputRef.current?.click()}
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: attachedImage ? "var(--accent-pale, rgba(244,114,182,0.15))" : "transparent",
              color: attachedImage ? "var(--accent, #f472b6)" : "var(--text-tertiary)",
              cursor: "pointer",
              transition: "all 150ms ease",
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
            onPaste={handlePaste}
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
          {isThinking || companionState === "thinking" || companionState === "speaking" ? (
            <button
              onClick={onStop}
              title="Stop generation & playback"
              aria-label="Stop generation & playback"
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
        </>
      )}
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

  // Render tool results using GenericResultRenderer (supports images, PDFs, browser actions, sources, etc.)
  const renderToolResults = () => {
    if (!message.toolResults || message.toolResults.length === 0) return null;
    
    return (
      <div style={{ marginTop: "var(--space-2)", display: "flex", flexDirection: "column", gap: "var(--space-2)", width: "100%" }}>
        {message.toolResults.map((tr, idx) => (
          <GenericResultRenderer key={`${tr.toolName}-${idx}`} toolName={tr.toolName} result={tr.result} />
        ))}
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

      {/* Attached image preview if user or assistant sent an image */}
      {message.imageUrl && (
        <div style={{ marginBottom: "var(--space-2)", maxWidth: "85%" }}>
          <img
            src={message.imageUrl}
            alt="Message attachment"
            style={{
              maxHeight: 240,
              maxWidth: "100%",
              borderRadius: "var(--radius-md, 8px)",
              objectFit: "contain",
              border: "1px solid var(--border-subtle)",
              display: "block",
            }}
          />
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
