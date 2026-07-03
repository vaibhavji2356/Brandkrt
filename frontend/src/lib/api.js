import axios from "axios";
import { API, normalizeAssetUrls } from "./brand";

const TOKEN_KEY = "brandkrt_access_token";

const api = axios.create({
  baseURL: API,
  withCredentials: true,
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
