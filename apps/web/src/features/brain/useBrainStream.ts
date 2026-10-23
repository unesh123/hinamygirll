/**
 * useBrainStream — connects to /api/v1/brain/run SSE and maps events
 * into a live BrainRunState for the BrainOrchestrationPanel.
 */
import { useState, useCallback, useRef } from 'react';
import type { BrainRunState, BrainRunEvent, SpecialistType } from './types';

const INITIAL_STATE: BrainRunState = {
  runId: '',
  status: 'idle',
  specialists: [],
};

const API_BASE = (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE ?? 'http://localhost:8000';

export function useBrainStream() {
  const [brainState, setBrainState] = useState<BrainRunState>(INITIAL_STATE);
  const esRef = useRef<AbortController | null>(null);

  const runBrain = useCallback(async (userText: string, sessionId?: string) => {
    // Cancel any running stream
    esRef.current?.abort();
    esRef.current = new AbortController();

    setBrainState({ runId: '', status: 'planning', specialists: [], startedAt: Date.now() });

    try {
      const resp = await fetch(`${API_BASE}/api/v1/brain/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_text: userText, session_id: sessionId }),
        signal: esRef.current.signal,
      });

      if (!resp.ok || !resp.body) return;

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;
          try {
            const event: BrainRunEvent = JSON.parse(raw);
            applyEvent(event, setBrainState);
          } catch {
            // ignore parse errors
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setBrainState(s => ({ ...s, status: 'failed' }));
    }
  }, []);

  const reset = useCallback(() => {
    esRef.current?.abort();
    setBrainState(INITIAL_STATE);
  }, []);

  return { brainState, runBrain, reset };
}

function applyEvent(event: BrainRunEvent, setState: React.Dispatch<React.SetStateAction<BrainRunState>>) {
  setState(prev => {
    const next = { ...prev };

    switch (event.event_type) {
      case 'brain.run.started':
        return {
          ...next,
          runId: event.run_id,
          status: 'planning' as const,
          startedAt: Date.now(),
          specialists: [],
        };

      case 'brain.specialist.started': {
        const type = event.specialist as SpecialistType;
        const exists = next.specialists.find(s => s.type === type);
        if (!exists) {
          next.specialists = [
            ...next.specialists,
            {
              type,
              status: 'running' as const,
              label: SPECIALIST_LABELS[type] ?? type,
              startedAt: Date.now(),
            },
          ];
        } else {
          next.specialists = next.specialists.map(s =>
            s.type === type ? { ...s, status: 'running' as const, startedAt: Date.now() } : s,
          );
        }
        next.status = 'running' as const;
        return next;
      }

      case 'brain.specialist.completed': {
        const type = event.specialist as SpecialistType;
        next.specialists = next.specialists.map(s => {
          if (s.type !== type) return s;
          const now = Date.now();
          return {
            ...s,
            status: 'completed' as const,
            completedAt: now,
            durationMs: now - (s.startedAt ?? now),
            sourceCount: (event.payload?.source_count as number) ?? s.sourceCount,
            tokenCount: (event.payload?.token_count as number) ?? s.tokenCount,
            detail: (event.payload?.detail as string) ?? s.detail,
          };
        });
        if (event.payload?.sources_found) {
          next.sourcesFound = event.payload.sources_found as number;
        }
        return next;
      }

      case 'brain.specialist.failed': {
        const type = event.specialist as SpecialistType;
        next.specialists = next.specialists.map(s =>
          s.type === type
            ? { ...s, status: 'failed' as const, error: (event.payload?.error as string) ?? 'failed' }
            : s,
        );
        return next;
      }

      case 'brain.run.completed':
        return { ...next, status: 'completed' as const };

      case 'brain.run.failed':
        return { ...next, status: 'failed' as const };
    }

    return next;
  });
}

const SPECIALIST_LABELS: Record<string, string> = {
  planner: 'Planning strategy',
  researcher: 'Researching sources',
  coder: 'Generating code',
  synthesizer: 'Synthesizing response',
  memory: 'Retrieving memory',
  operator: 'Executing operation',
};
