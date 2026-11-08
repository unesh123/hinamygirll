import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildCommands, filterCommands } from "../commands";
import OrganisationPage from "./OrganisationPage";

type Json = Record<string, unknown>;
interface Call { method: string; path: string; body: Json | null }

const ALL = ["org:manage", "members:manage", "apikeys:manage", "audit:read", "tools:execute", "tools:execute_high_risk", "data:write", "data:read"];
const ROLES = ["owner", "admin", "member", "viewer"];
const MEMBERS = [
  { userId: "u1", authSubject: "alice", role: "owner", joinedAt: null },
  { userId: "u2", authSubject: "bob", role: "member", joinedAt: null },
];
const KEY = { id: "k1", name: "ci", prefix: "hk_ab12cd34", scopes: ["data:read"], createdAt: null, expiresAt: null, lastUsedAt: null, revokedAt: null, active: true };
const AUDIT = { items: [{ seq: 1, userId: "u1", action: "org.create", target: "org:x", outcome: "success", requestId: "r", timestamp: "2026-11-08T00:00:00+00:00", hash: "h" }], total: 1, limit: 20, offset: 0 };

function me(role: string, permissions: string[]) {
  return { user: { id: "u1", authSubject: "alice" }, org: { id: "o1", name: "Personal", isPersonal: true, role }, role, permissions, roles: ROLES, rolePermissions: {} };
}

function mockApi(profile: Json | number): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = init?.method ?? "GET";
    calls.push({ method, path: url.pathname, body: init?.body ? (JSON.parse(String(init.body)) as Json) : null });
    const reply = (body: unknown, status = 200) =>
      Promise.resolve({ ok: status < 400, status, json: () => (status === 204 ? Promise.reject(new Error("no body")) : Promise.resolve(body)) } as Response);
    if (url.pathname.endsWith("/me")) return typeof profile === "number" ? reply({}, profile) : reply(profile);
    if (method === "POST" && url.pathname.endsWith("/api-keys")) return reply({ ...KEY, id: "k2", name: "deploy", key: "hk_ab12cd34_SECRETVALUE" }, 201);
    if (method === "DELETE") return reply(null, 204);
    if (url.pathname.endsWith("/members")) return reply({ items: MEMBERS });
    if (url.pathname.endsWith("/api-keys")) return reply({ items: [KEY] });
    if (url.pathname.endsWith("/audit/verify")) return reply({ ok: false, checked: 1, firstInvalidSeq: 1 });
    if (url.pathname.endsWith("/audit")) return reply(AUDIT);
    return reply({}, 404);
  }));
  return calls;
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("Organisation page", () => {
  it("shows loading, then every section for an owner", async () => {
    mockApi(me("owner", ALL));
    render(<OrganisationPage />);
    expect(screen.getByText("Loading organisation…")).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: "Members" })).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: "API keys" })).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: "Audit log" })).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Add member" })).toBeInTheDocument();
  });

  it("hides controls a viewer cannot use", async () => {
    mockApi(me("viewer", ["data:read"]));
    render(<OrganisationPage />);
    expect(await screen.findByRole("table", { name: "Members" })).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Add member" })).toBeNull();
    expect(screen.queryByRole("table", { name: "API keys" })).toBeNull();
    expect(screen.queryByRole("table", { name: "Audit log" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Remove/ })).toBeNull();
  });

  it("shows the error state with retry", async () => {
    mockApi(500);
    render(<OrganisationPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn’t load organisation");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("reveals a new key once and copies it", async () => {
    const calls = mockApi(me("owner", ALL));
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<OrganisationPage />);
    await screen.findByRole("table", { name: "API keys" });
    await user.type(screen.getByLabelText("Name"), "deploy");
    await user.click(screen.getByRole("button", { name: "Create key" }));
    expect(await screen.findByText("hk_ab12cd34_SECRETVALUE")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/api-keys"));
    expect(post?.body).toMatchObject({ name: "deploy", scopes: ["data:read"] });
    await user.click(screen.getByRole("button", { name: "Copy key" }));
    expect(writeText).toHaveBeenCalledWith("hk_ab12cd34_SECRETVALUE");
    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByText("hk_ab12cd34_SECRETVALUE")).toBeNull();
  });

  it("revokes a key and reports tampering from verify", async () => {
    const calls = mockApi(me("admin", ALL.filter((p) => p !== "org:manage")));
    const user = userEvent.setup();
    render(<OrganisationPage />);
    await user.click(await screen.findByRole("button", { name: "Revoke ci" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path.endsWith("/api-keys/k1"))).toBe(true));
    await user.click(screen.getByRole("button", { name: "Verify chain" }));
    expect(await screen.findByText("Tampering detected at entry 1")).toBeInTheDocument();
  });

  it("is reachable from the command palette", () => {
    const hits = filterCommands(buildCommands(() => undefined, "/workspace"), "organisation");
    expect(hits.some((c) => c.label.includes("Organisation"))).toBe(true);
  });
});
