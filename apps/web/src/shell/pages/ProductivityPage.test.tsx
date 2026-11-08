import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildCommands, filterCommands } from "../commands";
import { addDays, mondayOf, sparklinePoints, toIsoDate, trendPercent, type SalesSummary } from "../productivity/api";
import { ShellRoutes } from "../ShellApp";
import ProductivityPage from "./ProductivityPage";

vi.mock("../../App", () => ({ default: () => <div>legacy app</div> }));

type Json = Record<string, unknown>;
interface Call { method: string; path: string; body: Json | null }

const MONDAY = toIsoDate(mondayOf(new Date()));
const WEDNESDAY = addDays(MONDAY, 2);

const POST = { id: "p1", platform: "tiktok", title: "Launch teaser", caption: "", scheduledFor: `${WEDNESDAY}T18:00`, status: "scheduled", tags: ["launch"], notes: "" };
const PROJECT = { id: "j1", name: "Website", status: "active", priority: "high", dueDate: "2000-01-01", progress: 40, nextAction: "Ship pricing page", notes: "" };
const SALE = { id: "s1", occurredOn: MONDAY, amount: 1500, currency: "NPR", source: "instagram", customer: "Sile", product: "Hoodie", notes: "" };

function summary(period: string, total: number, previousTotal: number, changePct: number | null): Json {
  return {
    period, currency: "NPR", total, count: total ? 2 : 0,
    trend: { previousTotal, change: total - previousTotal, changePct, direction: total >= previousTotal ? "up" : "down" },
    series: [0, 100, 50, 300, 0, 200, 150].map((t, i) => ({ date: addDays(MONDAY, i), total: t })),
  };
}

function weekFor(start: string, posts: Json[]): Json {
  const days = Array.from({ length: 7 }, (_, i) => {
    const date = addDays(start, i);
    return { date, weekday: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][i], posts: posts.filter((p) => String(p.scheduledFor).startsWith(date)) };
  });
  return { weekStart: start, weekEnd: addDays(start, 6), total: posts.length, days };
}

interface Fixture { posts: Json[]; sales: Json[]; projects: Json[]; week?: "reject" | 404; sales404?: boolean }

function mockApi(fx: Fixture): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = init?.method ?? "GET";
    calls.push({ method, path: url.pathname + url.search, body: init?.body ? (JSON.parse(String(init.body)) as Json) : null });
    const reply = (body: unknown, status = 200) =>
      Promise.resolve({ ok: status < 400, status, json: () => (status === 204 ? Promise.reject(new Error("no body")) : Promise.resolve(body)) } as Response);
    if (method !== "GET") return reply(method === "DELETE" ? null : { id: "new" }, method === "DELETE" ? 204 : method === "POST" ? 201 : 200);
    if (url.pathname.endsWith("/content/week")) {
      if (fx.week === "reject") return Promise.reject(new Error("offline"));
      if (fx.week === 404) return reply({}, 404);
      return reply(weekFor(url.searchParams.get("week_start") ?? MONDAY, fx.posts));
    }
    if (url.pathname.endsWith("/sales/summary")) {
      if (fx.sales404) return reply({}, 404);
      const period = url.searchParams.get("period");
      return reply(period === "day" ? summary("day", 400, 0, null) : period === "week" ? summary("week", 500, 400, 25) : summary("month", 750, 1000, -25));
    }
    if (url.pathname.endsWith("/sales/records")) return reply({ items: fx.sales, total: fx.sales.length });
    if (url.pathname.endsWith("/projects")) return reply({ items: fx.projects, total: fx.projects.length });
    return reply({}, 404);
  }));
  return calls;
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("Productivity page — content calendar", () => {
  it("renders a seven-day week grid with the post on its day", async () => {
    mockApi({ posts: [POST], sales: [], projects: [] });
    render(<ProductivityPage />);

    const grid = await screen.findByRole("list", { name: /^Week of/ });
    const days = within(grid).getAllByRole("listitem", { name: "" }).filter((li) => li.classList.contains("prod-day"));
    expect(days).toHaveLength(7);
    const wednesday = within(screen.getByRole("list", { name: "Posts on Wednesday" }));
    expect(wednesday.getByText("Launch teaser")).toBeInTheDocument();
    expect(wednesday.getByText("tiktok")).toBeInTheDocument();
    expect(wednesday.getByText("scheduled")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Posts on Monday" })).queryAllByRole("listitem")).toHaveLength(0);
  });

  it("navigates to the previous and next week", async () => {
    const calls = mockApi({ posts: [], sales: [], projects: [] });
    render(<ProductivityPage />);
    await screen.findByRole("list", { name: /^Week of/ });

    await userEvent.click(screen.getByRole("button", { name: "Next week" }));
    await waitFor(() => expect(calls.some((c) => c.path.includes(`week_start=${addDays(MONDAY, 7)}`))).toBe(true));
    await userEvent.click(screen.getByRole("button", { name: "Previous week" }));
    await userEvent.click(screen.getByRole("button", { name: "Previous week" }));
    await waitFor(() => expect(calls.some((c) => c.path.includes(`week_start=${addDays(MONDAY, -7)}`))).toBe(true));
    await userEvent.click(screen.getByRole("button", { name: "This week" }));
    await waitFor(() => expect(calls.at(-1)?.path).toContain(`week_start=${MONDAY}`));
  });

  it("adds a post from a day cell and reloads the week", async () => {
    const calls = mockApi({ posts: [], sales: [], projects: [] });
    render(<ProductivityPage />);
    await screen.findByText("No posts planned this week yet.");

    await userEvent.click(screen.getByRole("button", { name: "Add post on Monday" }));
    const dialog = screen.getByRole("dialog", { name: "Add post" });
    expect(within(dialog).getByLabelText("Date")).toHaveValue(MONDAY);
    expect(within(dialog).getByLabelText("Title")).toHaveFocus();

    await userEvent.type(within(dialog).getByLabelText("Title"), "  Behind the scenes ");
    await userEvent.selectOptions(within(dialog).getByLabelText("Platform"), "youtube");
    await userEvent.type(within(dialog).getByLabelText(/Tags/), "bts, studio");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add post" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe("/v1/productivity/content/posts");
    expect(post?.body).toMatchObject({ title: "Behind the scenes", platform: "youtube", status: "scheduled", scheduledFor: `${MONDAY}T09:00`, tags: ["bts", "studio"] });
    expect(calls.filter((c) => c.path.includes("/content/week")).length).toBeGreaterThan(1);
  });

  it("requires a title and closes on Escape", async () => {
    const calls = mockApi({ posts: [], sales: [], projects: [] });
    render(<ProductivityPage />);
    await screen.findByRole("list", { name: /^Week of/ });
    const opener = screen.getByRole("button", { name: "Add post" });
    await userEvent.click(opener);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Add post" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A post needs a title.");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("edits and deletes an existing post", async () => {
    const calls = mockApi({ posts: [POST], sales: [], projects: [] });
    render(<ProductivityPage />);
    await userEvent.click(await screen.findByRole("button", { name: /Launch teaser/ }));
    const dialog = screen.getByRole("dialog", { name: "Edit post" });
    expect(within(dialog).getByLabelText("Title")).toHaveValue("Launch teaser");
    expect(within(dialog).getByLabelText("Time")).toHaveValue("18:00");

    await userEvent.selectOptions(within(dialog).getByLabelText("Status"), "published");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save post" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toMatchObject({ status: "published", scheduledFor: `${WEDNESDAY}T18:00` }));
    expect(calls.find((c) => c.method === "PATCH")?.path).toBe("/v1/productivity/content/posts/p1");

    await userEvent.click(await screen.findByRole("button", { name: /Launch teaser/ }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(calls.find((c) => c.method === "DELETE")?.path).toBe("/v1/productivity/content/posts/p1"));
  });

  it("shows an error with retry, and a not-available state", async () => {
    mockApi({ posts: [], sales: [], projects: [], week: "reject" });
    const first = render(<ProductivityPage />);
    expect(await screen.findByText(/Couldn’t load content calendar/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Retry" }).length).toBeGreaterThan(0);
    first.unmount();

    mockApi({ posts: [], sales: [], projects: [], week: 404 });
    render(<ProductivityPage />);
    expect(await screen.findByText(/content calendar endpoint isn’t available/)).toBeInTheDocument();
  });
});

describe("Productivity page — sales", () => {
  it("shows today / week / month tiles with trend and a sparkline", async () => {
    mockApi({ posts: [], sales: [SALE], projects: [] });
    render(<ProductivityPage />);

    expect(await screen.findByText("NPR 400.00")).toBeInTheDocument();
    expect(screen.getByText("NPR 500.00")).toBeInTheDocument();
    expect(screen.getByText("NPR 750.00")).toBeInTheDocument();
    expect(screen.getByText("No prior sales to compare")).toBeInTheDocument();
    const trends = screen.getAllByText(/% vs previous/);
    expect(trends.map((t) => t.getAttribute("data-direction"))).toEqual(["up", "down"]);
    expect(trends.map((t) => t.textContent)).toEqual([expect.stringContaining("▲ 25.0% vs previous"), expect.stringContaining("▼ 25.0% vs previous")]);
    expect(screen.getByRole("img", { name: /Daily sales this week, NPR 800\.00 in total/ })).toBeInTheDocument();

    const table = screen.getByRole("table", { name: "Recent sales" });
    expect(within(table).getByText("NPR 1,500.00")).toBeInTheDocument();
    expect(within(table).getByText("Sile")).toBeInTheDocument();
  });

  it("logs a sale from the quick form and validates the amount", async () => {
    const calls = mockApi({ posts: [], sales: [SALE], projects: [] });
    render(<ProductivityPage />);
    const form = await screen.findByRole("form", { name: "Log a sale" });

    await userEvent.click(within(form).getByRole("button", { name: "Log sale" }));
    expect(await screen.findByText("Enter a sale amount greater than zero.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);

    await userEvent.type(within(form).getByLabelText("Amount"), "2500.5");
    await userEvent.type(within(form).getByLabelText("Channel"), "walk-in");
    await userEvent.click(within(form).getByRole("button", { name: "Log sale" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({ amount: 2500.5, source: "walk-in" }));
    await waitFor(() => expect(within(form).getByLabelText("Amount")).toHaveValue(""));
    expect(calls.filter((c) => c.path.includes("period=day")).length).toBeGreaterThan(1);
  });

  it("shows empty and unavailable states", async () => {
    mockApi({ posts: [], sales: [], projects: [], sales404: true });
    render(<ProductivityPage />);
    expect(await screen.findByText("No sales yet.")).toBeInTheDocument();
    expect(screen.getAllByText("Not available")).toHaveLength(3);
  });
});

describe("Productivity page — projects", () => {
  it("renders project cards with status, priority, progress, next action and overdue due date", async () => {
    mockApi({ posts: [], sales: [], projects: [PROJECT] });
    render(<ProductivityPage />);
    const list = await screen.findByRole("list", { name: "Projects" });
    const card = within(list);
    expect(card.getByText("Website")).toBeInTheDocument();
    expect(card.getByText("active")).toBeInTheDocument();
    expect(card.getByText("high priority")).toBeInTheDocument();
    expect(card.getByRole("progressbar", { name: "Website progress" })).toHaveAttribute("aria-valuenow", "40");
    expect(card.getByText("Ship pricing page")).toBeInTheDocument();
    expect(card.getByText(/Overdue/)).toBeInTheDocument();
  });

  it("quick-adds and edits a project", async () => {
    const calls = mockApi({ posts: [], sales: [], projects: [PROJECT] });
    render(<ProductivityPage />);
    const quick = await screen.findByRole("form", { name: "Quick add project" });
    await userEvent.type(within(quick).getByLabelText("New project"), "Podcast");
    await userEvent.click(within(quick).getByRole("button", { name: "Add project" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({ name: "Podcast" }));

    await userEvent.click(screen.getByRole("button", { name: "Edit Website" }));
    const dialog = screen.getByRole("dialog", { name: "Edit project" });
    const progress = within(dialog).getByLabelText("Progress (%)");
    await userEvent.clear(progress);
    await userEvent.type(progress, "150");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save project" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Progress must be a whole number from 0 to 100.");

    await userEvent.clear(progress);
    await userEvent.type(progress, "75");
    await userEvent.selectOptions(within(dialog).getByLabelText("Status"), "blocked");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save project" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toMatchObject({ progress: 75, status: "blocked", dueDate: "2000-01-01" }));
  });

  it("shows the empty state", async () => {
    mockApi({ posts: [], sales: [], projects: [] });
    render(<ProductivityPage />);
    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
  });

  it("surfaces a server validation message when saving fails", async () => {
    mockApi({ posts: [], sales: [], projects: [] });
    const base = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve({ ok: false, status: 422, json: () => Promise.resolve({ message: "Name is too long." }) } as Response)
        : base(input, init)));
    render(<ProductivityPage />);
    const quick = await screen.findByRole("form", { name: "Quick add project" });
    await userEvent.type(within(quick).getByLabelText("New project"), "X");
    await userEvent.click(within(quick).getByRole("button", { name: "Add project" }));
    expect(await screen.findByText("Name is too long.")).toBeInTheDocument();
  });
});

describe("Productivity routing and helpers", () => {
  it("is in the page routes and the command palette", () => {
    const commands = buildCommands(() => undefined, "/");
    const entry = commands.find((c) => c.id === "go-productivity");
    expect(entry?.label).toBe("Go to Productivity");
    expect(filterCommands(commands, "productivity").map((c) => c.id)).toContain("go-productivity");
    expect(filterCommands(commands, "sales").map((c) => c.id)).toContain("go-productivity");
  });

  it("renders at /productivity inside the shell with a nav link", async () => {
    mockApi({ posts: [], sales: [], projects: [] });
    render(<MemoryRouter initialEntries={["/productivity"]}><ShellRoutes /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Productivity", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Productivity" }).length).toBeGreaterThan(0);
  });

  it("computes trend percent and sparkline geometry", () => {
    const base = { period: "week", currency: "NPR", total: 0, count: 0, series: [] } as const;
    const withTrend = (t: Partial<SalesSummary["trend"]>) => ({ ...base, trend: { previousTotal: 0, change: 0, changePct: null, direction: "flat", ...t } }) as SalesSummary;
    expect(trendPercent(withTrend({ changePct: 12.5 }))).toBe(12.5);
    expect(trendPercent(withTrend({ previousTotal: 200, change: 50 }))).toBe(25);
    expect(trendPercent(withTrend({}))).toBeNull();
    expect(sparklinePoints([], 100, 20)).toBe("");
    expect(sparklinePoints([0, 10], 100, 20, 0)).toBe("0.0,20.0 100.0,0.0");
    expect(sparklinePoints([5, 5], 100, 20, 0).split(" ")).toHaveLength(2);
  });
});
