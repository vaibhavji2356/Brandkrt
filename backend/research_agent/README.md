# Research Agent architecture

The Research Agent is an orchestration-only, fact-first pipeline:

`DiscoveryCriteria → task generation → validation → priority scheduling → sequential dispatch → result collection → existing normalization → existing deduplication → validation/bounding → existing ranking and identity suggestions → factual AI context → ResearchPackage`

No route, database handle, HTTP client, prompt, model call, or persistence mechanism is present. The dispatcher knows only the `ResearchExecutionProvider` interface. Its current providers wrap deterministic mock platform adapters. Real platform APIs, web search, website parsing, CRM, analytics, embeddings, vector search, and background workers are abstract hook contracts only.

## Tasks and scheduling

`ResearchTask` contains type, ID, `HIGH`/`NORMAL`/`LOW` priority, optional platform and entity type, query, status, metadata, and creation time. Supported task types are creator search, brand search, profile lookup, keyword lookup, website lookup, platform lookup, and future custom task. Website and custom tasks have no implementation in this phase.

Scheduling is stable and sequential: priority, creation time, then task ID. Validation rejects empty or unsafe queries, duplicate task fingerprints, unknown platforms, capability mismatches, and unavailable network-only providers.

## Context and package

The context builder serializes measurable normalized facts, ranking summaries, source summaries, and the sanitized discovery request. It removes null/empty fields, deduplicates upstream profiles, never includes task IDs, priority, status, metadata, or business-email hashes, and estimates tokens deterministically from compact UTF-8 JSON. Entities that would exceed the configured limit are omitted with an explicit warning; a limit too small for even the request envelope fails safely.

`ResearchPackage` includes the request summary, normalized entities, ranking summary, conservative identity suggestions, warnings, missing-information summary, aggregate confidence, source summary, context-size estimate, and bounded fact-only context. It contains no AI-generated prose.

Metrics record only counts and timings: tasks created/completed, aggregate dispatcher milliseconds, validation failures, context characters, and estimated tokens. Queries, prompts, metadata, credentials, and secrets are never recorded.

## Phase 5 boundary

Phase 5 may implement selected hook contracts after credentials, platform policies, quota behavior, safe transport, retention rules, and provider-specific tests are approved. AI reasoning can consume `ai_context` later, but must remain downstream of factual validation and must not mutate factual metrics.
