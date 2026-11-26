import type { TranscriptMessage } from "../features/companion/types";

/**
 * Deterministic 1,000-message fixture for chat virtualization and memory benchmarks.
 */
export function buildChatPerfMessages(count = 1000): TranscriptMessage[] {
  const baseMs = Date.UTC(2026, 10, 26, 12, 0, 0);
  const out: TranscriptMessage[] = new Array(count);
  for (let i = 0; i < count; i++) {
    const isUser = i % 2 === 0;
    const text = isUser
      ? `Turn #${i}: Check module_${i}.ts and report status.`
      : i % 6 === 1
        ? `Analyzed \`module_${i}.ts\` cleanly:\n\n\`\`\`ts\nexport const step_${i} = ${i};\n\`\`\`\n\n- Zero regressions detected.`
        : `Completed step ${i} across workspace verification without errors.`;
    out[i] = {
      id: `perf-msg-${i}`,
      role: isUser ? "user" : "assistant",
      text,
      createdAt: new Date(baseMs + i * 1000).toISOString(),
    };
  }
  return out;
}
