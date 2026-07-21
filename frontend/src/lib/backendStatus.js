import { API } from "./brand";

const DEFAULT_WAKE_TIMEOUT_MS = Number(process.env.REACT_APP_BACKEND_WAKE_TIMEOUT_MS || 90000);
const POLL_INTERVAL_MS = Number(process.env.REACT_APP_BACKEND_POLL_INTERVAL_MS || 1500);
const REQUEST_TIMEOUT_MS = Number(process.env.REACT_APP_BACKEND_HEALTH_TIMEOUT_MS || 10000);

let readyPayload = null;
let readinessPromise = null;
const listeners = new Set();

function publish(state, details = null) {
  listeners.forEach((listener) => listener({ state, details }));
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function readinessRequest() {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API}/health/ready`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    let data = null;
    try { data = await response.json(); } catch (_) { /* retry malformed cold-start responses */ }
    return { response, data };
  } finally {
    window.clearTimeout(timer);
  }
}

async function pollUntilReady(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let attempt = 0;
  publish("checking");

  while (Date.now() < deadline) {
    attempt += 1;
    try {
      const { response, data } = await readinessRequest();
      if (response.ok && data?.isReady) {
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
    } catch (error) {
      if (error?.status?.configuration?.valid === false) throw error;
      // Network errors and per-attempt timeouts are expected while Render wakes.
    }

    publish("waking", { attempt });
    const jitter = Math.floor(Math.random() * 250);
    await delay(POLL_INTERVAL_MS + jitter);
  }

  publish("unavailable");
  throw new Error("Backend did not become ready in time");
}

/**
 * Wait for the shared backend readiness probe. Concurrent callers reuse one
 * polling loop so AuthContext and Google login never create a wake-up storm.
 */
export function waitForBackendReady({ timeoutMs = DEFAULT_WAKE_TIMEOUT_MS, onState } = {}) {
  if (onState) listeners.add(onState);
  if (readyPayload) {
    onState?.({ state: "ready", details: readyPayload });
    if (onState) listeners.delete(onState);
    return Promise.resolve(readyPayload);
  }
  if (!readinessPromise) {
    readinessPromise = pollUntilReady(timeoutMs).finally(() => {
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
