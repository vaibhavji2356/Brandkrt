# Twitch Helix provider

`TwitchHelixAdapter` implements the existing `SourceProvider` interface. The production adapter factory replaces Twitch with the real Helix adapter while the explicitly mock-only preview retains `TwitchMockAdapter`. The existing Research Dispatcher already accepts any `SourceProvider`; no Research Agent architecture changed.

The adapter uses OAuth 2.0 client credentials to acquire an app access token. It stores the token only in memory, honors `expires_in` with a safety window, and reacts to a Helix `401` by acquiring one new app token and retrying once. Authentication parameters are sent in a form body, and secrets, tokens, Twitch messages, and raw responses are never exposed through public adapter errors.

Creator search calls `search/channels` once, then batches up to 100 broadcaster IDs into one `users` request. Profile lookup calls `users` by numeric ID or normalized login. Successful Helix responses are cached in memory for five minutes by endpoint and non-secret parameters. Failures and token responses are not placed in the result cache.

Normalized output includes Twitch ID, login, display name, channel URL, description, search language, current/last category and tags, account creation time, source confidence, and collection time. Twitch `partner` maps to `verified=true` because Partner channels receive Twitch’s verified checkmark. Affiliate status does not establish verification and remains `verified=null` with a warning.

An app access token cannot satisfy the user authorization required by `channels/followers`, so follower count remains null. The deprecated `users.view_count` is ignored. `profile_image_url` is retrieved as part of `users` but cannot be represented because the existing normalized schema has no image field; it is intentionally omitted with a warning rather than placed in an unrelated field.

Configuration:

- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`
- `TWITCH_ENABLED`
- `TWITCH_TIMEOUT_SECONDS` (1–60)
- `TWITCH_MAX_RESULTS` (1–100)

Rate limits (`429`), invalid credentials or tokens (`401`/`403`), timeouts, malformed responses, and service failures (`5xx`) map to distinct provider-safe errors. Twitch currently uses a token-bucket rate limit and exposes reset information in response headers; this adapter does not sleep or retry rate-limited calls automatically.
