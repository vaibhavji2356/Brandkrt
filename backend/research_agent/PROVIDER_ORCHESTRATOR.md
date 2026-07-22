# Unified Provider Orchestrator

## Architecture and execution flow

`ProviderOrchestrator` is the only discovery-provider execution layer used by the Research Agent:

`validated tasks -> deterministic provider selection -> health check -> capability check -> bounded execution -> normalized-profile validation -> attribution -> same-platform deduplication -> conservative confidence -> orchestration result`

The existing `SourceProvider` interface and YouTube, Twitch, and X implementations are unchanged. Instagram and Snapchat adapters can be registered later through the same interface; no real integration for either platform is introduced here. `ResearchDispatcher` remains as a compatibility facade for callers, but delegates all provider work to the orchestrator. Existing public Research Package and discovery API schemas are unchanged.

## Provider lifecycle

1. Tasks are grouped by platform in their deterministic input order.
2. The registered provider's `health_check()` runs before discovery.
3. Disabled, unconfigured, or unhealthy providers are skipped with safe diagnostics.
4. Current capability flags are checked per task. Unsupported operations are rejected without calling the provider.
5. Tasks run sequentially within a provider. Optional concurrency runs different providers concurrently while preserving output order.
6. Results are revalidated as `NormalizedProfile` values and must match the provider platform.
7. Failures remain local to their provider/task; other providers continue.

The supported production providers are YouTube, Twitch, and X. Deterministic mock providers remain available for network-free preview and tests.

## Timeout and failure model

Each provider has an independent `asyncio.wait_for` boundary. The default is 15 seconds and can be overridden per platform, with accepted values bounded to 120 seconds. A timeout cancels only that provider coroutine. Concurrent siblings and subsequent sequential providers continue. There is no sleep, background refresh, automatic network retry, raw response capture, or persistence in the orchestrator.

Provider exceptions are never serialized. Results expose only safe warnings for disabled, unhealthy, timeout, unsupported, malformed normalized data, or upstream failure. Credentials, raw payloads, response bodies, request headers, URLs, and stack traces are excluded.

## Aggregation and attribution

`ProviderOrchestrationResult` contains `providers_used`, `providers_failed`, `providers_skipped`, `warnings`, `aggregated_results`, conservative `aggregate_confidence`, safe `provider_diagnostics`, and compatible `task_results`.

Every aggregate wraps the unchanged normalized entity with explicit provider, platform, source, source confidence, and adjusted confidence. The Research Agent extracts the normalized entity for its existing public package, so public response contracts do not change.

## Deduplication rules

Within one platform, exact platform ID, normalized username, or canonical profile URL can identify a duplicate. The higher adjusted/source-confidence candidate replaces the weaker candidate at the original deterministic position. Profiles on different platforms are never merged. Cross-platform identity remains the separate conservative identity-suggestion service.

## Confidence calculation

The orchestrator never raises confidence above factual `source_confidence`. It applies only downward adjustments:

- exact profile/platform lookup factor: `1.0`
- keyword or discovery factor: `0.9`
- completeness factor: `0.8 + 0.2 * available_core_fields_ratio`

Core fields are username, display name, profile URL, biography, location, follower count, content count, and explicit verification. Missing fields are not treated as zero-valued facts. Aggregate confidence is the deterministic mean of retained adjusted confidences, or zero for no results.

## Future provider integration

To add an official Instagram or Snapchat provider later: implement the unchanged interface and normalized outputs, report conservative capabilities and health, register one provider per platform, set a bounded timeout, add mocked lifecycle/error tests, and document official access, policy, quota, retention, and classification limitations. Registration must never imply that every public account is discoverable.
