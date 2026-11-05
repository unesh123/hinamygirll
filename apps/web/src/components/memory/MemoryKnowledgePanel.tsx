import React, { useState, useEffect, useCallback } from "react";

export type MemoryScope = "user" | "project" | "system" | "session";
export type MemoryType = "fact" | "preference" | "entity" | "instruction" | "procedure" | "episode";
export type TrustTier = "verified" | "user_explicit" | "inferred" | "unverified" | "staged";

export interface MemoryRecord {
  id: string;
  tenant_id: string;
  user_id?: string | null;
  project_id?: string | null;
  scope: MemoryScope;
  memory_type: MemoryType;
  content: string;
  structured_data: Record<string, unknown>;
  trust_tier: TrustTier;
  confidence: number;
  source_url?: string | null;
  source_tool?: string | null;
  evidence_text?: string | null;
  is_active: boolean;
  is_contradicted: boolean;
  superseded_by_id?: string | null;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
}

export interface KnowledgeNode {
  id: string;
  canonical_name: string;
  entity_type: string;
  aliases: string[];
  attributes: Record<string, unknown>;
  valid_from: string;
  valid_to?: string | null;
}

export interface KnowledgeEdge {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  confidence: number;
  valid_from: string;
  valid_to?: string | null;
  is_contradiction: boolean;
}

export interface IngestionCandidate {
  id: string;
  candidate_fact: string;
  source_url?: string | null;
  source_tool?: string | null;
  raw_evidence: string;
  extracted_entities: Array<{ name: string; type: string }>;
  trust_tier: TrustTier;
  status: "pending" | "approved" | "rejected";
  review_notes?: string | null;
  created_at: string;
}

export interface MemoryStats {
  total_memories: number;
  active_memories: number;
  contradicted_memories: number;
  total_nodes: number;
  total_edges: number;
  pending_candidates: number;
  db_size_bytes: number;
}

export const MemoryKnowledgePanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"memories" | "graph" | "ingestion" | "export">("memories");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [scopeFilter, setScopeFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [includeContradicted, setIncludeContradicted] = useState<boolean>(false);

  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [graphNodes, setGraphNodes] = useState<KnowledgeNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<KnowledgeEdge[]>([]);
  const [candidates, setCandidates] = useState<IngestionCandidate[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);

  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // New Memory creation form
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newContent, setNewContent] = useState<string>("");
  const [newScope, setNewScope] = useState<MemoryScope>("user");
  const [newType, setNewType] = useState<MemoryType>("fact");

  // Fetch telemetry stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/memory/health");
      if (res.ok) {
        const data = await res.json();
        setStats(data.stats);
      }
    } catch {
      // Offline fallback
    }
  }, []);

  // Fetch memories list or hybrid search
  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      if (searchQuery.trim()) {
        const res = await fetch("/api/memory/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: searchQuery.trim(),
            scope: scopeFilter !== "all" ? scopeFilter : undefined,
            memory_type: typeFilter !== "all" ? typeFilter : undefined,
            include_contradicted: includeContradicted,
            limit: 30,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setMemories(data.results.map((r: { record: MemoryRecord }) => r.record));
        } else {
          setErrorMsg("Failed to execute hybrid search query.");
        }
      } else {
        const params = new URLSearchParams();
        if (scopeFilter !== "all") params.append("scope", scopeFilter);
        if (typeFilter !== "all") params.append("memory_type", typeFilter);
        if (includeContradicted) params.append("include_contradicted", "true");

        const res = await fetch(`/api/memory/items?${params.toString()}`);
        if (res.ok) {
          const data = await res.json();
          setMemories(data.items);
        }
      }
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Network error");
    } finally {
      setLoading(false);
    }
  }, [searchQuery, scopeFilter, typeFilter, includeContradicted]);

  // Fetch graph nodes & edges
  const fetchGraph = useCallback(async () => {
    try {
      const res = await fetch("/api/memory/knowledge/graph");
      if (res.ok) {
        const data = await res.json();
        setGraphNodes(data.nodes || []);
        setGraphEdges(data.edges || []);
      }
    } catch {
      // offline
    }
  }, []);

  // Fetch candidates
  const fetchCandidates = useCallback(async () => {
    try {
      const res = await fetch("/api/memory/ingestion/candidates");
      if (res.ok) {
        const data = await res.json();
        setCandidates(data.candidates || []);
      }
    } catch {
      // offline
    }
  }, []);

  useEffect(() => {
    fetchStats();
    if (activeTab === "memories") fetchMemories();
    if (activeTab === "graph") fetchGraph();
    if (activeTab === "ingestion") fetchCandidates();
  }, [activeTab, fetchStats, fetchMemories, fetchGraph, fetchCandidates]);

  // Handle memory creation
  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    try {
      const res = await fetch("/api/memory/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: newContent.trim(),
          scope: newScope,
          memory_type: newType,
          trust_tier: "user_explicit",
        }),
      });
      if (res.ok) {
        setSuccessMsg("Memory record created successfully.");
        setNewContent("");
        setShowCreateModal(false);
        fetchMemories();
        fetchStats();
      } else {
        setErrorMsg("Failed to store memory item.");
      }
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Creation error");
    }
  };

  // Handle memory delete
  const handleDeleteMemory = async (id: string) => {
    if (!confirm("Are you sure you want to permanently delete this memory? This triggers a cascade to derived edges and FTS indices.")) return;
    try {
      const res = await fetch(`/api/memory/items/${id}`, { method: "DELETE" });
      if (res.ok) {
        setSuccessMsg(`Memory deleted with full cascade.`);
        fetchMemories();
        fetchStats();
      }
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Delete error");
    }
  };

  // Handle Candidate Review
  const handleReviewCandidate = async (candidateId: string, decision: "approve" | "reject") => {
    try {
      const res = await fetch(`/api/memory/ingestion/${candidateId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, review_notes: `Processed via UI review` }),
      });
      if (res.ok) {
        setSuccessMsg(`Candidate ${decision}d.`);
        fetchCandidates();
        fetchStats();
      }
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Review error");
    }
  };

  // Handle Scoped Export
  const handleExport = async (format: "json" | "csv") => {
    try {
      const res = await fetch("/api/memory/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `hinaa_memories_${Date.now()}.${format}`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Export error");
    }
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 p-4 space-y-4 overflow-y-auto">
      {/* Top Header & Telemetry Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-white">Long-Term Memory & Knowledge Graph</h2>
            <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
              PHASE 10
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            ACID SQLite FTS5 persistence • Temporal Knowledge Graph • Non-destructive supersession
          </p>
        </div>

        {stats && (
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
              Memories: <strong className="text-emerald-400">{stats.active_memories}</strong>/{stats.total_memories}
            </span>
            <span className="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
              Contradicted: <strong className="text-amber-400">{stats.contradicted_memories}</strong>
            </span>
            <span className="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
              Graph: <strong className="text-sky-400">{stats.total_nodes}</strong> nodes / <strong className="text-sky-400">{stats.total_edges}</strong> edges
            </span>
            <span className="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
              Staged: <strong className="text-purple-400">{stats.pending_candidates}</strong>
            </span>
          </div>
        )}
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="bg-red-950/60 border border-red-800 text-red-200 text-xs px-3 py-2 rounded flex justify-between items-center">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-white ml-2">✕</button>
        </div>
      )}
      {successMsg && (
        <div className="bg-emerald-950/60 border border-emerald-800 text-emerald-200 text-xs px-3 py-2 rounded flex justify-between items-center">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-white ml-2">✕</button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        {(["memories", "graph", "ingestion", "export"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              activeTab === tab
                ? "bg-zinc-800 text-white shadow-sm border border-zinc-700"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
            }`}
          >
            {tab === "memories" && "🧠 Durable Memories"}
            {tab === "graph" && "🕸️ Knowledge Graph"}
            {tab === "ingestion" && "📥 Ingestion Queue"}
            {tab === "export" && "💾 Export & Audit"}
          </button>
        ))}

        <div className="ml-auto">
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-600 hover:bg-emerald-500 text-white transition-colors"
          >
            + Add Memory
          </button>
        </div>
      </div>

      {/* Tab 1: Memories List & Search */}
      {activeTab === "memories" && (
        <div className="space-y-3">
          {/* Controls */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <input
              type="text"
              placeholder="Hybrid search (keywords, semantic context, Devanagari)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchMemories()}
              className="flex-1 min-w-[240px] bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-600"
            />
            <button
              onClick={fetchMemories}
              className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded font-medium"
            >
              Search
            </button>
            <select
              value={scopeFilter}
              onChange={(e) => setScopeFilter(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-zinc-300"
            >
              <option value="all">All Scopes</option>
              <option value="user">User</option>
              <option value="project">Project</option>
              <option value="system">System</option>
              <option value="session">Session</option>
            </select>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-zinc-300"
            >
              <option value="all">All Types</option>
              <option value="fact">Fact</option>
              <option value="preference">Preference</option>
              <option value="entity">Entity</option>
              <option value="instruction">Instruction</option>
              <option value="procedure">Procedure</option>
            </select>
            <label className="flex items-center gap-1.5 text-zinc-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={includeContradicted}
                onChange={(e) => setIncludeContradicted(e.target.checked)}
                className="rounded border-zinc-700 bg-zinc-900 text-emerald-500"
              />
              Show superseded
            </label>
          </div>

          {/* Cards */}
          {loading ? (
            <div className="text-center py-8 text-zinc-500 text-xs font-mono">Retrieving memories...</div>
          ) : memories.length === 0 ? (
            <div className="text-center py-8 text-zinc-500 text-xs">No memories found matching criteria.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {memories.map((mem) => (
                <div
                  key={mem.id}
                  className={`p-3 rounded border text-xs flex flex-col justify-between space-y-2 transition-all ${
                    mem.is_contradicted
                      ? "bg-amber-950/20 border-amber-800/60 opacity-80"
                      : "bg-zinc-900/80 border-zinc-800 hover:border-zinc-700"
                  }`}
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-mono font-bold bg-zinc-800 text-zinc-300">
                          {mem.scope}
                        </span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-mono bg-sky-950 text-sky-400 border border-sky-800">
                          {mem.memory_type}
                        </span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-400">
                          {Math.round(mem.confidence * 100)}% conf
                        </span>
                      </div>
                      {mem.is_contradicted && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-900 text-amber-300">
                          SUPERSEDED
                        </span>
                      )}
                    </div>

                    <p className="text-zinc-200 text-sm leading-relaxed">{mem.content}</p>

                    {mem.evidence_text && (
                      <p className="text-zinc-500 text-[11px] italic line-clamp-2">
                        Evidence: "{mem.evidence_text}"
                      </p>
                    )}
                  </div>

                  <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-500">
                    <span title={mem.created_at}>
                      {new Date(mem.created_at).toLocaleDateString()} {new Date(mem.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <button
                      onClick={() => handleDeleteMemory(mem.id)}
                      className="text-red-400 hover:text-red-300 font-medium"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Knowledge Graph Visualization */}
      {activeTab === "graph" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-400 font-mono">
              Displaying {graphNodes.length} entity nodes and {graphEdges.length} typed relationships
            </span>
            <button
              onClick={fetchGraph}
              className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded font-medium"
            >
              Refresh Graph
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {graphNodes.map((node) => {
              const connectedEdges = graphEdges.filter(
                (e) => e.source_id === node.id || e.target_id === node.id
              );
              return (
                <div key={node.id} className="p-3 bg-zinc-900 border border-zinc-800 rounded text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <strong className="text-sky-400 font-semibold text-sm">{node.canonical_name}</strong>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-400">
                      {node.entity_type}
                    </span>
                  </div>

                  {node.aliases.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {node.aliases.map((alias, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded text-[10px]">
                          {alias}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="space-y-1 pt-1 border-t border-zinc-800">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">Edges:</span>
                    {connectedEdges.length === 0 ? (
                      <div className="text-[11px] text-zinc-600 italic">No direct connections</div>
                    ) : (
                      connectedEdges.map((edge) => {
                        const isOut = edge.source_id === node.id;
                        const otherNode = graphNodes.find((n) => n.id === (isOut ? edge.target_id : edge.source_id));
                        return (
                          <div key={edge.id} className="flex items-center gap-1.5 text-[11px] text-zinc-300 font-mono">
                            <span className="text-emerald-400 font-bold">{isOut ? "→" : "←"}</span>
                            <span className="text-amber-400 font-semibold">{edge.relation_type}</span>
                            <span className="text-zinc-400">{otherNode?.canonical_name || "Unknown"}</span>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 3: Ingestion Quarantine Queue */}
      {activeTab === "ingestion" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-400">
              Discovered candidate facts from CRAG research, browser runs, and coding actions. Requires review before promoting to memory.
            </span>
            <button
              onClick={fetchCandidates}
              className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded font-medium"
            >
              Refresh
            </button>
          </div>

          {candidates.length === 0 ? (
            <div className="text-center py-8 text-zinc-500 text-xs">Ingestion queue is clean. No staged candidates.</div>
          ) : (
            <div className="space-y-2">
              {candidates.map((cand) => (
                <div
                  key={cand.id}
                  className="p-3 bg-zinc-900 border border-zinc-800 rounded flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                >
                  <div className="space-y-1 max-w-2xl">
                    <p className="text-zinc-200 font-medium">{cand.candidate_fact}</p>
                    <div className="flex items-center gap-2 text-zinc-500 text-[11px]">
                      {cand.source_url && <span>Source: {cand.source_url}</span>}
                      {cand.source_tool && <span>Tool: {cand.source_tool}</span>}
                      <span>{new Date(cand.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleReviewCandidate(cand.id, "approve")}
                      className="px-2.5 py-1 bg-emerald-700 hover:bg-emerald-600 text-white rounded font-medium"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleReviewCandidate(cand.id, "reject")}
                      className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded font-medium"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Export & Maintenance */}
      {activeTab === "export" && (
        <div className="space-y-4 max-w-xl">
          <div className="p-4 bg-zinc-900 border border-zinc-800 rounded space-y-3">
            <h3 className="font-semibold text-sm text-zinc-200">Scoped Data Portability</h3>
            <p className="text-xs text-zinc-400">
              Download tenant memories for local backup, auditing, or migration compliance (GDPR/Right to Portability).
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleExport("json")}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded text-xs font-medium border border-zinc-700"
              >
                Export JSON
              </button>
              <button
                onClick={() => handleExport("csv")}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded text-xs font-medium border border-zinc-700"
              >
                Export CSV
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Memory Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5 max-w-md w-full space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
              <h3 className="font-semibold text-sm text-white">Create Durable Memory</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-zinc-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateMemory} className="space-y-3 text-xs">
              <div>
                <label className="block text-zinc-400 mb-1">Content / Assertion</label>
                <textarea
                  rows={3}
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="e.g. User prefers Python and FastAPI for backend development"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded p-2 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-600"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-zinc-400 mb-1">Scope</label>
                  <select
                    value={newScope}
                    onChange={(e) => setNewScope(e.target.value as MemoryScope)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded p-2 text-zinc-300"
                  >
                    <option value="user">User</option>
                    <option value="project">Project</option>
                    <option value="system">System</option>
                  </select>
                </div>
                <div>
                  <label className="block text-zinc-400 mb-1">Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value as MemoryType)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded p-2 text-zinc-300"
                  >
                    <option value="fact">Fact</option>
                    <option value="preference">Preference</option>
                    <option value="entity">Entity</option>
                    <option value="instruction">Instruction</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
                >
                  Save Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
