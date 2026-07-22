# Research Agent architecture

The Research Agent is a fact-first pipeline:

`DiscoveryCriteria -> task generation -> validation -> priority scheduling -> ProviderOrchestrator -> provider health/capability checks -> bounded execution -> aggregation/deduplication -> ranking and identity suggestions -> factual AI context -> ResearchPackage`

No route, database handle, prompt, model call, or persistence mechanism is present. The dispatcher delegates to `ProviderOrchestrator`, which knows only the unchanged `SourceProvider` interface. Deterministic mocks remain the default; production YouTube, Twitch, and X adapters can be injected without Research Agent changes. See `PROVIDER_ORCHESTRATOR.md` for lifecycle, timeout, aggregation, confidence, and future-provider rules.

## Tasks and scheduling

`ResearchTask` contains type, ID, `HIGH`/`NORMAL`/`LOW` priority, optional platform and entity type, query, status, metadata, and creation time. Supported types are creator search, brand search, profile lookup, keyword lookup, website lookup, platform lookup, and future custom task. Website and custom tasks remain unimplemented.

Scheduling is stable by priority, creation time, and task ID. The orchestrator supports sequential provider execution by default and optional cross-provider concurrency with deterministic output ordering. Validation rejects empty or unsafe queries, duplicate fingerprints, unknown platforms, and unavailable capabilities.

## Context and package

The context builder serializes measurable normalized facts, ranking summaries, source summaries, and a sanitized request. It removes null/empty fields, task internals, and business-email hashes, then estimates tokens deterministically. Oversized entity context is omitted with warnings; a request envelope that cannot fit fails safely.

`ResearchPackage` retains its existing public schema: request summary, normalized entities, ranking summary, conservative identity suggestions, warnings, missing-information summary, aggregate confidence, source summary, context-size estimate, and bounded fact-only context. It contains no AI-generated prose.

Metrics record only counts and timings. Queries, prompts, metadata, credentials, and secrets are never recorded.
