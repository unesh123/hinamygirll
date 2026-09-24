import { useCallback, useEffect, useRef, useState } from "react";
import { Radio } from "lucide-react";

export function PushToTalkButton({ onStart, onStop }: { onStart: () => void; onStop: () => void }) {
  const held = useRef(false);
  const stopRef = useRef(onStop);
  stopRef.current = onStop;
  const [pressed, setPressed] = useState(false);
  const release = useCallback(() => {
    if (!held.current) return;
    held.current = false;
    setPressed(false);
    stopRef.current();
  }, []);
  const press = () => {
    if (held.current) return;
    held.current = true;
    setPressed(true);
    onStart();
  };
  useEffect(() => {
    window.addEventListener("blur", release);
    return () => {
      window.removeEventListener("blur", release);
      if (held.current) stopRef.current();
    };
  }, [release]);
  return <button type="button" aria-label="Hold to speak" aria-pressed={pressed}
    onPointerDown={(event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.currentTarget.focus();
      event.currentTarget.setPointerCapture?.(event.pointerId);
      press();
    }}
    onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release} onBlur={release}
    onKeyDown={(event) => {
      if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        if (!event.repeat) press();
      }
    }}
    onKeyUp={(event) => {
      if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        release();
      }
    }}
    style={{ display: "flex", alignItems: "center", gap: 6, minHeight: 44, padding: "8px 14px", borderRadius: "var(--radius-pill)", border: "1px solid var(--accent)", background: pressed ? "var(--accent)" : "var(--accent-pale)", color: pressed ? "var(--bg-primary)" : "var(--accent)", cursor: "pointer", touchAction: "none", userSelect: "none" }}>
    <Radio size={16} aria-hidden="true" />{pressed ? "Listening…" : "Hold to speak"}
  </button>;
}
