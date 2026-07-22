# Admin AI Dashboard Guide

Phase 14 is available only to authenticated administrators under `/admin`. Backend authorization
remains authoritative; the frontend redirect is a usability layer.

## Navigation and workflows

- **Overview** links directly to brand discovery, creator discovery, and outreach.
- **AI Lead Intelligence** shows funnel metrics, top niches/platforms, and recent activity.
- **Brand Discovery** runs factual brand research and exposes provider limitations.
- **Creator Discovery** displays metrics, pricing estimates, strengths, weaknesses,
  recommendation scores, confidence, and grounded assistance.
- **Saved Leads** provides manual outreach statuses, admin-only notes, archive, search, filters,
  sorting, and pagination. It never sends messages.
- **Research History** searches prior jobs, shows stored explanations and duplicate suggestions,
  and reruns validated criteria.
- **Commercial Intelligence** reads authorized commercial profiles, performance, and aggregates.
- **AI Activity** identifies grounded AI versus deterministic fallback outcomes.
- **Operations** renders safe diagnostics and admin-protected Prometheus metrics.
- **Settings** shows safe read-only backend configuration state, never secret values.

Existing Users, Verification, Escrow, Withdrawals, Reports, and Logs screens remain intact.

## Discovery behavior

The UI creates a persisted job, polls it for up to two minutes, and displays progress. Results can
be searched, sorted, paginated, inspected, and saved. Provider failures produce a retryable error
or honest empty state; loading always resets. Missing fields render as `Unavailable` and are never
replaced with zero or generated facts. External links use new tabs with `noreferrer`.

Conversation starters and negotiation guidance are suggestions. Administrators must verify
identity, availability, price, rights, and terms directly before outreach or agreement.

## Responsive and API behavior

The sidebar becomes a dismissible drawer on small screens. Tables scroll horizontally, card grids
collapse, and filters reflow. Every data screen has loading, empty, error, and retry handling.

The UI uses `/api/admin/lead-intelligence/*`, existing Commercial Intelligence reads, and
`/api/admin/operations/*`. The shared Axios client preserves cookie authentication, refresh,
bounded timeout, and safe GET retry behavior.

## Validation

```powershell
cd frontend
$env:CI='true'
npm test -- --watchAll=false --runTestsByPath src/pages/admin/AdminAIPlatform.test.jsx
npm run build
```

Component tests cover dashboard access, discovery-to-save integration, retry/loading behavior,
outreach status updates, and research-history explanations.

