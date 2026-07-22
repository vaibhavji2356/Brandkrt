# Admin AI Lead Intelligence

Phase 14 adds an admin-only operating workspace over BrandKrt's existing factual discovery,
Research Agent, deterministic ranking, Match Intelligence, Creator Intelligence pricing,
Commercial Intelligence, observability, rate limiting, and audit infrastructure.

## Architecture

```text
Admin UI
  -> admin authorization + shared rate limiting
  -> persisted research job
  -> Research Agent / Provider Orchestrator
  -> normalized factual profiles
  -> deterministic ranking and lead priority
  -> optional grounded Match Intelligence
  -> safe public result snapshot
  -> saved-lead outreach workflow + audit events
```

Internal research tasks, AI context, prompts, raw provider responses, commercial private
notes, tenant identifiers, and credentials are never returned by this API.

## API

All routes are under `/api/admin/lead-intelligence` and require the `admin` role.

| Method | Route | Purpose |
|---|---|---|
| POST | `/research/jobs` | Queue factual brand, creator, or combined research |
| GET | `/research/jobs/{id}` | Poll progress and obtain normalized results |
| GET | `/research/history` | Search, filter, sort, and paginate sessions |
| POST | `/research/history/{id}/rerun` | Re-run stored validated criteria |
| POST | `/leads` | Save or safely refresh a result; duplicates are idempotent |
| GET | `/leads` | Search/filter/sort/paginate the outreach workspace |
| GET | `/leads/{id}` | View a saved lead and grounded assistance |
| PATCH | `/leads/{id}` | Update the controlled outreach status |
| POST | `/leads/{id}/notes` | Add an admin-only internal note |
| POST | `/leads/{id}/archive` | Archive without destructive deletion |
| GET | `/leads/{id}/audit` | Safe action metadata without note contents |
| GET | `/analytics` | Funnel, niche, platform, and research aggregates |
| GET | `/activity` | Safe AI/fallback activity summaries |

Brand, creator, and anonymous callers receive `403` or `401`. Responses never expose the
Research Agent `ai_context` or task metadata.

## Research execution

Requests support entity type, platforms, industry/niche, categories, keywords, exclusions,
geography, language, follower range, engagement threshold, campaign objective, budget range,
currency, and result limit. Audience-quality criteria are applied only when an official source
provides a legitimate quality measurement. Missing measurements are excluded, not scored zero.

FastAPI background tasks persist job progress and avoid long blocking HTTP requests. They are
not a durable distributed queue: a process restart can interrupt an active job. Its persisted
record remains available for review/rerun. A future worker can replace execution without changing
the public job contract. At most three active jobs are allowed per administrator.

## Provider policy

- Production registers the existing official YouTube, Twitch, and X adapters.
- Instagram and Snapchat remain unavailable until official factual adapters exist.
- Synthetic adapters require `ADMIN_LEAD_MOCK_MODE=true` in non-production. Mock attribution
  and warnings remain visible; production never registers them.
- No scraping or browser automation is used.
- Official APIs may return no brands when they do not provide reliable account classification.
- No claim is made that every public account is discoverable.

## Priority and assistance

Priority uses available data only: official activity 15%, reported engagement 20%, exact public
platform presence 15%, deterministic commercial/relevance fit 30%, and source confidence 20%.
Unavailable components are removed and remaining weights are normalized. Scores of 75+ are high,
50–74.99 medium, and below 50 low. Every result includes components and explanations.

Creator assistance reuses Match Intelligence. Provider failure returns its deterministic grounded
fallback. Brand assistance is deterministic and grounded. Suggestions cover why to contact,
campaign fit, outreach angle, conversation starter, and negotiation guidance. AI cannot create or
alter metrics, verification, identity, external validation, or commercial facts. Creator pricing
reuses the deterministic pricing engine and is labeled as an estimate requiring confirmation.

## Persistence, indexes, and audit

- `admin_research_jobs`: criteria, progress, safe results, sources, warnings, reasoning state.
- `admin_saved_leads`: unique fingerprint, factual snapshot, status, archive state, admin notes.
- `activity_logs`: safe action, entity, changed-field names, actor category, timestamp.

Audit records never store note text, prompts, provider responses, tokens, or credentials.
Run `python database_setup.py` to create indexes; readiness verifies the critical job and unique
fingerprint indexes.

`tests/test_admin_lead_intelligence.py` covers authorization, brand/creator research, grounded
results, safe failure, history/rerun, duplicate-safe saving, outreach status, note audit redaction,
archive, pagination, analytics, activity, and idempotent indexes without live provider calls.

