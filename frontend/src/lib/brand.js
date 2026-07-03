export const LOGO = {
  full: "/assets/brandkrt-og.svg",
  icon: "/assets/brandkrt-icon.svg",
};

export const BRAND = {
  name: "BrandKrt",
  domain: "brandkrt.com",
  tagline: "Connecting Brands With Creators",
  email: "support@brandkrt.com",
  contactEmail: "vaibhav@brandkrt.com",
};

const rawBackendUrl = process.env.REACT_APP_BACKEND_URL?.trim();
export const BACKEND_ORIGIN = rawBackendUrl ? rawBackendUrl.replace(/\/api\/?$/, "").replace(/\/$/, "") : "";
export const API = BACKEND_ORIGIN ? `${BACKEND_ORIGIN}/api` : "/api";

export function assetUrl(value) {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  if (/^(https?:|data:|blob:)/i.test(trimmed)) return trimmed;
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
