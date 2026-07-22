# Commercial Evidence and Retention

## Architecture

Phase 12 hardens commercial intelligence without changing authentication, payments, providers, deterministic scoring, or frontend behavior.

Evidence flow:

1. Authenticate the request and independently validate tenant ownership of the campaign-performance record.
2. Read a bounded file and validate its filename, extension, declared MIME type, detected content, size, and integrity.
3. Store bytes through `EvidenceStorage` under a generated private key outside the public upload tree.
4. Store only evidence metadata, checksum, ownership, retention, and review state in MongoDB.
5. Write a safe activity-log event containing changed field names, not the payload.

Correction flow:

1. Validate record ownership and exact base version.
2. Store an immutable, typed, allowlisted proposal without mutating the performance record.
3. Require an explicit admin review decision.
4. On approval, atomically check the base version, create the next record version, retain the prior snapshot, and audit the decision.

Export and retention remain synchronous and explicitly bounded. No scheduler, background worker, public bucket, archive generator, OCR engine, or document macro parser is introduced.

## Evidence model

Internal evidence documents contain:

- tenant and performance-record ownership;
- campaign and normalized creator platform identity copied from the owned performance record;
- evidence and source types;
- original display name, sanitized filename, generated storage key, detected MIME type, byte size, and SHA-256 checksum;
- separate evidence activity and verification states;
- explicitly mapped supported metrics;
- optional measurement period and capture time;
- private notes;
- submission and reviewer metadata;
- deletion and retention timestamps.

Public evidence responses expose safe metadata only. They exclude tenant IDs, actor IDs, storage keys, filesystem paths, raw checksums, internal notes, and internal review fields. `checksum_present` communicates that integrity metadata exists without publishing it.

File presence never means verified evidence. Uploads start as:

```text
evidence_status = active
verification_status = unverified
```

## File validation

Supported formats are deliberately limited to:

- PDF
- PNG
- JPEG

CSV and office documents are not accepted for evidence in this phase, even though other upload categories may support them.

Validation rules:

- default maximum size is 8 MB, configurable up to 25 MB;
- empty files are rejected;
- path separators, traversal markers, null bytes, and missing extensions are rejected;
- dangerous inner extensions such as `.exe.png`, scripts, archives, macro documents, and HTML are rejected;
- the existing content sniffer validates image/PDF signatures and image integrity;
- extensions and declared MIME types must match detected content;
- images are parsed only for safe format/integrity checks;
- PDFs must have a PDF signature and terminal EOF marker, and active/embedded content remains rejected by the existing validator;
- SHA-256 is calculated after validation;
- duplicate active content for the same tenant and performance record is rejected;
- filenames are sanitized, bounded, and never used as storage paths.

The checksum is integrity and duplicate-detection metadata. It does not prove who created the evidence or whether its contents are authentic.

## Storage strategy

`EvidenceStorage` provides:

- `save`
- `read`
- `exists`
- `mark_deleted`
- safe authenticated download-reference generation

The implemented provider is `LocalPrivateEvidenceStorage`. It rejects configuration beneath `UPLOAD_ROOT`, generates random storage keys, validates every key before resolving a path, uses exclusive file creation, and has no public URL. Downloads stream through authenticated tenant-scoped API endpoints with `Cache-Control: private, no-store`.

Development and tests can use `InMemoryEvidenceStorage` without filesystem effects. The production local directory must be mounted as private durable storage; Render-style ephemeral disks are not sufficient for durable evidence. A future private-object-storage provider must support authenticated or expiring access and must not reuse the current public Cloudinary upload behavior.

Soft deletion does not immediately erase bytes. Physical erasure is a later retention operation and is intentionally not implemented as a broad cleanup command. Evidence-file expiry is enforced independently of metadata expiry: once the file-retention timestamp passes, authenticated downloads and restores are unavailable even if safe metadata is still retained.

## Verification workflow

Allowed transitions:

```text
unverified → verified
unverified → rejected
verified + verified replacement → superseded
active → soft deleted
soft deleted → restored, when unexpired and authorized
```

Evidence verification, rejection, and superseding require an authenticated admin reviewer. Brand users can upload and read their own evidence but cannot self-verify it. Rejection requires a bounded reason. Superseding requires a second active, verified evidence record for the same tenant and performance record. The superseded record and its bytes remain retained.

Verified evidence requires admin review before soft deletion or restoration. Deleted, expired, rejected, and superseded evidence does not support active attribution.

Verification is an internal evidence-review state. It is not legal validation, an audit opinion, or proof of authenticity.

## Evidence-to-metric mapping

Every upload declares the exact metrics it supports. Declarations must be a subset of the evidence-type allowlist.

| Evidence type | Permitted metrics |
| --- | --- |
| Analytics screenshot | Reach, views, impressions, likes, comments, shares, clicks |
| Platform export | Reach, views, impressions, likes, comments, shares, clicks, conversions |
| Invoice copy | Agreed cost |
| Signed rate card | Agreed cost |
| Contract reference | Agreed cost, deliverables |
| Deliverable proof | Deliverables |
| Campaign report | Reach, views, impressions, likes, comments, shares, clicks, conversions, revenue, deliverables |
| Payment reference | Agreed cost |
| Other | No metrics by default |

Evidence measurement periods must overlap the campaign-performance measurement period. Campaign, creator identity, and tenant are copied from the owned performance record rather than accepted from upload metadata. Evidence never creates a metric value; it can only support an already supplied observation.

Reviewed platform exports, reports, and other mapped non-screenshot evidence can mark the mapped observation verified. Reviewed screenshots remain `reviewed_limited` and do not independently verify a metric. Unreviewed evidence supports only unverified observations. Rejected evidence has no supporting IDs and does not increase confidence. One evidence record cannot verify metrics outside its explicit mapping.

Followers are not an evidence type and are never substituted for reach.

## Evidence-aware attribution

Campaign-performance responses now include additive fields:

- `metric_evidence`
- `evidence_confidence`

Each metric reports observation status, evidence status, safe supporting evidence IDs, review level, and a confidence note. Missing observed values remain unavailable. Existing observed values without evidence remain unverified rather than becoming zero.

Performance comparisons apply the weakest required evidence status:

- CPE requires supported cost and engagement components;
- CPM requires supported cost and reach;
- engagement status combines the supplied likes, comments, and shares that are present;
- deliverable comparison uses deliverable evidence;
- revenue and conversion values remain observations only, with no causal claim.

## Correction review and versioning

Correction proposals support an allowlisted set of performance fields. Tenant, record identity, platform identity, campaign identity, storage details, audit metadata, and currency cannot be proposed. Currency changes are rejected as unknown fields and require a separately designed migration policy.

A proposal contains its base version, typed proposed values, reason, private notes, status, and retention metadata. The record remains unchanged while the proposal is pending. Pending proposals have no mutation endpoint.

Admin approval rechecks the record version. A stale version returns `409`. Successful approval increments the record version, stores the prior version in `commercial_record_versions`, and records the approved version ID on the proposal. Rejected and cancelled proposals remain available for audit review. Brand users can cancel only their own pending proposals.

The existing performance PATCH remains available for backward compatibility. The review workflow is the hardened path for sensitive, independently approved changes.

## Retention policy

Default policy:

| Category | Default |
| --- | ---: |
| Evidence metadata | 730 days |
| Evidence file | 730 days |
| Correction proposals | 1095 days |
| Export artifacts | 7 days |
| Audit events | 2555 days |

Configuration variables:

- `COMMERCIAL_RETENTION_EVIDENCE_METADATA_DAYS`
- `COMMERCIAL_RETENTION_EVIDENCE_FILE_DAYS`
- `COMMERCIAL_RETENTION_CORRECTION_DAYS`
- `COMMERCIAL_RETENTION_EXPORT_DAYS`
- `COMMERCIAL_RETENTION_AUDIT_DAYS`

An explicit value of `indefinite` is supported. Invalid values fall back to documented defaults. Dates use timezone-aware UTC.

No scheduler exists, so retention evaluation is an explicit admin-only maintenance endpoint. Evaluation is idempotent and soft-deletes only expired evidence metadata and export artifacts. It never hard-deletes commercial history or file bytes. Expiry is enforced on reads even before maintenance runs.

## Soft deletion and restore

Soft deletion writes `deleted_at`, internal actor, bounded reason, and inactive status while retaining metadata and referential integrity. Normal list/get/download queries exclude deleted records. Evidence restoration requires an existing private file and an unexpired retention period. Verified evidence delete/restore requires admin review.

Soft deletion is a logical availability state and does not imply immediate physical erasure.

## Tenant export

Exports are synchronous JSON only. CSV and ZIP are intentionally unsupported, eliminating spreadsheet formula execution and archive-handling risks.

Requests are limited to:

- a timezone-aware date range of at most 366 days;
- explicit record categories;
- at most 1000 rows per category;
- a serialized artifact of at most 2 MB.

The tenant is derived from authentication. Default exports recursively redact all public/private notes plus tenant IDs, actor IDs, credentials, tokens, storage keys, raw checksums, prior internal snapshots, raw AI prompt/response fields, and audit metadata payloads, including those found in nested objects. Evidence metadata may be included, but raw evidence bytes are never included. `include_private_notes=true` is an explicit tenant-authorized option; credentials and internal identifiers remain excluded regardless.

Artifacts are stored privately, expire according to policy, and download through authenticated endpoints. Repeated downloads create audit events. Deleted and expired artifacts are unavailable. Export generation does not mutate source records.

Example export manifest:

```json
{
  "schema_version": "1.0",
  "exported_at": "2026-07-22T10:00:00+00:00",
  "record_categories": ["profiles", "performance", "evidence"],
  "redacted_private_notes": true,
  "include_deleted": false,
  "data": {
    "profiles": [],
    "performance": [],
    "evidence": []
  }
}
```

## Sensitive commercial notes

New `internal_notes` fields are separated from public response models. They are bounded, tenant-controlled, excluded from AI narrative context, analytics, activity-log contents, evidence responses, and default exports. Existing public notes remain backward-compatible.

There is no existing key-management abstraction suitable for field-level encryption, so this phase does not invent cryptography or hard-code keys. Encryption at rest depends on MongoDB and private-storage deployment configuration. Field-level encryption and key rotation require a reviewed KMS design in a future phase.

## Audit review

Commercial hardening writes reuse `activity_logs`; no second audit system was created. New audit records include tenant scope and actor category internally, while public review responses redact actor IDs and return only action, record type/ID, changed field names, and timestamp.

The read endpoint supports bounded date range, record type, record ID, action, and limit filters with stable newest-first ordering. Brand users receive only their tenant events. Admin behavior follows existing conventions. Private payloads and note contents are never returned.

## Tenant isolation

- Tenant IDs are never request fields.
- Performance ownership is validated before evidence or correction work.
- Evidence and replacement evidence are independently scoped.
- Campaign and creator identity are inherited from the owned record.
- Brand cross-tenant access returns `404`.
- Evidence/correction review requires explicit admin role.
- Export, download, audit, soft delete, restore, and retention operations each perform their own authorization checks.
- Possession of a Mongo object ID grants no privilege.

## Database indexes

Focused compound indexes cover:

- tenant, performance record, and evidence submission time;
- tenant evidence/verification states;
- tenant, performance record, and checksum;
- tenant retention and deletion state;
- tenant correction record/status/submission time;
- tenant correction retention;
- tenant export creation/expiry/deletion;
- tenant audit creation time.

Checksum uniqueness is enforced deterministically in the service rather than with a global unique index, so tenant isolation and deleted history remain representable.

## API endpoints

Evidence:

- `POST /api/campaign-performance/{record_id}/evidence`
- `GET /api/campaign-performance/{record_id}/evidence`
- `GET /api/campaign-evidence/{evidence_id}`
- `GET /api/campaign-evidence/{evidence_id}/download`
- `POST /api/campaign-evidence/{evidence_id}/verify`
- `POST /api/campaign-evidence/{evidence_id}/reject`
- `POST /api/campaign-evidence/{evidence_id}/supersede`
- `DELETE /api/campaign-evidence/{evidence_id}`
- `POST /api/campaign-evidence/{evidence_id}/restore`

Corrections:

- `POST /api/campaign-performance/{record_id}/corrections`
- `GET /api/campaign-performance/{record_id}/corrections`
- `GET /api/commercial-corrections/{correction_id}`
- `POST /api/commercial-corrections/{correction_id}/approve`
- `POST /api/commercial-corrections/{correction_id}/reject`
- `POST /api/commercial-corrections/{correction_id}/cancel`

Export, audit, and retention:

- `POST /api/creator-commercial/exports`
- `GET /api/creator-commercial/exports/{export_id}`
- `GET /api/creator-commercial/exports/{export_id}/download`
- `DELETE /api/creator-commercial/exports/{export_id}`
- `GET /api/creator-commercial/audit-events`
- `POST /api/creator-commercial/retention/evaluate`

No payment, escrow, payout, invoice, contract, outreach, scraping, or public evidence URL is created.

## Privacy and operational limitations

Evidence can contain personal and commercially sensitive data. Brands must have an appropriate basis to retain it. Verification is not a legal determination. Retention configuration is policy enforcement, not a compliance certification. Audit logs deliberately omit payloads. Exports expire but remain sensitive while available. Soft deletion is not guaranteed immediate physical deletion.

This implementation makes no GDPR, SOC 2, PCI, legal-retention, evidentiary, accounting, or advertising-compliance claim. Formal policy approval, data-subject workflows, legal holds, tenant deletion/export obligations, private cloud object storage, malware scanning, field encryption, KMS rotation, and physical erasure procedures remain future work.

Example safe evidence response:

```json
{
  "id": "...",
  "campaign_performance_record_id": "...",
  "evidence_type": "platform_export",
  "source_type": "platform_export",
  "display_filename": "campaign-report.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 24018,
  "checksum_present": true,
  "evidence_status": "active",
  "verification_status": "unverified",
  "supported_metrics": ["observed_reach"],
  "retention_status": "active",
  "download_available": true
}
```

Example correction proposal:

```json
{
  "record_type": "campaign_performance",
  "record_id": "...",
  "base_version": 1,
  "proposed_changes": {"observed_reach": 12000},
  "proposed_fields": ["observed_reach"],
  "reason": "Corrected platform export",
  "status": "pending"
}
```
