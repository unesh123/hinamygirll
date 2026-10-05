import { useMemo } from 'react';
import type { LiveAgentStep } from '../companion/useCompanionController';
import type { BrainRunState, BrainSpecialist, SpecialistType, SpecialistStatus } from './types';

const SPECIALIST_LABELS: Record<SpecialistType, string> = {
  planner: 'Planning',
  researcher: 'Research',
  coder: 'Coding',
  synthesizer: 'Synthesis',
  memory: 'Memory',
};

export function useBrainState({
  agentSteps,
  isThinking,
  isSearching,
  searchQuery,
  currentAgentRunId,
  streamingText,
}: {
  agentSteps: LiveAgentStep[];
  isThinking: boolean;
  isSearching: boolean;
  searchQuery: string;
  currentAgentRunId?: string;
  streamingText: string;
}): BrainRunState {
  return useMemo(() => {
    const specialists: BrainSpecialist[] = [
      { type: 'planner', status: 'idle', label: SPECIALIST_LABELS.planner },
      { type: 'researcher', status: 'idle', label: SPECIALIST_LABELS.researcher },
      { type: 'coder', status: 'idle', label: SPECIALIST_LABELS.coder },
      { type: 'synthesizer', status: 'idle', label: SPECIALIST_LABELS.synthesizer },
      { type: 'memory', status: 'idle', label: SPECIALIST_LABELS.memory },
    ];

    let runStatus: BrainRunState['status'] = 'idle';
    let sourcesFound = 0;
    
    // Map agentSteps to specialists based on their labels/ids
    for (const step of agentSteps) {
      let matchedType: SpecialistType | undefined;
      
      const labelLower = step.label.toLowerCase();
      const idLower = step.id.toLowerCase();
      
      if (idLower.includes('plan') || labelLower.includes('plan')) {
        matchedType = 'planner';
      } else if (idLower.includes('search') || idLower.includes('research') || labelLower.includes('search')) {
        matchedType = 'researcher';
      } else if (idLower.includes('code') || labelLower.includes('code') || labelLower.includes('tool')) {
        matchedType = 'coder';
      } else if (idLower.includes('memory') || labelLower.includes('memory')) {
        matchedType = 'memory';
      } else if (idLower.includes('synthesiz') || labelLower.includes('synthesiz') || labelLower.includes('respond')) {
        matchedType = 'synthesizer';
      }

      if (matchedType) {
        const spec = specialists.find(s => s.type === matchedType);
        if (spec) {
          let specStatus: SpecialistStatus = 'idle';
          if (step.status === 'active') specStatus = 'running';
          else if (step.status === 'done') specStatus = 'completed';
          else if (step.status === 'error') specStatus = 'failed';
          else if (step.status === 'pending') specStatus = 'queued';
          else if (step.status === 'cancelled') specStatus = 'skipped';
          
          spec.status = specStatus;
          spec.detail = step.detail;
          spec.label = step.label; // override with specific label
        }
      }
    }

    // Heuristics based on top-level state
    if (isThinking) {
      runStatus = 'planning';
      const planner = specialists.find(s => s.type === 'planner');
      if (planner && planner.status === 'idle') planner.status = 'running';
    }

    if (isSearching) {
      runStatus = 'running';
      const researcher = specialists.find(s => s.type === 'researcher');
      if (researcher && researcher.status === 'idle') {
        researcher.status = 'running';
        researcher.detail = searchQuery;
      }
    }

    if (streamingText) {
      runStatus = 'running';
      const synth = specialists.find(s => s.type === 'synthesizer');
      if (synth && (synth.status === 'idle' || synth.status === 'queued')) synth.status = 'running';
    }

    if (currentAgentRunId) {
      if (runStatus === 'idle') runStatus = 'running';
    } else if (agentSteps.length > 0) {
      const anyActive = agentSteps.some(s => s.status === 'active');
      const anyError = agentSteps.some(s => s.status === 'error');
      if (anyError) runStatus = 'failed';
      else if (!anyActive && !isThinking && !isSearching && !streamingText) runStatus = 'completed';
      else runStatus = 'running';
    }

    return {
      runId: currentAgentRunId || 'local-run',
      status: runStatus,
      startedAt: Date.now(), // rough estimate without history
      specialists,
      sourcesFound,
      totalTokens: 0,
    };
  }, [agentSteps, isThinking, isSearching, searchQuery, currentAgentRunId, streamingText]);
}
