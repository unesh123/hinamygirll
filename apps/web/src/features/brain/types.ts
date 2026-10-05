export type SpecialistType = 'planner' | 'researcher' | 'coder' | 'synthesizer' | 'memory';
export type SpecialistStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'skipped';

export interface BrainSpecialist {
  type: SpecialistType;
  status: SpecialistStatus;
  label: string;
  detail?: string;
  startedAt?: number;
  completedAt?: number;
  durationMs?: number;
  sourceCount?: number;
  tokenCount?: number;
  error?: string;
}

export interface BrainRunState {
  runId: string;
  status: 'idle' | 'planning' | 'running' | 'completed' | 'failed';
  startedAt?: number;
  specialists: BrainSpecialist[];
  activePlan?: string[];
  sourcesFound?: number;
  totalTokens?: number;
}

export interface BrainRunEvent {
  event_type: string;
  run_id: string;
  specialist?: SpecialistType;
  step_id?: string;
  payload: Record<string, unknown>;
  timestamp: number;
}
