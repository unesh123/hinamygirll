/**
 * HINA ACTION ENGINE — Universal Action Protocol
 *
 * Every action card speaks this universal contract.
 * Law 1: One object, many states (pill -> card -> history row)
 * Law 5: What morphs vs what doesn't (Actions morph, chat stays chat)
 */

export type HinaIntent =
  | "split"
  | "timer.start"
  | "event.create"
  | "checklist.create"
  | "timezone.convert"
  | "reminder.create"
  | "random.roll"
  | "color.inspect"
  | "image.job"
  | "pdf.doc"
  | "plan.run"
  | "browser.agent"
  | "chat"; // Normal conversation, does NOT morph

export type ActionStatus = "preview" | "ready" | "executing" | "success" | "error";

export interface SplitFields {
  totalAmount: number;
  currency: string;
  peopleCount: number;
  perPerson: number;
  tipPercent?: number;
}

export interface TimerFields {
  durationSeconds: number;
  remainingSeconds: number;
  label: string;
  isRunning: boolean;
  isCompleted: boolean;
}

export interface EventFields {
  title: string;
  participant?: string;
  dateStr: string;
  timeStr: string;
  location?: string;
}

export interface ChecklistItem {
  id: string;
  text: string;
  checked: boolean;
}

export interface ChecklistFields {
  title: string;
  items: ChecklistItem[];
}

export interface TimezoneFields {
  sourceTime: string;
  sourceTz: string;
  targetTime: string;
  targetTz: string;
  isNextDay?: boolean;
}

export interface ReminderFields {
  title: string;
  when: string;
  isUrgent: boolean;
}

export interface RandomFields {
  type: "dice" | "coin" | "number";
  diceCount: number;
  diceSides: number;
  rolls: number[];
  total: number;
}

export interface ColorFields {
  hex: string;
  rgb: string;
  name?: string;
}

export interface ImageJobFields {
  prompt: string;
  stage: "seeing" | "generating" | "saved";
  progressPercent?: number;
  elapsedSeconds?: number;
  thumbnailUrl?: string;
  resultUrl?: string;
  isSearchFallback?: boolean;
  note?: string;
}

export interface PdfDocFields {
  title: string;
  outline: string[];
  stage: "outlining" | "generating" | "ready";
  downloadUrl?: string;
}

export interface PlanStep {
  id: string;
  title: string;
  status: "pending" | "running" | "done";
  iconName?: string;
}

export interface PlanFields {
  title: string;
  steps: PlanStep[];
  allCompleted: boolean;
}

export interface BrowserAgentFields {
  task: string;
  currentUrl: string;
  pageTitle: string;
  lastAction: string;
  statusText: string;
  isLive: boolean;
  canTakeOver: boolean;
}

export type ActionFields =
  | { intent: "split"; data: SplitFields }
  | { intent: "timer.start"; data: TimerFields }
  | { intent: "event.create"; data: EventFields }
  | { intent: "checklist.create"; data: ChecklistFields }
  | { intent: "timezone.convert"; data: TimezoneFields }
  | { intent: "reminder.create"; data: ReminderFields }
  | { intent: "random.roll"; data: RandomFields }
  | { intent: "color.inspect"; data: ColorFields }
  | { intent: "image.job"; data: ImageJobFields }
  | { intent: "pdf.doc"; data: PdfDocFields }
  | { intent: "plan.run"; data: PlanFields }
  | { intent: "browser.agent"; data: BrowserAgentFields }
  | { intent: "chat"; data: Record<string, never> };

export interface HinaActionDraft {
  id: string;
  intent: HinaIntent;
  confidence: number;
  input: string;
  entity?: {
    name: string;
    canonicalName?: string;
    type?: string;
  };
  fields: ActionFields;
  status: ActionStatus;
  createdAt: number;
}

export interface HinaCommittedAction {
  id: string;
  draft: HinaActionDraft;
  committedAt: number;
  summaryText: string;
  badgeLabel: string;
  isExpanded?: boolean;
}

// P1 Universal HinaObject Runtime Model
export type HinaObjectState = "suggested" | "draft" | "running" | "completed" | "failed";

export interface HinaArtifact {
  id: string;
  type: string;
  url?: string;
  title?: string;
  data?: any;
}

export interface HinaObject {
  id: string;
  capabilityId: string;
  state: HinaObjectState;
  fields: Record<string, any>;
  artifacts?: HinaArtifact[];
  revisions?: any[];
  title?: string;
  description?: string;
  suggestionText?: string;
  badgeLabel?: string;
  createdAt: number;
  updatedAt?: number;
}
