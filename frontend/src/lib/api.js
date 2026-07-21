import axios from "axios";
import { API, normalizeAssetUrls } from "./brand";

const DEFAULT_TIMEOUT_MS = 75000;
const RETRYABLE_STATUSES = new Set([408, 425, 429, 500, 502, 503, 504]);
const RETRYABLE_METHODS = new Set(["get", "head", "options"]);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isNetworkOrColdStartError(error) {
  if (!error) return false;
  if (!error.response) return true;
  return RETRYABLE_STATUSES.has(error.response.status);
}

function canRetryRequest(error) {
  const config = error?.config;
  if (!config) return false;
  const method = (config.method || "get").toLowerCase();
  const retryCount = config.__retryCount || 0;
  const maxRetries = config.__maxRetries ?? 2;
  const isRetryableMethod = RETRYABLE_METHODS.has(method);
  return retryCount < maxRetries && isRetryableMethod && isNetworkOrColdStartError(error);
}

const api = axios.create({
  baseURL: API,
  withCredentials: true,
  timeout: Number(process.env.REACT_APP_API_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
  headers: { "Content-Type": "application/json" },
});

let refreshPromise = null;

api.interceptors.response.use((response) => {
  response.data = normalizeAssetUrls(response.data);
  return response;
}, async (error) => {
  if (canRetryRequest(error)) {
    const config = error.config;
    config.__retryCount = (config.__retryCount || 0) + 1;
    const retryAfter = Number(error?.response?.headers?.["retry-after"] || 0) * 1000;
    const backoff = Math.min(750 * 2 ** (config.__retryCount - 1), 4000);
    const delay = retryAfter || backoff + Math.floor(Math.random() * 250);
    await sleep(delay);
    return api(config);
  }

  const status = error?.response?.status;
  const config = error?.config;
  const requestUrl = String(config?.url || "");
  const isAuthBootstrap = /\/auth\/(?:login|register|google|refresh|logout)(?:\/|$)/.test(requestUrl);
  if (status === 401 && config && !config._retryWithFreshAuth && !isAuthBootstrap) {
    config._retryWithFreshAuth = true;
    try {
      if (!refreshPromise) {
        refreshPromise = axios.post(`${API}/auth/refresh`, null, { withCredentials: true })
          .finally(() => { refreshPromise = null; });
      }
      await refreshPromise;
      return api(config);
    } catch (_) { /* the caller handles the original authentication failure */ }
  }
  return Promise.reject(error);
});

export function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (detail == null) return err?.message || "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  }
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
