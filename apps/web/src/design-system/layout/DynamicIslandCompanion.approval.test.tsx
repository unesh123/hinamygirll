import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DynamicIslandCompanion } from "./DynamicIslandCompanion";
import { WorkMode } from "../modes/WorkMode";
import { useCompanionController } from "../../features/companion/useCompanionController";
import type { ActiveLanguagePolicy } from "../../features/settings/types/settings";

const DEFAULT_TEST_LANGUAGE_POLICY: ActiveLanguagePolicy = {
  primaryLanguage: "en-US",
  mode: "auto",
  secondaryLanguages: [],
  hinglishEnabled: false,
} as unknown as ActiveLanguagePolicy;

describe("Robot HUD & Upper Build Dock Approval UI", () => {
  it("removes fake VAT/billing demo tasks and renders high-contrast light approval controls", () => {
    const onConfirm = vi.fn();
    render(
      <DynamicIslandCompanion
        isDark={false}
        pendingApproval={{
          stepId: "appr-1",
          actionName: "workspace_run_command",
          command: "pnpm build",
          detail: "Verify production frontend bundle",
        }}
        onConfirmStep={onConfirm}
      />,
    );

    expect(screen.queryByText(/Fix the VAT rounding/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/src\/billing\.ts/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Failed once, fixed on try 2/i)).not.toBeInTheDocument();

    const card = screen.getByTestId("island-approval-card");
    expect(card).toHaveTextContent("pnpm build");
    expect(card).toHaveTextContent("Verify production frontend bundle");

    const allowBtn = screen.getByRole("button", { name: "Allow" });
    const denyBtn = screen.getByRole("button", { name: "Deny" });
    expect(allowBtn).not.toBeDisabled();
    expect(denyBtn).not.toBeDisabled();
    // Light mode contrast: Deny must never be white-on-white
    expect(denyBtn.style.color).not.toBe("rgb(255, 255, 255)");
    expect(allowBtn.style.background).toBe("rgb(15, 23, 42)");

    fireEvent.click(allowBtn);
    expect(onConfirm).toHaveBeenCalledWith(true);
    fireEvent.click(denyBtn);
    expect(onConfirm).toHaveBeenCalledWith(false);
  });

  it("shows Allowing loading state and surfaces inline approval errors", () => {
    render(
      <DynamicIslandCompanion
        isDark={false}
        pendingApproval={{
          stepId: "appr-2",
          actionName: "workspace_write_file",
          command: "workspace_write_file index.html",
        }}
        approvalPending
        approvalError="Approval failed (500)"
        onConfirmStep={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Allowing..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deny" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Approval failed (500)");
  });

  it("keeps Upper-End Live Build Dock visible while WorkMode chat composer stays enabled", () => {
    const onConfirmAgentStep = vi.fn();
    const onCancelBackgroundBuild = vi.fn();

    render(
      <WorkMode
        companionState="idle"
        messages={[
          { id: "m1", role: "user", text: "Build a dark Merlin AI workspace", timestamp: Date.now() },
          { id: "m2", role: "assistant", text: "Which color accent do you prefer?", timestamp: Date.now() },
        ]}
        streamingText=""
        partialTranscript=""
        isThinking={false}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        onStop={vi.fn()}
        disabled={false}
        isVoiceActive={false}
        onStartVoice={vi.fn()}
        onStopVoice={vi.fn()}
        voiceFeedback={{ kind: "idle", label: "" }}
        powerUps={[]}
        onPowerUpToggle={vi.fn()}
        onResolveTool={vi.fn()}
        autoRunTools={false}
        agentSteps={[{ id: "s1", label: "Scaffolding hero section", status: "active", detail: "index.html" }]}
        backgroundBuild={{ runId: "run-bg-1", goal: "Build dark Merlin UI", status: "running" }}
        pendingApproval={{
          stepId: "appr-work-1",
          actionName: "workspace_run_command",
          command: "npm run build",
          detail: "Compile production bundle",
        }}
        onConfirmAgentStep={onConfirmAgentStep}
        onCancelBackgroundBuild={onCancelBackgroundBuild}
        onWelcomeAction={vi.fn()}
        attachedImage={null}
        onImageAttach={vi.fn()}
      />,
    );

    const hud = screen.getByTestId("upper-build-hud");
    expect(hud).toHaveTextContent("Build dark Merlin UI");
    expect(hud).toHaveTextContent("npm run build");

    const composer = screen.getByRole("textbox", { name: "Message HINAA" });
    expect(composer).not.toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Allow" }));
    expect(onConfirmAgentStep).toHaveBeenCalledWith(true);

    fireEvent.click(screen.getByRole("button", { name: "Stop build" }));
    expect(onCancelBackgroundBuild).toHaveBeenCalledTimes(1);
  });

  it("sends background=true and identity headers when approving an agentic step via controller", async () => {
    const encoder = new TextEncoder();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("turns:stream")) {
        const bodyLines = [
          JSON.stringify({
            type: "agent.step.started",
            runId: "run-ctrl-1",
            stepId: "step-1",
            sequence: 1,
            timestamp: new Date().toISOString(),
            label: "Inspecting workspace",
          }),
          JSON.stringify({
            type: "confirmation.required",
            runId: "run-ctrl-1",
            stepId: "appr-ctrl-1",
            sequence: 2,
            timestamp: new Date().toISOString(),
            tool: "workspace_run_command",
            arguments_hash: "hash-xyz-123",
            command: "npm run build",
            reason: "Verify local bundle",
          }),
        ].join("\n") + "\n";
        return new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(bodyLines));
              controller.close();
            },
          }),
          { status: 200, headers: { "Content-Type": "application/x-ndjson" } },
        );
      }
      if (url.includes("/approve")) {
        return new Response(
          JSON.stringify({ run_id: "run-ctrl-1", result: { run_id: "run-ctrl-1", status: "running" } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/stream")) {
        const finalFrame = JSON.stringify({
          type: "agentic.finalized",
          runId: "run-ctrl-1",
          status: "completed",
          summary: "Built cleanly.",
          markdown: "### Build Ready\nBuilt cleanly.",
        }) + "\n";
        return new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(finalFrame));
              controller.close();
            },
          }),
          { status: 200, headers: { "Content-Type": "application/x-ndjson" } },
        );
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    vi.stubGlobal("fetch", fetchMock);
    try {
      const { result } = renderHook(() =>
        useCompanionController({
          conversationId: "conv-appr-test",
          routing: { activeMode: "mock", activeModel: "mock-model" } as any,
          languagePolicy: DEFAULT_TEST_LANGUAGE_POLICY,
        }),
      );

      await act(async () => {
        await result.current.sendText("Build local page", { forceBackend: true });
      });

      await waitFor(() => {
        expect(result.current.currentAgentApprovalInfo?.command).toBe("npm run build");
      });

      await act(async () => {
        await result.current.confirmCurrentAgentStep(true);
      });

      const approveCall = fetchMock.mock.calls.find(([u]) => String(u).includes("/approve"));
      expect(approveCall).toBeDefined();
      const [, init] = approveCall!;
      expect(JSON.parse(String(init?.body))).toMatchObject({
        approved: true,
        argumentsHash: "hash-xyz-123",
        background: true,
      });
      await waitFor(() => {
        expect(result.current.backgroundBuild?.status).toBe("completed");
      });
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("handles agent.progress_update milestones cleanly in Upper HUD, live thread, and CompanionStage", async () => {
    const encoder = new TextEncoder();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("turns:stream")) {
        const bgStart =
          JSON.stringify({ type: "agentic.background", runId: "run-prog-1", goal: "Build SORA" }) +
          "\n" +
          JSON.stringify({
            type: "plan",
            plan: {
              spokenText: "Started SORA builder.",
              displayText: "Started SORA builder! What accent glow should lead?",
              language: "en-US",
              emotion: { primary: "warm", intensity: 0.7 },
              performance: { expression: "happy", gesture: "nod" },
              memoryCandidates: [],
              toolRequests: [],
            },
          }) +
          "\n" +
          JSON.stringify({ type: "run.completed", status: "completed" }) +
          "\n";
        return new Response(
          new ReadableStream({
            start(c) {
              c.enqueue(encoder.encode(bgStart));
              c.close();
            },
          }),
          { status: 200, headers: { "Content-Type": "application/x-ndjson" } },
        );
      }
      if (url.includes("/agent/agentic-runs/run-prog-1/stream")) {
        const lines =
          JSON.stringify({
            type: "agent.progress_update",
            runId: "run-prog-1",
            phase: "coding",
            headline: "Writing src/App.tsx...",
            filesChanged: ["package.json", "src/App.tsx"],
            previewUrls: ["http://127.0.0.1:4173/"],
          }) +
          "\n" +
          JSON.stringify({
            type: "agentic.finalized",
            runId: "run-prog-1",
            status: "completed",
            summary: "Built SORA cleanly.",
            markdown: "### SORA Built\nVerified desktop and mobile.",
            filesChanged: ["package.json", "src/App.tsx"],
            previewUrls: ["http://127.0.0.1:4173/"],
          }) +
          "\n";
        return new Response(
          new ReadableStream({
            start(c) {
              c.enqueue(encoder.encode(lines));
              c.close();
            },
          }),
          { status: 200, headers: { "Content-Type": "application/x-ndjson" } },
        );
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    vi.stubGlobal("fetch", fetchMock);
    try {
      const { result } = renderHook(() =>
        useCompanionController({
          conversationId: "conv-prog-test",
          routing: { activeMode: "mock", activeModel: "mock-model" } as any,
          languagePolicy: DEFAULT_TEST_LANGUAGE_POLICY,
        }),
      );

      await act(async () => {
        await result.current.sendText("Build SORA hub", { forceBackend: true });
      });

      await waitFor(() => {
        expect(result.current.backgroundBuild?.status).toBe("completed");
      });
      expect(result.current.backgroundBuild?.filesChanged).toEqual(["package.json", "src/App.tsx"]);
      expect(result.current.backgroundBuild?.previewUrls).toEqual(["http://127.0.0.1:4173/"]);
      expect(result.current.messages.some((m) => m.text.includes("SORA Built"))).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }

    render(
      <WorkMode
        companionState="idle"
        messages={[]}
        streamingText=""
        partialTranscript=""
        isThinking={false}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        onStop={vi.fn()}
        disabled={false}
        isVoiceActive={false}
        onStartVoice={vi.fn()}
        onStopVoice={vi.fn()}
        voiceFeedback={{ kind: "idle", label: "" }}
        powerUps={[]}
        onPowerUpToggle={vi.fn()}
        onResolveTool={vi.fn(async () => {})}
        autoRunTools={false}
        agentSteps={[]}
        backgroundBuild={{
          runId: "run-prog-2",
          goal: "Build SORA",
          status: "running",
          phase: "preview",
          headline: "Live preview available at http://127.0.0.1:4173/",
          filesChanged: ["package.json", "src/App.tsx"],
          previewUrls: ["http://127.0.0.1:4173/"],
        }}
        onCancelBackgroundBuild={vi.fn()}
        onWelcomeAction={vi.fn()}
        attachedImage={null}
        onImageAttach={vi.fn()}
      />,
    );
    expect(screen.getByTestId("upper-build-hud")).toHaveTextContent("Live preview available at http://127.0.0.1:4173/");
    expect(screen.getByTestId("upper-build-files-badge")).toHaveTextContent("2 files");
    expect(screen.getByTestId("upper-build-preview-link")).toHaveAttribute("href", "http://127.0.0.1:4173/");
  });
});
