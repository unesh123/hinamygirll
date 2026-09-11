import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MagnificImageStudio } from "./MagnificImageStudio";

const jsonResponse = (body: unknown, ok = true) => ({
  ok,
  json: async () => body,
}) as Response;

describe("MagnificImageStudio", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts an enhanced cloud job and shows the proxied result without leaking the localhost origin", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
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
          status: "success",
          completed: 1,
          total: 1,
          images: ["http://127.0.0.1:8000/v1/generated-images/abc"],
          slots: [
            { id: "abc", index: 1, status: "completed", seed: 7, url: "http://127.0.0.1:8000/v1/generated-images/abc" },
          ],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MagnificImageStudio onClose={() => undefined} />);

    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "a cat" } });
    fireEvent.click(screen.getByRole("button", { name: /Anime/ }));
    fireEvent.click(screen.getByRole("button", { name: /Generate with Magnific/ }));

    await waitFor(
      () => expect(screen.getByAltText("Generated 1")).toBeInTheDocument(),
      { timeout: 4_000 },
    );
    // localhost image URLs are normalised onto the web proxy so the preview host can load them
    expect(screen.getByAltText("Generated 1")).toHaveAttribute("src", "/api/v1/generated-images/abc");
    // the enhanced prompt is surfaced, and the request carries style + enhance defaults
    expect(await screen.findByText("a cat, soft key lighting, masterpiece")).toBeInTheDocument();
    const execCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/v1/tools/execute");
    const body = JSON.parse(String((execCall?.[1] as RequestInit)?.body));
    expect(body.parameters.style).toBe("anime");
    expect(body.parameters.enhance).toBe(true);
    expect(body.parameters.prompt).toBe("a cat");
    expect(body.confirmed).toBe(true);
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

    render(<MagnificImageStudio onClose={() => undefined} />);
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
});
