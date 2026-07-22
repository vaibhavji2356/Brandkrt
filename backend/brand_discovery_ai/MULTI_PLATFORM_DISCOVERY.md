# Multi-platform discovery architecture

This phase is a network-free architecture preview. `SourceProvider` is the vendor-neutral boundary; Instagram, YouTube, Snapchat, Twitch, and X currently use deterministic mock adapters. Adapters return platform-shaped mock payloads, the normalization layer validates factual fields, and deterministic ranking operates only on normalized profiles. Nothing is persisted.

## Normalized profile

`NormalizedProfile` supports `creator` and `brand` entities and includes platform identity, handle/name/URLs, biography, categories and keywords, location/language, optional follower/following/content/view/like/comment metrics, optional engagement and verification, website, business-email availability and a one-way email hash, linked social URLs, optional audience demographics, source confidence, collection time, and warnings. Fields unavailable under a platform capability remain `null`; they are never inferred or converted to zero.

## Capability matrix

| Platform | Keyword | Category | Username | Location filter | Followers | Content | Demographics | Brands | Creators |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Instagram | Yes | Yes | Yes | No | Yes | Yes | No | Yes | Yes |
| YouTube | Yes | Yes | Yes | No | Yes | Yes | No | Yes | Yes |
| Snapchat | No | No | Yes | No | No | No | No | No | Yes |
| Twitch | Yes | Yes | Yes | No | Yes | Yes | No | No | Yes |
| X | Yes | No | Yes | No | Yes | Yes | No | Yes | Yes |

This is a conservative architecture matrix, not a promise of production API access. Official APIs, account tier, user authorization, review status, geography, and policy can narrow fields and discovery. In particular, official APIs do not guarantee discovery of every public account.

## Factual and AI boundary

Platform adapters are the only future source of factual platform identity, verification, and metrics. Normalization rejects invalid counts, rates, timestamps, and unsafe URLs. Ranking calculates measurable fit without OpenAI. OpenAI may later explain strategy, suggest outreach angles, summarize verified facts, or propose campaign ideas; it must never invent or externally validate follower counts, engagement, verification, platform identity, or any absent source field.

## Ranking

Ranking combines category relevance (18%), keyword relevance (16%), location (10%), language (8%), selected platform (8%), follower-range fit (12%), engagement fit (12%), data completeness (8%), and source confidence (8%). Only applicable fields contribute to the denominator. Missing metrics produce warnings and are not scored as zero. Ordering is deterministic with platform and platform ID tie-breakers.

## Identity safeguards

Identity suggestions are non-persistent and keep profiles separate. Exact verified website, exact linked social URL, exact business-email hash, and exact normalized username are the only signals. Similar display names are ignored. Username alone scores 0.70 and cannot authorize merging; only confidence at or above 0.95 is marked eligible for a later, separately reviewed merge workflow.

## Preview endpoint

`POST /api/ai/discovery/preview` accepts `entity_type` (`creator`, `brand`, or `both`), platforms, niche, categories, keywords, exclusions, location, language, follower bounds, minimum engagement rate, campaign objective, budget bounds, and result limit. It requires an authenticated `brand` or `admin`, uses the existing in-memory rate-limit dependency (10/minute), invokes mock adapters only, exposes source attribution and score components, and performs no database writes. The existing `POST /api/ai/brand-discovery/preview` contract is unchanged.

## Future credentials and policy limits

Real adapters will require platform-specific developer applications, approved scopes, API keys or OAuth client credentials, redirect URIs where applicable, secret rotation, quota monitoring, and documented retention/deletion behavior. Availability differs by platform and account authorization. Audience demographics and business contact data must only be accepted when explicitly provided by an authorized API and policy permits their use.

Recommended Phase 4 order: YouTube first (mature search/data model), Twitch second (well-scoped creator data), X third (tier and quota validation), Instagram fourth (Meta review and business/creator constraints), and Snapchat last (most limited general discovery surface). Each integration should ship behind its adapter, contract tests, capability flags, quota controls, and policy review before enabling production traffic.
