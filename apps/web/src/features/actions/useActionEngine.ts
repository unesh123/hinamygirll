import { useState, useEffect, useCallback, useRef } from "react";
import type { HinaActionDraft, HinaCommittedAction, HinaObject } from "./types";
import { matchLocalActionIntent } from "./intentMatcher";
import { HINA_TIMINGS } from "../motion/MOTION";

const STORAGE_KEY = "hinaa_action_stack_v1";

export function useActionEngine(input: string, onClearInput?: () => void) {
  // P0 Suggestion layer: Non-blocking subtle hint while typing
  const [suggestion, setSuggestion] = useState<HinaObject | null>(null);

  // Adopted interactive draft (Only shown when explicitly adopted via Tab or click)
  const [activeDraft, setActiveDraft] = useState<HinaActionDraft | null>(null);

  const [committedActions, setCommittedActions] = useState<HinaCommittedAction[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return JSON.parse(saved);
    } catch {
      // ignore
    }
    return [];
  });

  const lastParsedInputRef = useRef<string>("");

  // Persist stack
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(committedActions));
    } catch {
      // ignore
    }
  }, [committedActions]);

  // Debounced fast local intent matching (< 80ms perceived parse)
  useEffect(() => {
    if (!input || input.trim().length < 3) {
      setSuggestion(null);
      if (activeDraft) setActiveDraft(null);
      lastParsedInputRef.current = "";
      return;
    }

    if (input === lastParsedInputRef.current) return;

    const timer = setTimeout(() => {
      lastParsedInputRef.current = input;
      const detected = matchLocalActionIntent(input);
      if (detected) {
        const { summary, badge } = getSummaryForDraft(detected);
        const newSuggestion: HinaObject = {
          id: detected.id,
          capabilityId: detected.intent,
          state: "suggested",
          fields: detected.fields.data,
          artifacts: [],
          revisions: [],
          title: badge,
          description: summary,
          suggestionText: summary,
          badgeLabel: badge,
          createdAt: detected.createdAt,
        };

        // If user already adopted a draft of the same intent, update activeDraft live
        if (activeDraft && activeDraft.intent === detected.intent) {
          setActiveDraft({
            ...detected,
            id: activeDraft.id,
          });
        } else if (!activeDraft) {
          // Otherwise, only show suggestion strip! Do NOT hijack composer into full card!
          setSuggestion(newSuggestion);
        }
      } else {
        setSuggestion(null);
      }
    }, HINA_TIMINGS.localParseDebounce);

    return () => clearTimeout(timer);
  }, [input, activeDraft]);

  // Helper to generate concise summary text for collapsed history row
  const getSummaryForDraft = (draft: HinaActionDraft): { summary: string; badge: string } => {
    const data = draft.fields.data as any;
    switch (draft.intent) {
      case "split":
        return {
          summary: `${data.currency}${data.totalAmount.toLocaleString()} ÷ ${data.peopleCount} = ${data.currency}${data.perPerson.toLocaleString()} each`,
          badge: "Split",
        };
      case "timer.start":
        return {
          summary: `⏱ ${data.label} · ${Math.round(data.durationSeconds / 60)}:00`,
          badge: "Timer",
        };
      case "event.create":
        return {
          summary: `📅 ${data.title} · ${data.dateStr}, ${data.timeStr}${data.participant ? ` with ${data.participant}` : ""}`,
          badge: "Event",
        };
      case "checklist.create":
        return {
          summary: `☑ ${data.title} (${data.items?.length || 0} items)`,
          badge: "Checklist",
        };
      case "timezone.convert":
        return {
          summary: `🌐 ${data.sourceTime} ${data.sourceTz} → ${data.targetTime} ${data.targetTz}`,
          badge: "Time zone",
        };
      case "reminder.create":
        return {
          summary: `🔔 ${data.title} · ${data.when}`,
          badge: data.isUrgent ? "Urgent" : "Reminder",
        };
      case "random.roll":
        return {
          summary: `🎲 Roll Result: ${data.total} (${data.rolls?.join(", ")})`,
          badge: "Random",
        };
      case "color.inspect":
        return {
          summary: `🎨 ${data.name || "Color"} · ${data.hex}`,
          badge: "Color",
        };
      case "image.job":
        return {
          summary: `🖼 ${data.prompt.slice(0, 36)}…`,
          badge: "Image",
        };
      case "pdf.doc":
        return {
          summary: `📄 ${data.title}`,
          badge: "PDF",
        };
      case "plan.run":
        return {
          summary: `⚡ ${data.title}`,
          badge: "Plan",
        };
      case "browser.agent":
        return {
          summary: `🌐 ${data.pageTitle} · ${data.task.slice(0, 30)}…`,
          badge: "Browser",
        };
      default:
        return { summary: draft.input, badge: "Action" };
    }
  };

  // Commit action into the stack
  const commitAction = useCallback(
    (draftToCommit?: HinaActionDraft) => {
      const draft = draftToCommit || activeDraft;
      if (!draft) return false;

      const { summary, badge } = getSummaryForDraft(draft);
      const committedItem: HinaCommittedAction = {
        id: draft.id,
        draft: { ...draft, status: "success" },
        committedAt: Date.now(),
        summaryText: summary,
        badgeLabel: badge,
      };

      setCommittedActions((prev) => [committedItem, ...prev]);
      setActiveDraft(null);
      if (onClearInput) onClearInput();
      return true;
    },
    [activeDraft, onClearInput]
  );

  // Adopt suggestion into active draft (Flow A: Tab / Click)
  const adoptSuggestion = useCallback(() => {
    if (!suggestion) return;
    const detected = matchLocalActionIntent(input);
    if (detected) {
      setActiveDraft(detected);
      setSuggestion(null);
    }
  }, [suggestion, input]);

  // Dismiss suggestion strip (Esc / click close)
  const dismissSuggestion = useCallback(() => {
    setSuggestion(null);
  }, []);

  // Dismiss / collapse draft
  const dismissDraft = useCallback(() => {
    setActiveDraft(null);
  }, []);

  // Stack management
  const removeCommittedAction = useCallback((id: string) => {
    setCommittedActions((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const updateCommittedAction = useCallback((id: string, updatedDraft: HinaActionDraft) => {
    setCommittedActions((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;
        const { summary, badge } = getSummaryForDraft(updatedDraft);
        return {
          ...item,
          draft: updatedDraft,
          summaryText: summary,
          badgeLabel: badge,
        };
      })
    );
  }, []);

  return {
    suggestion,
    activeDraft,
    committedActions,
    adoptSuggestion,
    dismissSuggestion,
    commitAction,
    dismissDraft,
    removeCommittedAction,
    updateCommittedAction,
  };
}
