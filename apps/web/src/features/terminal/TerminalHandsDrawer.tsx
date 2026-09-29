import React, { useState, useEffect, useRef } from "react";
import {
  Terminal,
  Play,
  X,
  Maximize2,
  Minimize2,
  Trash2,
  Copy,
  Check,
  Shield,
  Clock,
  Sparkles,
  GitBranch,
} from "lucide-react";

interface TerminalExecutionResult {
  status: "success" | "error" | "rejected";
  command: string;
  exitCode?: number;
  stdout?: string;
  stderr?: string;
  error?: string;
  summary?: string;
  timestamp: string;
}

interface TerminalHandsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  initialCommand?: string;
}

export function TerminalHandsDrawer({ isOpen, onClose, initialCommand }: TerminalHandsDrawerProps) {
  const [command, setCommand] = useState(initialCommand || "");
  const [isExecuting, setIsExecuting] = useState(false);
  const [history, setHistory] = useState<TerminalExecutionResult[]>([]);
  const [isMaximized, setIsMaximized] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialCommand) {
      setCommand(initialCommand);
    }
  }, [initialCommand]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history]);

  const executeCommand = async (cmdToRun: string) => {
    const trimmed = cmdToRun.trim();
    if (!trimmed || isExecuting) return;

    setIsExecuting(true);
    const startTs = new Date().toLocaleTimeString();

    try {
      const response = await fetch("/v1/terminal/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: trimmed }),
      });
      const data = await response.json();
      setHistory((prev) => [
        ...prev,
        {
          ...data,
          command: trimmed,
          timestamp: startTs,
        },
      ]);
      setCommand("");
    } catch (err: any) {
      setHistory((prev) => [
        ...prev,
        {
          status: "error",
          command: trimmed,
          error: err?.message || "Network execution error",
          timestamp: startTs,
        },
      ]);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeCommand(command);
  };

  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 1500);
  };

  const quickPills = [
    { label: "git status", cmd: "git status --short" },
    { label: "git branch", cmd: "git branch --show-current" },
    { label: "recent commits", cmd: "git log -n 5 --oneline" },
    { label: "python version", cmd: "python --version" },
    { label: "test suite", cmd: "pytest --version" },
  ];

  if (!isOpen) return null;

  return (
    <aside
      role="region"
      aria-label="Computer Hands Terminal Execution Environment"
      data-testid="terminal-hands-drawer"
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: isMaximized ? "85vh" : "420px",
        background: "#09090b",
        borderTop: "1px solid rgba(255,255,255,0.12)",
        boxShadow: "0 -8px 32px rgba(0,0,0,0.6)",
        zIndex: 1200,
        display: "flex",
        flexDirection: "column",
        fontFamily: "'JetBrains Mono', 'Fira Code', Menlo, monospace",
        color: "#f4f4f5",
        transition: "height 200ms ease",
      }}
    >
      {/* ── Terminal Header ─────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 16px",
          background: "#121215",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 22,
              height: 22,
              borderRadius: 5,
              background: "linear-gradient(135deg, #10b981, #06b6d4)",
              color: "#000",
            }}
          >
            <Terminal size={14} />
          </div>
          <span style={{ fontSize: "13px", fontWeight: 700, letterSpacing: "-0.01em" }}>
            HINAA Terminal & Computer Hands
          </span>
          <span
            style={{
              fontSize: "10px",
              padding: "1px 6px",
              borderRadius: 4,
              background: "rgba(16, 185, 129, 0.15)",
              color: "#34d399",
              border: "1px solid rgba(16, 185, 129, 0.3)",
            }}
          >
            SANDBOXED
          </span>
        </div>

        {/* Quick Action Pills */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {quickPills.map((pill) => (
            <button
              key={pill.label}
              onClick={() => executeCommand(pill.cmd)}
              disabled={isExecuting}
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#a1a1aa",
                padding: "3px 8px",
                borderRadius: 4,
                fontSize: "11px",
                cursor: "pointer",
                transition: "all 120ms ease",
              }}
            >
              {pill.label}
            </button>
          ))}

          <div style={{ width: 1, height: 16, background: "rgba(255,255,255,0.1)", margin: "0 4px" }} />

          <button
            onClick={() => setHistory([])}
            title="Clear Terminal"
            style={{
              background: "transparent",
              border: "none",
              color: "#71717a",
              cursor: "pointer",
              padding: 4,
            }}
          >
            <Trash2 size={14} />
          </button>
          <button
            onClick={() => setIsMaximized(!isMaximized)}
            title={isMaximized ? "Restore" : "Maximize"}
            style={{
              background: "transparent",
              border: "none",
              color: "#71717a",
              cursor: "pointer",
              padding: 4,
            }}
          >
            {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          <button
            onClick={onClose}
            title="Close Terminal"
            style={{
              background: "transparent",
              border: "none",
              color: "#71717a",
              cursor: "pointer",
              padding: 4,
            }}
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* ── Terminal Output History ──────────────────────────── */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          fontSize: "12px",
          lineHeight: "1.6",
        }}
      >
        {history.length === 0 && (
          <div style={{ color: "#71717a", padding: "16px 0", fontSize: "12px" }}>
            <p style={{ margin: "0 0 6px 0" }}>⚡ <strong>Computer Hands Ready.</strong> Execute sandboxed workspace commands, git operations, or python scripts.</p>
            <p style={{ margin: 0 }}>Type a command below or click a quick action above.</p>
          </div>
        )}

        {history.map((item, idx) => (
          <div
            key={idx}
            style={{
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 6,
              padding: "10px 12px",
            }}
          >
            {/* Command Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ color: "#10b981", fontWeight: 700 }}>$</span>
                <span style={{ color: "#f4f4f5", fontWeight: 600 }}>{item.command}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    fontSize: "10px",
                    padding: "1px 6px",
                    borderRadius: 3,
                    background: item.status === "success" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
                    color: item.status === "success" ? "#34d399" : "#f87171",
                    fontWeight: 600,
                  }}
                >
                  {item.status.toUpperCase()} {item.exitCode !== undefined ? `(code ${item.exitCode})` : ""}
                </span>
                <span style={{ fontSize: "10px", color: "#52525b" }}>{item.timestamp}</span>
                <button
                  onClick={() => copyToClipboard(item.stdout || item.error || "", idx)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: copiedIndex === idx ? "#10b981" : "#71717a",
                    cursor: "pointer",
                    padding: 2,
                  }}
                >
                  {copiedIndex === idx ? <Check size={12} /> : <Copy size={12} />}
                </button>
              </div>
            </div>

            {/* Output */}
            {item.stdout && (
              <pre
                style={{
                  margin: 0,
                  color: "#d4d4d8",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontFamily: "inherit",
                }}
              >
                {item.stdout}
              </pre>
            )}
            {item.stderr && (
              <pre
                style={{
                  margin: "4px 0 0 0",
                  color: "#f87171",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontFamily: "inherit",
                }}
              >
                {item.stderr}
              </pre>
            )}
            {item.error && (
              <div style={{ color: "#f87171", marginTop: 4 }}>
                ⚠️ {item.error}
              </div>
            )}
          </div>
        ))}
        {isExecuting && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#10b981" }}>
            <span style={{ animation: "spin 1s linear infinite" }}>⚡</span>
            <span>Executing command in project root…</span>
          </div>
        )}
        <div ref={terminalEndRef} />
      </div>

      {/* ── Command Input ───────────────────────────────────── */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 16px",
          background: "#121215",
          borderTop: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <span style={{ color: "#10b981", fontWeight: 700 }}>$</span>
        <input
          ref={inputRef}
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="Enter command (e.g. git status, python test.py, cargo check)..."
          disabled={isExecuting}
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "#f4f4f5",
            fontSize: "12px",
            fontFamily: "inherit",
          }}
        />
        <button
          type="submit"
          disabled={!command.trim() || isExecuting}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            background: "rgba(16,185,129,0.2)",
            border: "1px solid rgba(16,185,129,0.4)",
            color: "#34d399",
            padding: "4px 10px",
            borderRadius: 4,
            fontSize: "11px",
            fontWeight: 600,
            cursor: !command.trim() || isExecuting ? "not-allowed" : "pointer",
          }}
        >
          <Play size={11} />
          Execute
        </button>
      </form>
    </aside>
  );
}
