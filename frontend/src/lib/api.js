import axios from "axios";
import { API, normalizeAssetUrls } from "./brand";

const TOKEN_KEY = "brandkrt_access_token";
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
  const maxRetries = config.__maxRetries ?? (config.__retryOnNetwork ? 2 : 3);
  const optedIn = Boolean(config.__retryOnNetwork);
  const isRetryableMethod = RETRYABLE_METHODS.has(method);
  return retryCount < maxRetries && (isRetryableMethod || optedIn) && isNetworkOrColdStartError(error);
}

const api = axios.create({
  baseURL: API,
  withCredentials: true,
  timeout: Number(process.env.REACT_APP_API_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use((response) => {
  response.data = normalizeAssetUrls(response.data);
  return response;
}, async (error) => {
  if (canRetryRequest(error)) {
    const config = error.config;
    config.__retryCount = (config.__retryCount || 0) + 1;
    const delay = Math.min(1000 * 2 ** (config.__retryCount - 1), 5000);
    await sleep(delay);
    return api(config);
  }

  const status = error?.response?.status;
  const config = error?.config;
  const hasStoredToken = typeof window !== "undefined" && window.localStorage.getItem(TOKEN_KEY);
  if ((status === 401 || status === 403) && config && !config._retryWithFreshAuth) {
    config._retryWithFreshAuth = true;
    try {
      const refreshed = await axios.post(`${API}/auth/refresh`, null, { withCredentials: true });
      const token = refreshed?.data?.access_token;
      if (token && typeof window !== "undefined") {
        window.localStorage.setItem(TOKEN_KEY, token);
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
        return api(config);
      }
    } catch (_) {
      if (hasStoredToken && typeof window !== "undefined") {
        window.localStorage.removeItem(TOKEN_KEY);
      }
    }
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
