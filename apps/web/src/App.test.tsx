import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App, { isHinaApiUrl } from "./App";
import { buildMockPlan } from "./features/providers/mockConversationProvider";

class FakeUtterance {
  lang = "";
  rate = 1;
  pitch = 1;
  volume = 1;
  voice: SpeechSynthesisVoice | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly text: string) {}
}

function resetHinaaStorage(): void {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("hinaa")) localStorage.removeItem(key);
  }
}

describe("HINAA assistant workspace", () => {
  beforeEach(() => {
    resetHinaaStorage();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    resetHinaaStorage();
  });

  it("renders the Sakura OS navigation rail", () => {
    render(<App />);
    expect(screen.getByTestId("executive-nav-sidebar")).toBeInTheDocument();
  });

  it("renders Chat, Dashboard, and Models navigation destinations", () => {
    render(<App />);
    expect(screen.getAllByRole("button", { name: "Chat" })[0]).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Dashboard" })[0]).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Models" })[0]).toBeInTheDocument();
  });

  it("shows the Work mode text composer", () => {
    render(<App />);
    const composer = screen.getByPlaceholderText("Ask HINA anything — chat mode...");
    expect(composer).toBeInTheDocument();
  });

  it("does not claim an agent cluster the backend does not run", () => {
    render(<App />);
    const text = document.body.textContent || "";
    expect(text).not.toMatch(/agent cluster/i);
    expect(text).not.toMatch(/cluster on/i);
    expect(text).not.toMatch(/4\s*(parallel\s+)?workers?/i);
  });

  it("shows welcome actions in Work mode", () => {
    render(<App />);
    // Welcome cards should be visible in Work mode
    const research = screen.getAllByRole("button").find(el => el.textContent?.includes("Research"));
    const create = screen.getAllByRole("button").find(el => el.textContent?.includes("Create"));
    expect(research).toBeDefined();
    expect(create).toBeDefined();
  });

  it("system errors do not appear in the conversation", () => {
    render(<App />);
    expect(screen.queryByText(/safety limit/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/microphone frame was lost/i)).not.toBeInTheDocument();
  });

  it("speaks one concise spokenText utterance for a completed typed Demo turn", async () => {
    const speak = vi.fn();
    vi.stubGlobal("speechSynthesis", { getVoices: () => [], speak, cancel: vi.fn() });
    vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
    vi.stubGlobal("AudioContext", undefined);
    localStorage.setItem("hinaa_settings_v1", JSON.stringify({
      _version: 7,
      appearance: { theme: "system", motion: "system", avatarVisible: true, avatarStyle: "procedural" },
      provider: { preferredMode: "mock", preferredModelByProvider: {} },
      language: { activePolicy: "en-US" },
      automation: { autoRunTools: false },
    }));
    render(<App />);

    const composer = screen.getByPlaceholderText("Ask HINA anything — chat mode...");
    fireEvent.change(composer, { target: { value: "Give me a quick status update." } });
    fireEvent.keyDown(composer, { key: "Enter" });

    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1), { timeout: 6_000 });
    const utterance = speak.mock.calls[0][0] as FakeUtterance;
    expect(utterance.text).toBeTruthy();
    expect(utterance.text).not.toContain("```");
    utterance.onend?.();
  }, 10_000);

  async function sendAttachedPicture(roleLabel: string): Promise<any> {
    localStorage.setItem("hinaa_settings_v1", JSON.stringify({
      _version: 7,
      appearance: { theme: "system", motion: "system", avatarVisible: true, avatarStyle: "procedural" },
      provider: { preferredMode: "claude", preferredModelByProvider: {} },
      language: { activePolicy: "en-US" },
      automation: { autoRunTools: false },
    }));
    vi.stubGlobal("speechSynthesis", { getVoices: () => [], speak: vi.fn(), cancel: vi.fn() });
    vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
    vi.stubGlobal("AudioContext", undefined);

    const turns: any[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).includes("/conversations/turns:stream")) {
          const body = JSON.parse(String(init?.body));
          turns.push(body);
          const plan = buildMockPlan("Reference locked.", "hinaa");
          return new Response(`${JSON.stringify({ type: "plan", plan })}\n`, {
            status: 200,
            headers: { "Content-Type": "application/x-ndjson" },
          });
        }
        return new Response("{}", { status: 404, headers: { "Content-Type": "application/json" } });
      }),
    );

    render(<App />);

    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).not.toBeNull();
    fireEvent.change(fileInput as HTMLInputElement, {
      target: { files: [new File([new Uint8Array([137, 80, 78, 71])], "face.png", { type: "image/png" })] },
    });

    const chip = await screen.findByText("Role: Style");
    fireEvent.click(chip);
    fireEvent.click(screen.getByText(roleLabel));

    const composer = screen.getByPlaceholderText("Ask HINA anything — chat mode...");
    fireEvent.change(composer, { target: { value: "make it like this" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    await waitFor(() => expect(turns.length).toBeGreaterThan(0), { timeout: 8_000 });
    return turns[0];
  }

  it("sends an attached picture and the role chosen for it in the same turn", async () => {
    const turnBody = await sendAttachedPicture("Face Identity");

    expect(turnBody.text).toBe("make it like this");
    expect(String(turnBody.imageUrl)).toMatch(/^data:image\/png;base64,/);
    expect(turnBody.attachments).toEqual([
      { kind: "image", role: "face_reference", url: turnBody.imageUrl },
    ]);
    // The image workflow only takes a reference from this field, so a face
    // reference that never reaches it cannot be honoured by a draw.
    expect(turnBody.reference_images).toEqual([turnBody.imageUrl]);
  }, 20_000);

  it("keeps a look-at-this picture out of the reference-editing path", async () => {
    const turnBody = await sendAttachedPicture("General Inspection");

    expect(turnBody.attachments).toEqual([
      { kind: "image", role: "inspection", url: turnBody.imageUrl },
    ]);
    expect(turnBody.reference_images).toBeUndefined();
  }, 20_000);

  it.todo("starts live voice only after the user grants microphone permission");
  it.todo("offers a visible confirmation before executing an external assistant action");
});

describe("URLs that earn the Clerk token", () => {
  const origin = window.location.origin;

  it("matches the relative paths every call site uses today", () => {
    expect(isHinaApiUrl("/api/v1/conversations/turns:stream")).toBe(true);
    expect(isHinaApiUrl("/v1/providers")).toBe(true);
    expect(isHinaApiUrl("/health")).toBe(false);
  });

  it("matches absolute URLs to this origin, the shape a tunnelled API base takes", () => {
    expect(isHinaApiUrl(`${origin}/api/v1/capabilities`)).toBe(true);
    expect(isHinaApiUrl(`${origin}/v1/tasks/abc/events`)).toBe(true);
    expect(isHinaApiUrl(`${origin}/health`)).toBe(false);
  });

  it("never matches a foreign host, whatever path it exposes", () => {
    expect(isHinaApiUrl("https://third-party.example.com/api/v1/turns:stream")).toBe(false);
    expect(isHinaApiUrl("https://third-party.example.com/v1/providers")).toBe(false);
  });
});
