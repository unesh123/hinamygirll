import React, { useState, useEffect, useCallback } from "react";
import {
  GitBranch,
  Mail,
  Calendar,
  Share2,
  Music,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Send,
  Terminal,
  ExternalLink,
  Clock,
  ChevronRight,
  Sparkles,
} from "lucide-react";

const API_BASE = String(import.meta.env.VITE_HINAA_API_BASE_URL || "").replace(/\/+$/, "");

async function bridgeRequest(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}/api/v1/integrations/${path}`, { ...init, signal: AbortSignal.timeout(20000) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.detail || data.error?.message || `Request failed (${response.status})`);
  if (["failed", "error", "unavailable", "rejected"].includes(data.status)) throw new Error(data.message || data.error || "The integration could not complete this action.");
  return data;
}

export interface SaaSIntegration {
  service: "github" | "outlook" | "google_calendar" | "notion" | "spotify";
  status: "connected" | "disconnected" | "error" | "rate_limited";
  account_identifier?: string | null;
  status_text?: string;
  last_sync_time?: string | null;
  features_supported: string[];
  metadata?: Record<string, any>;
}

export interface AgendaEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
  organizer?: string;
}

interface SaaSBridgePanelProps {
  onOpenTerminal?: (initialCommand?: string) => void;
}

export function SaaSBridgePanel({ onOpenTerminal }: SaaSBridgePanelProps) {
  const [integrations, setIntegrations] = useState<SaaSIntegration[]>([]);
  const [agenda, setAgenda] = useState<AgendaEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // GitHub Quick Action
  const [gitActionLoading, setGitActionLoading] = useState(false);
  const [gitOutput, setGitOutput] = useState<string | null>(null);
  const [mcpStatus, setMCPStatus] = useState("");
  const [mcpLoading, setMCPLoading] = useState(false);
  const verifyMCP = async () => {
    setMCPLoading(true);
    try { const result = await bridgeRequest("github/mcp"); setMCPStatus(`GitHub MCP verified: ${result.tools.length} read-only tools discovered.`); }
    catch (error) {setMCPStatus(error instanceof Error ? error.message : "GitHub MCP connection failed");}
    finally {setMCPLoading(false);}
  };

  // Outlook Quick Draft
  const [emailDraft, setEmailDraft] = useState({
    recipient: "",
    subject: "",
    body: "",
  });
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const [emailStatus, setEmailStatus] = useState<string | null>(null);
  const [inbox, setInbox] = useState<Array<{id: string; subject: string; bodyPreview: string}>>([]);
  const [inboxLoading, setInboxLoading] = useState(false);
  const readInbox = async () => {
    setInboxLoading(true);
    setEmailStatus(null);
    try {
      const data = await bridgeRequest("outlook/inbox?limit=10");
      setInbox(data.messages || []);
      if (!(data.messages || []).length) setEmailStatus("Your Outlook inbox has no messages.");
    } catch (error) {
      setInbox([]);
      setEmailStatus(error instanceof Error ? error.message : "Could not read Outlook.");
    } finally { setInboxLoading(false); }
  };

  const fetchIntegrations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await bridgeRequest("status");
      setIntegrations((data.integrations || []).map((item: {service_id: string; connected: boolean; status_text: string; capabilities: string[]}) => ({
        service: item.service_id === "spotify_media" ? "spotify" : item.service_id,
        status: item.connected ? "connected" : "disconnected", status_text: item.status_text,
        features_supported: item.capabilities || [],
      })));
    } catch (err: any) {
      setError(err?.message || "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAgenda = useCallback(async () => {
    try {
      const data = await bridgeRequest("agenda");
      setAgenda(data.agenda || []);
    } catch {
      // Agenda load is non-critical
    }
  }, []);

  useEffect(() => {
    fetchIntegrations();
    fetchAgenda();
  }, [fetchIntegrations, fetchAgenda]);

  const handleGitHubAction = async (action: string) => {
    setGitActionLoading(true);
    setGitOutput(null);
    try {
      const data = await bridgeRequest("github/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      setGitOutput(data.output || JSON.stringify(data, null, 2));
    } catch (err: any) {
      setGitOutput(`Error executing GitHub action: ${err.message}`);
    } finally {
      setGitActionLoading(false);
    }
  };

  const handleSendEmail = async (sendNow: boolean = false) => {
    setIsSendingEmail(true);
    setEmailStatus(null);
    try {
      const data = await bridgeRequest("email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...emailDraft, send_now: sendNow }),
      });
      setEmailStatus(data.message || (sendNow ? "Sending request accepted; delivery is unverified." : "Draft prepared for review."));
    } catch (err: any) {
      setEmailStatus(`Failed: ${err.message}`);
    } finally {
      setIsSendingEmail(false);
    }
  };

  const getServiceIcon = (service: string) => {
    switch (service) {
      case "github":
        return <GitBranch size={16} color="#ffffff" />;
      case "outlook":
        return <Mail size={16} color="#38bdf8" />;
      case "google_calendar":
        return <Calendar size={16} color="#34d399" />;
      case "notion":
        return <Share2 size={16} color="#fbbf24" />;
      case "spotify":
        return <Music size={16} color="#4ade80" />;
      default:
        return <Sparkles size={16} color="#a1a1aa" />;
    }
  };

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: 24,
        display: "flex",
        flexDirection: "column",
        gap: 24,
        color: "var(--text-primary, #ffffff)",
      }}
    >
      {/* ── Top Bar ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                backgroundColor: "rgba(235, 111, 146, 0.15)",
                color: "#f472b6",
                padding: "2px 8px",
                borderRadius: 4,
              }}
            >
              Pillar 5
            </span>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
              Enterprise SaaS Bridges & External Nodes
            </h2>
          </div>
          <p style={{ margin: "4px 0 0 0", fontSize: 13, color: "var(--text-secondary, #a1a1aa)" }}>
            Live enterprise connectors for code repository control, institutional Office 365, timetable sync, and media streaming.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            fetchIntegrations();
            fetchAgenda();
          }}
          disabled={loading}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            backgroundColor: "rgba(255, 255, 255, 0.08)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            padding: "6px 12px",
            borderRadius: 6,
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
          Refresh Status
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: 12,
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: 8,
            color: "#f87171",
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* ── Integrations Grid ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 300px), 1fr))",
          gap: 16,
        }}
      >
        {integrations.map((item) => {
          const isConnected = item.status === "connected";
          return (
            <div
              key={item.service}
              style={{
                backgroundColor: "var(--bg-surface-raised, rgba(255, 255, 255, 0.04))",
                border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                borderRadius: 10,
                padding: 18,
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: 14,
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        backgroundColor: "rgba(255, 255, 255, 0.08)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {getServiceIcon(item.service)}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14, textTransform: "capitalize" }}>
                        {item.service.replace(/_/g, " ")}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary, #71717a)" }}>
                        {item.status_text || "Connection status unavailable"}
                      </div>
                    </div>
                  </div>

                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      fontSize: 10,
                      fontWeight: 700,
                      padding: "2px 8px",
                      borderRadius: 999,
                      backgroundColor: isConnected ? "rgba(34, 197, 94, 0.15)" : "rgba(113, 113, 122, 0.15)",
                      color: isConnected ? "#4ade80" : "#a1a1aa",
                    }}
                  >
                    <span
                      style={{
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        backgroundColor: isConnected ? "#4ade80" : "#a1a1aa",
                      }}
                    />
                    {isConnected ? "Configured" : "Disconnected"}
                  </span>
                </div>

                {/* Features */}
                <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 8 }}>
                  {item.features_supported.map((feat) => (
                    <span
                      key={feat}
                      style={{
                        fontSize: 10,
                        backgroundColor: "rgba(255, 255, 255, 0.06)",
                        padding: "2px 6px",
                        borderRadius: 4,
                        color: "var(--text-secondary, #d4d4d8)",
                      }}
                    >
                      {feat}
                    </span>
                  ))}
                </div>
              </div>

              {/* Service-Specific Micro Actions */}
              <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: 10, display: "flex", gap: 8 }}>
                {item.service === "github" && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleGitHubAction("status")}
                      disabled={gitActionLoading}
                      style={{
                        fontSize: 11,
                        padding: "4px 8px",
                        borderRadius: 4,
                        backgroundColor: "rgba(255, 255, 255, 0.08)",
                        border: "none",
                        color: "#ffffff",
                        cursor: "pointer",
                      }}
                    >
                      Git Status
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGitHubAction("branch")}
                      disabled={gitActionLoading}
                      style={{
                        fontSize: 11,
                        padding: "4px 8px",
                        borderRadius: 4,
                        backgroundColor: "rgba(255, 255, 255, 0.08)",
                        border: "none",
                        color: "#ffffff",
                        cursor: "pointer",
                      }}
                    >
                      Branch
                    </button>
                    {onOpenTerminal && (
                      <button
                        type="button"
                        onClick={() => onOpenTerminal("git log -n 5 --oneline")}
                        style={{
                          fontSize: 11,
                          padding: "4px 8px",
                          borderRadius: 4,
                          backgroundColor: "rgba(235, 111, 146, 0.15)",
                          border: "none",
                          color: "#f472b6",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <Terminal size={11} />
                        Terminal
                      </button>
                    )}
                  </>
                )}

                {item.service === "outlook" && (
                  <span style={{ fontSize: 11, color: "var(--text-tertiary, #71717a)" }}>
                    Ready to dispatch drafts below
                  </span>
                )}

                {item.service === "google_calendar" && (
                  <span style={{ fontSize: 11, color: "var(--text-tertiary, #71717a)" }}>
                    {agenda.length} timetable events synced
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── GitHub Action Output Window (if triggered) ── */}
      {gitOutput && (
        <div
          style={{
            backgroundColor: "#09090b",
            borderRadius: 8,
            border: "1px solid rgba(255, 255, 255, 0.1)",
            padding: 14,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 12, color: "#a1a1aa" }}>
            <span>GitHub Action Response:</span>
            <button
              type="button"
              onClick={() => setGitOutput(null)}
              style={{ background: "transparent", border: "none", color: "#71717a", cursor: "pointer", fontSize: 11 }}
            >
              Clear
            </button>
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: 12,
              fontFamily: "monospace",
              color: "#38bdf8",
              whiteSpace: "pre-wrap",
            }}
          >
            {gitOutput}
          </pre>
        </div>
      )}

      <section aria-label="GitHub MCP">
        <button type="button" disabled={mcpLoading} onClick={verifyMCP}>{mcpLoading ? "Connecting GitHub MCP…" : "Verify GitHub MCP"}</button>
        {mcpStatus && <p role="status">{mcpStatus}</p>}
      </section>
      <section aria-label="Outlook inbox" style={{minWidth: 0}}>
        <button type="button" onClick={readInbox} disabled={inboxLoading}>
          {inboxLoading ? "Reading Outlook…" : "Read Outlook inbox"}
        </button>
        {inbox.map(message => <article key={message.id} style={{padding: 12, overflowWrap: "anywhere"}}>
          <strong>{message.subject || "(No subject)"}</strong>
          <p>{message.bodyPreview}</p>
        </article>)}
      </section>

      {/* ── Two-Column Operational Row: Calendar Agenda & Outlook Quick Sender ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 20 }}>
        {/* Google Calendar Timetable */}
        <div
          style={{
            backgroundColor: "var(--bg-surface-raised, rgba(255, 255, 255, 0.04))",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
            borderRadius: 10,
            padding: 20,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <Calendar size={18} color="#34d399" />
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Daily Engineering & Academic Agenda</h3>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {agenda.length === 0 && <p>No calendar events are connected yet.</p>}
            {agenda.map((ev) => (
              <div
                key={ev.id}
                style={{
                  padding: "10px 14px",
                  borderRadius: 8,
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#ffffff" }}>{ev.title}</div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary, #71717a)" }}>{ev.location}</div>
                </div>
                <div
                  style={{
                    fontSize: 11,
                    backgroundColor: "rgba(52, 211, 153, 0.15)",
                    color: "#34d399",
                    padding: "3px 8px",
                    borderRadius: 4,
                    fontWeight: 600,
                  }}
                >
                  {ev.start_time} - {ev.end_time}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Outlook Email Dispatcher */}
        <div
          style={{
            backgroundColor: "var(--bg-surface-raised, rgba(255, 255, 255, 0.04))",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
            borderRadius: 10,
            padding: 20,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <Mail size={18} color="#38bdf8" />
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Outlook Office 365 Dispatcher</h3>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: "#a1a1aa", display: "block", marginBottom: 3 }}>Recipient</label>
              <input
                type="text"
                value={emailDraft.recipient}
                onChange={(e) => setEmailDraft({ ...emailDraft, recipient: e.target.value })}
                style={{
                  width: "100%",
                  padding: "7px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  backgroundColor: "rgba(0, 0, 0, 0.2)",
                  color: "#ffffff",
                  fontSize: 12,
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#a1a1aa", display: "block", marginBottom: 3 }}>Subject</label>
              <input
                type="text"
                value={emailDraft.subject}
                onChange={(e) => setEmailDraft({ ...emailDraft, subject: e.target.value })}
                style={{
                  width: "100%",
                  padding: "7px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  backgroundColor: "rgba(0, 0, 0, 0.2)",
                  color: "#ffffff",
                  fontSize: 12,
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#a1a1aa", display: "block", marginBottom: 3 }}>Body</label>
              <textarea
                rows={3}
                value={emailDraft.body}
                onChange={(e) => setEmailDraft({ ...emailDraft, body: e.target.value })}
                style={{
                  width: "100%",
                  padding: "7px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  backgroundColor: "rgba(0, 0, 0, 0.2)",
                  color: "#ffffff",
                  fontSize: 12,
                  boxSizing: "border-box",
                  resize: "vertical",
                }}
              />
            </div>

            {emailStatus && (
              <div
                style={{
                  fontSize: 12,
                  color: emailStatus.startsWith("Failed") ? "#f87171" : "#4ade80",
                  padding: "4px 8px",
                  borderRadius: 4,
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                }}
              >
                {emailStatus}
              </div>
            )}

            <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
              <button
                type="button"
                onClick={() => handleSendEmail(false)}
                disabled={isSendingEmail || !emailDraft.recipient.trim() || !emailDraft.subject.trim() || !emailDraft.body.trim()}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: 6,
                  backgroundColor: "rgba(255, 255, 255, 0.1)",
                  border: "none",
                  color: "#ffffff",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Save Draft
              </button>
              <button
                type="button"
                onClick={() => handleSendEmail(true)}
                disabled={isSendingEmail || !emailDraft.recipient.trim() || !emailDraft.subject.trim() || !emailDraft.body.trim()}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: 6,
                  backgroundColor: "#0284c7",
                  border: "none",
                  color: "#ffffff",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                }}
              >
                <Send size={12} />
                Send Email
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
