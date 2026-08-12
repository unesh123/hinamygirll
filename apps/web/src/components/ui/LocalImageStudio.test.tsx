import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocalImageStudio } from "./LocalImageStudio";

const jsonResponse = (body: unknown, ok = true) => ({
  ok,
  json: async () => body,
}) as Response;

describe("LocalImageStudio", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reveals the first completed local image while later sequential slots remain pending", async () => {
    let pollCount = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/local-services/comfyui") return jsonResponse({ status: "ready" });
      if (url === "/api/v1/tools/execute") return jsonResponse({ job_id: "set-1" });
      if (url.includes("/api/v1/tools/poll?job_id=set-1")) {
        pollCount += 1;
        return jsonResponse(pollCount === 1
          ? {
              status: "processing", completed: 1, total: 2,
              images: ["http://127.0.0.1:8000/v1/generated-images/first"],
              slots: [
                { id: "first", index: 1, status: "completed", seed: 42, url: "http://127.0.0.1:8000/v1/generated-images/first" },
                { id: "second", index: 2, status: "pending", seed: 43, url: null },
              ],
            }
          : {
              status: "success", completed: 2, total: 2,
              images: ["http://127.0.0.1:8000/v1/generated-images/first", "http://127.0.0.1:8000/v1/generated-images/second"],
              slots: [
                { id: "first", index: 1, status: "completed", seed: 42, url: "http://127.0.0.1:8000/v1/generated-images/first" },
                { id: "second", index: 2, status: "completed", seed: 43, url: "http://127.0.0.1:8000/v1/generated-images/second" },
              ],
            });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<LocalImageStudio onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText("ComfyUI ready on this device")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Image prompt"), { target: { value: "Hinaa in a neon studio" } });
    fireEvent.change(screen.getByLabelText("Image count"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Image seed"), { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate images" }));

    await waitFor(() => expect(screen.getByAltText("Generated image 1")).toBeInTheDocument(), { timeout: 3_000 });
    expect(screen.getByText("Image 1 · seed 42")).toBeInTheDocument();
    expect(screen.getByText("Image 2")).toBeInTheDocument();
    expect(screen.getByText("Waiting for its sequential turn")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => String(init?.body).includes('"seed":42'))).toBe(true);
  });
});
