import React, { memo } from "react";

export interface CipherDecoderTextProps {
  text: string;
  className?: string;
  style?: React.CSSProperties;
  color?: string;
  accentColor?: string;
}

/**
 * High-tech cipher text decoder component.
 * Scrambles and cycles through matrix-style glyphs before locking into the target word.
 */
export const CipherDecoderText: React.FC<CipherDecoderTextProps> = memo(({
  text,
  className = "",
  style,
  color = "currentColor",
  accentColor = "#FF4FD8",
}) => {
  const [displayText, setDisplayText] = React.useState(text);
  const [isDecoding, setIsDecoding] = React.useState(true);

  React.useEffect(() => {
    setIsDecoding(true);
    const chars = "▓░▒#$*&%☰£€0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    let iteration = 0;
    const maxIterations = Math.max(text.length * 2, 10);

    const interval = window.setInterval(() => {
      setDisplayText(() => {
        return text
          .split("")
          .map((char, index) => {
            if (char === " ") return " ";
            if (index < iteration / 2) {
              return text[index];
            }
            return chars[Math.floor(Math.random() * chars.length)];
          })
          .join("");
      });

      iteration += 1;
      if (iteration >= maxIterations) {
        setDisplayText(text);
        setIsDecoding(false);
        window.clearInterval(interval);
      }
    }, 45);

    return () => window.clearInterval(interval);
  }, [text]);

  return (
    <span
      className={`cipher-decoder-text ${className}`}
      style={{
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        letterSpacing: "0.06em",
        color: isDecoding ? accentColor : color,
        transition: "color 0.2s ease",
        ...style,
      }}
    >
      {displayText}
    </span>
  );
});

export interface GyroOrbLoaderProps {
  size?: number;
  color?: string;
  rate?: number;
  className?: string;
}

/**
 * 3D multi-tilt orbital gyroscopic ring spinner with counter-rotating beads and core.
 */
export const GyroOrbLoader: React.FC<GyroOrbLoaderProps> = memo(({
  size = 54,
  color = "#dc5f8b",
  rate = 1,
  className = "",
}) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={`hina-gyro-orb ${className}`}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      fill="none"
      role="img"
      aria-label="Processing neural synapses"
      style={
        {
          color,
          "--rate": rate,
          display: "inline-block",
          verticalAlign: "middle",
        } as React.CSSProperties
      }
    >
      <g
        className="orb-plane"
        style={
          {
            "--tilt": "-26deg",
            "--k": 0.3,
            "--inv": 3.3333,
            "--dur": "2.6s",
            "--dir": 1,
            "--rest": "34deg",
          } as React.CSSProperties
        }
      >
        <circle className="orb-track" cx="32" cy="32" r="20" />
        <g className="orb-arm">
          <circle className="orb-bead" cx="52" cy="32" r="2.5" />
        </g>
      </g>
      <g
        className="orb-plane"
        style={
          {
            "--tilt": "34deg",
            "--k": 0.38,
            "--inv": 2.6316,
            "--dur": "3.4s",
            "--dir": -1,
            "--rest": "158deg",
          } as React.CSSProperties
        }
      >
        <circle className="orb-track" cx="32" cy="32" r="16" />
        <g className="orb-arm">
          <circle className="orb-bead" cx="48" cy="32" r="2.5" />
        </g>
      </g>
      <g
        className="orb-plane"
        style={
          {
            "--tilt": "86deg",
            "--k": 0.26,
            "--inv": 3.8462,
            "--dur": "4.2s",
            "--dir": 1,
            "--rest": "262deg",
          } as React.CSSProperties
        }
      >
        <circle className="orb-track" cx="32" cy="32" r="22" />
        <g className="orb-arm">
          <circle className="orb-bead" cx="54" cy="32" r="2.5" />
        </g>
      </g>
      <circle className="orb-core" cx="32" cy="32" r="2" />
    </svg>
  );
});

export interface InfinityPathLoaderProps {
  size?: number;
  color?: string;
  rate?: number;
  className?: string;
}

/**
 * Continuous SVG path tracer (lemniscate/infinity loop) with head, mid, and tail animated strokes.
 */
export const InfinityPathLoader: React.FC<InfinityPathLoaderProps> = memo(({
  size = 54,
  color = "#5433eb",
  rate = 1,
  className = "",
}) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={`hina-infinity-lis ${className}`}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      fill="none"
      role="img"
      aria-label="Traversing cognitive weave"
      style={
        {
          color,
          "--rate": rate,
          display: "inline-block",
          verticalAlign: "middle",
        } as React.CSSProperties
      }
    >
      <g className="lis-rig">
        <path
          className="lis-track"
          d="M55.00,32.00L54.94,33.11L54.76,34.22L54.46,35.32L54.04,36.42L53.51,37.50L52.86,38.58L52.10,39.63L51.24,40.67L50.28,41.69L49.22,42.69L48.07,43.66L46.83,44.60L45.52,45.52L44.14,46.40L42.69,47.25L41.19,48.07L39.63,48.84L38.04,49.58L36.42,50.28L34.77,50.93L33.11,51.54L31.44,52.10L29.78,52.62L28.13,53.09L26.50,53.51L24.89,53.87L23.33,54.19L21.81,54.46L20.34,54.67L18.93,54.83L17.60,54.94L16.34,54.99L15.16,54.99L14.07,54.94L13.07,54.83L12.17,54.67L11.38,54.46L10.70,54.19L10.13,53.87L9.67,53.51L9.33,53.09L9.11,52.62L9.01,52.10L9.03,51.54L9.17,50.93L9.43,50.28L9.81,49.58L10.30,48.84L10.91,48.07L11.63,47.25L12.46,46.40L13.39,45.52L14.42,44.60L15.54,43.66L16.75,42.69L18.04,41.69L19.40,40.67L20.82,39.63L22.31,38.58L23.84,37.50L25.42,36.42L27.04,35.32L28.68,34.22L30.33,33.11L32.00,32.00L33.67,30.89L35.32,29.78L36.96,28.68L38.58,27.58L40.16,26.50L41.69,25.42L43.18,24.37L44.60,23.33L45.96,22.31L47.25,21.31L48.46,20.34L49.58,19.40L50.61,18.48L51.54,17.60L52.37,16.75L53.09,15.93L53.70,15.16L54.19,14.42L54.57,13.72L54.83,13.07L54.97,12.46L54.99,11.90L54.89,11.38L54.67,10.91L54.33,10.49L53.87,10.13L53.30,9.81L52.62,9.54L51.83,9.33L50.93,9.17L49.93,9.06L48.84,9.01L47.66,9.01L46.40,9.06L45.07,9.17L43.66,9.33L42.19,9.54L40.67,9.81L39.11,10.13L37.50,10.49L35.87,10.91L34.22,11.38L32.56,11.90L30.89,12.46L29.23,13.07L27.58,13.72L25.96,14.42L24.37,15.16L22.81,15.93L21.31,16.75L19.86,17.60L18.48,18.48L17.17,19.40L15.93,20.34L14.78,21.31L13.72,22.31L12.76,23.33L11.90,24.37L11.14,25.42L10.49,26.50L9.96,27.58L9.54,28.68L9.24,29.78L9.06,30.89L9.00,32.00Z"
        />
        <path
          className="lis-tail"
          d="M55.00,32.00L54.94,33.11L54.76,34.22L54.46,35.32L54.04,36.42L53.51,37.50L52.86,38.58L52.10,39.63L51.24,40.67L50.28,41.69L49.22,42.69L48.07,43.66L46.83,44.60L45.52,45.52L44.14,46.40L42.69,47.25L41.19,48.07L39.63,48.84L38.04,49.58L36.42,50.28L34.77,50.93L33.11,51.54L31.44,52.10L29.78,52.62L28.13,53.09L26.50,53.51L24.89,53.87L23.33,54.19L21.81,54.46L20.34,54.67L18.93,54.83L17.60,54.94L16.34,54.99L15.16,54.99L14.07,54.94L13.07,54.83L12.17,54.67L11.38,54.46L10.70,54.19L10.13,53.87L9.67,53.51L9.33,53.09L9.11,52.62L9.01,52.10L9.03,51.54L9.17,50.93L9.43,50.28L9.81,49.58L10.30,48.84L10.91,48.07L11.63,47.25L12.46,46.40L13.39,45.52L14.42,44.60L15.54,43.66L16.75,42.69L18.04,41.69L19.40,40.67L20.82,39.63L22.31,38.58L23.84,37.50L25.42,36.42L27.04,35.32L28.68,34.22L30.33,33.11L32.00,32.00Z"
          pathLength="100"
        />
        <path
          className="lis-mid"
          d="M55.00,32.00L54.94,33.11L54.76,34.22L54.46,35.32L54.04,36.42L53.51,37.50L52.86,38.58L52.10,39.63L51.24,40.67L50.28,41.69L49.22,42.69L48.07,43.66L46.83,44.60L45.52,45.52L44.14,46.40L42.69,47.25L41.19,48.07L39.63,48.84L38.04,49.58L36.42,50.28L34.77,50.93L33.11,51.54L31.44,52.10L29.78,52.62L28.13,53.09L26.50,53.51L24.89,53.87L23.33,54.19L21.81,54.46L20.34,54.67L18.93,54.83L17.60,54.94L16.34,54.99L15.16,54.99L14.07,54.94L13.07,54.83L12.17,54.67L11.38,54.46L10.70,54.19L10.13,53.87L9.67,53.51L9.33,53.09L9.11,52.62L9.01,52.10L9.03,51.54L9.17,50.93L9.43,50.28L9.81,49.58L10.30,48.84L10.91,48.07L11.63,47.25L12.46,46.40L13.39,45.52L14.42,44.60L15.54,43.66L16.75,42.69L18.04,41.69L19.40,40.67L20.82,39.63L22.31,38.58L23.84,37.50L25.42,36.42L27.04,35.32L28.68,34.22L30.33,33.11L32.00,32.00Z"
          pathLength="100"
        />
        <path
          className="lis-head"
          d="M55.00,32.00L54.94,33.11L54.76,34.22L54.46,35.32L54.04,36.42L53.51,37.50L52.86,38.58L52.10,39.63L51.24,40.67L50.28,41.69L49.22,42.69L48.07,43.66L46.83,44.60L45.52,45.52L44.14,46.40L42.69,47.25L41.19,48.07L39.63,48.84L38.04,49.58L36.42,50.28L34.77,50.93L33.11,51.54L31.44,52.10L29.78,52.62L28.13,53.09L26.50,53.51L24.89,53.87L23.33,54.19L21.81,54.46L20.34,54.67L18.93,54.83L17.60,54.94L16.34,54.99L15.16,54.99L14.07,54.94L13.07,54.83L12.17,54.67L11.38,54.46L10.70,54.19L10.13,53.87L9.67,53.51L9.33,53.09L9.11,52.62L9.01,52.10L9.03,51.54L9.17,50.93L9.43,50.28L9.81,49.58L10.30,48.84L10.91,48.07L11.63,47.25L12.46,46.40L13.39,45.52L14.42,44.60L15.54,43.66L16.75,42.69L18.04,41.69L19.40,40.67L20.82,39.63L22.31,38.58L23.84,37.50L25.42,36.42L27.04,35.32L28.68,34.22L30.33,33.11L32.00,32.00Z"
          pathLength="100"
        />
      </g>
    </svg>
  );
});
