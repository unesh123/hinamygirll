import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResponseMarkdown } from "./ResponseMarkdown";

describe("ResponseMarkdown", () => {
  it("renders nested Markdown, headings, lists and GFM tables", () => {
    render(<ResponseMarkdown text={'## Haan bro 🌸\n\n- **Ready** with `code`\n  1. nested\n\n| Result | Status |\n| --- | --- |\n| PDF | ready |'} />);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Haan bro 🌸");
    expect(screen.getByText("Ready").tagName).toBe("STRONG");
    expect(screen.getAllByRole("list")).toHaveLength(2);
    expect(screen.getByRole("table")).toHaveTextContent("PDFready");
  });

  it("neutralizes raw HTML and unsafe links while keeping safe links", () => {
    const { container } = render(<ResponseMarkdown text={'<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[unsafe](javascript:evil) [data](data:text/html,evil) [obfuscated](java&#x73;cript:evil) [safe](https://example.com)'} />);
    expect(container.querySelector("script, img, iframe")).toBeNull();
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "safe" })).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("preserves the last line and blank lines in an unfinished streaming code fence", () => {
    const { container, rerender } = render(<ResponseMarkdown text={'```python\nprint("**literal**")\n\nlast_line'} />);
    expect(container.querySelector("pre code")?.textContent).toBe('print("**literal**")\n\nlast_line\n');
    expect(container.querySelector("pre strong")).toBeNull();
    rerender(<ResponseMarkdown text={'```python\nprint("**literal**")\n\nlast_line\n```'} />);
    expect(container.querySelector("pre code")?.textContent).toBe('print("**literal**")\n\nlast_line\n');
  });

  it("copies the code without the toolbar and reports clipboard failure", async () => {
    const writeText = vi.fn().mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error("denied"));
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<ResponseMarkdown text={'```js\nconst x = "<hello>";\n```'} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy code" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Code copied"));
    expect(writeText).toHaveBeenCalledWith('const x = "<hello>";\n');
    fireEvent.click(screen.getByRole("button", { name: "Copy code" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Unable to copy code"));
  });
});
