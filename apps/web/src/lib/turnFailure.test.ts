import { describe, expect, it } from "vitest";
import {
  describeCode,
  describeResponseFailure,
  describeThrownFailure,
  looksLikeHtml,
  singleLine,
} from "./turnFailure";

/** The page a Cloudflare quick tunnel hands back when uvicorn is not listening. */
const CLOUDFLARE_502 = `<!DOCTYPE html>
<html>
<head>
<title>502: Bad gateway</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/normalize.css@8.0.1/normalize.min.css" />
</head>
<body class="browserlang en">
<div class="wrapper">
<h1>Error 502: Bad gateway</h1>
<p>The origin web server does not return a valid response. Please check your web server and try again.</p>
<p><span>A Cloudflare Proxy Ticket was provided. Please contact your hosting provider.</span></p>
</div>
</body>
</html>`;

describe("singleLine", () => {
  it("drops markup, collapses whitespace and stays on one line", () => {
    const line = singleLine("<div>\n  Bad   <b>gateway</b>  \n details &amp; more\t</div>");
    expect(line).toBe("Bad gateway details more");
    expect(line).not.toContain("\n");
  });

  it("caps a runaway body", () => {
    const line = singleLine(`boom ${"x".repeat(4000)}`);
    expect(line.length).toBeLessThanOrEqual(220);
    expect(line.endsWith("…")).toBe(true);
  });

  it("returns the fallback for values with no readable text", () => {
    expect(singleLine("<p></p>", "nothing to say")).toBe("nothing to say");
    expect(singleLine(undefined, "nothing to say")).toBe("nothing to say");
  });
});

describe("looksLikeHtml", () => {
  it("recognises an edge error page", () => {
    expect(looksLikeHtml(CLOUDFLARE_502)).toBe(true);
    expect(looksLikeHtml('{"detail":"nope"}')).toBe(false);
  });

  it("recognises a truncated fragment as markup", () => {
    expect(looksLikeHtml("<tr><td>upstream broke off here</td></tr>")).toBe(true);
    expect(looksLikeHtml("Expected </div> in the template")).toBe(false);
  });
});

describe("describeResponseFailure", () => {
  it("never quotes a Cloudflare body, and names the layer that answered", () => {
    const line = describeResponseFailure({
      status: 502,
      body: CLOUDFLARE_502,
      contentType: "text/html; charset=utf-8",
    });
    expect(line).toContain("502");
    expect(line).not.toContain("<");
    expect(line).not.toMatch(/cloudflare/i);
    expect(line.split("\n")).toHaveLength(1);
  });

  it("treats a 200 that announces itself as HTML as the same failure", () => {
    const line = describeResponseFailure({
      status: 200,
      body: CLOUDFLARE_502,
      contentType: "text/html",
    });
    expect(line).not.toContain("<");
    expect(line).toContain("200");
  });

  it("keeps the backend's own reason when the body is JSON", () => {
    expect(
      describeResponseFailure({
        status: 422,
        body: JSON.stringify({ detail: "brainModel is not configured for this mode" }),
        contentType: "application/json",
      }),
    ).toBe("brainModel is not configured for this mode");
  });

  it("reads FastAPI's validation list without dumping the whole array", () => {
    const body = JSON.stringify({
      detail: [
        { loc: ["body", "text"], msg: "field required", type: "value_error.missing" },
        { loc: ["body", "format"], msg: "extra inputs are not permitted" },
      ],
    });
    expect(
      describeResponseFailure({ status: 422, body, contentType: "application/json" }),
    ).toBe("field required");
  });

  it("maps a provider code carried in a JSON error body", () => {
    const body = JSON.stringify({ code: "PROVIDER_KEY_INVALID", message: "invalid api key" });
    expect(
      describeResponseFailure({ status: 502, body, contentType: "application/json" }),
    ).toBe("The selected brain rejected its API key.");
  });

  it("says the edge refused rather than quoting an HTML 403 challenge", () => {
    const line = describeResponseFailure({
      status: 403,
      body: "<html><head><title>Attention Required!</title></head><body>Security check</body></html>",
      contentType: "text/html",
    });
    expect(line).toContain("403");
    expect(line).not.toContain("<");
  });

  it("falls back to a plain sentence when the body says nothing usable", () => {
    expect(describeResponseFailure({ status: 500 })).toContain("500");
    expect(describeResponseFailure({ status: 404, body: "gateway timeout" })).toContain("404");
  });
});

describe("describeCode", () => {
  it("words the codes HINAA's live path already words", () => {
    expect(describeCode("PROVIDER_RATE_LIMIT")).toBe(
      "The selected brain is rate limited — try again shortly or switch brains.",
    );
    expect(describeCode("provider_timeout")).toBe(
      "The selected brain did not answer before the live safety timeout.",
    );
  });

  it("keeps an unmapped provider code readable instead of raw", () => {
    expect(describeCode("PROVIDER_WEIRD_THING", "Upstream said no")).toBe("Upstream said no");
    expect(describeCode("STREAM_ERROR", "boom")).toBeNull();
    expect(describeCode(undefined)).toBeNull();
  });
});

describe("describeThrownFailure", () => {
  it("uses an error's message without its class name", () => {
    const line = describeThrownFailure(
      new TypeError("Failed to fetch"),
      "The task list could not load",
    );
    expect(line).toBe("The task list could not load — Failed to fetch.");
    expect(line).not.toContain("TypeError");
  });

  it("yields only the caller's sentence when the error says nothing", () => {
    expect(describeThrownFailure(new Error("   "), "The tool registry could not load")).toBe(
      "The tool registry could not load.",
    );
    expect(describeThrownFailure(undefined, "HINAA's API never answered")).toBe(
      "HINAA's API never answered.",
    );
  });

  it("flattens a markup-bearing or overlong reason to one line", () => {
    expect(
      describeThrownFailure(new Error("<p>connection <b>reset</b></p>"), "The reports list"),
    ).toBe("The reports list — connection reset.");
    const long = describeThrownFailure(
      new Error("x".repeat(400)),
      "HINAA's API never answered",
    );
    expect(long.split("\n")).toHaveLength(1);
    expect(long.length).toBeLessThanOrEqual(220);
    expect(long.endsWith("…")).toBe(true);
  });
});
