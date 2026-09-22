import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  ThumbsUp,
  RefreshCw,
  Copy,
  Check,
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
  ArrowDown,
  Target,
  X,
} from "lucide-react";
import { useAutoScroll } from "../../features/chat/hooks/useAutoScroll";
import type { CompanionId, CompanionState, TranscriptMessage } from "../../features/companion/types";
import type { ProviderHealth } from "../../features/providers/types/provider";
import type { PowerUp, PowerUpId } from "../chat/ChatComposer";
import { ComposerV6, type ActionMode, type AttachmentRole, type IntelligenceLevel, type ContextChip } from "../chat/ComposerV6";
import { ApprovalCard, type ApprovalRiskLevel } from "../components/approval/ApprovalCard";
import { CodingTaskCard } from "../components/task/CodingTaskCard";
import { ArtifactCardV6 } from "../components/artifact/ArtifactCardV6";
import { ResponseEnvelopeRenderer } from "../components/response/ResponseEnvelopeRenderer";
import { CompanionDock, type DockMode } from "./CompanionDock";
import { PowerUpMentions, type ContextItem, type CommandItem } from "../../components/ui/PowerUpMentions";
import { SourceCard, type SourceItem } from "../../components/ui/SourceCard";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import { useCapabilities, type DiscoveredModel } from "../../features/providers/hooks/useCapabilities";


/* Local command registry fallback - used when /api/v1/commands is unavailable.
 * The capability field carries the frontend action routed through onCommand. */
const DEFAULT_COMMANDS: CommandItem[] = [
  { name: "goal", aliases: ["task", "objective"], label: "Goal Mode", description: "Autonomous multi-step goal execution with verification", descriptionShort: "Autonomous goal runner", icon: Target, color: "#e06c75", group: "agent", inputSchema: {}, capability: "agent-mode", riskLevel: "low-mutation", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/goal build a modern hero section"] },
  { name: "search", aliases: ["web", "research"], label: "Web Search", description: "Research a question with attributed sources", descriptionShort: "Research with sources", icon: Search, color: "#4FB989", group: "research", inputSchema: {}, capability: "search-web", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/search best coffee in Kathmandu"] },
  { name: "image", aliases: ["draw", "generate"], label: "Generate Image", description: "Open Image Studio to create an image locally", descriptionShort: "Create an image", icon: Sparkles, color: "#F36F9C", group: "creative", inputSchema: {}, capability: "generate-image", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "browser", examples: ["/image a sakura sunset"] },
  { name: "humanize", aliases: ["rewrite", "tone"], label: "Humanizer", description: "Open Humanizer Studio to rewrite text naturally", descriptionShort: "Rewrite text naturally", icon: Wand2, color: "#5B9DCF", group: "writing", inputSchema: {}, capability: "open-humanizer", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "browser", examples: ["/humanize"] },
  { name: "memory", aliases: ["remember"], label: "Memory", description: "Open your saved memories", descriptionShort: "Open memories", icon: Brain, color: "#B8A7F2", group: "personal", inputSchema: {}, capability: "remember-this", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/memory"] },
];

import { GenericResultRenderer } from "../../features/chat/components/GenericResultRenderer";
import { ResponseRenderer } from "../../components/ui/ResponseRenderer";
import { AgentActivityCard, type ActivityStep } from "../../features/chat/components/AgentActivityCard";
import { SearchingLoader, WebSearchLoader } from "../../components/ui/SearchingLoader";
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
    case "agent-router": return "Bynara Router";
    case "codecraft": return "CodeCraft AI";
    default:
      return mode.charAt(0).toUpperCase() + mode.slice(1);
  }
}

interface WorkModeProps {
  companionId?: CompanionId;
  companionState: CompanionState;
  plan?: AssistantTurnPlan;
  messages: TranscriptMessage[];
  streamingText: string;
  partialTranscript: string;
  isThinking: boolean;
  isSearching?: boolean;
  searchQuery?: string;
  input: string;
  onInputChange: (value: string) => void;
  onSend: (customText?: string) => void;
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
  availableModels?: any;
  companionName?: string;
  jawEnergy?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEvents?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  speechBridge?: React.MutableRefObject<any>;
  // Provider micro-status & fallback props
  activeProviderMode?: string;
  activeProviderModel?: string | null;
  providerHealth?: ProviderHealth;
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
  plan,
  messages,
  streamingText,
  partialTranscript,
  isThinking,
  isSearching = false,
  searchQuery,
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
  speechBridge,
  activeProviderMode,
  activeProviderModel,
  providerHealth = "unknown",
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
  onUpdateAttachmentRole,
}: WorkModeProps) {
  const { scrollRef, endRef, showJump, scrollToBottom } = useAutoScroll([messages, streamingText]);
  // Real capability discovery: providers + models actually configured on the
  // backend. The composer's model menu renders from this, so the user always
  // sees exactly what the runtime can answer with (never a fabricated list).
  const discoveredCapabilities = useCapabilities();
  const discoveredModels = discoveredCapabilities.models;
  const discoveredProviders = discoveredCapabilities.providers;
  const backendConnected = discoveredCapabilities.runtime.backendConnected;
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState("");
  const [mentionCursorPos, setMentionCursorPos] = useState(0);
  const [trigger, setTrigger] = useState<"@" | "/">("@");
  const [commands, setCommands] = useState<CommandItem[]>([]);
  const [dockMode, setDockMode] = useState<DockMode>(() => {
    try {
      const saved = localStorage.getItem("hinaa_companion_dock_mode");
      if (saved && ["right", "left", "floating", "compact", "hidden"].includes(saved)) {
        return saved as DockMode;
      }
    } catch {}
    return "right";
  });

  const handleDockModeChange = (mode: DockMode) => {
    setDockMode(mode);
    try {
      localStorage.setItem("hinaa_companion_dock_mode", mode);
    } catch {}
  };

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

  const [goalModeEnabled, setGoalModeEnabled] = useState<boolean>(() => {
    try {
      return localStorage.getItem("hinaa_goal_mode") === "true";
    } catch {
      return false;
    }
  });
  const toggleGoalMode = useCallback(() => {
    setGoalModeEnabled((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("hinaa_goal_mode", String(next));
      } catch {}
      return next;
    });
  }, []);

  const [contextChips, setContextChips] = useState<ContextChip[]>(() => {
    try {
      const saved = localStorage.getItem("hinaa_context_chips");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          // Filter out legacy fake default chips
          const filtered = parsed.filter((c: any) => c.id !== "p1" && c.id !== "r1" && c.id !== "i1");
          return filtered;
        }
      }
    } catch {}
    return [];
  });

  const handleRemoveChip = useCallback((id: string) => {
    setContextChips((prev) => {
      const next = prev.filter((c) => c.id !== id);
      try {
        localStorage.setItem("hinaa_context_chips", JSON.stringify(next));
      } catch {}
      return next;
    });
  }, []);

  const [actionMode, setActionMode] = useState<ActionMode>("chat");
  const [intelligenceLevel, setIntelligenceLevel] = useState<IntelligenceLevel>("auto");
  const [localTopic, setLocalTopic] = useState<string | null>(null);

  const activeTopic = localTopic !== null ? (localTopic || null) : (searchQuery || (plan as any)?.topic || null);

  const handleComposerSend = useCallback(
    (options?: { mode?: ActionMode; intelligence?: IntelligenceLevel; attachmentRole?: AttachmentRole; isGoalMode?: boolean } | ActionMode, role?: AttachmentRole) => {
      let text = input.trim();
      if (!text && !attachedImage) return;

      const mode = typeof options === "object" ? options?.mode : options;
      const isGoal = typeof options === "object" ? options?.isGoalMode : goalModeEnabled;

      if ((isGoal || mode === "goal") && !text.startsWith("/goal")) {
        text = `/goal ${text}`;
      } else if (mode === "research" && !text.startsWith("/search") && !text.startsWith("/research")) {
        text = `/search ${text}`;
      } else if (mode === "create" && !text.startsWith("/image") && !text.startsWith("/draw")) {
        text = `/image ${text}`;
      } else if (mode === "code" && !text.startsWith("/code")) {
        text = `/code ${text}`;
      }

      onSend(text);
    },
    [input, attachedImage, goalModeEnabled, onSend]
  );

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

  const replacePaletteToken = useCallback(
    (replacement: string) => {
      const tokenEnd = mentionCursorPos + 1 + mentionFilter.length;
      onInputChange(`${input.slice(0, mentionCursorPos)}${replacement}${input.slice(tokenEnd)}`);
      setShowMentions(false);
      setMentionFilter("");
    },
    [input, mentionCursorPos, mentionFilter, onInputChange],
  );

  const handleContextSelect = useCallback(
    (context: ContextItem) => {
      replacePaletteToken(`@${context.kind}:${context.sourceId} `);
    },
    [replacePaletteToken],
  );

  const handleCommandSelect = useCallback(
    (command: CommandItem) => {
      replacePaletteToken(`/${command.name} `);
    },
    [replacePaletteToken],
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
    if (dockMode === "hidden") return null;
    return (
      <CompanionDock
        dockMode={dockMode}
        onChangeDockMode={handleDockModeChange}
        companionId={companionId}
        companionState={companionState}
        plan={plan}
        avatarModel={avatarModel}
        avatarMode={avatarMode}
        companionName={companionName}
        jawEnergy={jawEnergy}
        speakingRef={speakingRef}
        visemeEvents={visemeEvents}
        audioStartTimeRef={audioStartTimeRef}
        speechBridge={speechBridge}
        onSelectModel={onSelectModel}
        onOpenAvatarLab={onOpenAvatarLab}
        isVoiceActive={isVoiceActive}
        onToggleVoice={isVoiceActive ? onStopVoice : onStartVoice}
        streamingText={streamingText}
        partialTranscript={partialTranscript}
        lastAssistantText={messages.filter((m) => m.role === "assistant").slice(-1)[0]?.text}
      />
    );
  };

  return (
    <div
      data-testid="work-mode"
      className="hinaa-work-surface"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
        overflow: "hidden",
        background: "var(--bg-canvas)",
      }}
    >
      {/* ── Work header — renders on every viewport. Its children are themselves
             device-gated (mobile view switcher vs. desktop model control bar),
             so gating the whole block on `isMobile` made the message count, the
             desktop ModelControlBar, and the "Show companion panel" button
             unreachable dead code. ─────────────────────────────────────────── */}
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
          {/* Duplicate of the inline research card below, and the phone header
              row cannot fit it without clipping it at the screen edge. */}
          {!isMobile && <SearchingLoader visible={Boolean(isSearching)} query={searchQuery} />}
          {!isMobile && avatarModel && dockMode === "hidden" && (
            <button
              type="button"
              aria-label="Show companion panel"
              onClick={() => handleDockModeChange("right")}
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
              plan={plan}
              reducedMotion={false}
              textOnly={false}
              jawEnergy={jawEnergy}
              speakingRef={speakingRef}
              visemeEvents={visemeEvents}
              audioStartTimeRef={audioStartTimeRef}
              speechBridge={speechBridge}
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
          <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden", position: "relative" }}>
        {/* Transcript column — full screen width with generous responsive padding */}
        <div
          ref={scrollRef}
          className="hinaa-work-transcript"
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            overflowX: "hidden",
            overscrollBehaviorY: "contain",
            WebkitOverflowScrolling: "touch",
            padding: "var(--space-4) clamp(20px, 4vw, 56px) var(--space-2)",
            display: "flex",
            flexDirection: "column",
            maxWidth: "100%",
            width: "100%",
            margin: "0",
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

          {/* Welcome */}
          {showWelcome && <WorkWelcome onAction={onWelcomeAction} />}

          {/* Messages */}
          {!showWelcome &&
            messages.map((msg) => (
              <WorkMessage key={msg.id} message={msg} />
            ))}

          {/* Execution progress — inline in the thread, between the trigger and
           * the answer it produced. */}
          <AgentActivityCard
            isActive={isThinking}
            steps={convertedActivitySteps}
            onCancel={currentAgentRunId ? onCancelAgentRun : onStop}
            onResume={currentAgentRunId ? onResumeAgentRun : undefined}
            onConfirm={currentAgentRunId && currentAgentConfirmationStepId ? () => onConfirmAgentStep?.(true) : undefined}
            onReject={currentAgentRunId && currentAgentConfirmationStepId ? () => onConfirmAgentStep?.(false) : undefined}
            onRecover={currentAgentRunId ? onRecoverAgentRun : undefined}
          />

          {/* Web Search Live Research Animation Card */}
          {isSearching && (
            <WebSearchLoader visible={true} query={searchQuery} />
          )}

          {/* Streaming */}
          {streamingText && (() => {
            const lastMsg = messages[messages.length - 1];
            if (
              lastMsg &&
              lastMsg.role === "assistant" &&
              (lastMsg.text.trim() === streamingText.trim() ||
                lastMsg.text.trim().startsWith(streamingText.trim()))
            ) {
              return null;
            }
            return (
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
            );
          })()}

          {/* Tool approvals */}
          {toolApprovals.map((ta) => (
            <div key={`${ta.messageId}-${ta.request.id}`} data-testid="tool-approval" style={{ marginBottom: "var(--space-3)" }}>
              <ApprovalCard
                id={ta.request.id}
                action={ta.request.toolName}
                target={ta.request.parameters ? JSON.stringify(ta.request.parameters).slice(0, 80) : undefined}
                riskLevel={(ta.request.riskLevel as ApprovalRiskLevel) || "medium"}
                reason={ta.request.description}
                onApprove={() => onResolveTool(ta.messageId, ta.request, true)}
                onReject={() => onResolveTool(ta.messageId, ta.request, false)}
              />
            </div>
          ))}

          {/* Spacer for composer */}
          <div style={{ height: "var(--space-2)", flexShrink: 0 }} />
          <div ref={endRef} />
        </div>

        {/* Floating jump-to-bottom button when user scrolled up */}
        {showJump && (
          <button
            type="button"
            data-testid="jump-to-bottom-button"
            onClick={() => scrollToBottom()}
            style={{
              position: "absolute",
              bottom: 16,
              right: isMobile ? 16 : 340,
              zIndex: 35,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 20,
              background: "var(--bg-surface-raised, #ffffff)",
              color: "var(--accent, #eb6f92)",
              border: "1px solid var(--border-default)",
              boxShadow: "0 4px 14px rgba(0,0,0,0.15)",
              fontSize: "0.75rem",
              fontWeight: 650,
              cursor: "pointer",
            }}
          >
            <ArrowDown size={14} />
            <span>Latest</span>
          </button>
        )}

        {/* Desktop Companion Panel */}
        {!isMobile && avatarModel && dockMode !== "hidden" && renderCompanionPanel()}
      </div>

      {/* ── Composer (attached to bottom) ─────────── */}
      <div
        data-testid="work-composer"
        className="hinaa-work-composer"
        style={{
          padding: "var(--space-2) clamp(20px, 4vw, 56px) var(--space-3)",
          maxWidth: "100%",
          width: "100%",
          margin: "0",
          flexShrink: 0,
          borderTop: "1px solid var(--border-subtle)",
          background: "var(--bg-surface)",
        }}
      >
        {/* Provider micro-status — the composer's own model chip already shows
            this on a phone, where 42px of transcript is worth more than a repeat. */}
        {!isMobile && (activeProviderMode || activeProviderModel) && (
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
                  background:
                    providerHealth === "unavailable" ? "var(--danger, #ef4444)"
                    : providerHealth === "healthy" ? "var(--success, #10b981)"
                    : "var(--text-tertiary, #64748b)",
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
                  : providerHealth === "degraded"
                    ? "Throttled"
                    : providerHealth === "healthy"
                      ? `Ready${providerLatencyMs ? ` · ${providerLatencyMs}ms` : ""}`
                      : providerHealth === "checking"
                        ? "Checking…"
                        : "Not tested yet"}
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

        {/* Goal Mode Status Banner */}
        {goalModeEnabled && (
          <div
            data-testid="goal-mode-banner"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "6px 12px",
              marginBottom: 8,
              background: "rgba(220, 95, 139, 0.08)",
              border: "1px solid rgba(220, 95, 139, 0.25)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--accent-primary, #dc5f8b)",
              fontWeight: 500,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Target size={14} />
              <span><strong>Goal Mode Active:</strong> Autonomous plan breakdown, verification criteria, and milestone execution enabled.</span>
            </div>
            <button
              onClick={toggleGoalMode}
              style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: 2 }}
              title="Exit Goal Mode"
            >
              <X size={13} />
            </button>
          </div>
        )}

        {/* Frontier V6 Composer */}
        <ComposerV6
          compact={isMobile}
          value={input}
          onChange={(val) => {
            onInputChange(val);
            const cursorPos = val.length;
            const beforeCursor = val.slice(0, cursorPos);
            const mentionMatch = beforeCursor.match(/@(\S*)$/);
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
          }}
          onSend={handleComposerSend}
          onStop={onStop}
          isGenerating={isThinking || companionState === "thinking" || companionState === "speaking"}
          disabled={disabled}
          isVoiceActive={isVoiceActive}
          onVoiceToggle={isVoiceActive ? onStopVoice : onStartVoice}
          contextChips={contextChips}
          onRemoveChip={handleRemoveChip}
          activeTopic={activeTopic}
          onClearTopic={() => setLocalTopic("")}
          activeModel={activeProviderModel || "gemini-2.5-flash"}
          activeProvider={getProviderDisplayName(activeProviderMode)}
          onOpenModelSelector={onOpenSettings}
          discoveredModels={discoveredModels}
          discoveredProviders={discoveredProviders}
          selectedModelId={activeProviderModel ?? null}
          selectedProviderId={activeProviderMode ?? null}
          isAutoRouter={!activeProviderModel}
          backendConnected={backendConnected}
          onSelectAuto={() => onSelectProvider?.("auto")}
          onSelectModel={(model: DiscoveredModel) => onSelectProvider?.(model.provider, model.id)}
          intelligenceLevel={intelligenceLevel}
          onChangeIntelligence={setIntelligenceLevel}
          actionMode={actionMode}
          onChangeActionMode={setActionMode}
          isGoalMode={goalModeEnabled}
          onToggleGoalMode={toggleGoalMode}
          attachedImage={attachedImage}
          onImageAttach={(dataUrl, role) => {
            onImageAttach(dataUrl);
            if (onUpdateAttachmentRole && role) onUpdateAttachmentRole(role);
          }}
          onSelectArtifact={(command) => onInputChange(`${command} `)}
        />
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
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(false);

  const plan = message.plan;
  const answeredBy = plan?.resolvedModel || plan?.resolvedProvider || null;
  const requestedBrain = plan?.requestedModel || plan?.requestedProvider || null;
  const answeredByLabel = answeredBy
    ? `${answeredBy}${plan?.latencyMs ? ` · ${Math.round(plan.latencyMs / 100) / 10}s` : ""}`
    : null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  // Render tool results using GenericResultRenderer
  const renderToolResults = () => {
    if (!message.toolResults || message.toolResults.length === 0) return null;
    return (
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
        {message.toolResults.map((tr, idx) => (
          <GenericResultRenderer key={`${tr.toolName}-${idx}`} toolName={tr.toolName} result={tr.result} />
        ))}
      </div>
    );
  };

  return (
    <div
      style={{
        marginBottom: 16,
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        width: "100%",
        maxWidth: 768,
        margin: isUser ? "12px 0 12px auto" : "12px 0",
      }}
    >
      {/* Assistant Header Line */}
      {!isUser && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            marginBottom: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: 8,
                background: "#1a232b",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Sparkles size={13} />
            </div>
            <span style={{ fontWeight: 700, fontSize: 13, letterSpacing: "0.04em", color: "#1e293b" }}>
              HINA
            </span>
            {message.createdAt && (
              <span style={{ fontSize: 11, color: "#94a3b8" }}>
                {new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
            {answeredByLabel && (
              <span
                style={{ fontSize: 10, color: plan?.fallback ? "#b45309" : "#94a3b8", fontWeight: plan?.fallback ? 600 : 400 }}
                title={plan?.fallback ? plan.fallbackReason ?? undefined : undefined}
              >
                {answeredByLabel}
              </span>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button
              type="button"
              onClick={handleCopy}
              title="Copy message"
              style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: 4 }}
            >
              {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
            </button>
          </div>
        </div>
      )}

      {plan?.fallback && !isUser && (
        <div
          style={{
            fontSize: 11,
            lineHeight: 1.5,
            color: "#92400e",
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 8,
            padding: "6px 10px",
            marginBottom: 6,
            marginLeft: 34,
            maxWidth: 620,
          }}
        >
          {`You asked for ${requestedBrain ?? "the selected brain"}, but ${answeredBy ?? "another brain"} answered because ${plan.fallbackReason ?? "the first attempt did not finish"}.`}
        </div>
      )}

      {/* Message bubble */}
      <div
        className="hinaa-work-bubble"
        style={{
          width: isUser ? "auto" : "100%",
          maxWidth: isUser ? 580 : "100%",
          padding: isUser ? "12px 18px" : "4px 0 8px 34px",
          borderRadius: isUser ? "18px 18px 4px 18px" : "0",
          background: isUser ? "#1a232b" : "transparent",
          border: "none",
          boxShadow: isUser ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
          color: isUser ? "#ffffff" : "#334155",
          fontSize: 14,
          lineHeight: 1.65,
          whiteSpace: isUser ? "pre-wrap" : "normal",
          wordBreak: "break-word",
        }}
      >
        {isUser && message.imageUrl && (
          <img
            src={message.imageUrl}
            alt="Your attached image"
            style={{
              display: "block",
              maxWidth: 220,
              width: "100%",
              borderRadius: 10,
              marginBottom: message.text ? 8 : 0,
            }}
          />
        )}
        {isUser ? message.text : <ResponseEnvelopeRenderer rawText={message.text} />}
        {isStreaming && (
          <span
            style={{
              display: "inline-block",
              width: 2,
              height: "1.1em",
              background: "#0f172a",
              marginLeft: 4,
              verticalAlign: "middle",
              animation: "blink 1s step-end infinite",
            }}
          />
        )}
      </div>

      {/* User message timestamp underneath on right */}
      {isUser && message.createdAt && (
        <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
          {new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      )}

      {/* Assistant reactions */}
      {!isUser && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 34, marginTop: 4 }}>
          <button
            type="button"
            onClick={() => setLiked(!liked)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: liked ? "#10b981" : "#94a3b8",
              display: "flex",
              alignItems: "center",
              padding: 2,
            }}
            title="Good response"
          >
            <ThumbsUp size={13} />
          </button>
          <button
            type="button"
            onClick={handleCopy}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "#94a3b8",
              display: "flex",
              alignItems: "center",
              padding: 2,
            }}
            title="Copy"
          >
            <Copy size={13} />
          </button>
          <button
            type="button"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "#94a3b8",
              display: "flex",
              alignItems: "center",
              padding: 2,
            }}
            title="Regenerate"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      )}

      {/* Tool Results with Source Cards */}
      {!isUser && renderToolResults()}
    </div>
  );
}


function StatusDot({ state }: { state: CompanionState }) {
  const color = state === "speaking" ? "#10b981" : state === "thinking" ? "#f59e0b" : "#94a3b8";
  return (
    <span
      style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        backgroundColor: color,
        display: "inline-block",
      }}
      title={`Companion state: ${state}`}
    />
  );
}

/* ── Welcome Screen ──────────────────────────────────────── */
function WorkWelcome({
  onAction,
}: {
  onAction: (action: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(false);

  const hour = new Date().getHours();
  const daypart = hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
  const greetingText = `Good ${daypart} — I'm Hina, your AI workspace companion. Ask me anything, research the live web with citations, create documents and images, or switch brains anytime from the model menu.`;

  const suggestions = [
    { label: "Explain a concept", prompt: "Explain Retrieval-Augmented Generation in simple terms with an example: " },
    { label: "Research live", prompt: "Research the latest developments in " },
    { label: "Create a document", prompt: "Create a comprehensive document about " },
    { label: "Generate an image", prompt: "/image " },
  ];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(greetingText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div style={{ maxWidth: 768, width: "100%", margin: "16px 0 24px 0" }}>
      {/* Header line */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 8,
              background: "#1a232b",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Sparkles size={13} />
          </div>
          <span style={{ fontWeight: 700, fontSize: 13, letterSpacing: "0.04em", color: "#1e293b" }}>
            HINA
          </span>
          <span style={{ fontSize: 11, color: "#94a3b8" }}>09:41</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button
            type="button"
            onClick={handleCopy}
            title="Copy message"
            style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: 4 }}
          >
            {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
          </button>
          <button
            type="button"
            onClick={() => onAction("research")}
            title="Regenerate"
            style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: 4 }}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Greeting text */}
      <div
        style={{
          padding: "6px 0 12px 34px",
          fontSize: 14,
          lineHeight: 1.65,
          color: "#334155",
        }}
      >
        {greetingText}
      </div>

      {/* Subtle feedback reaction buttons */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 34 }}>
        <button
          type="button"
          onClick={() => setLiked(!liked)}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: liked ? "#10b981" : "#94a3b8",
            display: "flex",
            alignItems: "center",
            padding: 2,
          }}
          title="Good response"
        >
          <ThumbsUp size={13} />
        </button>
        <button
          type="button"
          onClick={handleCopy}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "#94a3b8",
            display: "flex",
            alignItems: "center",
            padding: 2,
          }}
          title="Copy"
        >
          <Copy size={13} />
        </button>
        <button
          type="button"
          onClick={() => onAction("research")}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "#94a3b8",
            display: "flex",
            alignItems: "center",
            padding: 2,
          }}
          title="Regenerate"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Starter suggestion chips — real prompts, one click to start */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, paddingLeft: 34, marginTop: 14 }}>
        {suggestions.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => onAction(s.prompt)}
            style={{
              padding: "6px 12px",
              borderRadius: 999,
              border: "1px solid var(--border-default, #e2e8f0)",
              background: "var(--bg-surface, #ffffff)",
              color: "var(--text-secondary, #475569)",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}

