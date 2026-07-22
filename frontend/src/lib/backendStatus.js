import { API } from "./brand";

function boundedMilliseconds(name, fallback, maximum) {
  const configured = Number(process.env[name]);
  if (!Number.isFinite(configured) || configured <= 0) return fallback;
  return Math.min(configured, maximum);
}

const DEFAULT_WAKE_TIMEOUT_MS = boundedMilliseconds("REACT_APP_BACKEND_WAKE_TIMEOUT_MS", 65000, 75000);
const POLL_INTERVAL_MS = boundedMilliseconds("REACT_APP_BACKEND_POLL_INTERVAL_MS", 1000, 5000);
const REQUEST_TIMEOUT_MS = boundedMilliseconds("REACT_APP_BACKEND_HEALTH_TIMEOUT_MS", 8000, 15000);

let readyPayload = null;
let readinessPromise = null;
const listeners = new Set();

function publish(state, details = null) {
  listeners.forEach((listener) => listener({ state, details }));
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function unavailableError(message = "Backend is unavailable. Please try again.") {
  const error = new Error(message);
  error.code = "backend_unavailable";
  return error;
}

async function readinessRequest(timeoutMs) {
  const controller = new AbortController();
  let timer;
  const timedOut = new Promise((_, reject) => {
    timer = window.setTimeout(() => {
      controller.abort();
      reject(unavailableError("Backend readiness check timed out. Please try again."));
    }, timeoutMs);
  });
  try {
    const request = async () => {
      let endpoint = "ready";
      let response = await fetch(`${API}/health/ready`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal: controller.signal,
      });
      // The frontend can be deployed before Render. Older BrandKrt backends
      // expose /health but not /health/ready, so use the legacy liveness probe
      // only when the readiness route itself is absent.
      if (response.status === 404 || response.status === 405) {
        endpoint = "legacy";
        response = await fetch(`${API}/health`, {
          method: "GET",
          credentials: "include",
          headers: { Accept: "application/json" },
          cache: "no-store",
          signal: controller.signal,
        });
      }
      let data = null;
      try { data = await response.json(); } catch (_) { /* retry malformed cold-start responses */ }
      return { response, data, endpoint };
    };
    return await Promise.race([request(), timedOut]);
  } finally {
    window.clearTimeout(timer);
  }
}

async function pollUntilReady({ timeoutMs, pollIntervalMs, requestTimeoutMs }) {
  const deadline = Date.now() + timeoutMs;
  let attempt = 0;
  publish("checking");

  while (Date.now() < deadline) {
    attempt += 1;
    try {
      const remaining = Math.max(1, deadline - Date.now());
      const { response, data, endpoint } = await readinessRequest(Math.min(requestTimeoutMs, remaining));
      const legacyReady = endpoint === "legacy" && response.ok && data?.status === "ok";
      if ((response.ok && data?.isReady) || legacyReady) {
        readyPayload = data;
        publish("ready", data);
        return data;
      }

      // A reachable server with invalid configuration is not a cold start.
      if (data?.configuration && data.configuration.valid === false) {
        const error = new Error("Backend configuration is incomplete");
        error.status = data;
        publish("unavailable", data);
        throw error;
      }
      if (response.status >= 400 && response.status < 500) {
        const error = unavailableError("Backend readiness request was rejected. Please try again.");
        error.retryable = false;
        throw error;
      }
    } catch (error) {
      if (error?.status?.configuration?.valid === false) throw error;
      if (error?.retryable === false) {
        publish("unavailable");
        throw error;
      }
      if (error?.code === "backend_unavailable" && Date.now() >= deadline) break;
      // Network errors and per-attempt timeouts are expected while Render wakes.
    }

    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    publish("waking", { attempt });
    const jitter = Math.floor(Math.random() * 250);
    await delay(Math.min(pollIntervalMs + jitter, remaining));
  }

  publish("unavailable");
  throw unavailableError("Backend did not become ready in time. Please try again.");
}

/**
 * Wait for the shared backend readiness probe. Concurrent callers reuse one
 * polling loop so AuthContext and Google login never create a wake-up storm.
 */
export function waitForBackendReady({
  timeoutMs = DEFAULT_WAKE_TIMEOUT_MS,
  pollIntervalMs = POLL_INTERVAL_MS,
  requestTimeoutMs = REQUEST_TIMEOUT_MS,
  onState,
} = {}) {
  timeoutMs = Math.min(Math.max(Number(timeoutMs) || DEFAULT_WAKE_TIMEOUT_MS, 1), 75000);
  pollIntervalMs = Math.min(Math.max(Number(pollIntervalMs) || POLL_INTERVAL_MS, 1), 5000);
  requestTimeoutMs = Math.min(Math.max(Number(requestTimeoutMs) || REQUEST_TIMEOUT_MS, 1), 15000);
  if (onState) listeners.add(onState);
  if (readyPayload) {
    onState?.({ state: "ready", details: readyPayload });
    if (onState) listeners.delete(onState);
    return Promise.resolve(readyPayload);
  }
  if (!readinessPromise) {
    readinessPromise = pollUntilReady({ timeoutMs, pollIntervalMs, requestTimeoutMs }).finally(() => {
      readinessPromise = null;
    });
  }
  return readinessPromise.finally(() => {
    if (onState) listeners.delete(onState);
  });
}

export function resetBackendReadiness() {
  readyPayload = null;
}
