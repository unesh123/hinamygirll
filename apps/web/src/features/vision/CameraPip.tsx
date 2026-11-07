import { useEffect, useRef } from "react";

interface CameraPipProps {
  stream: MediaStream | null;
  onStop?: () => void;
}

export function CameraPip({ stream, onStop }: CameraPipProps) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = stream;
  }, [stream]);
  if (!stream) return null;
  return (
    <div className="camera-pip" role="status" aria-label="Camera is on" style={{ position: "relative", width: 120 }}>
      <video ref={ref} autoPlay muted playsInline style={{ width: "100%", borderRadius: 8, transform: "scaleX(-1)" }} />
      <span style={{ position: "absolute", top: 4, left: 4, fontSize: 11, color: "#fff", background: "#d32f2f", borderRadius: 4, padding: "0 4px" }}>
        ● Camera on
      </span>
      {onStop ? (
        <button type="button" onClick={onStop} aria-label="Turn camera off">
          Stop
        </button>
      ) : null}
    </div>
  );
}
