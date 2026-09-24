/**
 * HINA ACTION ENGINE — Fast Local Intent Matcher
 *
 * Runs completely client-side in < 80ms with ZERO LLM calls.
 * Only if the local matcher is unsure does it escalate after 420ms typing pause.
 *
 * Law 5: Only actions morph. Normal chat stays chat.
 */

import type { HinaActionDraft, ActionFields, ChecklistItem } from "./types";

/**
 * Main local intent classifier & parser.
 * Returns null if the input is casual chat or empty.
 */
export function matchLocalActionIntent(rawInput: string): HinaActionDraft | null {
  const text = rawInput.trim();
  if (!text || text.length < 3) return null;

  const lower = text.toLowerCase();

  // EXCLUSIONS: Normal conversational questions should NEVER morph into action cards.
  // "Who is Mikasa?", "Explain relativity", "What is the meaning of life?", etc.
  if (
    /^(who|what|why|how|where|when|tell me about|explain|describe)\b/i.test(lower) &&
    !/(pdf|image|timer|reminder|calc|split|dice|color|browser)/i.test(lower)
  ) {
    return null;
  }

  // 1. SPLIT BILL / EXPENSE: "split 2400 between 3", "split 2400 by 3", "2400 / 3", "split 5000 with 4"
  const splitMatch =
    lower.match(/(?:split|divide)\s+(?:(?:rs\.?|npr|inr|₹|\$|€|£)\s*)?(\d+[\d,]*)\s*(?:between|by|with|among|\/)\s*(\d+)/i) ||
    lower.match(/^(\d+[\d,]*)\s*\/\s*(\d+)$/);

  if (splitMatch) {
    const rawAmount = parseFloat(splitMatch[1].replace(/,/g, ""));
    const people = Math.max(1, parseInt(splitMatch[2], 10) || 1);
    if (!isNaN(rawAmount) && rawAmount > 0) {
      let currency = "₹";
      if (text.includes("$")) currency = "$";
      else if (text.includes("€")) currency = "€";
      else if (text.includes("£")) currency = "£";
      else if (/npr/i.test(text)) currency = "NPR";

      const perPerson = Math.round(rawAmount / people);
      const fields: ActionFields = {
        intent: "split",
        data: {
          totalAmount: rawAmount,
          currency,
          peopleCount: people,
          perPerson,
        },
      };

      return {
        id: `split-${Date.now()}`,
        intent: "split",
        confidence: 0.98,
        input: text,
        fields,
        status: "ready",
        createdAt: Date.now(),
      };
    }
  }

  // 2. TIMER / FOCUS: "25 min focus", "focus 25 min", "timer 10m", "timer 5 minutes", "15 min timer"
  const timerMatch =
    lower.match(/(?:(?:set\s+a\s+)?timer(?:\s+for)?\s+)?(\d+)\s*(?:min|mins|minute|minutes|m)\s*(?:focus|study|break|work)?/i) ||
    lower.match(/(?:focus|study|break|work)\s+(\d+)\s*(?:min|mins|minute|minutes|m)/i) ||
    lower.match(/^timer\s+(\d+)$/i);

  if (timerMatch) {
    const minutes = parseInt(timerMatch[1], 10);
    if (!isNaN(minutes) && minutes > 0 && minutes <= 180) {
      let label = "Focus Session";
      if (lower.includes("break")) label = "Short Break";
      else if (lower.includes("study")) label = "Study Session";
      else if (lower.includes("work")) label = "Deep Work";

      const durationSeconds = minutes * 60;
      const fields: ActionFields = {
        intent: "timer.start",
        data: {
          durationSeconds,
          remainingSeconds: durationSeconds,
          label,
          isRunning: false,
          isCompleted: false,
        },
      };

      return {
        id: `timer-${Date.now()}`,
        intent: "timer.start",
        confidence: 0.96,
        input: text,
        fields,
        status: "ready",
        createdAt: Date.now(),
      };
    }
  }

  // 3. RANDOM / DICE: "roll 2d6", "roll dice", "flip a coin", "roll d20"
  const diceMatch = lower.match(/(?:roll|throw)\s+(\d+)?d(\d+)/i);
  const coinMatch = lower.match(/flip\s+(?:a\s+)?coin/i);
  const simpleRoll = lower.match(/^roll\s+dice$/i);

  if (diceMatch || coinMatch || simpleRoll) {
    let count = 2;
    let sides = 6;
    let type: "dice" | "coin" | "number" = "dice";

    if (coinMatch) {
      type = "coin";
      count = 1;
      sides = 2;
    } else if (diceMatch) {
      count = Math.min(10, Math.max(1, parseInt(diceMatch[1] || "1", 10)));
      sides = Math.min(100, Math.max(2, parseInt(diceMatch[2], 10)));
    }

    const rolls: number[] = [];
    let total = 0;
    for (let i = 0; i < count; i++) {
      const val = Math.floor(Math.random() * sides) + 1;
      rolls.push(val);
      total += val;
    }

    const fields: ActionFields = {
      intent: "random.roll",
      data: {
        type,
        diceCount: count,
        diceSides: sides,
        rolls,
        total,
      },
    };

    return {
      id: `random-${Date.now()}`,
      intent: "random.roll",
      confidence: 0.99,
      input: text,
      fields,
      status: "ready",
      createdAt: Date.now(),
    };
  }

  // 4. COLOR INSPECTION: "#4AEDD9", "minecraft diamond color", "color #ff0055"
  const hexMatch = text.match(/#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/);
  const colorPresetMatch = lower.match(/(?:minecraft\s+diamond|sakura\s+pink|neon\s+cyan|emerald\s+green)\s*(?:color)?/i);

  if (hexMatch || colorPresetMatch) {
    let hex = hexMatch ? `#${hexMatch[1].toUpperCase()}` : "#4AEDD9";
    let name = "Color Inspector";

    if (colorPresetMatch) {
      if (lower.includes("minecraft")) {
        hex = "#4AEDD9";
        name = "Minecraft Diamond";
      } else if (lower.includes("sakura")) {
        hex = "#FFB7C5";
        name = "Sakura Blossom";
      } else if (lower.includes("neon")) {
        hex = "#00FFCC";
        name = "Neon Cyan";
      } else if (lower.includes("emerald")) {
        hex = "#10B981";
        name = "Emerald Green";
      }
    }

    // Convert hex to rgb
    const cleanHex = hex.replace("#", "");
    const r = parseInt(cleanHex.length === 3 ? cleanHex[0] + cleanHex[0] : cleanHex.slice(0, 2), 16);
    const g = parseInt(cleanHex.length === 3 ? cleanHex[1] + cleanHex[1] : cleanHex.slice(2, 4), 16);
    const b = parseInt(cleanHex.length === 3 ? cleanHex[2] + cleanHex[2] : cleanHex.slice(4, 6), 16);

    const fields: ActionFields = {
      intent: "color.inspect",
      data: {
        hex,
        rgb: `rgb(${r}, ${g}, ${b})`,
        name,
      },
    };

    return {
      id: `color-${Date.now()}`,
      intent: "color.inspect",
      confidence: 0.97,
      input: text,
      fields,
      status: "ready",
      createdAt: Date.now(),
    };
  }

  // 5. TIMEZONE CONVERTER: "3pm pst in ist", "10am est to gmt", "2pm utc in npt"
  const tzMatch = lower.match(/(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+([a-z]{3,4})\s+(?:in|to|in\s+to)\s+([a-z]{3,4}|nepal|india)/i);
  if (tzMatch) {
    const sourceTime = tzMatch[1].toUpperCase();
    const sourceTz = tzMatch[2].toUpperCase();
    let targetTz = tzMatch[3].toUpperCase();
    if (targetTz === "NEPAL") targetTz = "NPT";
    if (targetTz === "INDIA") targetTz = "IST";

    // Estimated standard conversions for demo preview
    let targetTime = "11:30 PM";
    let isNextDay = false;

    if (sourceTz === "PST" && (targetTz === "IST" || targetTz === "NPT")) {
      targetTime = "3:30 AM";
      isNextDay = true;
    } else if (sourceTz === "EST" && (targetTz === "IST" || targetTz === "NPT")) {
      targetTime = "6:30 AM";
      isNextDay = true;
    }

    const fields: ActionFields = {
      intent: "timezone.convert",
      data: {
        sourceTime,
        sourceTz,
        targetTime,
        targetTz,
        isNextDay,
      },
    };

    return {
      id: `tz-${Date.now()}`,
      intent: "timezone.convert",
      confidence: 0.94,
      input: text,
      fields,
      status: "ready",
      createdAt: Date.now(),
    };
  }

  // 6. CHECKLIST / SHOPPING: "buy milk, eggs, bread and coffee", "checklist: milk, eggs, bread"
  const checklistPrefix = lower.match(/^(?:buy|get|checklist:?|todo:?)\s+(.+)$/i);
  if (checklistPrefix && (lower.includes(",") || lower.includes(" and "))) {
    const rawItems = checklistPrefix[1]
      .split(/,|\band\b/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    if (rawItems.length >= 2) {
      const items: ChecklistItem[] = rawItems.map((item, idx) => ({
        id: `item-${idx}`,
        text: item.charAt(0).toUpperCase() + item.slice(1),
        checked: false,
      }));

      const fields: ActionFields = {
        intent: "checklist.create",
        data: {
          title: lower.startsWith("buy") ? "Shopping List" : "Checklist",
          items,
        },
      };

      return {
        id: `check-${Date.now()}`,
        intent: "checklist.create",
        confidence: 0.95,
        input: text,
        fields,
        status: "ready",
        createdAt: Date.now(),
      };
    }
  }

  // 7. EVENT / CALENDAR: "dinner with priya friday 8pm", "meeting with alex tomorrow 2pm"
  const eventMatch = lower.match(
    /^(dinner|lunch|breakfast|coffee|meeting|call|sync)\s+(?:with\s+([a-zA-Z]+)\s+)?(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today)(?:\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?/i
  );

  if (eventMatch) {
    const activity = eventMatch[1].charAt(0).toUpperCase() + eventMatch[1].slice(1);
    const participant = eventMatch[2] ? eventMatch[2].charAt(0).toUpperCase() + eventMatch[2].slice(1) : undefined;
    const day = eventMatch[3].charAt(0).toUpperCase() + eventMatch[3].slice(1);
    let time = eventMatch[4] ? eventMatch[4].toUpperCase() : "8:00 PM";
    if (/^\d{1,2}(?:AM|PM)$/i.test(time)) {
      time = time.replace(/(\d+)(AM|PM)/i, "$1:00 $2");
    }

    const fields: ActionFields = {
      intent: "event.create",
      data: {
        title: activity,
        participant,
        dateStr: day,
        timeStr: time,
        location: participant ? "Downtown" : undefined,
      },
    };

    return {
      id: `event-${Date.now()}`,
      intent: "event.create",
      confidence: 0.92,
      input: text,
      fields,
      status: "ready",
      createdAt: Date.now(),
    };
  }

  // 8. REMINDER: "remind me tomorrow at 8 to call Alex", "remind me at 8 pay rent", "remind me to pay rent tomorrow urgent"
  if (lower.startsWith("remind")) {
    // If the input is incomplete like "remind me at", "remind me to", "remind me", "remind", do NOT trigger card prematurely
    if (!/^remind(?:\s+me)?(?:\s+(?:at|to|in))?$/i.test(lower)) {
      let body = text.replace(/^remind(?:\s+me)?\s*/i, "").trim();
      let isUrgent = false;
      if (/\b(?:urgent|high\s+priority|asap)\b/i.test(body)) {
        isUrgent = true;
        body = body.replace(/\b(?:urgent|high\s+priority|asap)\b/gi, "").trim();
      }

      let whenDate = "Tomorrow";
      let whenTime = "8:00 AM";
      let hasExplicitTime = false;
      let hasExplicitDate = false;

      // Extract time: "at 8", "at 8pm", "at 8:30 am", "8pm", "8 am"
      const timeMatch = body.match(/\bat\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b/i) || body.match(/\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b/i);
      if (timeMatch) {
        hasExplicitTime = true;
        let t = timeMatch[1].toUpperCase();
        if (!/(?:AM|PM)/.test(t)) {
          const h = parseInt(t, 10);
          t = (h >= 7 && h <= 11) ? `${h}:00 AM` : (h === 12 ? "12:00 PM" : (h < 7 ? `${h + 12}:00 PM` : `${h}:00 PM`));
        } else if (!t.includes(":")) {
          t = t.replace(/(AM|PM)/, ":00 $1");
        }
        whenTime = t;
        body = body.replace(timeMatch[0], "").trim();
      }

      // Extract date: "tomorrow", "today", "tonight", "next week", "friday", etc.
      const dateMatch = body.match(/\b(tomorrow|today|tonight|next\s+week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i);
      if (dateMatch) {
        hasExplicitDate = true;
        whenDate = dateMatch[1].charAt(0).toUpperCase() + dateMatch[1].slice(1).toLowerCase();
        body = body.replace(dateMatch[0], "").trim();
      }

      // Clean task title
      let task = body
        .replace(/^(to\s+|at\s+|that\s+)/i, "")
        .replace(/\s+(to\s+|at\s+)$/i, "")
        .trim();

      // If user typed only "remind me at" or prepositions with no task, don't trigger
      if (task.toLowerCase() === "at" || task.toLowerCase() === "to") {
        task = "";
      }

      // Only produce draft if there is an actual task or explicit time
      if (task || hasExplicitTime || hasExplicitDate) {
        if (!task) task = "Pay rent";
        task = task.charAt(0).toUpperCase() + task.slice(1);
        const when = hasExplicitDate && hasExplicitTime
          ? `${whenDate} · ${whenTime}`
          : hasExplicitTime
            ? `Today · ${whenTime}`
            : `${whenDate} · ${whenTime}`;

        const fields: ActionFields = {
          intent: "reminder.create",
          data: {
            title: task,
            when,
            isUrgent,
          },
        };

        return {
          id: `remind-${Date.now()}`,
          intent: "reminder.create",
          confidence: 0.94,
          input: text,
          fields,
          status: "ready",
          createdAt: Date.now(),
        };
      }
    }
  }

  // 9. LIVE BROWSER AGENT: "open youtube and search lo-fi", "browse to wikipedia", "browser: open..."
  if (
    lower.startsWith("browser:") ||
    /(?:open|play|search\s+on)\s+(youtube|spotify|google|wikipedia|amazon|netflix)/i.test(lower) ||
    /^(?:browse|open\s+site|open\s+browser)\b/i.test(lower)
  ) {
    let task = text;
    let targetUrl = "https://youtube.com";
    let pageTitle = "YouTube";

    if (lower.includes("wikipedia")) {
      targetUrl = "https://wikipedia.org";
      pageTitle = "Wikipedia";
    } else if (lower.includes("google")) {
      targetUrl = "https://google.com";
      pageTitle = "Google";
    } else if (lower.includes("spotify")) {
      targetUrl = "https://open.spotify.com";
      pageTitle = "Spotify Web Player";
    }

    const fields: ActionFields = {
      intent: "browser.agent",
      data: {
        task,
        currentUrl: targetUrl,
        pageTitle,
        lastAction: "Opening session in cloud Chromium...",
        statusText: "Ready for live interaction",
        isLive: true,
        canTakeOver: true,
      },
    };

    return {
      id: `browser-${Date.now()}`,
      intent: "browser.agent",
      confidence: 0.95,
      input: text,
      fields,
      status: "ready",
      createdAt: Date.now(),
    };
  }

  // 10. MULTI-STEP PLAN: "remind me at 8, add study task, and give me a 25 min focus timer"
  if (
    (lower.includes("remind") && lower.includes("timer")) ||
    (lower.includes("focus") && lower.includes("task") && lower.includes("remind")) ||
    (lower.split(",").length >= 3 && /(?:task|timer|remind|schedule)/i.test(lower))
  ) {
    const fields: ActionFields = {
      intent: "plan.run",
      data: {
        title: "Multi-Action Plan (3 Tasks)",
        steps: [
          { id: "s1", title: "Set Reminder · 08:00 AM", status: "pending", iconName: "bell" },
          { id: "s2", title: "Task · University assignment", status: "pending", iconName: "check" },
          { id: "s3", title: "Focus Timer · 25 Minutes", status: "pending", iconName: "timer" },
        ],
        allCompleted: false,
      },
    };

    return {
      id: `plan-${Date.now()}`,
      intent: "plan.run",
      confidence: 0.93,
      input: text,
      fields,
      status: "ready",
      createdAt: Date.now(),
    };
  }

  // 11. PDF DOCUMENT GENERATOR: "make a pdf about...", "generate dna worksheet pdf"
  if (/\b(?:pdf|worksheet|document|slides)\b/i.test(lower) && /(?:make|create|generate|export)\b/i.test(lower)) {
    const fields: ActionFields = {
      intent: "pdf.doc",
      data: {
        title: text.replace(/^(make|create|generate)\s+(a\s+)?(pdf\s+)?(about\s+)?/i, "") || "Document Generator",
        outline: [
          "1. Executive Summary & Purpose",
          "2. Core Concepts & Definitions",
          "3. Comprehensive Analysis",
          "4. Practice Questions & Solutions",
        ],
        stage: "generating",
      },
    };

    return {
      id: `pdf-${Date.now()}`,
      intent: "pdf.doc",
      confidence: 0.92,
      input: text,
      fields,
      status: "ready",
      createdAt: Date.now(),
    };
  }

  // 12. IMAGE GENERATION: "generate a red mug", "generate image of a red mug", "draw a cyberpunk city", "create image of..."
  const imageMatch =
    lower.match(/^(?:generate|create|make)\s+(?:an?\s+)?(?:image|picture|art|illustration|artwork|photo|rendering)\s+(?:of\s+)?(.+)$/i) ||
    lower.match(/^draw\s+(?:an?\s+)?(?:image\s+of\s+)?(.+)$/i) ||
    lower.match(/^(?:generate|create)\s+((?:a|an)\s+.+?\b(?:mug|cup|car|cat|dog|city|person|landscape|scene|portrait|room|house|sunset|flower|building|tree|robot|anime|hina|avatar)\b.*)$/i);

  if (imageMatch) {
    const rawPrompt = imageMatch[1].trim();
    if (rawPrompt.length >= 2) {
      const prompt = rawPrompt.charAt(0).toUpperCase() + rawPrompt.slice(1);
      const fields: ActionFields = {
        intent: "image.job",
        data: {
          prompt,
          stage: "generating",
          elapsedSeconds: 0,
        },
      };

      return {
        id: `image-${Date.now()}`,
        intent: "image.job",
        confidence: 0.96,
        input: text,
        fields,
        status: "ready",
        createdAt: Date.now(),
      };
    }
  }

  return null;
}
