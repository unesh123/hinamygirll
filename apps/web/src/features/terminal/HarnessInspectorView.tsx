import React, { useState, useEffect } from "react";
import {
  GitBranch,
  Shield,
  Layers,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Play,
  RefreshCw,
  FolderTree,
  Terminal,
  FileCode,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { hinaaIdentityHeaders } from "../../lib/hinaaIdentity";

export function HarnessInspectorView() {
  const [activeSubTab, setActiveSubTab] = useState<"graph" | "policy" | "memory" | "verifier">("graph");
  const [threads, setThreads] = useState<any[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string>("");
  const [graphData, setGraphData] = useState<any>(null);
  const [boardMessages, setBoardMessages] = useState<any[]>([]);
  const [policyData, setPolicyData] = useState<any>(null);
  const [repoMemory, setRepoMemory] = useState<any>(null);
  const [selectedMemoryKey, setSelectedMemoryKey] = useState<string>("architecture");
  const [verifierInput, setVerifierInput] = useState<string>("def calculate_score(points):\n    return sum(points)");
  const [verifierReport, setVerifierReport] = useState<any>(null);
  const [isSpawning, setIsSpawning] = useState<boolean>(false);
  const [spawnRole, setSpawnRole] = useState<string>("researcher");
  const [spawnObjective, setSpawnObjective] = useState<string>("Audit network security and port exposure");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchHarnessData = async () => {
    setIsLoading(true);
    try {
      const headers = { ...hinaaIdentityHeaders(), "bypass-tunnel-reminder": "true" };

      // 1. Fetch Threads
      const tRes = await fetch("/v1/harness/threads", { headers });
      if (tRes.ok) {
        const tJson = await tRes.json();
        const ths = tJson.threads || [];
        setThreads(ths);
        const currId = selectedThreadId || (ths.length > 0 ? ths[0].thread_id : "");
        setSelectedThreadId(currId);

        if (currId) {
          // Fetch Graph
          const gRes = await fetch(`/v1/harness/threads/${currId}/graph`, { headers });
          if (gRes.ok) {
            const gJson = await gRes.json();
            setGraphData(gJson.graph);
          }
          // Fetch Board
          const bRes = await fetch(`/v1/harness/threads/${currId}/board`, { headers });
          if (bRes.ok) {
            const bJson = await bRes.json();
            setBoardMessages(bJson.messages || []);
          }
        }
      }

      // 2. Fetch Policy
      const pRes = await fetch("/v1/harness/effective-policy", { headers });
      if (pRes.ok) {
        const pJson = await pRes.json();
        setPolicyData(pJson);
      }

      // 3. Fetch Repo Memory
      const mRes = await fetch("/v1/harness/repository-memory", { headers });
      if (mRes.ok) {
        const mJson = await mRes.json();
        setRepoMemory(mJson.memory || {});
      }
    } catch (e) {
      console.error("Failed to fetch harness data:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHarnessData();
  }, [selectedThreadId]);

  const handleSpawnSubagent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedThreadId) return;
    setIsSpawning(true);
    try {
      const headers = {
        "Content-Type": "application/json",
        ...hinaaIdentityHeaders(),
        "bypass-tunnel-reminder": "true",
      };
      const res = await fetch(`/v1/harness/threads/${selectedThreadId}/subagents`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          role: spawnRole,
          objective: spawnObjective,
        }),
      });
      if (res.ok) {
        await fetchHarnessData();
      }
    } catch (err) {
      console.error("Failed to spawn subagent:", err);
    } finally {
      setIsSpawning(false);
    }
  };

  const handleVerify = async () => {
    try {
      const headers = {
        "Content-Type": "application/json",
        ...hinaaIdentityHeaders(),
        "bypass-tunnel-reminder": "true",
      };
      const res = await fetch("/v1/harness/verify", {
        method: "POST",
        headers,
        body: JSON.stringify({
          text: verifierInput,
          filePath: "script.py",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setVerifierReport(data.report);
      }
    } catch (err) {
      console.error("Failed to verify:", err);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#0a0a0c", color: "#e4e4e7", fontSize: "12px" }}>
      {/* ── Subtab Navigation ────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 16px", borderBottom: "1px solid rgba(255,255,255,0.08)", background: "#111115" }}>
        <div style={{ display: "flex", gap: "6px" }}>
          {[
            { id: "graph", label: "🌳 Multi-Agent Graph", icon: GitBranch },
            { id: "policy", label: "🛡️ Sandbox & Policy", icon: Shield },
            { id: "memory", label: "📁 Repo Memory (.hina)", icon: FolderTree },
            { id: "verifier", label: "⚡ Verifier Brain", icon: Cpu },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id as any)}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "11px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeSubTab === tab.id ? "#8b5cf6" : "rgba(255,255,255,0.05)",
                color: activeSubTab === tab.id ? "#ffffff" : "#a1a1aa",
                display: "flex",
                alignItems: "center",
                gap: "5px",
                transition: "all 120ms ease",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <button
          onClick={fetchHarnessData}
          disabled={isLoading}
          style={{
            background: "none",
            border: "none",
            color: "#a1a1aa",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "4px",
            fontSize: "11px",
          }}
        >
          <RefreshCw size={13} style={{ animation: isLoading ? "spin 1s linear infinite" : "none" }} /> Refresh
        </button>
      </div>

      {/* ── Subtab Body ───────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
        {/* TAB 1: MULTI-AGENT GRAPH */}
        {activeSubTab === "graph" && (
          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "16px", height: "100%" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: "13px", color: "#f4f4f5", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                <GitBranch size={15} color="#8b5cf6" /> Persistent Agent Graph Hierarchy
              </div>
              <div style={{ padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", minHeight: "180px" }}>
                {graphData ? (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 8px", background: "rgba(139,92,246,0.15)", borderRadius: "6px", border: "1px solid rgba(139,92,246,0.3)", marginBottom: "8px" }}>
                      <span style={{ padding: "2px 6px", background: "#8b5cf6", color: "#fff", borderRadius: "4px", fontSize: "10px", fontWeight: 700 }}>ROOT</span>
                      <span style={{ fontWeight: 600 }}>{graphData.id}</span>
                      <span style={{ marginLeft: "auto", color: "#22c55e", fontSize: "11px" }}>● {graphData.status}</span>
                      <span style={{ color: "#a1a1aa", fontSize: "10px" }}>Budget: {graphData.budget_tokens?.toLocaleString()} tokens</span>
                    </div>

                    {graphData.children && graphData.children.length > 0 ? (
                      <div style={{ paddingLeft: "24px", borderLeft: "2px solid rgba(139,92,246,0.3)", marginLeft: "12px", display: "flex", flexDirection: "column", gap: "6px" }}>
                        {graphData.children.map((child: any) => (
                          <div key={child.id} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 8px", background: "rgba(255,255,255,0.03)", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.06)" }}>
                            <span style={{ padding: "2px 6px", background: "#3b82f6", color: "#fff", borderRadius: "4px", fontSize: "10px", fontWeight: 700 }}>{child.role?.toUpperCase()}</span>
                            <span style={{ fontWeight: 500 }}>{child.id}</span>
                            <span style={{ marginLeft: "auto", color: "#38bdf8", fontSize: "10px" }}>Depth {child.depth}</span>
                            <span style={{ color: "#a1a1aa", fontSize: "10px" }}>{child.budget_tokens?.toLocaleString()} tokens</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ padding: "12px", color: "#71717a", fontStyle: "italic", textAlign: "center" }}>
                        No subordinate agents currently spawned.
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ color: "#71717a" }}>Loading Agent Graph...</div>
                )}
              </div>

              {/* Spawn subagent form */}
              <form onSubmit={handleSpawnSubagent} style={{ marginTop: "12px", padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}>
                <div style={{ fontWeight: 600, fontSize: "11px", marginBottom: "8px", color: "#d4d4d8" }}>Spawn Specialist Subagent</div>
                <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                  <select
                    value={spawnRole}
                    onChange={(e) => setSpawnRole(e.target.value)}
                    style={{ background: "#1c1c24", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", borderRadius: "6px", padding: "4px 8px", fontSize: "11px" }}
                  >
                    <option value="researcher">Researcher</option>
                    <option value="coder">Coder</option>
                    <option value="verifier">Verifier</option>
                    <option value="security">Security Lab</option>
                    <option value="creative">Creative</option>
                  </select>
                  <input
                    type="text"
                    value={spawnObjective}
                    onChange={(e) => setSpawnObjective(e.target.value)}
                    placeholder="Objective for subagent..."
                    style={{ flex: 1, background: "#1c1c24", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", borderRadius: "6px", padding: "4px 8px", fontSize: "11px" }}
                  />
                  <button
                    type="submit"
                    disabled={isSpawning}
                    style={{ background: "#8b5cf6", color: "#fff", border: "none", borderRadius: "6px", padding: "4px 12px", fontWeight: 600, cursor: "pointer", fontSize: "11px" }}
                  >
                    {isSpawning ? "Spawning..." : "Spawn"}
                  </button>
                </div>
              </form>
            </div>

            {/* Message Board */}
            <div>
              <div style={{ fontWeight: 700, fontSize: "13px", color: "#f4f4f5", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                <MessageSquare size={15} color="#38bdf8" /> Local Agent Message Board
              </div>
              <div style={{ padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", height: "300px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
                {boardMessages.length > 0 ? (
                  boardMessages.map((msg, i) => (
                    <div key={i} style={{ padding: "8px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "6px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px", fontSize: "10px", color: "#a1a1aa" }}>
                        <span>From: <strong style={{ color: "#8b5cf6" }}>{msg.sender_id}</strong> → <strong style={{ color: "#38bdf8" }}>{msg.recipient_id}</strong></span>
                        <span style={{ padding: "1px 5px", background: "rgba(56,189,248,0.1)", color: "#38bdf8", borderRadius: "3px" }}>{msg.message_type}</span>
                      </div>
                      <div style={{ color: "#e4e4e7", fontSize: "11px" }}>
                        {msg.payload?.objective || JSON.stringify(msg.payload)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ color: "#71717a", textAlign: "center", marginTop: "40px" }}>No inter-agent messages yet.</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: SANDBOX & POLICY */}
        {activeSubTab === "policy" && policyData && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
              <div style={{ padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}>
                <div style={{ color: "#a1a1aa", fontSize: "11px" }}>GHSA-w5fx-fh39-j5rw Protection</div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#22c55e", marginTop: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <Shield size={16} /> {policyData.ghsa_w5fx_fh39_j5rw_mitigation}
                </div>
                <div style={{ color: "#71717a", fontSize: "10px", marginTop: "4px" }}>Canonical root validation enforced; model cwd cannot define boundary.</div>
              </div>

              <div style={{ padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}>
                <div style={{ color: "#a1a1aa", fontSize: "11px" }}>Shell Runtime</div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#38bdf8", marginTop: "4px" }}>
                  {policyData.shellRuntime}
                </div>
                <div style={{ color: "#71717a", fontSize: "10px", marginTop: "4px" }}>WSL 2 Kali Linux container with native toolchain.</div>
              </div>

              <div style={{ padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}>
                <div style={{ color: "#a1a1aa", fontSize: "11px" }}>Credential Stripping</div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#eab308", marginTop: "4px" }}>
                  {policyData.secretStripping}
                </div>
                <div style={{ color: "#71717a", fontSize: "10px", marginTop: "4px" }}>Ambient API keys scrubbed from child subprocess env.</div>
              </div>
            </div>

            <div style={{ padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}>
              <div style={{ fontWeight: 600, fontSize: "12px", marginBottom: "6px" }}>Trusted Workspace Roots</div>
              {policyData.workspaceRoots?.map((r: string, i: number) => (
                <code key={i} style={{ display: "block", padding: "6px", background: "rgba(0,0,0,0.3)", borderRadius: "4px", color: "#a7f3d0", fontSize: "11px" }}>
                  {r}
                </code>
              ))}
            </div>

            <div style={{ padding: "12px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px" }}>
              <div style={{ fontWeight: 600, fontSize: "12px", marginBottom: "6px" }}>Network Egress Policy</div>
              <div style={{ color: "#d4d4d8", fontSize: "11px" }}>
                <strong>Allowed Domains:</strong> {policyData.networkPolicy?.allowed_domains?.join(", ") || "github.com, pypi.org, npmjs.org"}
              </div>
              <div style={{ color: "#ef4444", fontSize: "11px", marginTop: "4px" }}>
                <strong>Blocked Raw Protocols:</strong> raw_tcp, udp, unfiltered_dns (prevents DNS exfiltration tunnels)
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: REPOSITORY AS MEMORY */}
        {activeSubTab === "memory" && repoMemory && (
          <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "16px", height: "100%" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {Object.keys(repoMemory).map((key) => (
                <button
                  key={key}
                  onClick={() => setSelectedMemoryKey(key)}
                  style={{
                    padding: "6px 10px",
                    textAlign: "left",
                    background: selectedMemoryKey === key ? "rgba(139,92,246,0.2)" : "transparent",
                    color: selectedMemoryKey === key ? "#c4b5fd" : "#a1a1aa",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "11px",
                    fontWeight: selectedMemoryKey === key ? 700 : 400,
                  }}
                >
                  📄 {key}.md
                </button>
              ))}
            </div>
            <div style={{ padding: "16px", background: "#131318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", overflowY: "auto", maxHeight: "340px" }}>
              <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", color: "#e4e4e7", margin: 0 }}>
                {repoMemory[selectedMemoryKey] || "Empty memory section"}
              </pre>
            </div>
          </div>
        )}

        {/* TAB 4: AUTONOMOUS VERIFIER BRAIN */}
        {activeSubTab === "verifier" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: "12px", marginBottom: "4px" }}>Candidate Code / Output Verifier</div>
              <textarea
                value={verifierInput}
                onChange={(e) => setVerifierInput(e.target.value)}
                rows={6}
                style={{
                  width: "100%",
                  background: "#131318",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#f4f4f5",
                  borderRadius: "6px",
                  padding: "8px",
                  fontFamily: "inherit",
                  fontSize: "11px",
                }}
              />
              <button
                onClick={handleVerify}
                style={{
                  marginTop: "6px",
                  background: "#22c55e",
                  color: "#000",
                  fontWeight: 700,
                  border: "none",
                  borderRadius: "6px",
                  padding: "6px 16px",
                  cursor: "pointer",
                  fontSize: "11px",
                }}
              >
                Run Autonomous Verifier Check
              </button>
            </div>

            {verifierReport && (
              <div style={{ padding: "12px", background: verifierReport.valid ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)", border: `1px solid ${verifierReport.valid ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`, borderRadius: "8px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, color: verifierReport.valid ? "#22c55e" : "#ef4444" }}>
                  {verifierReport.valid ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  Status: {verifierReport.valid ? "PASSED (Clean Verification)" : "FAILED (Violations Detected)"} — Score: {(verifierReport.score * 100).toFixed(0)}%
                </div>
                {verifierReport.issues?.length > 0 && (
                  <div style={{ marginTop: "6px", color: "#fca5a5" }}>
                    <strong>Issues:</strong>
                    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                      {verifierReport.issues.map((iss: string, i: number) => <li key={i}>{iss}</li>)}
                    </ul>
                  </div>
                )}
                {verifierReport.suggested_repairs?.length > 0 && (
                  <div style={{ marginTop: "6px", color: "#fef08a" }}>
                    <strong>Suggested Repairs:</strong>
                    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                      {verifierReport.suggested_repairs.map((rep: string, i: number) => <li key={i}>{rep}</li>)}
                    </ul>
                  </div>
                )}
                {verifierReport.evidence?.length > 0 && (
                  <div style={{ marginTop: "6px", color: "#86efac" }}>
                    <strong>Evidence:</strong>
                    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                      {verifierReport.evidence.map((ev: string, i: number) => <li key={i}>{ev}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
