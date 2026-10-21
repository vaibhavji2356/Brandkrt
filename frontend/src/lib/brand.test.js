import { resolveBackendOrigin, assetUrl } from "./brand";


describe("production API routing", () => {
  test.each([
    "brandkrt.com",
    "www.brandkrt.com",
    "brandkrt-preview.vercel.app",
  ])("uses the same-origin API proxy on %s", (hostname) => {
    expect(resolveBackendOrigin("https://brandkrt.onrender.com", hostname)).toBe("");
  });

  test("keeps an explicit backend override for local development", () => {
    expect(resolveBackendOrigin("http://localhost:8000/api/", "localhost"))
      .toBe("http://localhost:8000");
  });
});

describe("untrusted links", () => {
  test.each(["javascript:alert(1)", "java\nscript:alert(1)", "vbscript:evil", "file:///private", "data:text/html,<script>alert(1)</script>", "data:image/svg+xml,<svg onload=evil>"])("blocks executable URL %s", (url) => {
    expect(assetUrl(url)).toBe("");
  });
  test("preserves ordinary HTTPS links", () => {
    expect(assetUrl("https://example.com/profile")).toBe("https://example.com/profile");
  });
});
