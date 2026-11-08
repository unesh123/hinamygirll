import { useMemo } from "react";
import { asList, str, useApiJson, type ApiResource, type ApiStatus } from "./useApi";

export interface Connector {
  id: string;
  name: string;
  category: string;
  configured: boolean;
  statusText: string;
  capabilities: string[];
}

export interface Skill { id: string; name: string; description: string; category: string }
export interface ToolInfo { name: string; displayName: string; description: string; riskLevel: string; requiresConfirmation: boolean }
export interface McpServer { id: string; name: string; status: string; toolCount: number | null; transport: string }
export interface MemoryItem { id: string; content: string; scope: string; type: string; confidence: number; updatedAt: string }

type Raw = Record<string, unknown>;

export function normalizeConnector(raw: Raw): Connector {
  const configured = raw.connected ?? raw.configured ?? raw.enabled;
  const name = str(raw.display_name) || str(raw.displayName) || str(raw.name) || str(raw.service_id) || str(raw.id, "Unknown");
  return {
    id: str(raw.service_id) || str(raw.id) || name,
    name,
    category: str(raw.category, "other"),
    configured: typeof configured === "boolean" ? configured : str(raw.status) === "connected" || str(raw.status) === "configured",
    statusText: str(raw.status_text) || str(raw.statusText) || str(raw.status),
    capabilities: Array.isArray(raw.capabilities) ? raw.capabilities.map(String) : [],
  };
}

export function normalizeSkill(raw: Raw): Skill {
  const name = str(raw.name) || str(raw.title) || str(raw.id, "Skill");
  return { id: str(raw.id) || str(raw.slug) || name, name, description: str(raw.description), category: str(raw.category, "general") };
}

export function normalizeMcpServer(raw: Raw): McpServer {
  const name = str(raw.name) || str(raw.id, "server");
  const tools = raw.tool_count ?? raw.toolCount ?? (Array.isArray(raw.tools) ? raw.tools.length : null);
  return {
    id: str(raw.id) || name,
    name,
    status: str(raw.status) || (raw.connected === true ? "connected" : raw.connected === false ? "disconnected" : "unknown"),
    toolCount: typeof tools === "number" ? tools : null,
    transport: str(raw.transport) || str(raw.type),
  };
}

export function normalizeMemory(raw: Raw): MemoryItem {
  return {
    id: str(raw.id),
    content: str(raw.content),
    scope: str(raw.scope, "user"),
    type: str(raw.memory_type, "fact"),
    confidence: typeof raw.confidence === "number" ? raw.confidence : 1,
    updatedAt: str(raw.updated_at),
  };
}

export type MemoryGroup = "about" | "projects" | "preferences";

export function groupMemory(items: MemoryItem[]): Record<MemoryGroup, MemoryItem[]> {
  const out: Record<MemoryGroup, MemoryItem[]> = { about: [], projects: [], preferences: [] };
  for (const item of items) {
    if (item.scope === "project") out.projects.push(item);
    else if (item.type === "preference" || item.type === "instruction" || item.type === "procedure") out.preferences.push(item);
    else out.about.push(item);
  }
  return out;
}

function useMapped<T>(res: ApiResource<unknown>, keys: string[], norm: (raw: Raw) => T): { status: ApiStatus; error: string | null; items: T[]; reload: () => void } {
  const items = useMemo(() => asList<Raw>(res.data, keys).map(norm), [res.data]); // eslint-disable-line react-hooks/exhaustive-deps
  return { status: res.status, error: res.error, items, reload: res.reload };
}

/** /v1/integrations, falling back to the legacy /v1/integrations/status when absent. */
export function useConnectors() {
  const primary = useApiJson<unknown>("/v1/integrations");
  const fallback = useApiJson<unknown>(primary.status === "missing" ? "/v1/integrations/status" : null);
  const active = primary.status === "missing" ? fallback : primary;
  const res = useMapped(active, ["integrations", "connectors", "items"], normalizeConnector);
  const reload = () => { primary.reload(); fallback.reload(); };
  return { ...res, status: primary.status === "missing" && fallback.status === "loading" && fallback.data === null ? ("loading" as ApiStatus) : res.status, reload };
}

export const useSkills = () => useMapped(useApiJson<unknown>("/api/skills"), ["skills", "items"], normalizeSkill);
export const useMcpServers = () => useMapped(useApiJson<unknown>("/v1/mcp/servers"), ["servers", "items"], normalizeMcpServer);
export const useTools = () =>
  useMapped(useApiJson<unknown>("/v1/tools"), ["tools", "items"], (raw): ToolInfo => ({
    name: str(raw.name),
    displayName: str(raw.displayName) || str(raw.name),
    description: str(raw.description),
    riskLevel: str(raw.riskLevel, "unknown"),
    requiresConfirmation: raw.requiresConfirmation === true,
  }));
export const useMemoryItems = (limit = 200) => useMapped(useApiJson<unknown>(`/v1/memory/items?limit=${limit}`), ["items"], normalizeMemory);
