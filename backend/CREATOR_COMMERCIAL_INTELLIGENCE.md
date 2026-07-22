# Creator Commercial Intelligence

## Architecture

Phase 11 adds two optional layers around the existing deterministic Creator Intelligence Engine. The engine remains the only authority for ranking, selection, scores, pricing analysis, budgets, reach, engagement, ROI, and confidence.

Grounded narrative flow:

1. Build the deterministic `CreatorIntelligenceResponse`.
2. Build a bounded narrative context from that response and the supplied campaign objective.
3. Optionally make one call through the existing OpenAI configuration, structured-output, cost-accounting, and rate-limit conventions.
4. Validate the strict Pydantic response.
5. Ground every identity, creator order, currency, numeric claim, and safety claim against the deterministic result.
6. Return the grounded narrative, or a deterministic fallback without exposing provider output or errors.

Commercial persistence flow:

1. Authenticate and enforce the existing `brand`/`admin` role semantics.
2. Derive the tenant from the authenticated actor; tenant ownership is never accepted from a request payload.
3. Validate ownership, currency, platform identity, timestamps, and record integrity in `CommercialService`.
4. Execute a tenant-filtered operation through `CommercialRepository`.
5. Store safe audit metadata in the existing `activity_logs` collection.

Narrative generation and persistence are isolated. Deterministic recommendations do not require MongoDB or OpenAI unless the caller explicitly enables the corresponding optional feature.

## Deterministic source-of-truth rule

The AI narrative cannot change:

- creator references or ordering;
- selected portfolio membership;
- rates, rate types, currency, or pricing verification;
- campaign budget, expected spend, or remaining budget;
- creator, recommendation, budget-fit, confidence, or ROI scores;
- expected reach or engagements;
- warnings or evidence status.

`include_ai_narrative` defaults to `false`. `use_commercial_history` also defaults to `false`, preserving the Phase 10 request and response behavior.

## Structured narrative output

`CreatorNarrative` contains only bounded fields:

- exact `profile_reference`, `platform`, `platform_id`, and optional `username`;
- selection reason;
- up to five strengths and weaknesses;
- pricing assessment and negotiation guidance;
- uncertainty statement;
- up to five risk flags.

`PortfolioNarrative` contains bounded executive summary, objective alignment, budget assessment, portfolio trade-offs, expected-efficiency summary, risk summary, recommended actions, creator narratives, confidence statement, and warnings. Arbitrary metadata and unknown fields are forbidden. Raw model output is never returned.

## Grounding validation

The validator requires every deterministic creator exactly once and in the authoritative ranking order. Platform identity must exactly match the source result. Numeric claims are validated within their semantic field: pricing text can use only that creator's pricing numbers; budget text can use only budget values; confidence text can use only authoritative confidence; and efficiency text can use only authoritative ROI values. A number that exists elsewhere in the result cannot be repurposed as a creator rate.

It rejects:

- unknown or reordered creators;
- identity, currency, rate, budget, spend, confidence, ROI, reach, or engagement changes;
- unsupported demographics or campaign outcomes;
- guarantees and revenue/conversion/install forecasts;
- followers-as-reach claims;
- claims that estimates are verified facts;
- HTML and Markdown-link payloads.

On any parse, provider, timeout, cost, context-size, or grounding failure, the API discards the model output and returns the unchanged deterministic result with a provider-safe warning and deterministic fallback narrative.

## Fallback narrative

The no-network fallback summarizes selected creators, exact budget utilization, confidence, pricing limitations, missing evidence, portfolio trade-offs, and next verification steps. It makes no causal, revenue, conversion, or guaranteed-outcome claims.

The fallback is used when AI is requested but OpenAI is disabled or unconfigured, the usage guardrail rejects the call, the provider fails or times out, structured output is malformed, or grounding validation fails. No provider call occurs when narration is disabled.

## Commercial data model

### Creator commercial profile

Stores tenant-scoped platform identity, username, currency, current known and negotiated rates, verification status, bounded pricing notes, timestamps, and internal actor metadata. Tenant and actor identifiers are excluded from public response models.

### Creator rate history

Append-only rate facts contain type, amount or range, currency, source, verification state, effective time, notes, and creation metadata. There are no update or delete endpoints.

### Negotiation record

Append-only negotiations preserve initially quoted, counter-offer, and agreed amounts as separate fields. An agreed value never overwrites the quote. Campaign linkage is optional but, when present, is ownership-validated.

### Campaign performance record

Stores the owned campaign and commercial profile, objective, agreed cost, deliverables, optional observed metrics, evidence state, measurement source and period, optional selection-time estimates, notes, timestamps, and normalized platform identity. Missing measurements remain `null`.

Verified performance changes require an explicit correction reason. Every correction stores a tenant-scoped prior version and writes an audit event. Completed deliverables exceeding committed deliverables remain representable but produce an explicit evidence warning.

## Pricing precedence

When commercial history is enabled, the deterministic merge precedence is:

1. verified commercial history;
2. verified request data;
3. request manual override;
4. unverified commercial history;
5. unverified request data;
6. caller estimate;
7. deterministic estimate.

Rejected history is ignored. History older than 180 days is marked stale and receives a confidence reduction. A history currency different from the campaign currency is ignored with a warning. Recommendation reads never write or refresh stored records.

## Authorization and tenant isolation

Only authenticated `brand` and `admin` roles can use commercial endpoints. Brand tenant scope is derived from the authenticated user ID and included in every profile, rate, negotiation, performance, history-integration, and analytics query. A record belonging to another brand returns `404`, preventing identifier probing and horizontal privilege escalation.

Admins retain the repository's existing convention of reading and managing records across tenants. Admin-created records use the authenticated admin's own tenant namespace unless they append to an existing tenant-owned record. Public responses do not expose tenant IDs, creator/brand actor IDs, or audit internals.

Campaign-linked writes independently validate campaign ownership against the authenticated brand's user ID or brand profile ID. These endpoints never invoke payment, escrow, payout, invoice, contract, or outreach behavior.

## Persistence and indexes

Collections:

- `creator_commercial_profiles`
- `creator_rate_history`
- `creator_negotiations`
- `campaign_performance_records`
- `commercial_record_versions`
- existing `activity_logs` for audit metadata

The deployment index setup adds tenant/identity uniqueness and tenant/date lookup indexes. Database index creation remains an explicit deployment operation through `database_setup.py`, not web-process startup work.

## Performance attribution

The comparison reader reports estimate and observation separately for spend, reach, engagements, CPE, CPM, and deliverables. Each observed value is labeled `verified`, `unverified`, or `unavailable`; each estimate is labeled `estimate` or `unavailable`. Percentage variance is calculated only when both values exist and the estimate denominator is non-zero.

Observed engagements equal the sum of supplied likes, comments, and shares when at least one is present. Observed CPE and CPM require agreed cost and their observed denominator. Followers are never substituted for reach. The normalized observed efficiency score is descriptive, and no causal attribution is claimed. Revenue and conversions are merely retained as optional supplied observations; no causal claim is generated.

Example abbreviated comparison:

```json
{
  "currency": "USD",
  "reach": {
    "estimate": 9000,
    "observed": 10000,
    "variance": 11.11,
    "estimate_status": "estimate",
    "observed_status": "verified"
  },
  "methodology": "Deterministic estimate-versus-observation comparison; no causal attribution is claimed."
}
```

## Analytics methodology

`GET /api/creator-commercial/analytics/summary` supports a maximum 366-day range and at most 500 records per source collection. It returns sample sizes, rate trend, negotiated discount, quote-versus-agreed totals, spend by creator/platform, observed CPE/CPM, deliverable completion, repeat collaborations, estimated-versus-observed reach variance, low-evidence records, and missing-performance records.

Required missing values are excluded, never counted as zero. If more than one currency exists and no currency filter is selected, aggregation returns `409` instead of producing a false cross-currency total. Empty states return empty collections, zero sample counts, and `null` unavailable metrics.

## Audit behavior

Commercial writes use the existing `activity_logs` infrastructure. Audit entries contain actor identifier, action category, record type and identifier, UTC timestamp, and changed field names only. They do not include full payloads, note contents, prompts, model responses, credentials, or tokens. Performance correction snapshots are operational version records rather than logs and remain tenant-scoped.

## API endpoints

- `POST /api/creator-commercial/profiles`
- `GET /api/creator-commercial/profiles`
- `GET /api/creator-commercial/profiles/{profile_id}`
- `PATCH /api/creator-commercial/profiles/{profile_id}`
- `POST /api/creator-commercial/profiles/{profile_id}/rates`
- `GET /api/creator-commercial/profiles/{profile_id}/rates`
- `POST /api/creator-commercial/profiles/{profile_id}/negotiations`
- `GET /api/creator-commercial/profiles/{profile_id}/negotiations`
- `GET /api/creator-commercial/analytics/summary`
- `POST /api/campaign-performance`
- `GET /api/campaign-performance`
- `GET /api/campaign-performance/{record_id}`
- `PATCH /api/campaign-performance/{record_id}`
- `GET /api/campaign-performance/{record_id}/comparison`
- Existing `POST /api/ai/creator-intelligence/recommendations`, with optional `include_ai_narrative` and `use_commercial_history` flags.

No delete endpoints are exposed.

## Privacy and retention

Commercial rates, negotiations, notes, and campaign evidence are tenant-owned sensitive business records. Only the minimum creator identity required to link a platform profile is stored. Notes are bounded and should not contain unnecessary personal data. Evidence should be stored only when the brand is authorized to retain it.

The implementation provides versioned corrections and audit metadata but does not claim compliance with any specific privacy, tax, accounting, employment, or advertising regime. Retention periods, legal holds, creator access, consent, tenant export, and deletion workflows require a verified policy in a future phase. Sensitive records should not be copied into prompts or logs.

## Operational limitations and future boundaries

- AI narrative quality is limited by the deterministic evidence supplied.
- In-process AI usage accounting remains single-process, matching the existing guardrail architecture.
- Commercial history is MongoDB-backed and does not perform background refresh.
- Revenue and conversion methodology are not independently verified.
- No payment, escrow, payout, invoicing, contract, autonomous negotiation, outreach, scraping, CRM, or background-worker behavior is implemented.
- Future payment integration must consume agreed commercial facts through a separately authorized workflow; these endpoints must never trigger money movement.

Example commercial rate record:

```json
{
  "commercial_profile_id": "...",
  "rate_type": "negotiated",
  "amount": 425,
  "currency": "USD",
  "source": "signed_rate_card",
  "verification_status": "verified",
  "effective_at": "2026-07-22T10:00:00Z",
  "notes": []
}
```

Example grounded narrative excerpt:

```json
{
  "executive_summary": "The deterministic portfolio selected the available funded creators for the supplied objective.",
  "budget_assessment": "Expected spend and utilization match the deterministic budget analysis.",
  "recommended_actions": [
    "Verify commercial terms and evidence before contracting.",
    "Capture observed campaign performance for later comparison."
  ]
}
```
