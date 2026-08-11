import React from "react";

export function ImageGeneration({
  prompt = "a calm mountain lake at dawn",
  resolution = "1024 × 1024",
}: {
  prompt?: string;
  resolution?: string;
}) {
  return (
    <div className="flex flex-col gap-3 w-full max-w-sm">
      <div 
        className="relative aspect-square w-full rounded-xl overflow-hidden bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800"
        role="img" 
        aria-label="Generating image"
      >
        {/* Animated Background Canvas */}
        <div 
          className="absolute inset-0 opacity-40 mix-blend-overlay dark:mix-blend-color-dodge"
          style={{
            backgroundImage: "radial-gradient(circle at center, rgba(14, 165, 233, 0.4) 0%, transparent 70%), radial-gradient(circle at center, rgba(139, 92, 246, 0.4) 0%, transparent 70%)",
            backgroundSize: "100% 100%, 100% 100%",
            backgroundPosition: "0% 0%, 100% 100%",
            animation: "ig-morph 8s ease-in-out infinite",
            WebkitMaskImage: "radial-gradient(white, black)",
            WebkitMaskSize: "200% 200%",
          }}
          aria-hidden 
        />
        
        {/* Shimmer overlay */}
        <div 
          className="absolute inset-0"
          style={{
            background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)",
            backgroundSize: "200% 100%",
            animation: "ig-shine 3s infinite linear"
          }}
          aria-hidden
        />

        {/* Center Spinner */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-sky-500/30 border-t-sky-500 animate-spin" />
        </div>

        <span className="absolute bottom-3 right-3 text-[10px] font-medium text-zinc-500 bg-zinc-100/50 dark:bg-zinc-900/50 px-2 py-1 rounded backdrop-blur-sm">
          {resolution}
        </span>
      </div>
      <div className="flex flex-col gap-1 px-1">
        <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 flex items-center gap-2">
          Generating image
          <span className="flex gap-0.5">
            <span className="w-1 h-1 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1 h-1 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1 h-1 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: '300ms' }} />
          </span>
        </span>
        <span className="text-xs text-zinc-500 dark:text-zinc-500 italic line-clamp-2" style={{ animation: "ig-breathe 3s infinite ease-in-out" }}>
          “{prompt}”
        </span>
      </div>
    </div>
  );
}

export default ImageGeneration;
