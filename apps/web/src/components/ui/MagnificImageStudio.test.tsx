import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MagnificImageStudio } from "./MagnificImageStudio";

const jsonResponse = (body: unknown, ok = true) => ({
  ok,
  json: async () => body,
}) as Response;

describe("MagnificImageStudio", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("URL", Object.assign(URL, {
      createObjectURL: vi.fn(() => "blob:protected-image"),
      revokeObjectURL: vi.fn(),
    }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts an enhanced cloud job and shows the proxied result without leaking the localhost origin", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/generated-images/abc") return { ok: true, blob: async () => new Blob(["image"], { type: "image/png" }) } as Response;
      if (url === "/api/v1/tools/execute") {
        return jsonResponse({
          status: "processing",
          job_id: "set-9",
          renderer: "magnific-flux",
          enhanced_prompt: "a cat, soft key lighting, masterpiece",
        });
      }
      if (url.includes("/api/v1/tools/poll?job_id=set-9")) {
        return jsonResponse({
          id: "set-9",
          status: "completed",
          total: 1,
          prompt: "a cat",
          mode: "quality",
          error: null,
          images: ["http://127.0.0.1:8000/v1/generated-images/abc"],
          slots: [
            { id: "abc", index: 1, status: "completed", seed: 7, url: "http://127.0.0.1:8000/v1/generated-images/abc" },
          ],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MagnificImageStudio storageScope="test-user" onClose={() => undefined} />);

    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "a cat" } });
    fireEvent.click(screen.getByRole("button", { name: /Anime/ }));
    fireEvent.click(screen.getByRole("button", { name: /Generate with Magnific/ }));

    await waitFor(
      () => expect(screen.getByAltText("Generated 1")).toBeInTheDocument(),
      { timeout: 4_000 },
    );
    // localhost image URLs are normalised onto the web proxy so the preview host can load them
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/v1/generated-images/abc")).toBe(true);
    expect(screen.getByAltText("Generated 1")).toHaveAttribute("src", "blob:protected-image");
    // the enhanced prompt is surfaced, and the request carries style + enhance defaults
    expect(await screen.findByText("a cat, soft key lighting, masterpiece")).toBeInTheDocument();
    const execCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/v1/tools/execute");
    const body = JSON.parse(String((execCall?.[1] as RequestInit)?.body));
    expect(body.parameters.style).toBe("anime");
    expect(body.parameters.enhance).toBe(true);
    expect(body.parameters.prompt).toBe("a cat");
    expect(body.confirmed).toBe(true);
    expect(body.approvalSource).toBe("user");
  });

  it("surfaces a key failure verbatim and never polls a job that was not created", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/image-studio/status") return jsonResponse({ renderer: "magnific-flux", detail: "", setup: [] });
      if (url === "/api/v1/tools/execute") {
        return jsonResponse({
          status: "error",
          code: "MAGNIFIC_KEY_INVALID",
          error: "Magnific rejected the API key. Update MAGNIFIC_API_KEY in apps/api/.env.local.",
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MagnificImageStudio storageScope="test-user" onClose={() => undefined} />);
    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "sunset ridge" } });
    fireEvent.click(screen.getByRole("button", { name: /Generate with Magnific/ }));

    expect(await screen.findByText(/Magnific rejected the API key/)).toBeInTheDocument();
    // exactly one execute call — and crucially, zero poll calls for a job that was never created
    const calls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(calls.filter((u) => u === "/api/v1/tools/execute")).toHaveLength(1);
    expect(calls.some((u) => u.includes("/api/v1/tools/poll"))).toBe(false);
  });

  it("keeps generation gated until a prompt exists", () => {
    render(<MagnificImageStudio onClose={() => undefined} />);
    expect(screen.getByRole("button", { name: /Generate with Magnific/ })).toBeDisabled();
  });

  it("restores only the current owner's job and stops observation without cancelling it", async () => {
    localStorage.setItem("hinaa.image-studio.job:alice", "set-alice");
    localStorage.setItem("hinaa.image-studio.job:bob", "set-bob");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("image-studio/status")) return jsonResponse({ renderer: "magnific-flux", state: "unverified", detail: "Key detected; generation not verified.", setup: [] });
      if (url.includes("tools/poll")) return jsonResponse({ status: "processing", completed: 0, total: 1, slots: [{ id: "a", status: "processing", index: 1 }] });
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<MagnificImageStudio storageScope="alice" />);
    await screen.findByText("Rendering image 1 of 1…");
    expect(screen.getByText(/configured · unverified/)).toBeInTheDocument();
    expect(screen.queryByText(/online/)).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("set-bob"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Stop watching" }));
    expect(screen.getByText(/does not cancel provider generation/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resume watching" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("tools/poll"))).toHaveLength(2));
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("execute"))).toBe(false);
    unmount();
    render(<MagnificImageStudio storageScope="alice" />);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("tools/poll"))).toHaveLength(3));
  });

  it("aborts an in-flight poll when closed and retains the opaque recovery reference", async () => {
    localStorage.setItem("hinaa.image-studio.job:alice", "set-alice");
    let pollSignal: AbortSignal | null | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes("tools/poll")) {
        pollSignal = init?.signal;
        return new Promise(() => undefined);
      }
      return Promise.resolve(jsonResponse({ renderer: "none", state: "offline", setup: [] }));
    }));
    const { unmount } = render(<MagnificImageStudio storageScope="alice" />);
    await waitFor(() => expect(pollSignal).toBeDefined());
    unmount();
    expect(pollSignal?.aborted).toBe(true);
    expect(localStorage.getItem("hinaa.image-studio.job:alice")).toBe("set-alice");
  });

  it("does not call a completed job without artifacts a successful generation", async () => {
    localStorage.setItem("hinaa.image-studio.job:alice", "empty-job");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).includes("tools/poll")
      ? jsonResponse({ id: "empty-job", status: "completed", total: 0, images: [], slots: [], error: null })
      : jsonResponse({ renderer: "none", state: "offline", setup: [] })));
    render(<MagnificImageStudio storageScope="alice" />);
    expect(await screen.findByText("The job ended without a downloadable image.")).toBeInTheDocument();
    expect(screen.queryByText(/0 images ready/)).not.toBeInTheDocument();
  });

  it("stops watching a partially failed job and says which output broke", async () => {
    localStorage.setItem("hinaa.image-studio.job:alice", "set-partial");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => String(input).includes("tools/poll")
      ? jsonResponse({
        id: "set-partial",
        status: "completed",
        total: 2,
        images: ["/api/v1/generated-images/one"],
        slots: [
          { id: "one", index: 1, status: "completed", seed: 4, url: "/api/v1/generated-images/one" },
          { id: "two", index: 2, status: "failed", seed: 5, url: null },
        ],
        error: "Image 2 failed",
      })
      : jsonResponse({ renderer: "none", state: "offline", setup: [] }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MagnificImageStudio storageScope="alice" />);
    expect(await screen.findByText("1 of 2 images are ready — Image 2 failed.")).toBeInTheDocument();
    await new Promise((resolve) => window.setTimeout(resolve, 1_800));
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("tools/poll"))).toHaveLength(1);
  });
});
