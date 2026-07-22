# Official X API v2 integration

## Architecture and authentication

`XApiAdapter` implements the existing `SourceProvider` interface. The production factory uses the real adapter for X while `build_mock_adapters()` remains deterministic and network-free for the protected mock preview. Instagram and Snapchat remain mocks. App-only requests use `Authorization: Bearer ...`; tokens are loaded from the environment, excluded from object representations and cache keys, and are never persisted or returned in errors.

Configuration is disabled by default:

- `X_ENABLED=false`
- `X_BEARER_TOKEN=`
- `X_TIMEOUT_SECONDS=10` (valid range 1–60)
- `X_MAX_RESULTS=10` (valid range 1–50)
- `X_CACHE_TTL_SECONDS=300` (valid range 1–3600)

The repository did not previously use `TWITTER_*` settings, so the adapter consistently uses the current platform name, `X_*`.

## Official endpoints and capabilities

The adapter uses only documented API v2 endpoints:

- `GET /2/users/by/username/{username}` for exact username lookup
- `GET /2/users/{id}` for platform-ID lookup
- `GET /2/users/search` for one bounded page of keyword creator candidates

No pagination, scraping, post-author inference, or undocumented transport is used. User Search availability and billing depend on the app's current X API access. A `403` becomes a safe access-restriction error; it does not trigger a fallback. X documents app-only bearer authentication for public user lookup, per-endpoint rate limits, and a separate User Search endpoint. See [User Lookup](https://docs.x.com/x-api/users/lookup/introduction), [User Search](https://docs.x.com/x-api/users/search/introduction), and [Rate Limits](https://docs.x.com/x-api/fundamentals/rate-limits).

Capabilities when enabled are keyword discovery, exact username/ID lookup, creator discovery, and returned follower/content metrics. Category search, server-side location filtering, audience demographics, and brand discovery are false. Disabled instances advertise no operational discovery capability and never make a request.

Not every public account is guaranteed to be discoverable: access tier, account state, protection, indexing, API policy, billing, and rate limits can all constrain results.

## Normalization and brand safeguards

Only official response fields are mapped:

| X field | Normalized field |
|---|---|
| `id` | `platform_id` |
| `username` | `username`, canonical `profile_url` |
| `name` | `display_name` |
| `description` | `biography` |
| `location` | `location` (free-form; not country) |
| expanded `entities.url` / `url` | safe `website` |
| `public_metrics.followers_count` | `follower_count` |
| `public_metrics.following_count` | `following_count` |
| `public_metrics.tweet_count` | `content_count` |
| explicit `verified` | `verified` |
| `created_at` | `published_at` |

Engagement, average content metrics, audience data, language, email availability, pricing, country, and cross-platform identity remain null. Raw X responses and unrelated metrics such as `listed_count` or `verified_type` never enter the normalized output. Although X can return `profile_image_url`, it is omitted: adding it to the shared schema would alter every existing serialized profile and existing Twitch contract, so the narrower backward-compatible choice is to defer it.

X does not provide authoritative creator-versus-brand classification. Search results are creator candidates only because the caller requested creator discovery and include a warning about that semantic. `search_brands` always returns an empty list; verification, name, and follower counts are never used to infer a brand.

## Errors, limits, caching, and privacy

Provider-specific safe exceptions cover disabled configuration, malformed requests, invalid/revoked tokens, access restrictions, missing profiles, rate limits, timeout, malformed responses, and upstream failure. Upstream bodies, URLs, headers, tokens, and stack details are not propagated. `429` is never retried or slept on. A `5xx` response receives at most one immediate retry.

Successful JSON responses use a provider-local TTL cache with deterministic non-secret keys. Profile and search namespaces are separate, expired entries are removed on access, and the cache is capped at 256 entries. Failures are not cached, there is no background refresh, and no data is persisted. Multi-worker production deployments may later use an approved shared cache with equivalent retention and credential controls.

Production rollout should create a least-privilege X app, store its bearer token in the deployment secret manager, restrict operator access, set `X_ENABLED=true` only after endpoint entitlement and billing are verified, and monitor rate/usage dashboards. Future user-authorized OAuth may enable user-context operations, but is intentionally outside this read-only phase.
