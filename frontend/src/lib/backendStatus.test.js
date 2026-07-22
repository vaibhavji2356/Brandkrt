import { resetBackendReadiness, waitForBackendReady } from "./backendStatus";


function readyResponse() {
  return {
    ok: true,
    status: 200,
    json: async () => ({ isReady: true, status: "ready" }),
  };
}


describe("backend readiness", () => {
  beforeEach(() => {
    resetBackendReadiness();
    global.fetch = jest.fn();
    jest.spyOn(Math, "random").mockReturnValue(0);
  });

  afterEach(() => {
    Math.random.mockRestore();
    jest.restoreAllMocks();
  });

  test("resolves a successful readiness response", async () => {
    fetch.mockResolvedValueOnce(readyResponse());
    const states = [];

    const result = await waitForBackendReady({
      timeoutMs: 50,
      pollIntervalMs: 1,
      requestTimeoutMs: 20,
      onState: ({ state }) => states.push(state),
    });

    expect(result.isReady).toBe(true);
    expect(states).toEqual(["checking", "ready"]);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  test("falls back to the legacy health route when readiness is not deployed", async () => {
    fetch
      .mockResolvedValueOnce({ ok: false, status: 405, json: async () => ({ detail: "Method Not Allowed" }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ status: "ok" }) });

    const result = await waitForBackendReady({
      timeoutMs: 50,
      pollIntervalMs: 1,
      requestTimeoutMs: 20,
    });

    expect(result.status).toBe("ok");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[1][0]).toBe("/api/health");
  });

  test("polls once after a delayed backend wake-up without overlapping", async () => {
    fetch
      .mockRejectedValueOnce(new TypeError("cold start"))
      .mockResolvedValueOnce(readyResponse());

    const result = await waitForBackendReady({
      timeoutMs: 100,
      pollIntervalMs: 1,
      requestTimeoutMs: 20,
    });

    expect(result.isReady).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  test("enforces the total readiness timeout even when fetch never settles", async () => {
    fetch.mockImplementation(() => new Promise(() => {}));
    const started = Date.now();

    await expect(waitForBackendReady({
      timeoutMs: 20,
      pollIntervalMs: 1,
      requestTimeoutMs: 100,
    })).rejects.toMatchObject({ code: "backend_unavailable" });

    expect(Date.now() - started).toBeLessThan(250);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  test("failed readiness requests end in a retryable unavailable error", async () => {
    fetch.mockRejectedValue(new TypeError("network unavailable"));

    await expect(waitForBackendReady({
      timeoutMs: 15,
      pollIntervalMs: 2,
      requestTimeoutMs: 5,
    })).rejects.toThrow("Please try again");

    expect(fetch.mock.calls.length).toBeGreaterThan(0);
  });
});
