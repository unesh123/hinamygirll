import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResponseMarkdown, protectCurrencyDollars } from "./ResponseMarkdown";

describe("ResponseMarkdown highlighting and math", () => {
  it("highlights known languages with hljs token spans and keeps the language label", () => {
    const { container } = render(<ResponseMarkdown text={'```python\ndef add(a, b):\n    return a + b  # sum\n```'} />);
    expect(container.querySelector("pre code.hljs.language-python")).not.toBeNull();
    expect(container.querySelectorAll("pre code .hljs-keyword").length).toBeGreaterThan(0);
    expect(container.querySelector("pre code .hljs-comment")).toHaveTextContent("# sum");
    expect(screen.getByText("PYTHON")).toBeInTheDocument();
  });

  it("copies the exact plain code text despite highlight spans", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const code = 'const total = items.reduce((a, b) => a + b, 0); // "sum"\n';
    render(<ResponseMarkdown text={"```ts\n" + code + "```"} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy code" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(code));
  });

  it("does not throw on unknown languages and leaves the text intact", () => {
    const { container } = render(<ResponseMarkdown text={'```nepalilang\nnamaste ho\n```'} />);
    expect(container.querySelector("pre code")?.textContent).toBe("namaste ho\n");
    expect(screen.getByText("NEPALILANG")).toBeInTheDocument();
  });

  it("leaves mermaid, html and svg fences to their dedicated renderers", () => {
    const { container } = render(
      <ResponseMarkdown text={'```mermaid\ngraph TD\n  A --> B\n```\n\n```html\n<div class="x">Hi</div>\n```\n\n```svg\n<svg></svg>\n```'} />,
    );
    expect(screen.getByText("Architecture Blueprint")).toBeInTheDocument();
    expect(screen.getAllByText("Interactive Artifact")).toHaveLength(2);
    expect(container.querySelector(".hljs")).toBeNull();
    expect(container.textContent).not.toContain("[object Object]");
  });

  it("does not highlight inline code", () => {
    const { container } = render(<ResponseMarkdown text={"Use `return x` here"} />);
    expect(container.querySelector("code.hljs, code .hljs-keyword")).toBeNull();
  });

  it("renders inline and display math with KaTeX", () => {
    const { container } = render(<ResponseMarkdown text={"Inline $x^2$ and\n\n$$\n\\int_0^1 x\\,dx = \\frac12\n$$"} />);
    expect(container.querySelectorAll(".katex").length).toBe(2);
    expect(container.querySelector(".katex-display")).not.toBeNull();
    expect(container.querySelector("p .katex")).not.toBeNull();
  });

  it("renders ```math fences with KaTeX instead of highlighting them", () => {
    const { container } = render(<ResponseMarkdown text={"```math\nE = mc^2\n```"} />);
    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector(".hljs")).toBeNull();
  });

  it("keeps currency dollars as text", () => {
    const { container } = render(<ResponseMarkdown text={"It costs $5 and $10, or $1,200.50 total. Rs. 500 is cheaper."} />);
    expect(container.querySelector(".katex")).toBeNull();
    expect(container.textContent).toBe("It costs $5 and $10, or $1,200.50 total. Rs. 500 is cheaper.");
  });

  it("does not touch dollars inside code or real math", () => {
    expect(protectCurrencyDollars("```sh\necho $5 $10\n```")).toBe("```sh\necho $5 $10\n```");
    expect(protectCurrencyDollars("run `echo $5` now")).toBe("run `echo $5` now");
    expect(protectCurrencyDollars("math $x$ and $$a$$ and $5$")).toBe("math $x$ and $$a$$ and $5$");
    expect(protectCurrencyDollars("pay $5 now")).toBe("pay \\$5 now");
  });

  it("does not throw on partial or invalid math while streaming", () => {
    for (const text of ["text $$\\int", "text $$\n\\frac{1", "inline $\\frac{a$ done", "$$\\badmacro{x}$$"]) {
      expect(() => render(<ResponseMarkdown text={text} streaming />)).not.toThrow();
    }
  });

  it("still strips raw HTML", () => {
    const { container } = render(<ResponseMarkdown text={"<script>alert(1)</script>\n\nmath $x$"} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector(".katex")).not.toBeNull();
  });
});
