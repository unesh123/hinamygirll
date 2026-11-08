export { call } from "../news/api";

export const ORG_BASE = "/v1/org";

export type Role = "owner" | "admin" | "member" | "viewer";

export interface OrgSummary { id: string; name: string; isPersonal: boolean; role: Role }

export interface OrgMe {
  user: { id: string; authSubject: string };
  org: OrgSummary | null;
  role: Role;
  permissions: string[];
  roles: Role[];
  rolePermissions: Record<string, string[]>;
}

export interface Member { userId: string; authSubject: string | null; role: Role; joinedAt: string | null }

export interface ApiKeyRow {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  createdAt: string | null;
  expiresAt: string | null;
  lastUsedAt: string | null;
  revokedAt: string | null;
  active: boolean;
}

export interface CreatedKey extends ApiKeyRow { key: string }

export interface AuditRow {
  seq: number;
  userId: string;
  action: string;
  target: string;
  outcome: string;
  requestId: string;
  timestamp: string;
  hash: string;
}

export interface AuditPage { items: AuditRow[]; total: number; limit: number; offset: number }
export interface AuditVerdict { ok: boolean; checked: number; firstInvalidSeq: number | null }

export const can = (me: OrgMe, permission: string): boolean => me.permissions.includes(permission);

export function when(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}
