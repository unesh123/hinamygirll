import { describe, expect, it } from "vitest";
import { escapeHtml, renderMarkdownHtml } from "./markdown";

describe("escapeHtml", () => {
  it("escapes the dangerous five", () => {
    expect(escapeHtml(`<img src=x onerror="alert('&')">`)).toBe(
      "&lt;img src=x onerror=&quot;alert(&#39;&amp;&#39;)&quot;&gt;",
    );
  });
});

describe("renderMarkdownHtml", () => {
  it("neutralises raw HTML from model output", () => {
    const html = renderMarkdownHtml("hello <script>document.cookie</script>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("renders links only for safe protocols and drops javascript: urls", () => {
    const ok = renderMarkdownHtml("[docs](https://example.com/a)");
    expect(ok).toContain('<a href="https://example.com/a"');
    const bad = renderMarkdownHtml("[x](javascript:alert(1))");
    expect(bad).not.toContain("<a");
  });

  it("renders fenced code with language chip and escaped body", () => {
    const html = renderMarkdownHtml("```python\nprint('<hi>')\n```");
    expect(html).toContain('<pre class="hinaa-code" data-lang="python">');
    expect(html).toContain("print(&#39;&lt;hi&gt;&#39;)");
  });

  it("keeps inline code contents verbatim (no markdown processing inside)", () => {
    const html = renderMarkdownHtml("use `a **b** c` here");
    expect(html).toContain("<code>a **b** c</code>");
  });

  it("renders tables with head and body cells", () => {
    const html = renderMarkdownHtml("| name | age |\n| --- | --- |\n| Hinaa | 3 |");
    expect(html).toContain('<div class="hinaa-table-wrap"><table class="hinaa-table">');
    expect(html).toContain("<th>name</th>");
    expect(html).toContain("<td>Hinaa</td>");
  });

  it("renders nested ordered/unordered lists", () => {
    const html = renderMarkdownHtml("- one\n  1. nested\n- two");
    expect(html).toContain("<ul><li>one");
    expect(html).toContain("<ol><li>nested</li></ol>");
  });

  it("wraps mentions and tags in companion chip tokens", () => {
    const html = renderMarkdownHtml("ping @hinaa about #research");
    expect(html).toContain('<span class="hinaa-token hinaa-token--mention">@hinaa</span>');
    expect(html).toContain('<span class="hinaa-token hinaa-token--tag">#research</span>');
  });

  it("renders headings, quotes and dividers", () => {
    const html = renderMarkdownHtml("## Title\n\n> quoted line\n\n---");
    expect(html).toContain("<h2>Title</h2>");
    expect(html).toContain("<blockquote><p>quoted line</p></blockquote>");
    expect(html).toContain('<hr class="hinaa-hr" />');
  });
});
