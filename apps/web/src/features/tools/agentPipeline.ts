/**
 * HINAA Agent Automation Pipeline
 * Chains multiple tool calls into automated workflows with progress tracking.
 *
 * Pipelines:
 * - Search → Fetch → Summarize
 * - Browser → Read → Explain
 * - Image Search → Display Gallery
 * - Code Analysis → Explain → Fix
 */

import { toolEventBus, createToolEvent, type ToolEvent } from "./toolRegistry";

export type PipelineStepStatus = "pending" | "active" | "completed" | "failed" | "cancelled";

export interface PipelineStep {
  id: string;
  label: string;
  toolId: string;
  status: PipelineStepStatus;
  detail?: string;
  result?: unknown;
}

export interface AgentPipeline {
  id: string;
  name: string;
  description: string;
  steps: PipelineStep[];
  status: PipelineStepStatus;
  conversationId: string;
  createdAt: number;
}

export type PipelineListener = (pipeline: AgentPipeline) => void;

/* ─── Pipeline Manager ────────────────────────────────── */
class PipelineManager {
  private pipelines = new Map<string, AgentPipeline>();
  private listeners = new Set<PipelineListener>();

  create(
    name: string,
    description: string,
    steps: Array<{ label: string; toolId: string }>,
    conversationId: string,
  ): AgentPipeline {
    const id = `pipeline-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const pipeline: AgentPipeline = {
      id,
      name,
      description,
      steps: steps.map((s, i) => ({
        id: `${id}-step-${i}`,
        label: s.label,
        toolId: s.toolId,
        status: "pending",
      })),
      status: "pending",
      conversationId,
      createdAt: Date.now(),
    };

    this.pipelines.set(id, pipeline);
    this.notify(pipeline);

    // Emit pipeline events
    toolEventBus.emit(
      createToolEvent(id, conversationId, "pipeline", "tool.started", `Starting pipeline: ${name}`, pipeline),
    );

    return pipeline;
  }

  updateStep(pipelineId: string, stepId: string, update: Partial<PipelineStep>): void {
    const pipeline = this.pipelines.get(pipelineId);
    if (!pipeline) return;

    pipeline.steps = pipeline.steps.map((s) =>
      s.id === stepId ? { ...s, ...update } : s,
    );

    // Update overall status
    const allDone = pipeline.steps.every((s) => s.status === "completed");
    const anyFailed = pipeline.steps.some((s) => s.status === "failed");
    pipeline.status = allDone ? "completed" : anyFailed ? "failed" : "active";

    this.notify(pipeline);

    toolEventBus.emit(
      createToolEvent(pipelineId, pipeline.conversationId, update.toolId || "pipeline", "tool.progress", update.detail || update.label || "Step updated", update),
    );
  }

  complete(pipelineId: string): void {
    const pipeline = this.pipelines.get(pipelineId);
    if (!pipeline) return;

    pipeline.status = "completed";
    pipeline.steps = pipeline.steps.map((s) => ({ ...s, status: "completed" as const }));
    this.notify(pipeline);

    toolEventBus.emit(
      createToolEvent(pipelineId, pipeline.conversationId, "pipeline", "tool.completed", `Pipeline complete: ${pipeline.name}`),
    );
  }

  cancel(pipelineId: string): void {
    const pipeline = this.pipelines.get(pipelineId);
    if (!pipeline) return;

    pipeline.status = "cancelled";
    pipeline.steps = pipeline.steps.filter((s) => s.status !== "completed").map((s) => ({ ...s, status: "cancelled" as const }));
    this.notify(pipeline);

    toolEventBus.emit(
      createToolEvent(pipelineId, pipeline.conversationId, "pipeline", "tool.cancelled", `Pipeline cancelled: ${pipeline.name}`),
    );
  }

  get(pipelineId: string): AgentPipeline | undefined {
    return this.pipelines.get(pipelineId);
  }

  getAll(): AgentPipeline[] {
    return Array.from(this.pipelines.values());
  }

  subscribe(listener: PipelineListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(pipeline: AgentPipeline): void {
    this.listeners.forEach((fn) => {
      try { fn({ ...pipeline }); } catch { /* ignore */ }
    });
  }
}

export const pipelineManager = new PipelineManager();

/* ─── Predefined Pipelines ────────────────────────────── */
export const PIPELINE_TEMPLATES = {
  "search-summarize": {
    name: "Research & Summarize",
    description: "Search the web, fetch top results, and create a summary",
    steps: [
      { label: "Searching the web", toolId: "web_search" },
      { label: "Opening top results", toolId: "browser_navigate" },
      { label: "Reading and extracting", toolId: "browser_read" },
      { label: "Synthesizing summary", toolId: "synthesize" },
    ],
  },
  "browse-explain": {
    name: "Browse & Explain",
    description: "Navigate to a URL, read content, and explain it",
    steps: [
      { label: "Navigating to page", toolId: "browser_navigate" },
      { label: "Reading page content", toolId: "browser_read" },
      { label: "Explaining findings", toolId: "explain" },
    ],
  },
  "image-fetch": {
    name: "Find & Display Images",
    description: "Search for images and display them in a gallery",
    steps: [
      { label: "Searching for images", toolId: "image_search" },
      { label: "Fetching image details", toolId: "fetch_images" },
      { label: "Displaying gallery", toolId: "display_gallery" },
    ],
  },
  "code-analyze": {
    name: "Code Analysis",
    description: "Analyze code, find issues, and suggest fixes",
    steps: [
      { label: "Reading code", toolId: "file_search" },
      { label: "Analyzing structure", toolId: "analyze_code" },
      { label: "Finding issues", toolId: "lint_check" },
      { label: "Suggesting fixes", toolId: "suggest_fix" },
    ],
  },
};
