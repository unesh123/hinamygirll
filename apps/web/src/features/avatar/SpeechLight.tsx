/**
 * SpeechLight — the "voice shaping light": as Hinaa speaks, her words do not
 * drop like YouTube subtitles. Each phrase forms beside her with a soft glow,
 * the current phrase stays brightest, and finished phrases settle into a calm,
 * readable trail above the transcript. Hidden entirely when there is no
 * streaming speech.
 */
import { useMemo } from "react";
import type { CSSProperties } from "react";
import { splitIntoPhrases } from "./stageModes";

interface SpeechLightProps {
  /** The assistant's currently streaming text. */
  text: string;
  /** True while she is actively speaking (audio + text). */
  active: boolean;
  /** Side of the avatar the light text should form on. */
  side?: "left" | "right";
  /** Warm accent color for the active phrase glow. */
  accent?: string;
}

export function SpeechLight({
  text,
  active,
  side = "right",
  accent = "#8b5cf6",
}: SpeechLightProps) {
  const phrases = useMemo(() => splitIntoPhrases(text), [text]);
  if (!text || phrases.length === 0) return null;

  const activeIndex = phrases.length - 1;

  return (
    <div
      className={`speech-light speech-light-${side}`}
      data-active={active}
      data-testid="speech-light"
      aria-live="polite"
      aria-atomic="false"
    >
      {phrases.map((phrase, index) => {
        const isActive = index === activeIndex;
        return (
          <span
            key={`${index}-${phrase.slice(0, 12)}`}
            className={`speech-phrase${isActive ? " is-active" : " is-settled"}`}
            style={{ "--speech-accent": accent } as CSSProperties}
          >
            {phrase}
          </span>
        );
      })}
    </div>
  );
}
