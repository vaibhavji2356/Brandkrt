// Lightweight loader for Google Identity Services (GIS). Used by Login / Register
// to render the "Continue with Google" button. Activated only when both
// REACT_APP_GOOGLE_CLIENT_ID is set in the build and the backend reports
// /api/auth/google/config -> enabled = true.

const GIS_SRC = "https://accounts.google.com/gsi/client";
let _loaded = null;

export const GOOGLE_CLIENT_ID =
  (typeof process !== "undefined" && process.env && process.env.REACT_APP_GOOGLE_CLIENT_ID) || "";

export function isGoogleConfigured() {
  return !!GOOGLE_CLIENT_ID;
}

export function loadGoogleIdentity() {
  if (typeof window === "undefined") return Promise.reject(new Error("SSR"));
  if (_loaded) return _loaded;
  _loaded = new Promise((resolve, reject) => {
    if (window.google && window.google.accounts && window.google.accounts.id) {
      return resolve(window.google);
    }
    const existing = document.querySelector(`script[src="${GIS_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(window.google));
      existing.addEventListener("error", reject);
      return;
    }
    const s = document.createElement("script");
    s.src = GIS_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve(window.google);
    s.onerror = (e) => reject(e);
    document.head.appendChild(s);
  });
  return _loaded;
}

/**
 * Triggers the Google account chooser and resolves with the ID-token credential.
 * Uses GIS button rendering inside the given container element (preferred) — if
 * no container is passed we fall back to GIS prompt() one-tap behaviour.
 */
export async function requestGoogleCredential({ containerEl } = {}) {
  if (!GOOGLE_CLIENT_ID) {
    throw new Error("Google sign-in is not configured (REACT_APP_GOOGLE_CLIENT_ID missing)");
  }
  const google = await loadGoogleIdentity();
  return new Promise((resolve, reject) => {
    try {
      google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        ux_mode: "popup",
        callback: (resp) => {
          if (resp && resp.credential) resolve(resp.credential);
          else reject(new Error("No credential returned from Google"));
        },
      });
      if (containerEl) {
        google.accounts.id.renderButton(containerEl, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "pill",
          logo_alignment: "left",
          text: "continue_with",
        });
        // Also offer one-tap (silent)
        try { google.accounts.id.prompt(); } catch (_) { /* ignore */ }
      } else {
        google.accounts.id.prompt();
      }
    } catch (e) {
      reject(e);
    }
  });
}
