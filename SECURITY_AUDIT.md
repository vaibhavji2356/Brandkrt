# BrandKrt security review — 21 October 2026

Implementation base: `fa11617` from `origin/main`. Changes are in the separate
`security/privacy-hardening` worktree at `D:\Brandkrt-security`, preserving the
older checkout's unrelated uncommitted work. This report describes source and
isolated automated tests, not certification of the deployed service.

## Findings and fixes

| Severity | Finding | Result |
|---|---|---|
| High | Creator could override the active-campaign filter with `status=draft`; unknown roles received an unscoped listing | Enforce known roles and the active filter independently of request parameters. Existing per-ID campaign ownership checks retained. |
| High | MongoDB chat/contract/invoice uploads were public; legacy folders were mounted publicly | Only profile/logo/product images remain public. Private files require their owner/admin; chat recipients must belong to a conversation containing a message from the actual upload owner. Removed legacy private static mounts and prohibited private uploads via public Cloudinary/local storage helper. |
| High | Chat attachment metadata could point at another user's upload or an executable link | Accept only canonical chat upload IDs owned by the authenticated sender. |
| High | Refresh rotation issued another token without invalidating the original; logout only cleared cookies | Atomically consume refresh digests using MongoDB's unique `_id`; logout increments the user's token version, ending all sessions. Existing password-change/reset version revocation retained. |
| High | Stripe intent creation was treated as funded escrow; production could use fake/stub payments | Stripe funding disabled until a genuine confirmation flow exists. Nondevelopment payment operations require Razorpay; production provider errors cannot fall back to fake escrow. |
| High | Razorpay checked a signature without checking captured funds; a repeat confirmation could reset released escrow | Verify signature, payment capture, order binding, paid order, amount and currency with Razorpay. Already verified/released records return idempotently, without resetting release state. Conditional updates prevent invalid confirmations downgrading a completed verification. |
| High | Concurrent escrow creation lacked a unique live obligation constraint | Add partial unique indexes on live deal/agreement payments. Index creation stops on legacy duplicates; no records are deleted. |
| Medium | Brand could supply its own platform-fee percentage | Normal brands use the existing 10% server-side fee; only admin can override it. |
| Medium | Financial fields persisted without application field encryption | AES-256-GCM envelopes for profile bank details/UPI and withdrawal payout details; fresh nonce and field-bound authentication, with a server-only 32-byte key. Added resumable, compare-and-update migration. |
| Medium | Google login bypassed the origin guard | Removed exemption; production requires an approved Origin/Referer for this login too. |
| Medium | Several marketplace operations/reset/verification routes lacked request limits | Shared Mongo-capable API read/write, chat, campaign and payment limits, plus explicit reset/email-verification/resend limits. Existing login/register/upload/AI limits retained. |
| Medium | Registration OTP and reset consumption were non-atomic | Compare-and-update consumption; five bad registration OTP attempts retire the current OTP. New reset/verification links store SHA-256 digests; short-lived legacy links remain compatible. |
| Medium | Regex search interpreted attacker-controlled patterns | Escape and bound chat/conversation/admin-user search text. Existing escaped discovery searches retained. |
| Medium | Broad legacy document serialization could expose future authentication fields | Recursive credential filtering across domain/chat/performance serializers, including nested fields; minimal JWT claims remove email and role. Existing explicit public profile allowlists retained and applied before financial decryption. |
| Medium | No scoped staff access model | Staff can list users only with database-assigned `users:read`. All other admin actions remain admin-only. Frontend role/permission values confer no authority. Admin/staff API access is audited. |
| Medium | Executable/data HTML URL values and token-bearing browser history | Block executable schemes and HTML/SVG data URLs in API asset normalization. Reset/verification screens capture the token in component memory and remove it from the address bar. React text escaping retained; no unsafe HTML rendering found. |
| Low | Suspended users could receive login cookies; malformed signed user IDs could raise internal errors | Refuse disabled/suspended/deleted login accounts and turn malformed IDs into 401 responses. |

## Existing controls inspected and retained

- FastAPI/Pydantic, Motor/MongoDB, React. Passwords already use salted bcrypt;
  names, emails and other account data are not bcrypt-hashed.
- Authentication uses HttpOnly cookies, 15-minute access tokens, seven-day
  refresh tokens, production Secure/SameSite settings, current database roles
  and account status. Bearer tokens from browser storage are not accepted.
- Public marketplace profiles use an explicit field allowlist. `/me` reads are
  scoped to the authenticated database user. Deal, legacy-message, agreement,
  collaboration, performance, commercial-history, evidence/export and payment
  routes contain server-side tenant/participant checks, covered by existing tests.
- Admin intelligence, diagnostics and metrics require server-side admin access.
  Staff privileges do not imply blanket admin access. No self-registration or
  profile-update route can grant staff/admin privileges.
- Upload signatures, extensions, claimed MIME, image decoding, folder types and
  bounded reads are validated. Storage IDs are server-generated. Nonimages and
  private downloads are attachments with `nosniff` and private/no-store caching.
- CORS uses exact approved origins, not wildcard credentials. Production CSRF
  rejects missing/unapproved origins. Security headers include CSP, frame denial,
  HSTS, referrer and permissions policies. Frontend CSP now permits the existing
  Razorpay checkout explicitly, while keeping script origins bounded.
- Production exception handlers suppress validation inputs, database details and
  unexpected stack traces. Access logging omits query strings and bodies.
- RazorpayX already uses a stable payout idempotency header. There is no payment
  webhook ingress endpoint to accept unsigned events; checkout verification is
  the implemented funding confirmation path.

## Validation and second review

- Full backend suite: **321 passed**, including the new anonymous GET-route sweep,
  cross-user private files, legitimate chat sharing, unknown-role campaign access,
  explicit staff permissions, token replay/logout revocation, database role checks,
  production Google CSRF, Razorpay capture and production fake-payment rejection.
- Existing regression tests cover cross-tenant deals/payments/messages, protected
  performance/evidence/exports, profile redaction, upload spoofing/SVG rejection,
  CORS, withdrawals and normal marketplace workflows.
- AES-GCM tests check ciphertext secrecy, random nonces, correct decryption, wrong
  key failure and real profile API round trips without cross-user finance exposure.
- Frontend: **25 tests passed**, four suites; production build compiled successfully.
- Generated inventory: **164 API routes**, with handler and dependency names in
  `SECURITY_ROUTE_INVENTORY.json`. All private GET routes reject anonymous visitors.
- Heuristic secret scan traversed Git history across available refs: five matched
  commit/file locations, inspected as example MongoDB credentials and a fake test
  API key. No confirmed live key was identified by these patterns. This is not a
  complete entropy scan or evidence that no secret has ever escaped.
- Second source pass covered modified filters, serializers, private/static files,
  session revocation/rotation, payment transitions, logging, encryption, CORS and
  frontend links. `git diff --check` passed.

## Required deployment configuration and migration

Changed files:

- Authentication/API/security: `backend/server.py`, `backend/security.py`,
  `backend/authorization.py`, `backend/serialization.py`.
- Marketplace/files/payments: `backend/domain.py`, `backend/part4b.py`,
  `backend/part4c.py`, `backend/payments.py`, `backend/storage.py`.
- Encryption/database/config: `backend/private_fields.py`,
  `backend/database_setup.py`, `backend/.env.example`,
  `backend/scripts/encrypt_private_fields.py`.
- Verification: `backend/tests/test_privacy_hardening.py`,
  `backend/scripts/security_inventory.py`, `SECURITY_ROUTE_INVENTORY.json`.
- Frontend: `frontend/src/lib/brand.js`, `frontend/src/lib/brand.test.js`,
  `frontend/src/pages/auth/ResetPassword.jsx`,
  `frontend/src/pages/auth/VerifyEmail.jsx`, `frontend/vercel.json`.
- Report: `SECURITY_AUDIT.md`.

Set `APP_ENV=production`, strong `JWT_SECRET`, `MONGO_URL`, `DB_NAME`, exact HTTPS
`CORS_ORIGINS`, HTTPS `FRONTEND_URL`, `RATE_LIMIT_BACKEND=mongo`,
`PAYMENT_PROVIDER=razorpay`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and the new
`PRIVATE_DATA_ENCRYPTION_KEY`. RazorpayX also needs `RAZORPAYX_ACCOUNT_NUMBER`.
Keep all secrets in backend hosting secret settings, never `REACT_APP_*`.
Existing production validation also requires durable private evidence storage
(S3 bucket/region/access/secret/encryption settings), and Mongo AI accounting
when paid AI is enabled. Retain configured transactional email credentials.

Generate the financial key **on the server** and save it in secret management:

```powershell
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Back up MongoDB and store a separate secure backup of the encryption key before
applying encryption. Losing or replacing this key makes encrypted fields
unreadable. This migration changes field representation but deletes no data.
Legacy plaintext financial records remain readable until migrated; privacy is
enforced by authorization throughout.

```powershell
Set-Location D:\Brandkrt-security\backend
python -m pip install -r requirements.txt
python scripts/encrypt_private_fields.py          # dry-run counts only
python scripts/encrypt_private_fields.py --apply  # encrypt existing financial fields
python database_setup.py                         # indexes, TTL, configured admin bootstrap
python -m pytest tests -q
python scripts/security_inventory.py
uvicorn server:app --host 0.0.0.0 --port 8000 --no-access-log
```

`database_setup.py` also performs its existing admin bootstrap: configure the
intended admin credentials deliberately. Use MongoDB 6+ for partial `$in` indexes.
If unique live-payment indexes report duplicates, reconcile provider payments
manually before deployment; never delete financial records to make indexes pass.

```powershell
Set-Location D:\Brandkrt-security\frontend
yarn install --frozen-lockfile
$env:CI='true'
npm test -- --watch=false --runInBand
npm run build
```

For isolated backend tests without deployment secrets, set `APP_ENV=development`
and a nonproduction `JWT_SECRET`. Do not run the migration/setup commands against
production with the test secret or test database credentials.

## Remaining operational limits

These changes have not been deployed or pushed. No production database writes,
key rotations, paid provider transactions, network firewall changes or destructive
schema operations were performed. The original dirty checkout is unchanged by
this security branch.

- Verify live HTTPS redirects/TLS, CDN headers and proxy trust configuration at
  Render/Vercel. The repository cannot establish the live deployment settings.
- Verify MongoDB network allowlists/private connectivity, TLS, least-privilege
  credentials, provider encryption at rest, backups and storage bucket policy.
  Application field encryption covers financial fields; general PII still needs
  the database/storage provider's encryption and access controls.
- Existing publicly cached private files cannot be recalled by a source change.
  Purge CDN copies and revoke/migrate any old public Cloudinary document links.
  Legacy disk documents have no reliable ownership metadata and are intentionally
  unavailable until mapped to authenticated uploads.
- Test Razorpay capture with provider sandbox credentials, reconciliation,
  concurrent requests and timeouts against real MongoDB before production.
  Mock-backed tests do not establish a live provider/network guarantee. Stripe
  funding is deliberately unavailable until verified confirmation is implemented.
- Required encryption key must be configured before production financial writes.
  Rotate it by decrypting with the old key and re-encrypting with the new one;
  simply replacing the environment value is unsafe.
- If any real credential was previously disclosed outside the scanned Git text,
  rotate it at its issuer (MongoDB, JWT, email, payment, AI, storage, Instagram),
  update backend secrets and invalidate affected sessions. No live key exposure
  was confirmed here, so no potentially disruptive blind rotation was attempted.
- Dependency vulnerability feeds, penetration testing of the deployed service,
  live browser session separation and hosting/provider audit logs were not audited.
  This source review and its passing tests do not justify an absolute security guarantee.

References: [OWASP BOLA](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/),
[OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
