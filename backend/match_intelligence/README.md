# AI Match and Campaign Intelligence

The match pipeline accepts a validated `ResearchPackage`, builds one compact prompt from its bounded `ai_context`, requests qualitative structured output once for all creator profiles, validates references and protected factual claims, and combines the qualitative output with authoritative deterministic ranking scores. AI never owns measurable match scores or platform facts.

`POST /api/ai/match/recommendations` is authenticated and role-protected using existing dependencies. Provider configuration, budget, timeout, refusal, malformed output, grounding, or transport failures degrade to deterministic recommendations rather than returning a provider error. Request authentication and schema validation remain normal API boundaries.

The deterministic engine derives recommendation categories from existing scores: Excellent at 85+, Strong at 70+, Possible at 50+, and Weak below 50. Campaign type and content style are strategy suggestions. Budget fit and audience overlap explicitly return `Insufficient verified data.` when pricing or audience evidence is absent.

The OpenAI prompt receives only the fact-only context built by the Research Agent. It asks for concise marketing reasoning, campaign strategy, professional outreach, and explained risks. Structured Outputs constrains the response shape. Post-validation rejects mismatched or duplicate profile references, duplicate prose, numeric metric claims, and inferred verification or official website claims. Rejected output is never partially returned.

Performance controls include one provider call per package, low output verbosity, no tools, no persistence, no duplicate per-profile calls, stable prompt prefixes, bounded factual context reuse, strict output lengths, and the existing paid-provider usage and budget accounting.
