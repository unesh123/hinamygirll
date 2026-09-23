import { fireEvent, render, screen } from "@testing-library/react";
import { act, useState } from "react";
import { flushSync } from "react-dom";
import { describe, expect, it, vi } from "vitest";
import { PowerUpMentions, type CommandItem } from "./PowerUpMentions";

function command(name: string, label: string): CommandItem {
  return {
    name,
    aliases: [],
    label,
    description: `${label} description`,
    descriptionShort: label,
    icon: undefined as unknown as CommandItem["icon"],
    color: "#F36F9C",
    group: "Create",
    inputSchema: {},
    capability: name,
    riskLevel: "read",
    approvalPolicy: "automatic",
    availability: "available",
    executionLocation: "api",
    examples: [],
  };
}

const COMMANDS = [command("research", "Deep Research"), command("generate", "Generate Image")];

/**
 * Reproduces the real defect. The existing tests fire keydown on `window`,
 * which skips the composer entirely and so cannot observe the Enter leak:
 * React attaches its synthetic handler to the root container, so a bubble-phase
 * palette listener only runs after the textarea has already submitted the chat.
 */
function ComposerHarness({
  paletteOpen,
  onSelectCommand,
  onSend,
}: {
  paletteOpen: boolean;
  onSelectCommand: (cmd: CommandItem) => void;
  onSend: () => void;
}) {
  return (
    <>
      <textarea
        data-testid="composer"
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) onSend();
        }}
      />
      {paletteOpen && (
        <PowerUpMentions
          visible
          filter=""
          trigger="/"
          contexts={[]}
          commands={COMMANDS}
          onSelectCommand={onSelectCommand}
          onClose={() => undefined}
        />
      )}
    </>
  );
}

describe("PowerUpMentions keyboard priority", () => {
  it("consumes Enter fired on the textarea instead of submitting the chat", () => {
    const onSelectCommand = vi.fn();
    const onSend = vi.fn();
    render(<ComposerHarness paletteOpen onSelectCommand={onSelectCommand} onSend={onSend} />);

    fireEvent.keyDown(screen.getByTestId("composer"), { key: "Enter", shiftKey: false });

    expect(onSelectCommand).toHaveBeenCalledWith(expect.objectContaining({ name: "research" }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("moves the highlight with ArrowDown through the real event path", () => {
    const onSelectCommand = vi.fn();
    const onSend = vi.fn();
    render(<ComposerHarness paletteOpen onSelectCommand={onSelectCommand} onSend={onSend} />);
    const composer = screen.getByTestId("composer");

    fireEvent.keyDown(composer, { key: "ArrowDown" });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(onSelectCommand).toHaveBeenCalledWith(expect.objectContaining({ name: "generate" }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("still sends the chat normally when the palette is closed", () => {
    const onSelectCommand = vi.fn();
    const onSend = vi.fn();
    render(<ComposerHarness paletteOpen={false} onSelectCommand={onSelectCommand} onSend={onSend} />);

    fireEvent.keyDown(screen.getByTestId("composer"), { key: "Enter", shiftKey: false });

    expect(onSelectCommand).not.toHaveBeenCalled();
    expect(onSend).toHaveBeenCalledOnce();
  });

  /**
   * The registry can resolve after the palette is already open, so the first
   * frame showing a highlighted command may be the frame Enter lands on. Enter
   * must still select there rather than fall through and send the chat.
   */
  it("selects a command the registry added in the same frame Enter lands", () => {
    const onSelectCommand = vi.fn();
    const onSend = vi.fn();
    let pushCommands: (commands: CommandItem[]) => void = () => {};

    function LateRegistryHarness() {
      const [commands, setCommands] = useState<CommandItem[]>([]);
      pushCommands = setCommands;
      return (
        <>
          <textarea
            data-testid="composer"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) onSend();
            }}
          />
          <PowerUpMentions
            visible
            filter=""
            trigger="/"
            contexts={[]}
            commands={commands}
            onSelectCommand={onSelectCommand}
            onClose={() => undefined}
          />
        </>
      );
    }

    render(<LateRegistryHarness />);
    const composer = screen.getByTestId("composer");

    act(() => {
      flushSync(() => pushCommands(COMMANDS));
      composer.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });

    expect(onSelectCommand).toHaveBeenCalledWith(expect.objectContaining({ name: "research" }));
    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("PowerUpMentions", () => {
  it("matches slash queries against /-aliases and surfaces the exact verb first", () => {
    render(<PowerUpMentions visible filter="research" sigil="/" onSelect={() => undefined} onClose={() => undefined} />);
    expect(screen.getByText("Deep Research")).toBeInTheDocument();
  });

  it("moves the selection with ArrowDown and submits the highlighted entry on Enter", () => {
    const onSelect = vi.fn();
    render(<PowerUpMentions visible filter="research" sigil="/" onSelect={onSelect} onClose={() => undefined} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "@research", slash: "/research" }));
  });

  it("closes instead of hijacking Enter when nothing matches", () => {
    const onClose = vi.fn();
    const onSelect = vi.fn();
    render(<PowerUpMentions visible filter="zzzz" sigil="/" onSelect={onSelect} onClose={onClose} />);
    expect(onClose).toHaveBeenCalled();
    expect(onSelect).not.toHaveBeenCalled();
  });
});
