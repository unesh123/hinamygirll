// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ResponseMarkdown } from "./ResponseMarkdown";
import { toolRegistry } from "../../features/tools/toolRegistry";

describe("ResponseMarkdown video playback & new tool metadata", () => {
  it("renders an inline playable <video> for creative MP4 asset links", () => {
    const html = renderToStaticMarkup(
      <ResponseMarkdown text={"**Rendered MP4 (480x854 · 24 fps):** [Download / Play MP4](/v1/creative/assets/asset-abc123/download)"} />,
    );
    expect(html).toContain("<video");
    expect(html).not.toMatch(/<p>[\s\S]*<div/);
    expect(html).toContain('src="/v1/creative/assets/asset-abc123/download"');
    expect(html).toContain("controls");
    expect(html).toContain('href="/v1/creative/assets/asset-abc123/download"');
  });

  it("keeps ordinary external links as anchor tags without <video>", () => {
    const html = renderToStaticMarkup(<ResponseMarkdown text={"See [Example](https://example.com) for details."} />);
    expect(html).not.toContain("<video");
    expect(html).toContain('href="https://example.com"');
  });

  it("exposes studio, workspace coding, and ML AI Code metadata in toolRegistry", () => {
    for (const id of [
      "render_code_animation",
      "workspace_read_file",
      "workspace_edit_file",
      "workspace_glob",
      "workspace_grep",
      "mlai_list_routines",
      "mlai_run_routine",
    ]) {
      expect(toolRegistry[id]).toBeDefined();
      expect(toolRegistry[id]?.id).toBe(id);
    }
  });
});
