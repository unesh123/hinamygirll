import { useState, useEffect, useRef, useCallback } from "react";

// Web Speech API interface definitions
interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface IWindowSpeech extends Window {
  SpeechRecognition?: any;
  webkitSpeechRecognition?: any;
}

export interface UseVoiceTypingOptions {
  onTranscript?: (text: string, isFinal: boolean) => void;
  lang?: string;
  continuous?: boolean;
}

export interface VoiceTypingState {
  isListening: boolean;
  isSupported: boolean;
  interimTranscript: string;
  finalTranscript: string;
  error: string | null;
  startListening: (language?: string) => void;
  stopListening: () => void;
  toggleListening: (language?: string) => void;
  resetTranscript: () => void;
}

export function useVoiceTyping(options: UseVoiceTypingOptions = {}): VoiceTypingState {
  const { onTranscript, lang = "en-US", continuous = true } = options;
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const isExplicitlyStopped = useRef(true);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  useEffect(() => {
    if (typeof window === "undefined") return;
    const win = window as IWindowSpeech;
    const SpeechRecognition = win.SpeechRecognition || win.webkitSpeechRecognition;
    setIsSupported(Boolean(SpeechRecognition));
  }, []);

  const stopListening = useCallback(() => {
    isExplicitlyStopped.current = true;
    setIsListening(false);
    setInterimTranscript("");
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignored
      }
    }
  }, []);

  const startListening = useCallback(
    (customLang?: string) => {
      if (typeof window === "undefined") return;
      const win = window as IWindowSpeech;
      const SpeechRecognition = win.SpeechRecognition || win.webkitSpeechRecognition;

      if (!SpeechRecognition) {
        setError("Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
        return;
      }

      setError(null);
      isExplicitlyStopped.current = false;

      // Abort any existing instance
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignored
        }
      }

      try {
        const recognition = new SpeechRecognition();
        recognition.continuous = continuous;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.lang = customLang || lang || "en-US";

        recognition.onstart = () => {
          setIsListening(true);
          setError(null);
        };

        recognition.onresult = (event: SpeechRecognitionEvent) => {
          let currentInterim = "";
          let currentFinal = "";

          for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            const transcript = result[0]?.transcript || "";
            if (result.isFinal) {
              currentFinal += transcript;
            } else {
              currentInterim += transcript;
            }
          }

          if (currentInterim) {
            setInterimTranscript(currentInterim);
            onTranscriptRef.current?.(currentInterim, false);
          }

          if (currentFinal) {
            setFinalTranscript((prev) => (prev ? `${prev} ${currentFinal.trim()}` : currentFinal.trim()));
            setInterimTranscript("");
            onTranscriptRef.current?.(currentFinal.trim(), true);
          }
        };

        recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
          if (event.error === "no-speech") {
            // Non-fatal, keep listening
            return;
          }
          if (event.error === "aborted") {
            return;
          }
          console.warn("[VoiceTyping] recognition error:", event.error);
          setError(`Speech recognition notice: ${event.error}`);
          if (event.error === "not-allowed") {
            setIsListening(false);
            isExplicitlyStopped.current = true;
          }
        };

        recognition.onend = () => {
          // If not explicitly stopped and continuous is desired, restart automatically
          if (!isExplicitlyStopped.current && continuous) {
            try {
              recognition.start();
              return;
            } catch {
              // Failed restart, drop to idle
            }
          }
          setIsListening(false);
          setInterimTranscript("");
        };

        recognitionRef.current = recognition;
        recognition.start();
      } catch (err: any) {
        console.error("[VoiceTyping] start failed:", err);
        setError(err?.message || "Failed to start microphone speech recognition.");
        setIsListening(false);
      }
    },
    [continuous, lang]
  );

  const toggleListening = useCallback(
    (customLang?: string) => {
      if (isListening) {
        stopListening();
      } else {
        startListening(customLang);
      }
    },
    [isListening, startListening, stopListening]
  );

  const resetTranscript = useCallback(() => {
    setFinalTranscript("");
    setInterimTranscript("");
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isExplicitlyStopped.current = true;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignored
        }
      }
    };
  }, []);

  return {
    isListening,
    isSupported,
    interimTranscript,
    finalTranscript,
    error,
    startListening,
    stopListening,
    toggleListening,
    resetTranscript,
  };
}
