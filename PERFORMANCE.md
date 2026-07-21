# BrandKrt startup performance report

Measured locally on 2026-07-21 using the repository Python environment and the
configured remote MongoDB connection. Render platform wake time is not
available locally, so platform figures below are estimates and are separated
from measured application timings.

## Measured optimized timings

| Measurement | Result |
|---|---:|
| FastAPI lifecycle live | 1,057.21 ms |
| First MongoDB ping | 891.83 ms |
| First readiness check | 896.87 ms |
| Process module load to ready | 1,954.08 ms |
| Warm pooled MongoDB ping | 54.94 ms |

These timings are emitted at runtime as `app_boot_ms`, `mongo_ping_ms`,
`readiness_ms`, and `check_ms`. The API preserves the first connection and
readiness measurements while also reporting the latest ping separately.
Subsequent readiness calls within the configured five-second cache window do
not issue another MongoDB ping.

## Before and after estimate

| Area | Before | After |
|---|---|---|
| Web-process startup work | Imports, 30+ index checks, database reads, bcrypt admin verification, possible password update | Imports only |
| Application live time | Estimated 2.5-8 seconds with a warm remote database; longer during Atlas/network contention | Measured 1.06 seconds locally |
| Application ready time | Estimated 3.5-9 seconds | Measured 1.95 seconds locally |
| Render platform plus app cold start | Estimated 25-75 seconds, depending mainly on Render instance wake time | Estimated 22-68 seconds on the same tier |
| Startup database commands with two workers | Approximately 60+ index/admin commands | Zero before liveness; one readiness ping per worker when checked |

The old application phase was not replayed because it could mutate the admin
password and indexes. Its range is an engineering estimate based on the
removed database operations. Render infrastructure sleep/wake latency is not
controlled by application code and must be measured from production logs.

## Memory and connection impact

- The recommended Render baseline is one async worker instead of two. This
  avoids a duplicate Python runtime, route graph, import set, and Mongo pool.
- MongoDB pools now start with zero minimum connections and are capped at 50
  connections per worker. The previous driver default could allow up to 100
  per worker, so the documented one-worker deployment reduces the theoretical
  connection ceiling from 200 to 50.
- Removing index and bcrypt work reduces transient startup allocations. The
  lasting RSS benefit from that code alone is expected to be small (typically
  under 5 MB); using one worker is the material memory reduction and commonly
  saves one full backend process footprint.

## Network impact

- No MongoDB traffic is required for the process to become live.
- Readiness uses a bounded MongoDB ping and caches its result for five seconds,
  preventing simultaneous Render and browser probes from duplicating work.
- AuthContext and Google configuration share one frontend wake-up polling
  promise instead of running independent cold-start request loops.
- Only idempotent `GET`, `HEAD`, and `OPTIONS` API calls are retried.
  Login, Google login, OTP generation, registration, refresh, and other POST
  operations are no longer automatically replayed.
- Google certificate retrieval reuses one HTTP session and honors Google's
  certificate cache lifetime. Verification runs in a worker thread, so a
  first certificate fetch does not block the FastAPI event loop.

## Production measurement

Use the structured startup lines in Render logs:

```text
[STARTUP] app_boot_ms=...
[READINESS] ready=... mongo_ping_ms=... readiness_ms=... check_ms=...
```

Capture p50, p95, and maximum values for at least one week. Measure Render wake
time separately as the duration from the first external request until
`/api/health/live` succeeds. This distinguishes hosting-tier latency from
BrandKrt application and MongoDB latency.
