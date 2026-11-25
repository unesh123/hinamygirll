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

  youtube_playback_request: {
    id: "youtube_playback_request",
    displayName: "Play YouTube Music",
    description: "Search and play music or videos directly in YouTube with verified playback",
    group: "media",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "media",
    voiceAliases: ["play music", "play song", "put on music", "play on youtube"],
    suggestedActions: ["pause", "next_song", "loop"],
    availability: "connected",
    inputSchema: {
      query: { type: "string", description: "Song, artist, or video title", required: true },
    },
  },

  browser_execute_task: {
    id: "browser_execute_task",
    displayName: "Browser Agent",
    description: "Autonomously navigate, interact, and extract information from the web to complete high-level tasks",
    group: "browser",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "browser",
    voiceAliases: ["browse web", "automate browser", "do research on web"],
    suggestedActions: ["view_steps", "cancel_task"],
    availability: "connected",
    inputSchema: {
      goal: { type: "string", description: "Goal for the browser agent", required: true },
    },
  },

  computer_operator: {
    id: "computer_operator",
    displayName: "Computer Operator",
    description: "Operate native OS applications, media controls, and keyboard shortcuts",
    group: "system",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["control computer", "media keys", "open application"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      action: { type: "string", description: "OS action to perform", required: true },
      target: { type: "string", description: "Target app, URL, or key", required: false },
    },
  },

  ui_control: {
    id: "ui_control",
    displayName: "UI & Workspace Control",
    description: "Switch layouts, modes, and window arrangements in HINAA OS",
    group: "system",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["switch mode", "open studio", "change layout"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      action: { type: "string", description: "set_mode, set_layout, or minimize", required: true },
    },
  },

  ultra_file_write: {
    id: "ultra_file_write",
    displayName: "Workspace: Write File",
    description: "Write a file in ~/hinaa-ultra/exports",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "file",
    voiceAliases: ["write file", "create file", "save file"],
    suggestedActions: ["open_file"],
    availability: "connected",
    inputSchema: {
      filename: { type: "string", description: "Target filename", required: true },
      content: { type: "string", description: "File content", required: true },
    },
  },

  file_list: {
    id: "file_list",
    displayName: "Workspace: List Files",
    description: "Inspect files and folders in ~/hinaa-ultra",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "file",
    voiceAliases: ["list workspace", "show files"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      path: { type: "string", description: "Subfolder path", required: false },
    },
  },

  video_create: {
    id: "video_create",
    displayName: "Studio: Create MP4 Video",
    description: "Render deterministic HTML animation frames and export MP4 via FFmpeg",
    group: "media",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "media",
    voiceAliases: ["create video", "bridal reel", "make mp4"],
    suggestedActions: ["download_video"],
    availability: "connected",
    inputSchema: {
      prompt: { type: "string", description: "Animation description", required: true },
      duration_seconds: { type: "number", description: "Clip duration seconds", required: false },
    },
  },

  record_frames: {
    id: "record_frames",
    displayName: "Studio: Record Frames",
    description: "Capture headless Chromium frames for an HTML animation",
    group: "media",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "media",
    voiceAliases: ["record frames"],
    suggestedActions: ["export_mp4"],
    availability: "connected",
    inputSchema: {
      html_file: { type: "string", description: "HTML animation file", required: true },
    },
  },

  ffmpeg_export: {
    id: "ffmpeg_export",
    displayName: "Studio: FFmpeg MP4 Export",
    description: "Stitch rendered PNG frames into H.264 MP4",
    group: "media",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "media",
    voiceAliases: ["export mp4", "stitch video"],
    suggestedActions: ["download_video"],
    availability: "connected",
    inputSchema: {
      frames_dir: { type: "string", description: "Frames directory", required: true },
    },
  },

  server_start: {
    id: "server_start",
    displayName: "Host Local Static Server",
    description: "Serve workspace exports or static site over localhost",
    group: "system",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "browser",
    voiceAliases: ["start server", "serve exports"],
    suggestedActions: ["open_url"],
    availability: "connected",
    inputSchema: {
      port: { type: "number", description: "Port number", required: true },
      dir_path: { type: "string", description: "Directory path", required: true },
    },
  },

  shell_run: {
    id: "shell_run",
    displayName: "Run Ultra Shell Command",
    description: "Execute approved command inside ~/hinaa-ultra workspace",
    group: "code",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["run command", "shell execute"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      command: { type: "string", description: "Command string", required: true },
    },
  },

  agent_spawn: {
    id: "agent_spawn",
    displayName: "Delegate to Agent Swarm",
    description: "Dispatch task to Kira (coder), Nova (designer), or Sage (researcher)",
    group: "system",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["ask kira", "ask nova", "ask sage"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      name: { type: "string", description: "Agent name", required: true },
      task: { type: "string", description: "Task description", required: true },
    },
  },

  browser_screenshot: {
    id: "browser_screenshot",
    displayName: "Browser Screenshot",
    description: "Capture screenshot of URL into ~/hinaa-ultra/exports",
    group: "browser",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "image",
    voiceAliases: ["take screenshot"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      url: { type: "string", description: "Target URL", required: true },
    },
  },

  render_code_animation: {
    id: "render_code_animation",
    displayName: "Code-to-MP4 Studio",
    description: "Render HTML/CSS/Canvas or timeline animations to H.264 MP4 via Playwright + FFmpeg",
    group: "media",
    permission: "low",
    requiresConfirmation: false,
    cancellable: true,
    rollbackAvailable: false,
    resultType: "media",
    voiceAliases: ["render mp4", "render code animation", "kinetic video"],
    suggestedActions: ["download", "play"],
    availability: "connected",
    inputSchema: {
      title: { type: "string", description: "Animation title", required: true },
      duration_seconds: { type: "number", description: "Duration in seconds", required: false },
      preview: { type: "boolean", description: "Render fast 480p preview", required: false },
    },
  },

  workspace_read_file: {
    id: "workspace_read_file",
    displayName: "Workspace: Read File",
    description: "Read numbered lines and SHA-256 base hash from a file inside the workspace root",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["read workspace file"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      file_path: { type: "string", description: "Relative file path", required: true },
    },
  },

  workspace_list_dir: {
    id: "workspace_list_dir",
    displayName: "Workspace: List Directory",
    description: "Inspect files and folders inside the bounded project workspace",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "file",
    voiceAliases: ["list workspace directory", "inspect project tree"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      subpath: { type: "string", description: "Relative directory path", required: false },
    },
  },

  workspace_write_file: {
    id: "workspace_write_file",
    displayName: "Workspace: Write File",
    description: "Create or update HTML, Python, TypeScript, JSON, or test files inside workspace root",
    group: "code",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: true,
    resultType: "code",
    voiceAliases: ["write workspace file", "create html page"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      file_path: { type: "string", description: "Relative file path", required: true },
      content: { type: "string", description: "Complete UTF-8 file contents", required: true },
    },
  },

  workspace_run_command: {
    id: "workspace_run_command",
    displayName: "Workspace: Run Command / Tests",
    description: "Execute bounded pytest, Python, Node, Vitest, TypeScript, git inspect, or FFmpeg checks inside workspace",
    group: "code",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["run tests", "execute workspace command"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      command: { type: "string", description: "Command string without shell operators", required: true },
    },
  },

  workspace_verify_html: {
    id: "workspace_verify_html",
    displayName: "Workspace: Verify HTML Render",
    description: "Verify a workspace HTML page in network-isolated Chromium for DOM nodes, JS errors, and rendered pixels",
    group: "code",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["verify html page", "check webpage render"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      file_path: { type: "string", description: "Relative HTML file path", required: true },
    },
  },

  workspace_edit_file: {
    id: "workspace_edit_file",
    displayName: "Workspace: Edit File",
    description: "Apply hash-checked atomic search/replace patch inside the workspace root",
    group: "code",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: true,
    resultType: "code",
    voiceAliases: ["edit workspace file"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      file_path: { type: "string", description: "Relative file path", required: true },
      target_content: { type: "string", description: "Exact existing snippet", required: true },
      replacement_content: { type: "string", description: "Replacement snippet", required: true },
    },
  },

  workspace_glob: {
    id: "workspace_glob",
    displayName: "Workspace: Glob Search",
    description: "Discover workspace files by glob pattern safely",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "file",
    voiceAliases: ["find files", "glob workspace"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      pattern: { type: "string", description: "Glob pattern", required: true },
    },
  },

  workspace_grep: {
    id: "workspace_grep",
    displayName: "Workspace: Grep Search",
    description: "Search lines inside workspace files by text or regex",
    group: "files",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["search code", "grep workspace"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      pattern: { type: "string", description: "Regex or substring query", required: true },
    },
  },

  workspace_verify_url: {
    id: "workspace_verify_url",
    displayName: "Workspace: Verify Local URL",
    description: "Verify a running localhost/127.0.0.1 server route in Chromium for HTTP status, JS errors, DOM, and pixels",
    group: "code",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["verify localhost url"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      url: { type: "string", description: "Loopback HTTP URL", required: true },
    },
  },

  workspace_start_process: {
    id: "workspace_start_process",
    displayName: "Workspace: Start Background Server",
    description: "Launch a bounded local dev server or daemon in the workspace with loopback readiness check",
    group: "code",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: true,
    resultType: "code",
    voiceAliases: ["start local server"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      command: { type: "string", description: "Safe server command", required: true },
    },
  },

  workspace_process_logs: {
    id: "workspace_process_logs",
    displayName: "Workspace: Process Logs",
    description: "Read recent stdout/stderr lines from a managed workspace background server",
    group: "code",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["check server logs"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      process_id: { type: "string", description: "Managed process ID", required: true },
    },
  },

  workspace_stop_process: {
    id: "workspace_stop_process",
    displayName: "Workspace: Stop Background Server",
    description: "Terminate a managed workspace background server",
    group: "code",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "code",
    voiceAliases: ["stop local server"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      process_id: { type: "string", description: "Managed process ID", required: true },
    },
  },

  workspace_spawn_subagent: {
    id: "workspace_spawn_subagent",
    displayName: "Agent: Spawn Subagent",
    description: "Run an isolated read-and-verify specialist subagent with its own context window",
    group: "system",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["spawn subagent"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      role: { type: "string", description: "Subagent role", required: true },
      task: { type: "string", description: "Subagent task", required: true },
    },
  },

  mlai_list_routines: {
    id: "mlai_list_routines",
    displayName: "ML AI Code: List Routines",
    description: "List automation routines registered on code.ml.ai",
    group: "system",
    permission: "low",
    requiresConfirmation: false,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["list mlai routines"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {},
  },

  mlai_run_routine: {
    id: "mlai_run_routine",
    displayName: "ML AI Code: Run Routine",
    description: "Trigger an asynchronous routine run on code.ml.ai (requires approval)",
    group: "system",
    permission: "confirm",
    requiresConfirmation: true,
    cancellable: false,
    rollbackAvailable: false,
    resultType: "text",
    voiceAliases: ["run mlai routine"],
    suggestedActions: [],
    availability: "connected",
    inputSchema: {
      routine_id: { type: "string", description: "Routine ID", required: true },
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
