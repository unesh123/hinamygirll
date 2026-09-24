/**
 * markdown.ts — HINAA's structured response renderer.
 *
 * Turns the assistant's markdown into real document furniture: headings,
 * lists (nested), tables, fenced code with a language tag, blockquotes,
 * dividers, links, and the companion's @/# mention chips. Everything is
 * escaped first, so no raw HTML from a model response can reach the DOM.
 *
 * Dependency-free by design: MessageBubble already renders through
 * dangerouslySetInnerHTML and this module is hot on every stream frame.
 */

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (ch) => ESCAPES[ch] ?? ch);
}

const URL_SAFE = /^(https?:|mailto:|#|\/)/i;

function inline(md: string): string {
  let out = escapeHtml(md);
  // Inline code first so its contents are not re-processed.
  const codeStubs: string[] = [];
  out = out.replace(/`([^`\n]+)`/g, (_m, code: string) => {
    codeStubs.push(code);
    return `\u0000C${codeStubs.length - 1}\u0000`;
  });
  // Links [label](url)
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, label: string, url: string) =>
    URL_SAFE.test(url)
      ? `<a href="${url}" target="_blank" rel="noopener">${label}</a>`
      : label,
  );
  // Bold, italic, strike
  out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  out = out.replace(/~~([^~\n]+)~~/g, "<del>$1</del>");
  // @ power-ups and # tags keep the companion's chip language.
  out = out.replace(
    /(^|\s)(@[a-zA-Z0-9_]+)/g,
    '$1<span class="hinaa-token hinaa-token--mention">$2</span>',
  );
  out = out.replace(
    /(^|\s)(#[a-zA-Z0-9_]+)/g,
    '$1<span class="hinaa-token hinaa-token--tag">$2</span>',
  );
  // Restore code stubs.
  // eslint-disable-next-line no-control-regex -- sentinels are deliberate NUL-wrapped
    out = out.replace(/\u0000C(\d+)\u0000/g, (_m, idx: string) => `<code>${escapeHtml(codeStubs[Number(idx)] ?? "")}</code>`);
  return out;
}

function isTableSeparator(line: string): boolean {
  return /^\s*\|?[\s:-]*-{2,}[\s|:-]*$/.test(line) && line.includes("-");
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((cell) => cell.trim());
}

interface ListItem {
  indent: number;
  ordered: boolean;
  text: string;
}

function renderList(items: ListItem[]): string {
  // Group consecutive items by depth, supporting one nesting level cleanly.
  const build = (list: ListItem[], start: number, indent: number): [string, number] => {
    const ordered = list[start]?.ordered ?? false;
    const tag = ordered ? "ol" : "ul";
    let html = `<${tag}>`;
    let i = start;
    while (i < list.length && list[i].indent >= indent) {
      if (list[i].indent > indent) {
        i += 1;
        continue;
      }
      const item = list[i];
      let inner = `<li>${inline(item.text)}`;
      if (i + 1 < list.length && list[i + 1].indent > indent) {
        const [nested, next] = build(list, i + 1, list[i + 1].indent);
        inner += nested;
        i = next - 1;
      }
      html += `${inner}</li>`;
      i += 1;
    }
    return [`${html}</${tag}>`, i];
  };
  return build(items, 0, items[0]?.indent ?? 0)[0];
}

/** Render markdown to a sanitized HTML string. */
export function renderMarkdownHtml(source: string): string {
  const text = source.replace(/\r\n?/g, "\n");
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code blocks — kept escaped, tagged with its language.
    const fence = line.match(/^\s*```([\w+-]*)\s*$/);
    if (fence) {
      const lang = fence[1] || "";
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence
      out.push(
        `<pre class="hinaa-code"${lang ? ` data-lang="${escapeHtml(lang)}"` : ""}><code>${escapeHtml(
          code.join("\n"),
        )}</code></pre>`,
      );
      continue;
    }

    // Headings
    const heading = line.match(/^\s*(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      out.push(`<h${level}>${inline(heading[2].replace(/\s*#+\s*$/, ""))}</h${level}>`);
      i += 1;
      continue;
    }

    // Horizontal rule
    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      out.push('<hr class="hinaa-hr" />');
      i += 1;
      continue;
    }

    // Blockquote
    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      out.push(`<blockquote>${quote.map((q) => `<p>${inline(q)}</p>`).join("")}</blockquote>`);
      continue;
    }

    // Tables: header row + separator row + body rows
    if (line.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      const header = splitRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        rows.push(splitRow(lines[i]));
        i += 1;
      }
      const head = header.map((cell) => `<th>${inline(cell)}</th>`).join("");
      const body = rows
        .map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join("")}</tr>`)
        .join("");
      out.push(
        `<div class="hinaa-table-wrap"><table class="hinaa-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
      );
      continue;
    }

    // Lists (with 1–2 space indent nesting)
    if (/^\s*(?:[-*•]|\d+[.)])\s+/.test(line)) {
      const items: ListItem[] = [];
      while (i < lines.length && /^\s*(?:[-*•]|\d+[.)])\s+/.test(lines[i])) {
        const m = lines[i].match(/^(\s*)(?:([-*•])|(\d+)[.)])\s+(.*)$/);
        if (m) {
          items.push({
            indent: Math.floor(m[1].replace(/\t/g, "  ").length / 2),
            ordered: Boolean(m[3]),
            text: m[4],
          });
        }
        i += 1;
      }
      out.push(renderList(items));
      continue;
    }

    // Blank line
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Paragraph: consume until blank line or a structural start.
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^\s*(#{1,6}\s|```|>|(?:[-*•]|\d+[.)])\s|(-{3,}|\*{3,})\s*$)/.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    if (para.length > 0) {
      out.push(`<p>${para.map(inline).join("<br />")}</p>`);
    } else if (i < lines.length) {
      // Structural line we did not consume above: advance to avoid a stall.
      out.push(`<p>${inline(lines[i])}</p>`);
      i += 1;
    }
  }

  return out.join("");
}
