import { useCallback, useEffect, useRef, useState } from "react";

interface PlaybackController {
  playing: boolean;
  muted: boolean;
  hasReplay: boolean;
  jawEnergy: number;
  play: (blob: Blob) => Promise<void>;
  replay: () => Promise<void>;
  stop: () => void;
  toggleMute: () => void;
}

export function useAudioPlayback(): PlaybackController {
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [hasReplay, setHasReplay] = useState(false);
  const [jawEnergy, setJawEnergy] = useState(0);
  const audio = useRef<HTMLAudioElement | undefined>(undefined);
  const lastBlob = useRef<Blob | undefined>(undefined);
  const objectUrl = useRef<string | undefined>(undefined);
  const frame = useRef<number | undefined>(undefined);
  const context = useRef<AudioContext | undefined>(undefined);

  const stop = useCallback(() => {
    if (frame.current) cancelAnimationFrame(frame.current);
    frame.current = undefined;
    audio.current?.pause();
    if (audio.current) audio.current.src = "";
    audio.current = undefined;
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = undefined;
    if (context.current?.state !== "closed") void context.current?.close();
    context.current = undefined;
    setJawEnergy(0);
    setPlaying(false);
  }, []);

  const play = useCallback(
    async (blob: Blob) => {
      stop();
      lastBlob.current = blob;
      setHasReplay(true);
      const element = new Audio();
      element.muted = muted;
      objectUrl.current = URL.createObjectURL(blob);
      element.src = objectUrl.current;
      audio.current = element;
      const audioContext = new AudioContext({ latencyHint: "interactive" });
      context.current = audioContext;
      const source = audioContext.createMediaElementSource(element);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyser.connect(audioContext.destination);
      const samples = new Uint8Array(analyser.frequencyBinCount);
      const animate = () => {
        analyser.getByteTimeDomainData(samples);
        let sum = 0;
        for (const value of samples) sum += ((value - 128) / 128) ** 2;
        const rms = Math.sqrt(sum / samples.length);
        setJawEnergy((current) => current * 0.62 + Math.min(1, rms * 5) * 0.38);
        frame.current = requestAnimationFrame(animate);
      };
      element.onended = stop;
      element.onerror = stop;
      await audioContext.resume();
      await element.play();
      setPlaying(true);
      animate();
    },
    [muted, stop],
  );

  const replay = useCallback(async () => {
    if (lastBlob.current) await play(lastBlob.current);
  }, [play]);

  const toggleMute = useCallback(() => {
    setMuted((value) => {
      const next = !value;
      if (audio.current) audio.current.muted = next;
      return next;
    });
  }, []);

  useEffect(() => stop, [stop]);

  return {
    playing,
    muted,
    hasReplay,
    jawEnergy,
    play,
    replay,
    stop,
    toggleMute,
  };
}
