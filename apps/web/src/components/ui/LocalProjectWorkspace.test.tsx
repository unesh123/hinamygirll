import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LocalProjectWorkspace } from "./LocalProjectWorkspace";

const project = { id: "project-1", title: "Private research", description: "A local report workspace" };

function response(payload: unknown) {
  return { ok: true, json: async () => payload } as Response;
}

describe("LocalProjectWorkspace", () => {
  afterEach(() => vi.restoreAllMocks());

  it("builds a deterministic private report from the selected local project", async () => {
    let reportCreated = false;
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/projects") return Promise.resolve(response([project]));
      if (url === "/api/v1/projects/project-1/report" && init?.method === "POST") {
        reportCreated = true;
        return Promise.resolve(response({ id: "report-1", kind: "document", title: "Evidence bundle" }));
      }
      if (url === "/api/v1/projects/project-1") {
        return Promise.resolve(response({
          ...project,
          tasks: [],
          files: [],
          artifacts: reportCreated ? [{ id: "report-1", kind: "document", title: "Evidence bundle" }] : [],
          runs: [],
        }));
      }
      throw new Error(`Unexpected local workspace request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<LocalProjectWorkspace active />);
    await waitFor(() => expect(screen.getByLabelText("Local report title")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Local report title"), { target: { value: "Evidence bundle" } });
    fireEvent.click(screen.getByRole("button", { name: "Build report" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/projects/project-1/report",
      expect.objectContaining({ method: "POST" }),
    ));
    const reportCall = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/report") && (init as RequestInit | undefined)?.method === "POST");
    if (!reportCall) throw new Error("Expected a local report request.");
    expect(JSON.parse(String((reportCall[1] as RequestInit).body))).toEqual({ title: "Evidence bundle" });
    await waitFor(() => expect(screen.getByText("document: Evidence bundle")).toBeInTheDocument());
    expect(screen.getByText(/No model, provider, browser, or external transfer is used/i)).toBeInTheDocument();
  });
});
