/**
 * One shared path from any rendered markdown surface (chat answer, research
 * dossier, plan) to a real branded PDF, produced by the backend renderer so
 * the file matches what the model wrote — tables, code blocks and all.
 */
export async function downloadMarkdownPdf(title: string, markdown: string, subtitle?: string): Promise<void> {
  const response = await fetch("/api/v1/documents/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, markdown, subtitle }),
  });
  if (!response.ok) {
    let detail = `PDF export failed (HTTP ${response.status}).`;
    try {
      const body = await response.json();
      detail = body?.message || body?.detail || detail;
    } catch {
      /* non-JSON error body — keep the status-line message */
    }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${(title || "hinaa-report")
    .toLowerCase()
    .replace(/[^a-z0-9\u0900-\u097F]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "hinaa-report"}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}
