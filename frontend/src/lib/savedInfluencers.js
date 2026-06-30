// Local-only "saved influencers" store per logged-in user.
// Brand-side feature — no backend collection involved.

const KEY = (userId) => `brandkrt:saved_influencers:${userId || "anon"}`;

export function readSaved(userId) {
  try {
    const raw = localStorage.getItem(KEY(userId));
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_) {
    return {};
  }
}

export function writeSaved(userId, map) {
  try { localStorage.setItem(KEY(userId), JSON.stringify(map)); } catch (_) { /* noop */ }
}

export function toggleSaved(userId, influencer) {
  const map = readSaved(userId);
  if (map[influencer.id]) {
    delete map[influencer.id];
  } else {
    map[influencer.id] = {
      id: influencer.id,
      username: influencer.username,
      category: influencer.category,
      city: influencer.city,
      country: influencer.country,
      followers: influencer.followers,
      avg_reel_views: influencer.avg_reel_views,
      collab_price: influencer.collab_price,
      profile_photo_url: influencer.profile_photo_url,
      verification_status: influencer.verification_status,
      saved_at: new Date().toISOString(),
    };
  }
  writeSaved(userId, map);
  return map;
}
