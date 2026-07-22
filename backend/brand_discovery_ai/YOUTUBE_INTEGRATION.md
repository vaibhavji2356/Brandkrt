# YouTube Data API v3 adapter

`YouTubeDataAPIAdapter` implements the existing `SourceProvider` contract. The production factory replaces only the YouTube mock with this adapter; the explicitly mock-only discovery preview continues using `build_mock_adapters()` and cannot make platform requests.

Configuration:

- `YOUTUBE_ENABLED` must be explicitly true before requests are allowed.
- `YOUTUBE_API_KEY` is required when enabled.
- `YOUTUBE_TIMEOUT_SECONDS` is constrained to 1–60 seconds.
- `YOUTUBE_MAX_RESULTS` is constrained to 1–50.

Creator search uses one `search.list(type=channel)` request followed by one batched `channels.list` request for channel details. Profile lookup uses `channels.list` by channel ID, handle, legacy username URL, or supported YouTube URL. Successful responses are cached in memory for five minutes by resource and non-secret request parameters. Repeated calls therefore avoid quota use; failures are never cached.

The adapter maps only selected channel facts into `NormalizedProfile`: ID, handle, canonical channel URL, title, description, country, default language, publication time, public subscriber count, public video count, total channel view count, topics, and channel keywords. Subscriber counts hidden by the owner remain null. Lifetime channel views use `total_view_count`, never `average_views`. YouTube does not expose the public verification badge through this API, so `verified` remains null with a warning. Raw Google response objects, etags, thumbnails, and error messages are never returned.

Quota exhaustion, daily limits, rate limits, invalid keys, disabled API projects, timeouts, malformed responses, and general upstream rejection have distinct secret-safe exceptions. Search result pages are not automatically traversed, keeping each search bounded to the configured maximum and avoiding surprise quota consumption.

The adapter follows the official `search.list`, `channels.list`, channel-resource, error, and quota documentation. Quotas are controlled by the Google Cloud project and can change; production operations should monitor Cloud Console usage and keep `YOUTUBE_ENABLED=false` until the API key is restricted and the project quota is approved.
