import {render, screen, waitFor, fireEvent} from "@testing-library/react";
import {beforeEach, expect, test, vi} from "vitest";
import {SaaSBridgePanel} from "./SaaSBridgePanel";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok: true, json: async () => url.includes("/status") ? {
    integrations: [{service_id: "outlook", connected: false, status_text: "Microsoft sign-in required", capabilities: ["draft-email"]}],
  } : {agenda: []}})));
});

test("renders the backend schema and disconnected Outlook honestly", async () => {
  render(<SaaSBridgePanel/>);
  expect(await screen.findByText("Microsoft sign-in required")).toBeTruthy();
  expect(screen.getByText("Disconnected")).toBeTruthy();
  expect(screen.getByText("draft-email")).toBeTruthy();
  expect(screen.getByText("No calendar events are connected yet.")).toBeTruthy();
});

test("reports denied inbox access without a fake success", async () => {
  render(<SaaSBridgePanel/>);
  await screen.findByText("Microsoft sign-in required");
  vi.mocked(fetch).mockResolvedValueOnce({ok: false, status: 403, json: async () => ({detail: "Microsoft denied access"})} as Response);
  fireEvent.click(screen.getByText("Read Outlook inbox"));
  await waitFor(() => expect(screen.getByText("Microsoft denied access")).toBeTruthy());
});
