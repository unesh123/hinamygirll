/**
 * HINAA Unified Tool Registry
 *
 * Every capability exposed to the AI is defined here with:
 * - Unique ID, display name, description
 * - Permission level, confirmation requirements
 * - Input/output schemas
 * - Rich result types
 * - Voice aliases
 * - Availability state
 */

/* ─── Permission Levels ─────────────────────────────────── */
export type PermissionLevel = "low" | "confirm" | "strong_confirm" | "blocked";

/* ─── Tool Availability ─────────────────────────────────── */
export type ToolAvailability =
  | "connected"
  | "needs_authorization"
  | "unavailable"
  | "mock_only";

/* ─── Capability Group ──────────────────────────────────── */
export type CapabilityGroup =
  | "web_search"
  | "browser"
  | "image_search"
  | "image_generation"
  | "media"
  | "email"
  | "calendar"
  | "files"
  | "code"
  | "memory"
  | "system";

/* ─── Tool Definition ───────────────────────────────────── */
export interface ToolDefinition {
  /** Unique tool identifier */
  id: string;
  /** Human-readable display name */
  displayName: string;
  /** Short description */
  description: string;
  /** Capability group */
  group: CapabilityGroup;
  /** Permission level required */
  permission: PermissionLevel;
  /** Requires user confirmation before execution */
  requiresConfirmation: boolean;
  /** Supports cancellation */
  cancellable: boolean;
  /** Has rollback support */
  rollbackAvailable: boolean;
  /** Rich result display type */
  resultType: "search" | "image" | "code" | "email" | "calendar" | "media" | "file" | "browser" | "text";
  /** Voice command aliases */
  voiceAliases: string[];
  /** Suggested follow-up action IDs */
  suggestedActions: string[];
  /** Current availability */
  availability: ToolAvailability;
  /** Input parameter schema (simplified) */
  inputSchema: Record<string, { type: string; description: string; required: boolean }>;
}

/* ─── Tool Registry ─────────────────────────────────────── */
export const toolRegistry: Record<string, ToolDefinition> = {
  /* ── Web Search ──────────────────────────────────────── */
  web_search: {
    id: "web_search",
    displayName: "Web Search",
    description: "Search the web for real-time information with source citations",
    group: "web_search",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "search",
    voiceAliases: ["search", "search the web", "look up", "find online", "google"],
    suggestedActions: ["show_sources", "compare_results", "show_images", "deep_research"],
    availability: "mock_only",
    inputSchema: {
      query: { type: "string", description: "Search query", required: true },
      maxResults: { type: "number", description: "Maximum results", required: false },
    },
  },

  /* ── Browser Navigation ──────────────────────────────── */
  browser_navigate: {
    id: "browser_navigate",
    displayName: "Open URL",
    description: "Open a verified URL in a new browser tab",
    group: "browser",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "browser",
    voiceAliases: ["open", "go to", "navigate to", "browse"],
    suggestedActions: ["read_page", "take_screenshot"],
    availability: "connected",
    inputSchema: {
      url: { type: "string", description: "URL to navigate to", required: true },
    },
  },

  browser_read: {
    id: "browser_read",
    displayName: "Read Page",
    description: "Read and extract visible text from the current page",
    group: "browser",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["read page", "what's on the page", "summarize page"],
    suggestedActions: ["extract_links", "search_on_page"],
    availability: "needs_authorization",
    inputSchema: {
      selector: { type: "string", description: "CSS selector (optional)", required: false },
    },
  },

  browser_click: {
    id: "browser_click",
    displayName: "Click Element",
    description: "Click an approved element on a web page",
    group: "browser",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "browser",
    voiceAliases: ["click", "press the button"],
    suggestedActions: [],
    availability: "needs_authorization",
    inputSchema: {
      selector: { type: "string", description: "Element selector", required: true },
    },
  },

  browser_fill: {
    id: "browser_fill",
    displayName: "Fill Form",
    description: "Enter approved text into a form field",
    group: "browser",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "browser",
    voiceAliases: ["fill", "type into", "enter text"],
    suggestedActions: [],
    availability: "needs_authorization",
    inputSchema: {
      selector: { type: "string", description: "Input selector", required: true },
      text: { type: "string", description: "Text to enter", required: true },
    },
  },

  /* ── Image Search ────────────────────────────────────── */
  image_search: {
    id: "image_search",
    displayName: "Image Search",
    description: "Search for images on the web with source attribution",
    group: "image_search",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "image",
    voiceAliases: ["find images", "show me pictures", "search for photos"],
    suggestedActions: ["use_as_reference", "open_source"],
    availability: "mock_only",
    inputSchema: {
      query: { type: "string", description: "Image search query", required: true },
    },
  },

  /* ── Image Generation ────────────────────────────────── */
  image_generate: {
    id: "image_generate",
    displayName: "Generate Image",
    description: "Generate an AI image from a text description",
    group: "image_generation",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "image",
    voiceAliases: ["generate image", "create picture", "make an image", "draw"],
    suggestedActions: ["regenerate", "create_variation", "save_image"],
    availability: "needs_authorization",
    inputSchema: {
      prompt: { type: "string", description: "Image description", required: true },
      style: { type: "string", description: "Style preference", required: false },
    },
  },

  /* ── Media / YouTube ─────────────────────────────────── */
  media_search: {
    id: "media_search",
    displayName: "Find & Open Media",
    description: "Search for a song or video on YouTube and open the result",
    group: "media",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "media",
    voiceAliases: ["play", "find song", "search youtube", "music", "video"],
    suggestedActions: ["try_another", "show_similar"],
    availability: "connected",
    inputSchema: {
      query: { type: "string", description: "Song or video to find", required: true },
    },
  },

  /* ── Email ───────────────────────────────────────────── */
  email_find: {
    id: "email_find",
    displayName: "Find Emails",
    description: "Find recent or important emails",
    group: "email",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "email",
    voiceAliases: ["check mail", "show emails", "find email"],
    suggestedActions: ["open_email", "summarize_email", "draft_reply"],
    availability: "needs_authorization",
    inputSchema: {
      query: { type: "string", description: "Search query", required: false },
      limit: { type: "number", description: "Max results", required: false },
    },
  },

  email_send: {
    id: "email_send",
    displayName: "Send Email",
    description: "Send an email after confirmation",
    group: "email",
    permission: "strong_confirm",
    requiresConfirmation: true,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "email",
    voiceAliases: ["send email", "email to"],
    suggestedActions: [],
    availability: "needs_authorization",
    inputSchema: {
      to: { type: "string", description: "Recipient email", required: true },
      subject: { type: "string", description: "Email subject", required: true },
      body: { type: "string", description: "Email body", required: true },
    },
  },

  /* ── Calendar ────────────────────────────────────────── */
  calendar_show: {
    id: "calendar_show",
    displayName: "Show Schedule",
    description: "Show upcoming calendar events",
    group: "calendar",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "calendar",
    voiceAliases: ["schedule", "calendar", "meetings", "what's next"],
    suggestedActions: ["prepare_meeting", "create_meeting"],
    availability: "needs_authorization",
    inputSchema: {
      period: { type: "string", description: "today, week, month", required: false },
    },
  },

  /* ── Files ───────────────────────────────────────────── */
  file_search: {
    id: "file_search",
    displayName: "Search Files",
    description: "Search local and project files",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "file",
    voiceAliases: ["find file", "search files", "open document"],
    suggestedActions: ["open_file", "summarize_file"],
    availability: "connected",
    inputSchema: {
      query: { type: "string", description: "File search query", required: true },
    },
  },

  file_create: {
    id: "file_create",
    displayName: "Create File",
    description: "Create a new file with specified content",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: true,
    resultType: "file",
    voiceAliases: ["create file", "save as", "write to file"],
    suggestedActions: ["open_file", "attach_to_chat"],
    availability: "connected",
    inputSchema: {
      path: { type: "string", description: "File path", required: true },
      content: { type: "string", description: "File content", required: true },
    },
  },

  /* ── Memory ──────────────────────────────────────────── */
  memory_remember: {
    id: "memory_remember",
    displayName: "Remember",
    description: "Save a fact or preference to memory",
    group: "memory",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: true,
    resultType: "text",
    voiceAliases: ["remember this", "save that", "keep this in mind"],
    suggestedActions: ["show_memory", "forget"],
    availability: "connected",
    inputSchema: {
      content: { type: "string", description: "What to remember", required: true },
      category: { type: "string", description: "fact, preference, workflow", required: false },
    },
  },

  /* ── System ──────────────────────────────────────────── */
  system_open_app: {
    id: "system_open_app",
    displayName: "Open Application",
    description: "Open a local application",
    group: "system",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["open app", "launch", "start application"],
    suggestedActions: [],
    availability: "needs_authorization",
    inputSchema: {
      appName: { type: "string", description: "Application name", required: true },
    },
  },
};

/* ─── Tool Event System ─────────────────────────────────── */
export type ToolEventType =
  | "tool.requested"
  | "tool.started"
  | "tool.progress"
  | "tool.result"
  | "tool.confirmation_required"
  | "tool.confirmed"
  | "tool.cancelled"
  | "tool.failed"
  | "tool.completed";

export interface ToolEvent {
  eventId: string;
  toolCallId: string;
  conversationId: string;
  timestamp: number;
  toolId: string;
  type: ToolEventType;
  displayMessage: string;
  payload?: unknown;
  state: "pending" | "active" | "completed" | "failed" | "cancelled" | "waiting_approval";
}

export type ToolEventListener = (event: ToolEvent) => void;

/* ─── Tool Event Bus ───────────────────────────────────── */
class ToolEventBus {
  private listeners = new Map<string, Set<ToolEventListener>>();
  private eventLog: ToolEvent[] = [];

  subscribe(toolCallId: string, listener: ToolEventListener): () => void {
    if (!this.listeners.has(toolCallId)) {
      this.listeners.set(toolCallId, new Set());
    }
    this.listeners.get(toolCallId)!.add(listener);
    return () => {
      this.listeners.get(toolCallId)?.delete(listener);
    };
  }

  emit(event: ToolEvent): void {
    this.eventLog.push(event);
    this.listeners.get(event.toolCallId)?.forEach((fn) => {
      try {
        fn(event);
      } catch (e) {
        console.error("Tool event listener error", e);
      }
    });
  }

  getEvents(toolCallId: string): ToolEvent[] {
    return this.eventLog.filter((e) => e.toolCallId === toolCallId);
  }

  clear(): void {
    this.eventLog = [];
  }
}

export const toolEventBus = new ToolEventBus();

/* ─── Helpers ──────────────────────────────────────────── */
export function getTool(id: string): ToolDefinition | undefined {
  return toolRegistry[id];
}

export function getToolsByGroup(group: CapabilityGroup): ToolDefinition[] {
  return Object.values(toolRegistry).filter((t) => t.group === group);
}

export function getConnectedTools(): ToolDefinition[] {
  return Object.values(toolRegistry).filter((t) => t.availability === "connected");
}

export function getToolsNeedingAuth(): ToolDefinition[] {
  return Object.values(toolRegistry).filter((t) => t.availability === "needs_authorization");
}

export function createEventId(): string {
  return `evt-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function createToolEvent(
  toolCallId: string,
  conversationId: string,
  toolId: string,
  type: ToolEventType,
  displayMessage: string,
  payload?: unknown,
): ToolEvent {
  const stateMap: Record<ToolEventType, ToolEvent["state"]> = {
    "tool.requested": "pending",
    "tool.started": "active",
    "tool.progress": "active",
    "tool.result": "completed",
    "tool.confirmation_required": "waiting_approval",
    "tool.confirmed": "active",
    "tool.cancelled": "cancelled",
    "tool.failed": "failed",
    "tool.completed": "completed",
  };

  return {
    eventId: createEventId(),
    toolCallId,
    conversationId,
    timestamp: Date.now(),
    toolId,
    type,
    displayMessage,
    payload,
    state: stateMap[type],
  };
}
