export const LOGO = {
  full: "/assets/brandkrt-logo-original.jpeg",
  icon: "/assets/brandkrt-logo-original.jpeg",
};

export const BRAND = {
  name: "BrandKrt",
  domain: "brandkrt.com",
  tagline: "Connecting Brands With Creators",
  email: "support@brandkrt.com",
  contactEmail: "vaibhav@brandkrt.com",
};

const rawBackendUrl = process.env.REACT_APP_BACKEND_URL?.trim();
// Production uses the checked-in Vercel /api rewrite by default. Keeping API
// requests same-origin makes HTTP-only auth cookies reliable in browsers that
// block third-party cookies. A custom API origin remains an explicit override.
const DEFAULT_BACKEND_ORIGIN = "";
export const BACKEND_ORIGIN = rawBackendUrl
  ? rawBackendUrl.replace(/\/api\/?$/, "").replace(/\/$/, "")
  : DEFAULT_BACKEND_ORIGIN;
export const API = BACKEND_ORIGIN ? `${BACKEND_ORIGIN}/api` : "/api";

export function assetUrl(value) {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  if (/^(data:|blob:)/i.test(trimmed)) return trimmed;
  if (/^https?:/i.test(trimmed)) {
    try {
      const url = new URL(trimmed);
      const isUpload = url.pathname.startsWith("/uploads/") || url.pathname.startsWith("/api/uploads/");
      const isAppHost = ["brandkrt.com", "www.brandkrt.com"].includes(url.hostname)
        || (typeof window !== "undefined" && url.hostname === window.location.hostname);
      if (isUpload && (isAppHost || url.hostname.endsWith(".onrender.com"))) {
        return BACKEND_ORIGIN
          ? `${BACKEND_ORIGIN}${url.pathname}${url.search}`
          : `${url.pathname}${url.search}`;
      }
    } catch (_) {
      return trimmed;
    }
    return trimmed;
  }
  if (trimmed.startsWith("/uploads/")) {
    const origin = BACKEND_ORIGIN || (typeof window !== "undefined" ? window.location.origin : "");
    return `${origin}${trimmed}`;
  }
  return trimmed;
}

export function normalizeAssetUrls(value) {
  if (Array.isArray(value)) return value.map(normalizeAssetUrls);
  if (!value || typeof value !== "object") return assetUrl(value);

  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [key, normalizeAssetUrls(entry)])
  );
}
