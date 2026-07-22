# Creator Intelligence Engine

## Scope and architecture

Phase 10 is an additive, deterministic layer downstream of the Research Agent. It does not call provider APIs, OpenAI, payment systems, or the database. Existing discovery, normalized-profile, research-package, provider-orchestration, and match-intelligence contracts remain unchanged.

Flow:

1. Accept a completed `ResearchPackage`, campaign objective, budget constraints, and optional caller-supplied commercial or historical observations.
2. Preserve normalized platform facts and combine only explicitly supplied supplemental observations.
3. Select a usable price according to verified-rate precedence and produce an estimated negotiation range.
4. Calculate available-data creator quality, budget fit, efficiency/ROI, and recommendation scores.
5. Select a deterministic multi-creator portfolio under the budget and creator-count limits.
6. Return factual metrics, estimates with confidence, budget totals, warnings, and bounded deterministic explanations.

The implementation is split into `pricing.py`, `scoring.py`, `roi.py`, `optimizer.py`, and `engine.py`. The engine depends on their public contracts and does not know platform-provider internals.

## Input and output schema

`CreatorIntelligenceRequest` contains:

- `research_package`: existing factual Research Agent output.
- `campaign_budget`: positive amount, capped at 1 billion.
- `number_of_creators`: 1 through 10.
- `minimum_reach`: optional observed-reach target.
- `campaign_objective`: Brand Awareness, App Install, Sales, Gaming Launch, or Product Review.
- `currency`: ISO-style three-letter uppercase code.
- `creator_inputs`: optional, uniquely keyed supplemental insights and pricing evidence.

Supplemental fields include known, estimated, negotiated, and manually overridden rates; rate verification flags; range, confidence, source and notes; non-persistent negotiation-history placeholders; observed average views/likes/comments; posting frequency; audience quality; and content quality. They do not alter `NormalizedProfile`.

All per-creator currencies must match the campaign currency; mixed-currency portfolios are rejected rather than combined without a legitimate exchange-rate source.

The response contains:

- ranked creator recommendations and the selected-portfolio flag;
- measurable and optional creator intelligence metrics;
- per-creator pricing and ROI analysis;
- portfolio spend, remaining budget, utilization, reach and engagement totals;
- confidence and explicit warnings;
- `reasoning_source = deterministic_creator_intelligence`.

Unavailable fields remain `null`. Missing metrics are never serialized as invented zero values.

## Pricing rules

Rate selection uses this strict precedence:

1. verified negotiated rate;
2. verified known rate;
3. manual override;
4. unverified negotiated rate;
5. unverified known rate;
6. caller estimate;
7. deterministic estimate.

A manual override cannot replace a verified known or negotiated rate. The response states whether a verified rate was preserved and whether a manual override was applied.

When no supplied price exists, an estimate may use observed average views and a documented platform benchmark. A follower-based fallback is permitted only as a low-confidence pricing estimate; followers are never treated as expected campaign reach. The default negotiation range is 85% to 115% of the selected rate unless a legitimate range is supplied. Estimates are planning inputs, not creator quotes.

## Scoring

All scores are normalized to 0–100. Components absent from the available data are omitted and remaining weights are re-normalized; absence is not scored as zero.

Creator quality components:

| Component | Weight |
| --- | ---: |
| Engagement rate | 25% |
| Observed average views | 20% |
| Posting frequency | 15% |
| Audience quality | 20% |
| Content quality | 15% |
| Verification signal | 5% |

Recommendation score components:

| Component | Weight |
| --- | ---: |
| Creator quality | 35% |
| Existing Research Agent rank | 30% |
| Budget fit | 20% |
| Efficiency/ROI score | 15% |

Confidence combines source confidence, pricing confidence, ROI evidence, Research Package confidence, and component coverage. Therefore a partial profile can receive a meaningful score while carrying lower confidence.

## ROI and reach safeguards

Expected reach is populated only from observed/supplied average views. Follower count is not a reach substitute. Expected engagements use observed likes plus comments, or—at lower confidence—observed reach multiplied by a factual engagement rate. Cost per engagement and CPM are calculated only when their price and outcome denominators exist.

The ROI score is a normalized cost-efficiency comparison. It is not a forecast of revenue, conversions, installs, or profit. Those values remain unavailable until legitimate campaign performance data is supplied. Every modeled calculation carries confidence and warnings.

## Budget portfolio

The optimizer uses bounded sparse dynamic programming. It maximizes total recommendation utility subject to campaign budget and maximum creator count, with deterministic tie-breaking on reach, spend, and profile reference. A 5,000-state cap bounds pathological inputs while preserving deterministic behavior.

Only creators with a usable selected rate can enter the funded portfolio. Unpriced creators remain in the ranking with a warning. Portfolio reach and engagement totals are returned only when every selected creator has the required measurable basis. A requested minimum-reach result remains unknown when the evidence is incomplete.

## Explanation boundary

The current explanation is deterministic and objective-specific. It can describe factual strengths, missing-data weaknesses, pricing concerns, budget fit, and risks. It cannot introduce metrics or claims.

A future OpenAI explanation layer may summarize this grounded output, propose campaign messaging, or make the language more concise. It must treat the structured response as authoritative and must never invent or modify rates, reach, engagement, verification, identity, conversions, or external validation.

## API

`POST /api/ai/creator-intelligence/recommendations`

- Requires an authenticated `brand` or `admin` role.
- Uses the existing rate-limiting framework (10 requests per 60 seconds).
- Accepts `CreatorIntelligenceRequest` and returns `CreatorIntelligenceResponse`.
- Performs no database writes and no external requests.
- Existing discovery, research, and match endpoints are unchanged.

Example abbreviated response:

```json
{
  "ranking": ["youtube:channel-123"],
  "budget_analysis": {
    "campaign_budget": 5000,
    "expected_spend": 1200,
    "remaining_budget": 3800,
    "budget_utilization": 24,
    "selected_creator_count": 1,
    "requested_creator_count": 3,
    "expected_reach": 42000,
    "confidence": 0.71
  },
  "reasoning_source": "deterministic_creator_intelligence",
  "warnings": ["Pricing and ROI outputs are estimates unless explicitly marked as verified."]
}
```

## Phase 11 candidates

- Grounded, schema-validated AI narrative generation over the completed deterministic package.
- Legitimate CRM and analytics readers through the existing research hook interfaces.
- Persisted rate cards and negotiation history with authorization and audit controls.
- Campaign-performance ingestion for verified conversion and revenue attribution.
- Background optimization for larger portfolios.

These are hook points only. Phase 10 implements none of those external integrations or persistence paths.
