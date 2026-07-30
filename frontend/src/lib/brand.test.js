import { resolveBackendOrigin } from "./brand";


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
