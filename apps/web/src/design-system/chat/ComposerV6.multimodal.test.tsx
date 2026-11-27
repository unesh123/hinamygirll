import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ComposerV6 } from "./ComposerV6";

describe("ComposerV6 multi-file, video frame-by-frame, and multi-image uploads", () => {
  it("supports multiple selection, inspects video via /api/v1/media/inspect-video, and sends structured attachedMedia", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/media/inspect-video")) {
        return new Response(
          JSON.stringify({
            asset_id: "vid-asset-1",
            metadata: { duration_seconds: 2.5 },
            contact_sheet_data_url: "data:image/jpeg;base64,SHEET123",
            frames: [{ index: 1 }, { index: 2 }, { index: 3 }, { index: 4 }],
            summary: "Video Frame-by-Frame Inspection (320x180, 4 frames)",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/assets")) {
        return new Response(JSON.stringify({ asset_id: "doc-asset-1" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/documents/extract")) {
        return new Response(JSON.stringify({ text: "# SORA Spec\nVite + Three.js", kind: "md" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({}), { status: 404 });
    });

    vi.stubGlobal("fetch", fetchMock);
    try {
      const onSend = vi.fn();
      const onImageAttach = vi.fn();
      const { container } = render(
        <ComposerV6
          value="Build SORA from this video and spec"
          onChange={vi.fn()}
          onSend={onSend}
          attachedImage={null}
          onImageAttach={onImageAttach}
        />,
      );

      // Plus menu exposes real "Inspect Video Frames" action
      fireEvent.click(screen.getByTitle(/Attach an image or start a deliverable/i));
      expect(screen.getByText("Inspect Video Frames")).toBeInTheDocument();

      const input = container.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toHaveAttribute("multiple");

      const vidFile = new File(["mp4bytes"], "demo_ui.mp4", { type: "video/mp4" });
      const mdFile = new File(["# SORA Spec\nVite + Three.js"], "SORA_SPEC.md", { type: "text/markdown" });
      const img1 = new File(["png1"], "ref1.png", { type: "image/png" });
      const img2 = new File(["png2"], "ref2.png", { type: "image/png" });

      fireEvent.change(input, { target: { files: [img1, img2, vidFile, mdFile] } });

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith("/api/v1/media/inspect-video", expect.anything());
      });
      await waitFor(() => {
        expect(screen.getByTestId("composer-media-strip")).toHaveTextContent("demo_ui.mp4");
        expect(screen.getByTestId("composer-media-strip")).toHaveTextContent("SORA_SPEC.md");
      });
      expect(onImageAttach).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByTestId("composer-send-btn"));
      expect(onSend).toHaveBeenCalledTimes(1);
      const sentOpts = onSend.mock.calls[0][0];
      expect(sentOpts.attachedMedia).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ name: "demo_ui.mp4", kind: "video", assetId: "vid-asset-1" }),
          expect.objectContaining({ name: "SORA_SPEC.md", kind: "md", assetId: "doc-asset-1" }),
          expect.objectContaining({ kind: "image" }),
        ]),
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
