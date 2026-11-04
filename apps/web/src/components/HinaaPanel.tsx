import React, { Suspense } from "react";
import { Sparkles, Activity, Eye, Compass, Heart } from "lucide-react";
import { HinaaScene } from "../three/HinaaScene";
import type { CompanionState } from "../features/companion/types";

export interface HinaaPanelProps {
  modelName?: string;
  modelUrl?: string;
  companionState?: CompanionState;
  isWalking?: boolean;
  speakingRef?: React.MutableRefObject<boolean>;
  jawEnergy?: React.MutableRefObject<number>;
  activeMode?: string;
  currentMood?: string;
  onOpenAvatarLab?: () => void;
}

/**
 * Centered pulsing silhouette / skeleton loader for the 3D model.
 * Replaces blank `null` Suspense fallback, preventing blank canvas flash during slow GLB/VRM loads.
 */
function ModelSkeletonLoader() {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-radial from-[#171124] to-[#0b0710] text-white p-6">
      <div className="relative flex items-center justify-center mb-4">
        {/* Pulsing avatar silhouette circle */}
        <div className="w-24 h-24 rounded-full bg-brand-300/20 animate-ping absolute" />
        <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-accent/40 to-brand-300/40 border border-brand-300/40 flex items-center justify-center shadow-lg relative backdrop-blur-xs">
          <Sparkles className="text-brand-300 animate-pulse" size={28} />
        </div>
      </div>
      <span className="text-xs font-semibold text-brand-100 tracking-wide animate-pulse">
        Loading 3D Model…
      </span>
      <span className="text-[10px] text-text-muted mt-1">
        Compiling shaders & bones
      </span>
    </div>
  );
}

export function HinaaPanel({
  modelName = "Hinaa (Original)",
  modelUrl = "/models/hinaa-original.vrm",
  companionState = "idle",
  isWalking = false,
  speakingRef,
  jawEnergy,
  activeMode = "Co-Pilot",
  currentMood = "Calm",
  onOpenAvatarLab,
}: HinaaPanelProps) {
  return (
    <aside className="w-[360px] h-full flex flex-col min-w-0 min-h-0 bg-frost/70 backdrop-blur-md border border-glass-border rounded-xl shadow-soft overflow-hidden">
      {/* ── 1. Upper: 3D Model Canvas with Suspense Fallback ── */}
      <div className="h-[340px] w-full relative flex-shrink-0 bg-[#0b0710] overflow-hidden">
        <Suspense fallback={<ModelSkeletonLoader />}>
          <HinaaScene
            modelUrl={modelUrl}
            companionState={companionState}
            isWalking={isWalking}
            speakingRef={speakingRef}
            jawEnergy={jawEnergy}
          />
        </Suspense>

        {/* Floating status tag */}
        <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-white text-[10px] font-medium pointer-events-none">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="capitalize">{companionState}</span>
        </div>

        {onOpenAvatarLab && (
          <button
            type="button"
            onClick={onOpenAvatarLab}
            className="absolute top-3 right-3 p-1.5 rounded-lg bg-black/40 hover:bg-black/60 backdrop-blur-md border border-white/10 text-white text-xs transition-colors"
            title="Configure Avatar"
          >
            <Eye size={13} />
          </button>
        )}
      </div>

      {/* ── 2. Lower: Information Card with break-words and min-w-0 (NO HORIZONTAL SCROLL) ── */}
      <div className="flex-1 p-3.5 flex flex-col justify-between overflow-y-auto min-h-0 min-w-0">
        <div className="space-y-3 min-w-0">
          {/* Header row with name badge */}
          <div className="flex items-center justify-between min-w-0 gap-2">
            <h2 className="font-bold text-xs text-text-primary truncate min-w-0">
              {modelName}
            </h2>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-100 text-accent flex-shrink-0">
              Verified VRM
            </span>
          </div>

          {/* Body text strictly wrapped with break-words min-w-0 to eliminate horizontal scrollbar */}
          <p className="text-[11px] leading-relaxed text-text-secondary break-words min-w-0">
            Interactive digital companion equipped with facial tracking, autonomous locomotion, and real-time emotive expressions.
          </p>

          {/* Operational Matrix Chips */}
          <div className="grid grid-cols-2 gap-2 pt-1 min-w-0">
            <div className="p-2 rounded-lg bg-white border border-glass-border min-w-0">
              <span className="text-[9px] font-bold text-text-muted uppercase block tracking-wider">
                Relationship
              </span>
              <span className="text-xs font-semibold text-text-primary truncate block mt-0.5">
                {activeMode}
              </span>
            </div>

            <div className="p-2 rounded-lg bg-white border border-glass-border min-w-0">
              <span className="text-[9px] font-bold text-text-muted uppercase block tracking-wider">
                Mood State
              </span>
              <span className="text-xs font-semibold text-accent truncate block mt-0.5 flex items-center gap-1">
                <Heart size={11} className="fill-accent/20" />
                {currentMood}
              </span>
            </div>
          </div>
        </div>

        {/* Footer info pill */}
        <div className="mt-3 pt-2.5 border-t border-glass-border flex items-center justify-between text-[10px] text-text-muted min-w-0 flex-shrink-0">
          <span className="truncate">Physics: Active</span>
          <span className="font-mono">FPS: 60</span>
        </div>
      </div>
    </aside>
  );
}
