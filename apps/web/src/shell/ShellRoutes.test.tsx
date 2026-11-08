import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ShellRoutes } from "./ShellApp";
import { MODE_STORAGE_KEY, getShellState, registerAppCommands, shell } from "./store";

// The legacy conversation host is covered by App.test.tsx; stub it here.
vi.mock("../App", () => ({ default: () => <div data-testid="legacy-app">legacy app</div> }));

function Where() {
  return <output data-testid="where">{useLocation().pathname}</output>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ShellRoutes />
      <Where />
    </MemoryRouter>,
  );
}

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) } as Response);

beforeEach(() => {
  localStorage.clear();
  shell.reset();
  vi.stubGlobal("fetch", vi.fn(() => jsonResponse({}, 404)));
});
afterEach(() => vi.unstubAllGlobals());

describe("shell router", () => {
  it("redirects / to the persisted mode route", async () => {
    localStorage.setItem(MODE_STORAGE_KEY, "companion");
    shell.reset();
    renderAt("/");
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/companion"));
    expect(await screen.findByTestId("legacy-app")).toBeInTheDocument();
    expect(getShellState().mode).toBe("companion");
  });

  it("hosts the legacy app on /workspace and syncs the mode from the URL", async () => {
    renderAt("/workspace");
    expect(await screen.findByTestId("legacy-app")).toBeInTheDocument();
    expect(getShellState().mode).toBe("workspace");

  });

  it("lazy-loads page routes", async () => {
    renderAt("/integrations");
    expect(await screen.findByRole("heading", { name: "Integrations" })).toBeInTheDocument();
    expect(screen.queryByTestId("legacy-app")).not.toBeInTheDocument();
  });

  it("switches modes from the top bar, keeps the host mounted, and persists the choice", async () => {
    renderAt("/workspace");
    const host = await screen.findByTestId("legacy-app");
    await userEvent.click(screen.getByRole("radio", { name: /companion/i }));
    expect(screen.getByTestId("where")).toHaveTextContent("/companion");
    expect(localStorage.getItem(MODE_STORAGE_KEY)).toBe("companion");
    expect(screen.getByTestId("legacy-app")).toBe(host);
    expect(await screen.findByTestId("legacy-app")).toBeInTheDocument();
    expect(getShellState().mode).toBe("companion");
  });

  it("toggles the mode with Ctrl+.", async () => {
    renderAt("/workspace");
    await screen.findByTestId("legacy-app");
    act(() => { fireEvent.keyDown(window, { key: ".", ctrlKey: true }); });
    expect(screen.getByTestId("where")).toHaveTextContent("/companion");
  });
});

describe("command palette", () => {
  it("opens with Ctrl+K, filters, and navigates on Enter", async () => {
    renderAt("/workspace");
    await screen.findByTestId("legacy-app");
    expect(screen.queryByRole("dialog", { name: "Command palette" })).not.toBeInTheDocument();
    act(() => { fireEvent.keyDown(window, { key: "k", ctrlKey: true }); });
    const input = await screen.findByRole("combobox", { name: "Search commands" });
    await userEvent.type(input, "go to security");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/security"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape and shows an empty state for no matches", async () => {
    renderAt("/workspace");
    await screen.findByTestId("legacy-app");
    act(() => shell.setPalette(true));
    await userEvent.type(await screen.findByRole("combobox"), "zzzzqq");
    expect(screen.getByText("No matching commands")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("switches mode and starts voice through host commands", async () => {
    const startVoice = vi.fn();
    renderAt("/workspace");
    await screen.findByTestId("legacy-app");
    const off = registerAppCommands({ "start-voice": startVoice });
    act(() => shell.setPalette(true));
    await userEvent.type(await screen.findByRole("combobox"), "start voice");
    await userEvent.keyboard("{Enter}");
    expect(startVoice).toHaveBeenCalledTimes(1);

    act(() => shell.setPalette(true));
    await userEvent.type(await screen.findByRole("combobox"), "companion mode");
    await userEvent.keyboard("{Enter}");
    expect(getShellState().mode).toBe("companion");
    expect(screen.getByTestId("where")).toHaveTextContent("/companion");
    off();
  });

  it("opens an inspector panel from the palette", async () => {
    renderAt("/workspace");
    await screen.findByTestId("legacy-app");
    act(() => shell.setPalette(true));
    await userEvent.type(await screen.findByRole("combobox"), "tools panel");
    await userEvent.keyboard("{Enter}");
    expect(await screen.findByRole("tab", { name: "Tools", selected: true })).toBeInTheDocument();
  });

  it("toggles the theme from the top bar", async () => {
    renderAt("/workspace");
    await screen.findByTestId("legacy-app");
    act(() => shell.setTheme("dark"));
    await userEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
  });
});
