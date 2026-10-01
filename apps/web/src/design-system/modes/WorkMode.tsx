import React, { useCallback, useEffect, useRef, useState, useMemo, memo } from "react";
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
  FileDown,
  Presentation,
  Loader2,
  Eye,
} from "lucide-react";
import { useLiveVision } from "../../features/vision/useLiveVision";
import { downloadMarkdownPdf, downloadMarkdownPptx } from "../../features/documents/exportPdf";
import { useAutoScroll } from "../../features/chat/hooks/useAutoScroll";
import type { CompanionId, CompanionState, TranscriptMessage } from "../../features/companion/types";
import type { ProviderHealth } from "../../features/providers/types/provider";
import type { RecoveryBrain } from "../../features/providers/utils/resolveProviderSelection";
import type { PowerUp, PowerUpId } from "../chat/ChatComposer";
import { ATTACHMENT_ROLES, ComposerV6, type ActionMode, type AttachmentRole, type IntelligenceLevel, type ContextChip } from "../chat/ComposerV6";
import { ApprovalCard, type ApprovalRiskLevel } from "../components/approval/ApprovalCard";
import { CodingTaskCard } from "../components/task/CodingTaskCard";
import { ArtifactCardV6 } from "../components/artifact/ArtifactCardV6";
import { ResponseEnvelopeRenderer } from "../components/response/ResponseEnvelopeRenderer";
import { CompanionDock, type DockMode } from "./CompanionDock";
import { PowerUpMentions, type ContextItem, type CommandItem } from "../../components/ui/PowerUpMentions";
import { SourceCard, type SourceItem } from "../../components/ui/SourceCard";
import { HinaBrainThinking } from "../../components/ui/HinaBrainThinking";
import { SteepAnalyticsBar } from "../../features/telemetry/SteepAnalyticsBar";
import { extractBrainThought } from "../../lib/brainThoughtExtractor";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import { useCapabilities, type DiscoveredModel } from "../../features/providers/hooks/useCapabilities";
import {
  useActionEngine,
  HinaSurface,
  ComposerSuggestionStrip,
  ReminderCard,
  ImageJobCard,
  SplitCard,
  matchLocalActionIntent,
  type HinaActionDraft,
} from "../../features/actions";


/* Local command registry fallback - used when /api/v1/commands is unavailable.
 * Rows listed in LOCAL_COMMAND_ACTIONS below are opened in this tab. */
const DEFAULT_COMMANDS: CommandItem[] = [
  { name: "goal", aliases: ["task", "objective"], label: "Goal Mode", description: "Autonomous multi-step goal execution with verification", descriptionShort: "Autonomous goal runner", icon: Target, color: "#e06c75", group: "agent", inputSchema: {}, capability: "agent-mode", riskLevel: "low-mutation", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/goal build a modern hero section"] },
  { name: "search", aliases: ["web", "research"], label: "Web Search", description: "Research a question with attributed sources", descriptionShort: "Research with sources", icon: Search, color: "#4FB989", group: "research", inputSchema: {}, capability: "search-web", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/search best coffee in Kathmandu"] },
  { name: "image", aliases: ["draw", "generate"], label: "Generate Image", description: "Open Image Studio to create an image locally", descriptionShort: "Create an image", icon: Sparkles, color: "#F36F9C", group: "creative", inputSchema: {}, capability: "generate-image", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "browser", examples: ["/image a sakura sunset"] },
  { name: "humanize", aliases: ["rewrite", "tone"], label: "Humanizer", description: "Open Humanizer Studio to rewrite text naturally", descriptionShort: "Rewrite text naturally", icon: Wand2, color: "#5B9DCF", group: "writing", inputSchema: {}, capability: "open-humanizer", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "browser", examples: ["/humanize"] },
  { name: "memory", aliases: ["remember"], label: "Memory", description: "Open your saved memories", descriptionShort: "Open memories", icon: Brain, color: "#B8A7F2", group: "personal", inputSchema: {}, capability: "remember-this", riskLevel: "read", approvalPolicy: "automatic", availability: "configured", executionLocation: "api", examples: ["/memory"] },
];

/* Palette rows whose handler is a surface in this browser tab. Selecting one
 * opens it through onCommand; the rest keep their /token for the composer. */
const LOCAL_COMMAND_ACTIONS: Record<string, string> = {
  memory: "remember-this",
  settings: "open-settings",
  avatar: "open-avatar-lab",
};

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
    case "pgsgrove": return "PGSGrove AI";
    case "seekai": return "SeekAI";
    case "tokentable": return "TokenTable";
    case "xkiro": return "XKiro AI";
    case "cavoti": return "Cavoti AI";
    case "apmix": return "APMIX.AI";
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
  onSend: (customText?: string, attachmentRole?: AttachmentRole) => void;
  onAddMessage?: (message: TranscriptMessage) => void;
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
  /** Brain a recovery button may offer: the strongest one whose last live call answered. */
  brainRecovery?: RecoveryBrain | null;
  onSelectProvider?: (mode: string, modelId?: string) => void;
  onRetry?: () => void;
  onOpenLibrary?: () => void;
  onOpenImages?: () => void;
  providerOptions?: any[];
  getModelOptions?: (mode: any) => Array<{ id: string; label: string; isDefault: boolean }>;
  imageEngine?: string;
  onSelectImageEngine?: (engine: string) => void;
  voiceEngine?: string;
  onSelectVoiceEngine?: (engine: string) => void;
  onOpenSettings?: () => void;
  conversationId?: string;
  onOpenTerminal?: (initialCommand?: string) => void;
  onOpenVault?: () => void;
  isDark?: boolean;
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
  isDark = false,
  input,
  onInputChange,
  onSend,
  onAddMessage,
  onStop,
  disabled,
  isVoiceActive,
  onStartVoice,
  onStopVoice,
  onOpenTerminal,
  onOpenVault,
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
  brainRecovery,
  onSelectProvider,
  onRetry,
  providerOptions,
  getModelOptions,
  imageEngine,
  onSelectImageEngine,
  voiceEngine,
  onSelectVoiceEngine,
  onOpenSettings,
  conversationId,
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
  const liveVision = useLiveVision(conversationId);

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

  // HINA Action Engine & Motion System ("The Walk" + Non-blocking Suggestion Strip)
  const {
    suggestion,
    activeDraft,
    committedActions,
    adoptSuggestion,
    dismissSuggestion,
    commitAction,
    dismissDraft,
    removeCommittedAction,
    updateCommittedAction,
  } = useActionEngine(input, () => onInputChange(""));

  const handleCommitAction = useCallback(
    (draft: HinaActionDraft) => {
      commitAction(draft);
      const data = draft.fields?.data as any;
      let text = `Action committed: ${data?.title || draft.intent}`;

      if (draft.intent === "reminder.create") {
        text = `Reminder scheduled: ${data?.title || "Reminder"} · ${data?.when || ""}`;
      } else if (draft.intent === "pdf.doc") {
        text = `Generating PDF document: "${data?.title || "Document"}"`;
        // Trigger actual PDF generation command through chat so backend compiles it
        if (data?.title) {
          onSend(`/pdf ${data.title}`);
        }
      } else if (draft.intent === "image.job") {
        text = `Generating artwork for "${data?.prompt || "image"}"`;
        if (data?.prompt) {
          onSend(`/image ${data.prompt}`);
        }
      } else if (draft.intent === "timer.start") {
        text = `Timer started: ${data?.label || "Timer"} · ${Math.round((data?.durationSeconds || 0) / 60)}:00`;
      } else if (draft.intent === "split") {
        text = `Bill split: ${data?.currency || "₹"}${data?.totalAmount || 0} ÷ ${data?.peopleCount || 1} = ${data?.currency || "₹"}${data?.perPerson || 0} each`;
      } else if (draft.intent === "checklist.create") {
        text = `Checklist created: ${data?.title || "Checklist"} (${data?.items?.length || 0} items)`;
      } else if (draft.intent === "event.create") {
        text = `Event scheduled: ${data?.title || "Event"} · ${data?.dateStr || ""}, ${data?.timeStr || ""}`;
      }

      if (onAddMessage) {
        onAddMessage({
          id: `action-${draft.intent}-${Date.now()}`,
          role: "assistant",
          text,
          createdAt: new Date().toISOString(),
          actionDraft: {
            ...draft,
            status: "success",
          },
        });
      }
    },
    [commitAction, onAddMessage, onSend]
  );

  const handleComposerSend = useCallback(
    (options?: {
      mode?: ActionMode;
      intelligence?: IntelligenceLevel;
      attachmentRole?: AttachmentRole;
      isGoalMode?: boolean;
    }) => {
      // Flow B: Enter ALWAYS sends normal chat text! Never block or hijack user input!
      let text = input.trim();
      if (!text && !attachedImage) return;

      // Auto-attach Live Eyes screen frame if active and no manual picture attached
      if (liveVision.isActive && !attachedImage) {
        const frame = liveVision.grabFrame() || liveVision.latestFrame;
        if (frame) {
          onImageAttach(frame);
        }
      }

      // Clear any pending suggestion strip or draft so conversation proceeds cleanly
      if (suggestion) {
        dismissSuggestion();
      }
      if (activeDraft) {
        dismissDraft();
      }

      const mode = options?.mode;
      const isGoal = options?.isGoalMode ?? goalModeEnabled;

      if ((isGoal || mode === "goal") && !text.startsWith("/goal")) {
        text = `/goal ${text}`;
      } else if (mode === "research" && !text.startsWith("/search") && !text.startsWith("/research")) {
        text = `/search ${text}`;
      } else if (mode === "create" && !text.startsWith("/image") && !text.startsWith("/draw")) {
        text = `/image ${text}`;
      } else if (mode === "code" && !text.startsWith("/code")) {
        text = `/code ${text}`;
      }

      onSend(text, options?.attachmentRole);

      // Requirements 1 & 2: Object stays IN THE THREAD
      const detected = matchLocalActionIntent(text);
      if (detected && onAddMessage) {
        const data = detected.fields?.data as any;
        if (detected.intent === "reminder.create") {
          onAddMessage({
            id: `action-reminder-${Date.now()}`,
            role: "assistant",
            text: `Reminder scheduled: ${data?.title || "Reminder"} · ${data?.when || ""}`,
            createdAt: new Date().toISOString(),
            actionDraft: {
              ...detected,
              status: "success",
            },
          });
        } else if (detected.intent === "pdf.doc") {
          onAddMessage({
            id: `action-pdf-${Date.now()}`,
            role: "assistant",
            text: `Compiling PDF document: "${data?.title || text}"`,
            createdAt: new Date().toISOString(),
            actionDraft: {
              ...detected,
              status: "running",
            },
          });
        } else if (detected.intent === "image.job") {
          onAddMessage({
            id: `action-image-${Date.now()}`,
            role: "assistant",
            text: `Generating image for "${data?.prompt || text}"`,
            createdAt: new Date().toISOString(),
            actionDraft: {
              ...detected,
              status: "running",
              fields: {
                ...detected.fields,
                data: {
                  ...data,
                  stage: "generating",
                  elapsedSeconds: 0,
                },
              },
            },
          });
        }
      }
    },
    [input, attachedImage, goalModeEnabled, onSend, suggestion, activeDraft, dismissSuggestion, dismissDraft, onAddMessage]
  );

  const currentAvatarDef = AVATAR_REGISTRY.find((a) => a.fileUrl === avatarModel);
  const currentModelName = currentAvatarDef?.name || "Hinaa (Original)";

  const toolActivitySteps: ActivityStep[] = useMemo(() => {
    // Only inspect the assistant message of the current active turn to avoid leaking previous turns' completed tools
    const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
    const activity =
      lastMessage && lastMessage.role === "assistant" ? lastMessage.toolActivity || [] : [];

    const toStep = (act: (typeof activity)[number], index: number): ActivityStep => ({
      id: act.id,
      toolName: act.id,
      title: act.label || `Running ${act.id}`,
      status:
        act.status === "complete" || act.status === "completed"
          ? ("completed" as const)
          : act.status === "error" || act.status === "failed"
            ? ("failed" as const)
            : act.status === "cancelled"
              ? ("cancelled" as const)
              : act.status === "pending"
                ? ("pending" as const)
                : ("running" as const),
      stepNumber: index + 1,
      totalSteps: activity.length,
    });

    // The turn stream closes long before the action it proposed finishes: a
    // PDF keeps being built against /tools/execute for tens of seconds while
    // `isThinking` is already false. Gating these rows on the turn made a
    // genuinely running tool invisible. Pending proposals are excluded — they
    // have their own ApprovalCard, and "Active Execution" would over-claim an
    // action that has not been allowed yet.
    if (!isThinking) {
      return activity.filter((act) => act.status === "running").map(toStep);
    }
    return activity.map(toStep);
  }, [isThinking, messages]);

  const convertedActivitySteps: ActivityStep[] = useMemo(() => {
    if (toolActivitySteps.length > 0) return toolActivitySteps;

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
  }, [toolActivitySteps, agentSteps]);

  const isAgentActive = (Boolean(currentAgentRunId) || agentSteps.length > 0) && agentSteps.some((s) => s.status === "active" || s.status === "pending");
  const isToolActive = toolActivitySteps.some((s) => s.status === "running");
  const isExecutionLive = isAgentActive || isToolActive;

  // What a recovery button may promise. `null` means no gateway answered its
  // last live call, and the honest UI then says so rather than naming a model.
  const recoveryLabel = brainRecovery ? getProviderDisplayName(brainRecovery.mode) : null;

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
      const action = LOCAL_COMMAND_ACTIONS[command.name];
      if (action) {
        replacePaletteToken("");
        onCommand?.(action);
        return;
      }
      replacePaletteToken(`/${command.name} `);
    },
    [replacePaletteToken, onCommand],
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
        lastAssistantText={
          plan?.spokenText ||
          plan?.displayText ||
          (() => {
            const raw = messages.filter((m) => m.role === "assistant").slice(-1)[0]?.text;
            if (!raw) return "";
            try {
              const parsed = JSON.parse(raw);
              return parsed.spokenText || parsed.displayText || raw;
            } catch {
              return raw;
            }
          })()
        }
        isDark={isDark}
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
          display: isMobile ? "none" : "flex",
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
        {!isMobile ? (
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
                · {messages.length} {messages.length === 1 ? "message" : "messages"}
              </span>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", paddingRight: 4 }}>
            <Sparkles size={16} color="var(--accent)" />
          </div>
        )}

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

        {/* Model Control Bar */}
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

      {/* ── Steep Editorial Analytics Bar (Pillar 4) ── */}
      <SteepAnalyticsBar
        activeModel={activeProviderModel || activeProviderMode || "qwen3.8-max"}
        onOpenTerminal={() => onOpenTerminal?.()}
        onOpenVault={onOpenVault}
      />

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
            padding: isMobile ? "8px 10px 14px" : "var(--space-4) clamp(20px, 4vw, 56px) var(--space-2)",
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
                {recoveryLabel
                  ? `The selected brain model is temporarily rate limited. Wait a moment, or switch to ${recoveryLabel} — the last brain to answer a live call.`
                  : "The selected brain model is temporarily rate limited, and no other brain has answered a live call yet. Retry is the only honest option."}
              </div>
              <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-1)" }}>
                {brainRecovery && (
                  <button
                    type="button"
                    data-testid="brain-recovery-switch"
                    onClick={() =>
                      onSelectProvider?.(brainRecovery.mode, brainRecovery.model ?? undefined)
                    }
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
                    Switch to {recoveryLabel}
                  </button>
                )}
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
          {showWelcome && <WorkWelcome isDark={isDark} onAction={onWelcomeAction} />}

          {/* Messages (Deduplicated: strictly one response at a time) */}
          {!showWelcome &&
            messages
              .filter((msg, idx, arr) => {
                // Deduplicate identical message IDs
                if (arr.findIndex((m) => m.id === msg.id) !== idx) return false;
                // Deduplicate consecutive identical assistant messages
                if (
                  msg.role === "assistant" &&
                  idx > 0 &&
                  arr[idx - 1].role === "assistant" &&
                  arr[idx - 1].text.trim() === msg.text.trim()
                ) {
                  return false;
                }
                return true;
              })
              .map((msg) => (
                <WorkMessage key={msg.id} message={msg} isDark={isDark} />
              ))}

          {/* Execution progress — only shown when execution is actually live with real steps */}
          {isExecutionLive && convertedActivitySteps.length > 0 && (
            <AgentActivityCard
              isActive={isExecutionLive}
              steps={convertedActivitySteps}
              onCancel={() => {
                onCancelAgentRun?.();
                onStop?.();
              }}
              onResume={currentAgentRunId ? onResumeAgentRun : undefined}
              onConfirm={currentAgentRunId && currentAgentConfirmationStepId ? () => onConfirmAgentStep?.(true) : undefined}
              onReject={currentAgentRunId && currentAgentConfirmationStepId ? () => onConfirmAgentStep?.(false) : undefined}
              onRecover={currentAgentRunId ? onRecoverAgentRun : undefined}
            />
          )}

          {/* Single active in-progress response bubble: thinking, searching, or streaming */}
          {(() => {
            const hasActiveTurn = isThinking || isSearching || Boolean(streamingText);
            if (!hasActiveTurn) return null;
            const lastMsg = messages[messages.length - 1];
            if (
              lastMsg &&
              lastMsg.role === "assistant" &&
              streamingText &&
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
                    text: streamingText || "",
                    createdAt: new Date().toISOString(),
                  } as TranscriptMessage
                }
                isStreaming={Boolean(streamingText)}
                isThinkingLive={isThinking && !streamingText}
                isSearchingLive={isSearching}
                searchQueryLive={searchQuery}
                isDark={isDark}
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
          padding: isMobile ? "8px 10px calc(8px + env(safe-area-inset-bottom, 0px))" : "var(--space-2) clamp(20px, 4vw, 56px) var(--space-3)",
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

            {providerHealth === "unavailable" && brainRecovery && (
              <button
                type="button"
                data-testid="micro-status-recovery"
                onClick={() =>
                  onSelectProvider?.(brainRecovery.mode, brainRecovery.model ?? undefined)
                }
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
                Switch to {recoveryLabel}
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

        {/* P0 Suggestion Layer: Non-blocking subtle hint while typing */}
        {suggestion && !activeDraft && (
          <div style={{ display: "flex", justifyContent: "center", width: "100%" }}>
            <ComposerSuggestionStrip
              suggestion={suggestion}
              compact={isMobile}
              onAdopt={adoptSuggestion}
              onDismiss={dismissSuggestion}
            />
          </div>
        )}

        {/* The Walk: Live Morphing Action Surface (Only when adopted via Tab or Click) */}
        {activeDraft && (
          <div style={{ marginBottom: 10, display: "flex", justifyContent: "center", width: "100%" }}>
            <HinaSurface
              draft={activeDraft}
              compact={isMobile}
              onCommit={(draft) => handleCommitAction(draft)}
              onDismiss={dismissDraft}
            />
          </div>
        )}

        {/* Live Eyes Floating Indicator Bar */}
        {liveVision.isActive && (
          <div
            data-testid="live-eyes-indicator"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "6px 14px",
              margin: "0 16px 8px",
              background: "rgba(16, 185, 129, 0.12)",
              border: "1px solid rgba(16, 185, 129, 0.35)",
              borderRadius: 12,
              fontSize: 12,
              color: "#10b981",
              boxShadow: "0 4px 12px rgba(16, 185, 129, 0.1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#10b981",
                  boxShadow: "0 0 8px #10b981",
                }}
              />
              <span style={{ fontWeight: 650, letterSpacing: "0.02em" }}>
                LIVE EYES: {liveVision.mode === "screen" ? "Watching Screen" : "Camera Active"}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  void liveVision.observeScreen("Look at my screen and give me sharp observations and feedback.");
                }}
                disabled={liveVision.isObserving}
                style={{
                  padding: "3px 10px",
                  borderRadius: 6,
                  background: "#10b981",
                  color: "#ffffff",
                  border: "none",
                  fontSize: 11,
                  fontWeight: 650,
                  cursor: "pointer",
                }}
              >
                {liveVision.isObserving ? "Analyzing..." : "Ask Hina About Screen"}
              </button>
              <button
                type="button"
                onClick={liveVision.stopCapture}
                title="Stop Live Eyes"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "inherit",
                  cursor: "pointer",
                  fontSize: 15,
                  fontWeight: 700,
                  lineHeight: 1,
                  padding: "2px 4px",
                }}
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Frontier V6 Composer */}
        <ComposerV6
          isDark={isDark}
          compact={isMobile}
          value={input}
          onTabAdopt={() => {
            if (suggestion) {
              adoptSuggestion();
              return true;
            }
            return false;
          }}
          onEscDismiss={() => {
            if (suggestion) dismissSuggestion();
            if (activeDraft) dismissDraft();
          }}
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
          isLiveVisionActive={liveVision.isActive}
          onToggleLiveVision={liveVision.isActive ? liveVision.stopCapture : liveVision.startScreenShare}
          contextChips={contextChips}
          onRemoveChip={handleRemoveChip}
          activeTopic={activeTopic}
          onClearTopic={() => setLocalTopic("")}
          onOpenModelSelector={onOpenSettings}
          discoveredModels={discoveredModels}
          selectedModelId={activeProviderMode === "auto" ? null : (activeProviderModel ?? null)}
          selectedProviderId={activeProviderMode ?? null}
          isAutoRouter={activeProviderMode === "auto" || !activeProviderModel}
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
          onImageAttach={onImageAttach}
          onSelectArtifact={(command) => onInputChange(`${command} `)}
        />
      </div>
        </>
      )}
    </div>
  );
}

/* ── Message Component ───────────────────────────────────── */
export const WorkMessage = React.memo(function WorkMessage({
  message,
  isStreaming,
  isThinkingLive,
  isSearchingLive,
  searchQueryLive,
  isDark = false,
}: {
  message: TranscriptMessage;
  isStreaming?: boolean;
  isThinkingLive?: boolean;
  isSearchingLive?: boolean;
  searchQueryLive?: string;
  isDark?: boolean;
}) {
  const isUser = message.role === "user";
  const attachmentRole = ATTACHMENT_ROLES.find(
    (item) => item.role === message.attachments?.[0]?.role,
  );
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportingPptx, setExportingPptx] = useState(false);

  const plan = message.plan;
  const answeredBy = plan?.resolvedModel || plan?.resolvedProvider || null;
  const requestedBrain = plan?.requestedModel || plan?.requestedProvider || null;
  const answeredByLabel = answeredBy
    ? `${answeredBy}${plan?.latencyMs ? ` · ${Math.round(plan.latencyMs / 100) / 10}s` : ""}`
    : null;

  // Automatically extract internal reasoning / thinking process, clean response text, and sources
  const { thought, cleanText, sources: extractedSources } = useMemo(() => {
    if (isUser) return { thought: "", cleanText: message.text, sources: [] };
    return extractBrainThought(message.text, plan?.thinking);
  }, [isUser, message.text, plan?.thinking]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(isUser ? message.text : (cleanText || message.text));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const handleExportPdf = async () => {
    try {
      setExportingPdf(true);
      const textToExport = cleanText || message.text;
      const titleMatch = textToExport.match(/^#{1,3}\s+(.+)$/m);
      const title = titleMatch ? titleMatch[1].trim() : "HINAA Report";
      await downloadMarkdownPdf(title, textToExport);
    } catch (err) {
      console.error("Failed to export PDF:", err);
    } finally {
      setExportingPdf(false);
    }
  };

  const handleExportPptx = async () => {
    try {
      setExportingPptx(true);
      const textToExport = cleanText || message.text;
      const titleMatch = textToExport.match(/^#{1,3}\s+(.+)$/m);
      const title = titleMatch ? titleMatch[1].trim() : "HINAA Keynote";
      await downloadMarkdownPptx(title, textToExport);
    } catch (err) {
      console.error("Failed to export PowerPoint presentation:", err);
    } finally {
      setExportingPptx(false);
    }
  };

  // Extract grounded sources from web_search tool results or parsed from markdown citations
  const brainSources = useMemo(() => {
    if (isUser) return [];
    const webSearchTool = message.toolResults?.find((tr) => tr.toolName === "web_search");
    const rawSources = webSearchTool?.result?.sources || webSearchTool?.result?.data?.sources;
    if (Array.isArray(rawSources) && rawSources.length > 0) {
      return rawSources.map((s: any, idx: number) => ({
        id: s.id || `S${idx + 1}`,
        title: s.title || "Web Source",
        url: s.url,
        domain: s.domain,
        snippet: s.snippet,
      }));
    }
    return extractedSources || [];
  }, [isUser, message.toolResults, extractedSources]);

  // Render external tool results using GenericResultRenderer (excluding web_search, which is inside Hina's brain)
  const renderToolResults = () => {
    if (!message.toolResults || message.toolResults.length === 0) return null;
    const externalTools = message.toolResults.filter((tr) => {
      if (tr.toolName === "web_search") return false;
      // Image jobs are rendered cleanly by ImageJobCard below
      if (
        tr.toolName === "image_generate" ||
        tr.toolName === "magnific_image_generate" ||
        tr.toolName === "freepik_image_generate" ||
        tr.toolName === "comfy_ui"
      ) {
        return false;
      }
      return true;
    });
    if (externalTools.length === 0) return null;
    return (
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
        {externalTools.map((tr, idx) => (
          <GenericResultRenderer key={`${tr.toolName}-${idx}`} toolName={tr.toolName} result={tr.result} />
        ))}
      </div>
    );
  };

  // Render interactive action objects (Reminder, Image Job, Split) directly in the thread
  const renderActionObject = () => {
    let draft = message.actionDraft;
    if (!draft) {
      const imageResult = message.toolResults?.find(
        (tr) =>
          tr.toolName === "image_generate" ||
          tr.toolName === "magnific_image_generate" ||
          tr.toolName === "freepik_image_generate"
      );
      if (imageResult) {
        const res = imageResult.result;
        const resUrl = res?.images?.[0] || res?.resultUrl || res?.thumbnailUrl || "";
        draft = {
          intent: "image.job",
          status: "success",
          fields: {
            data: {
              prompt: res?.prompt || "",
              stage: "saved",
              isSearchFallback: false,
              thumbnailUrl: resUrl,
              resultUrl: resUrl,
              images: res?.images || (resUrl ? [resUrl] : []),
              model: res?.mode || "FLUX.1 [dev]",
            },
          },
        } as any;
      }
    }
    if (!draft) return null;
    return (
      <div style={{ marginTop: 8, paddingLeft: isUser ? 0 : 34, width: "100%", maxWidth: 540 }}>
        {draft.intent === "reminder.create" && (
          <ReminderCard
            data={draft.fields?.data as any}
            compact={false}
          />
        )}
        {draft.intent === "image.job" && (() => {
          const rawData = (draft.fields?.data || draft.fields || {}) as any;
          const imageToolResult = message.toolResults?.find(
            (tr) =>
              tr.toolName === "image_generate" ||
              tr.toolName === "magnific_image_generate" ||
              tr.toolName === "freepik_image_generate"
          )?.result;
          const mergedData =
            imageToolResult && (imageToolResult.images?.length || imageToolResult.status === "completed")
              ? {
                  ...rawData,
                  stage: imageToolResult.status === "completed" ? "saved" : rawData.stage,
                  images: imageToolResult.images || rawData.images,
                  resultUrl: imageToolResult.images?.[0] || rawData.resultUrl,
                  thumbnailUrl: imageToolResult.images?.[0] || rawData.thumbnailUrl,
                  slots: imageToolResult.slots || rawData.slots,
                  model: imageToolResult.mode
                    ? imageToolResult.mode.includes("flux")
                      ? "FLUX.1 [dev]"
                      : imageToolResult.mode
                    : rawData.model,
                }
              : rawData;
          return <ImageJobCard data={mergedData} compact={false} />;
        })()}
        {draft.intent === "split" && (
          <SplitCard
            data={draft.fields?.data as any}
            compact={false}
          />
        )}
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
                background: isDark ? "#f5f5f5" : "#1a232b",
                color: isDark ? "#1b1b1b" : "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Sparkles size={13} />
            </div>
            <span style={{ fontWeight: 700, fontSize: 13, letterSpacing: "0.04em", color: isDark ? "#ffffff" : "#1e293b" }}>
              HINA
            </span>
            {message.createdAt && (
              <span style={{ fontSize: 11, color: isDark ? "#426188" : "#94a3b8" }}>
                {new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
            {answeredByLabel && (
              <span
                style={{ fontSize: 10, color: plan?.fallback ? "#b45309" : (isDark ? "#426188" : "#94a3b8"), fontWeight: plan?.fallback ? 600 : 400 }}
                title={plan?.fallback ? plan.fallbackReason ?? undefined : undefined}
              >
                {answeredByLabel}
              </span>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {(cleanText || message.text).length > 80 && (
              <button
                type="button"
                onClick={handleExportPdf}
                disabled={exportingPdf}
                title="Download formatted PDF report (< 1s)"
                data-testid="message-export-pdf-btn"
                style={{
                  background: "none",
                  border: "none",
                  color: exportingPdf ? "var(--accent, #6366f1)" : (isDark ? "rgba(255, 255, 255, 0.6)" : "#94a3b8"),
                  cursor: exportingPdf ? "wait" : "pointer",
                  padding: 4,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 3,
                  fontSize: 11,
                  fontWeight: 650,
                  transition: "color 0.15s ease",
                }}
              >
                {exportingPdf ? <Loader2 size={12} className="animate-spin" /> : <FileDown size={12} />}
                <span>PDF</span>
              </button>
            )}
            {(cleanText || message.text).length > 80 && (
              <button
                type="button"
                onClick={handleExportPptx}
                disabled={exportingPptx}
                title="Download 16:9 PowerPoint presentation deck (< 1s)"
                data-testid="message-export-pptx-btn"
                style={{
                  background: "none",
                  border: "none",
                  color: exportingPptx ? "var(--accent, #6366f1)" : (isDark ? "rgba(255, 255, 255, 0.6)" : "#94a3b8"),
                  cursor: exportingPptx ? "wait" : "pointer",
                  padding: 4,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 3,
                  fontSize: 11,
                  fontWeight: 650,
                  transition: "color 0.15s ease",
                }}
              >
                {exportingPptx ? <Loader2 size={12} className="animate-spin" /> : <Presentation size={12} />}
                <span>Slides</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleCopy}
              title="Copy message"
              style={{ background: "none", border: "none", color: isDark ? "rgba(255, 255, 255, 0.6)" : "#94a3b8", cursor: "pointer", padding: 4 }}
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
            lineHeight: 1.4,
            color: "#b45309",
            background: "rgba(254, 243, 199, 0.45)",
            border: "1px solid rgba(251, 191, 36, 0.35)",
            borderRadius: 6,
            padding: "4px 8px",
            marginBottom: 6,
            marginLeft: 34,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span style={{ fontSize: 12 }}>⚡</span>
          <span>
            {`Switched to ${answeredBy ?? "high-performance model"} (auto-routed for uptime)`}
          </span>
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
          background: isUser ? (isDark ? "#2b7fff" : "#1a232b") : "transparent",
          border: "none",
          boxShadow: isUser ? (isDark ? "0 2px 12px rgba(43, 127, 255, 0.3)" : "0 1px 3px rgba(0,0,0,0.1)") : "none",
          color: isUser ? "#ffffff" : (isDark ? "#ffffff" : "#334155"),
          fontSize: 14,
          lineHeight: 1.65,
          whiteSpace: isUser ? "pre-wrap" : "normal",
          wordBreak: "break-word",
        }}
      >
        {isUser && message.imageUrl && (
          <>
            <img
              src={message.imageUrl}
              alt="Your attached image"
              style={{
                display: "block",
                maxWidth: 220,
                width: "100%",
                borderRadius: 10,
                marginBottom: attachmentRole || message.text ? 8 : 0,
              }}
            />
            {attachmentRole && (
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: "0.02em",
                  opacity: 0.7,
                  marginBottom: message.text ? 8 : 0,
                }}
              >
                {attachmentRole.label}
              </div>
            )}
          </>
        )}

        {/* Integrated Hina Brain & Grounded Sources */}
        {!isUser && (
          <HinaBrainThinking
            thought={thought}
            sources={brainSources}
            isLive={isThinkingLive || isSearchingLive || (isStreaming && !cleanText)}
            isSearching={isSearchingLive}
            searchQuery={searchQueryLive}
            latencyMs={plan?.latencyMs}
          />
        )}

        {isUser ? (
          message.text
        ) : cleanText ? (
          <ResponseEnvelopeRenderer rawText={cleanText} streaming={isStreaming} />
        ) : isThinkingLive || isSearchingLive ? null : isStreaming && !thought ? (
          <span style={{ color: "rgba(255, 255, 255, 0.5)", fontStyle: "italic", fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span>Formulating response...</span>
            <span className="hina-live-stream-cursor" />
          </span>
        ) : thought ? (
          <div style={{ color: isDark ? "rgba(255, 255, 255, 0.75)" : "#64748b", fontSize: 13.5, fontStyle: "italic", paddingTop: 4 }}>
            <span>I've finished synthesizing the thoughts above for you! ✨</span>
          </div>
        ) : null}
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

      {/* Action Object in thread */}
      {!isUser && renderActionObject()}

      {/* Tool Results with Source Cards */}
      {!isUser && renderToolResults()}
    </div>
  );
});


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
  isDark = false,
}: {
  onAction: (action: string) => void;
  isDark?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(false);
  const [briefing, setBriefing] = useState<{
    greeting?: string;
    suggestions?: Array<{ id: string; title: string; subtitle: string; prompt: string }>;
  } | null>(null);

  const hour = new Date().getHours();
  const daypart = hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
  const defaultGreetingText = isDark
    ? "Midnight sky through glass sculpture. Ask anything, orchestrate deep reasoning, or compose live intelligence."
    : `Good ${daypart} — I'm Hina, your AI workspace companion. Ask me anything, research the live web with citations, create documents and images, or switch brains anytime from the model menu.`;

  useEffect(() => {
    let mounted = true;
    fetch("/api/v1/companion/briefing")
      .then((r) => r.json())
      .then((d) => {
        if (mounted && d.status === "success") {
          setBriefing(d);
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  const activeGreeting = briefing?.greeting || defaultGreetingText;

  const defaultSuggestions = [
    { label: "Explain a concept", prompt: "Explain Retrieval-Augmented Generation in simple terms with an example: " },
    { label: "Research live", prompt: "Research the latest developments in " },
    { label: "Create a document", prompt: "Create a comprehensive document about " },
    { label: "Generate an image", prompt: "/image " },
  ];

  const activeSuggestions = briefing?.suggestions?.length
    ? briefing.suggestions.map((s) => ({ label: s.title, prompt: s.prompt }))
    : defaultSuggestions;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(activeGreeting);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  if (isDark) {
    return (
      <div style={{ maxWidth: 820, width: "100%", margin: "20px 0 28px 0" }}>
        {/* Air Hero Section: Anton 900 + Caveat cursive */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
            <h1
              style={{
                fontFamily: "var(--font-control-compressed, 'Anton', sans-serif)",
                fontSize: "clamp(2.6rem, 6.5vw, 4rem)",
                fontWeight: 900,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                lineHeight: 0.95,
                color: "#ffffff",
                margin: 0,
              }}
            >
              MAKE IT
            </h1>
            <span
              style={{
                fontFamily: "var(--font-control-cursive, 'Caveat', cursive)",
                fontSize: "clamp(3rem, 7.5vw, 4.6rem)",
                fontStyle: "italic",
                fontWeight: 600,
                color: "#ffffff",
                lineHeight: 0.9,
              }}
            >
              real.
            </span>
          </div>
          <p
            style={{
              fontFamily: "var(--font-control, 'Inter', sans-serif)",
              fontSize: 14.5,
              lineHeight: 1.6,
              color: "rgba(255, 255, 255, 0.7)",
              maxWidth: 620,
              margin: 0,
            }}
          >
            {activeGreeting}
          </p>
        </div>

        {/* Air Pure Haze Cards Grid (#f5f5f5) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12,
            marginTop: 18,
          }}
        >
          {activeSuggestions.map((s, idx) => (
            <button
              key={s.label}
              type="button"
              onClick={() => onAction(s.prompt)}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                justifyContent: "space-between",
                padding: "16px 18px",
                minHeight: 104,
                borderRadius: 14,
                background: "#f5f5f5",
                border: "1px solid rgba(255, 255, 255, 0.6)",
                color: "#1b1b1b",
                textAlign: "left",
                cursor: "pointer",
                boxShadow: "0 4px 20px -2px rgba(0, 0, 0, 0.35)",
                transition: "transform 0.15s ease, box-shadow 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 8px 24px -2px rgba(0, 0, 0, 0.45)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "none";
                e.currentTarget.style.boxShadow = "0 4px 20px -2px rgba(0, 0, 0, 0.35)";
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", marginBottom: 8 }}>
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "#426188",
                  }}
                >
                  0{idx + 1} // PROMPT
                </span>
                <span style={{ fontSize: 13, color: "#2b7fff", fontWeight: 700 }}>→</span>
              </div>
              <div
                style={{
                  fontFamily: "var(--font-control, 'Inter', sans-serif)",
                  fontSize: 14,
                  fontWeight: 650,
                  color: "#1b1b1b",
                  lineHeight: 1.3,
                }}
              >
                {s.label}
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

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
          <span style={{ fontSize: 11, color: "#94a3b8" }}>
            {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
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
        {activeGreeting}
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
      </div>

      {/* Starter suggestion chips — real prompts, one click to start */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, paddingLeft: 34, marginTop: 14 }}>
        {activeSuggestions.map((s) => (
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

