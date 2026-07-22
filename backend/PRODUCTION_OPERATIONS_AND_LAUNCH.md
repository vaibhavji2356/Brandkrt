# Production Operations and Launch Readiness

## Phase 14 admin intelligence operations

Admin Lead Intelligence adds `admin_research_jobs` and `admin_saved_leads`. Run
`python database_setup.py` before deployment so job/status and unique fingerprint indexes exist;
readiness treats the primary indexes as critical. Include both collections in Atlas backup scope
and verify restored timestamps, lead statuses, note access, and audit references during drills.

Research execution uses persisted FastAPI background tasks, not a durable worker queue. A deploy
or process restart can interrupt active jobs. Inspect failed/stale jobs and rerun from the admin UI
rather than editing records. Monitor `admin_research.failed`, rate-limit rejections, AI fallback
counts, and provider-orchestrator timeouts. No research job sends outreach automatically.

Production must keep `ADMIN_LEAD_MOCK_MODE=false`. Instagram and Snapchat stay unavailable until
official factual adapters are added; never enable synthetic providers to fill production results.
See `admin_lead_intelligence/README.md` for API and provider policy.

## Operational architecture

```text
Client request
→ Request-correlation middleware
→ CORS/security middleware
→ Authentication and shared rate limit
→ Route/domain/repository or provider
→ Central safe error handler
→ Structured response and access log

Process startup
→ Secret-safe configuration validation
→ MongoDB bounded connectivity check
→ Critical index verification
→ Rate-limit and AI-accounting backend selection
→ Private evidence-storage initialization/health check
→ Application readiness state
```

Optional OpenAI and social platform APIs are not readiness dependencies. Deterministic creator intelligence remains available when optional AI reasoning degrades.

## Configuration matrix

| Setting | Development | Production |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` |
| `DEBUG` | normally `false` | must be `false` |
| `MONGO_URL`, `DB_NAME` | required | required Atlas configuration |
| `JWT_SECRET` | required | non-placeholder, at least 32 characters |
| `CORS_ORIGINS` | exact local origins | required exact HTTPS origins; no wildcard |
| `TRUST_PROXY_HEADERS` | normally `false` | explicitly choose for Render |
| `TRUSTED_PROXY_HOPS` | `1` | match the reviewed proxy chain |
| `EVIDENCE_STORAGE_PROVIDER` | `local` allowed | `s3` when evidence is enabled |
| `RATE_LIMIT_BACKEND` | `memory` | `mongo` |
| `AI_USAGE_BACKEND` | `memory` | `mongo` whenever paid AI is enabled |
| `AI_PROVIDER` | normally `mock` | `openai` only with a reviewed key/budget |

Validation errors contain setting names and stable codes only. Values are never included. Production validation rejects debug mode, wildcard/insecure CORS, weak or placeholder JWT secrets, local evidence storage, unsafe signed-reference TTLs, incomplete S3 credentials, memory-only rate limiting, and memory-only paid-AI accounting.

## Health semantics

- `GET /api/health/live` checks only that the process and request loop can respond. It makes no external call.
- `GET /api/health/ready` returns `200` only when MongoDB, configuration, critical indexes, required storage, and required shared protection backends are usable. It returns `503` otherwise.
- Readiness is cached briefly using `READINESS_CACHE_SECONDS` to avoid probe pressure.
- OpenAI, YouTube, Twitch, X, and optional narrative generation never block readiness.
- Public health responses expose safe component states and timings, never database URLs, bucket names, credentials, topology, stack traces, or tenant data.

Admin-only operational endpoints:

- `GET /api/admin/operations/diagnostics`
- `GET /api/admin/operations/metrics`

Diagnostics expose only aggregate component state, backend type, safe failure counters, provider aggregates, and evidence-consistency counts. Metrics use Prometheus text format and low-cardinality normalized route labels.

## Startup and shutdown

Startup is idempotent per process. It validates configuration, performs a bounded Mongo ping, selects shared backends, verifies indexes without destructive recreation, initializes private storage, and emits one safe summary. Optional provider APIs are not contacted.

Shutdown closes the private storage SDK session and the single process-wide Mongo client using bounded waits. No background loop is started. Database index creation remains an explicit deployment step:

```bash
cd backend
python database_setup.py
```

Missing critical indexes make readiness fail; the web process does not silently recreate or drop them.

## Structured logging and request IDs

Production logs are one-line JSON. Development logs remain readable. Request completion events include timestamp, level, event, request ID, method, normalized route template, status code, duration, safe role category, component, service, and environment.

`X-Request-ID` is accepted only when it matches a strict 1–64 character ASCII pattern. Invalid or oversized values are replaced with a cryptographically random ID. The ID is returned in every handled response and available through context-local logging. It is never authorization input.

Logs intentionally omit headers, cookies, query strings, request bodies, evidence bytes, notes, emails, object IDs, signed URLs, prompts, provider responses, and secrets. Route templates prevent object IDs from becoming metrics labels.

## Error taxonomy

Central handlers add a stable `code` and `request_id` while retaining existing status behavior:

- `validation_error`
- `authentication_error`
- `authorization_error`
- `not_found`
- `conflict`
- `rate_limited`
- `dependency_timeout`
- `dependency_unavailable`
- `storage_error`
- `database_error`
- `internal_error`

Validation details are bounded and exclude submitted values. Expected 4xx responses are represented by the normal access event rather than duplicate error logs. Unexpected failures are logged once; production responses never contain traces or internal dependency messages.

## MongoDB resilience and indexes

The application uses one Motor client per process with bounded server-selection, connect, socket, pool wait, pool size, and idle timeouts. Retryable reads/writes are enabled at the driver level; application code does not wrap non-idempotent writes in aggressive retries. UTC-aware decoding is enabled. The client closes during shutdown.

Critical verification covers users, campaign performance, evidence, corrections, exports, audit events, operational rate limits, and AI usage. Operational counters use TTL indexes because their expiration is intentional physical deletion. Commercial/evidence history uses no TTL index because it requires soft-deletion and audit preservation.

Run `database_setup.py` whenever a release changes index declarations. Index creation is idempotent; destructive recreation is never automatic.

## Durable evidence storage

`EvidenceStorage` supports local development and private S3-compatible production providers. The S3 implementation works with a reviewed AWS S3, R2, B2 S3, or equivalent endpoint without embedding vendor URLs in API contracts.

Production behavior:

- private bucket only;
- generated prefixed keys and conditional non-overwrite uploads;
- pre-transfer size validation;
- detected content type and SHA-256 metadata;
- optional `AES256` or configured `aws:kms` server-side encryption;
- bounded connect/read/operation timeouts and SDK attempts;
- authenticated backend-proxied downloads by default;
- bounded temporary signed references available through the abstraction, never logged;
- soft deletion quarantines/tags the object;
- physical delete exists only as an explicit approved maintenance primitive.

Local storage is development-only. Render ephemeral disk is not durable and production validation rejects local evidence storage when uploads are enabled.

### Mongo/object consistency

MongoDB and object storage do not share one transaction. Behavior is deterministic:

| Failure | Behavior |
| --- | --- |
| Upload fails before metadata | no metadata is written; safe storage error |
| Upload succeeds, metadata fails | object is quarantined when possible; request fails |
| Object missing for metadata | record receives `object_missing`; download returns unavailable |
| Checksum mismatch | record receives `checksum_mismatch`; bytes are not served |
| Storage timeout | safe `storage_error`; internal vendor text is suppressed |
| Quarantine failure | record receives `quarantine_failed`; operator diagnostics show it |
| Duplicate key | conditional upload fails; no overwrite |
| Signed-reference failure | caller receives a safe storage error; URL is not logged |

Diagnostics report counts only. They never perform automatic destructive repair.

## Distributed rate limiting

The development backend is bounded in-memory state. The production Mongo backend uses hashed fixed-window keys, atomic conditional increments, and TTL expiry. Raw cookies/tokens are never keys. Client IP headers are used only when `TRUST_PROXY_HEADERS=true`; the reviewed hop count selects the trusted address.

If the configured shared backend is unavailable, protected requests fail with `503` and `Retry-After`; production never silently becomes unlimited. Existing `429` semantics remain and include bounded retry metadata.

## Distributed AI usage accounting

The production Mongo backend uses an Atlas transaction spanning global daily cost, per-user daily requests, per-IP minute requests, and a safe reservation record. Identities are one-way hashed. Estimates and, where available, actual token/cost aggregates are stored without prompts or responses.

Budget reservation happens before a paid provider call. If accounting is unavailable, the paid call does not run. Match and narrative flows retain their existing deterministic fallback. Failed provider attempts keep their conservative reservation rather than refunding and creating a double-spend opportunity. Atlas transaction support is therefore a production prerequisite for paid AI.

## Metrics and alert starting points

Safe aggregates include HTTP counts/latency/status class, unhandled errors, database/storage failures, evidence upload size buckets, rate-limit rejection/backend failures, AI calls/failures/fallbacks, provider-orchestrator timeouts, and readiness failures.

Initial operator alert thresholds, to be tuned from observed traffic:

- readiness unhealthy for 2 consecutive minutes;
- 5xx rate above 2% for 5 minutes;
- database or storage failures above 3 in 5 minutes;
- p95 request latency above 2 seconds for 10 minutes;
- rate-limit backend failure greater than zero;
- AI fallback ratio above 20% for 15 minutes;
- any evidence `checksum_mismatch` or `quarantine_failed` record.

An external monitoring/alerting destination is an integration point, not configured by this repository.

## Timeout and retry policy

| Dependency | Timeout | Retry behavior | Readiness impact |
| --- | --- | --- | --- |
| MongoDB | selection/connect 5s, socket 10s, pool wait 5s by default | driver retryable reads/writes only | required |
| S3-compatible storage | connect 4s, read 10s, operation 12s | standard SDK, max 3 attempts; conditional writes | required in production |
| OpenAI | `AI_TIMEOUT_SECONDS`, default 20s | at most `AI_MAX_RETRIES`, maximum 1 | optional |
| YouTube | `YOUTUBE_TIMEOUT_SECONDS`, default 10s | adapter quota-safe behavior | optional |
| Twitch | `TWITCH_TIMEOUT_SECONDS`, default 10s | one token refresh on authentication expiry | optional |
| X | `X_TIMEOUT_SECONDS`, default 10s | at most one documented retry for retryable 5xx | optional |
| Provider orchestration | bounded per-provider, default 15s | provider isolation; no retry storm | optional |

Unsafe non-idempotent business writes are not automatically retried by application wrappers.

## Backup and restore checklist

The repository cannot prove that backups or object versioning are enabled. The operator must verify them.

Before launch and monthly:

- [ ] Identify the owner for MongoDB and object-storage recovery.
- [ ] Confirm Atlas backup tier, schedule, retention, and point-in-time recovery in the Atlas console.
- [ ] Confirm the evidence bucket is private and versioning/object-lock policy matches the approved retention policy.
- [ ] Confirm encryption mode and key access for both normal operation and restoration.
- [ ] Record the most recent successful restore drill date and recovery duration.
- [ ] Confirm tenant-isolated restore limitations; Atlas snapshot restore may require restoring to a separate cluster and selectively validating/importing data.

Restore procedure:

1. Freeze writes or isolate the affected environment.
2. Restore Atlas/object versions to a separate recovery target where possible.
3. Reapply least-privilege application access.
4. Run index verification and readiness checks.
5. Compare evidence SHA-256 metadata to restored bytes.
6. Verify tenant authorization with designated recovery test accounts.
7. Run the read-only smoke suite.
8. Record audit implications and any records reconstructed outside normal workflows.

No destructive automated restore script is provided.

## Deployment and rollback

Pre-deploy:

- [ ] Backend tests and compilation pass.
- [ ] Production configuration validates with secrets supplied by Render.
- [ ] Previous commit and rollback owner are recorded.
- [ ] Atlas backup state and evidence versioning are manually confirmed.
- [ ] `python database_setup.py` succeeds against the target database.
- [ ] S3 storage health, private access, encryption, and credentials are verified.
- [ ] Schema changes are backward-compatible and non-destructive.

Deploy:

1. Deploy the Render backend without changing Vercel frontend code.
2. Wait for `/api/health/ready` to return `200`.
3. Run `scripts/production_smoke.py`.
4. Observe readiness, 5xx rate, storage/database failures, and latency.
5. Verify login cookies and exact production CORS origins.

Rollback when readiness remains unhealthy, unexpected 5xx exceeds the agreed threshold, authentication regresses, storage consistency errors appear, or data writes cannot be verified.

Rollback procedure:

1. Select the recorded previous Git commit in Render.
2. Confirm it can read records written by the new release.
3. Do not delete newly written Mongo or object-storage records.
4. Redeploy the previous commit.
5. Verify liveness/readiness and run the read-only smoke suite.
6. Preserve logs/request IDs and open an incident record.

## Smoke-test usage

Read-only public checks:

```bash
cd backend
python scripts/production_smoke.py --base-url https://api.example.com
```

Optional authenticated read checks use environment-only credentials:

```bash
BRANDKRT_SMOKE_EMAIL=<test-account> BRANDKRT_SMOKE_PASSWORD=<secret> \
python scripts/production_smoke.py --base-url https://api.example.com
```

The script never prints credentials, uses bounded timeouts, performs no payment/provider call, and makes no write by default. Use only a dedicated least-privilege smoke account.

## Incident basics

1. Capture time range, release, normalized route, safe request IDs, and aggregate metrics.
2. Classify configuration, database, storage, rate-limit, AI-accounting, or application failure.
3. Disable optional paid AI/provider features before weakening safety controls.
4. Never switch production rate limits or paid-AI accounting to silent bypass.
5. Quarantine inconsistent evidence; do not automatically delete or overwrite it.
6. Roll back when the current version cannot serve safely.
7. Document recovery validation and follow-up controls.

## Launch-readiness assessment

Repository state: **conditionally ready**.

Blocking production items outside the repository:

- configure and test a private durable S3-compatible bucket;
- confirm bucket versioning/encryption and Atlas backup/PITR manually;
- configure exact Render/Vercel production origins and strong secrets;
- enable Mongo rate limiting and Mongo AI accounting for paid AI;
- run database setup and confirm critical index readiness;
- configure an external metrics/log alert destination;
- run the smoke suite against the actual Render deployment;
- complete and record a backup restore and rollback drill.

The application must not be marked launch-ready until every blocker is evidenced by the operator.

## Known limitations and Phase 14

- Mongo and object storage cannot commit atomically; compensation and repair diagnostics reduce but do not eliminate orphan risk.
- Metrics are process-local; shared counters protect rate limits and AI budgets, while production metric aggregation requires an external scraper/backend.
- No malware scanning or document OCR is performed.
- Physical evidence erasure and legal-hold workflows require reviewed operational policy.
- External error monitoring, paging, SLO dashboards, restore automation, and chaos/failover drills remain Phase 14 candidates.
- Payments, contracts, payouts, escrow, and automated outreach remain outside this phase.
