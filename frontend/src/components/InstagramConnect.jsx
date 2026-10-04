import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";

export default function InstagramConnect({ onSync }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const outcome = new URLSearchParams(window.location.search).get("instagram");
  const load = () => api.get("/instagram/status").then(({ data }) => setStatus(data)).catch(() => setStatus({ unavailable: true }));
  useEffect(() => { load(); }, []);
  const act = async (action) => {
    setBusy(true);
    try {
      if (action === "connect") {
        const { data } = await api.post("/instagram/connect");
        window.location.assign(data.url);
      } else {
        if (action === "sync") await api.post("/instagram/sync");
        else await api.delete("/instagram/connection");
        await load();
        if (onSync) await onSync();
        toast.success(action === "sync" ? "Instagram profile updated" : "Instagram disconnected; imported profile retained");
      }
    } catch (error) { toast.error(formatApiError(error)); }
    finally { setBusy(false); }
  };
  const analytics = status?.analytics;
  return <section className="rounded-2xl border border-border bg-card p-6 space-y-4" data-testid="instagram-connect">
    <h3 className="text-lg font-semibold">Connect Instagram</h3>
    {outcome === "failed" && <p role="alert" className="text-sm text-destructive">Instagram connection could not finish. Reconnect and approve profile, insights and comments access.</p>}
    {outcome === "cancelled" && <p className="text-sm text-muted-foreground">Instagram permission was cancelled. You can connect again when ready.</p>}
    <p className="text-sm text-muted-foreground">Connect your Creator or Business account to build your profile automatically. We import your bio, photo, followers and available content insights. Add your username and payout details below.</p>
    {!status ? <p>Checking connection…</p> : status.unavailable ? <p>Instagram connection is temporarily unavailable.</p> : !status.configured ? <p className="text-sm text-muted-foreground">Instagram connection will be available once Brandkrt completes Meta setup.</p> : <div className="flex flex-wrap gap-3">
      <button type="button" disabled={busy} onClick={() => act("connect")} className="rounded-full bg-primary text-primary-foreground px-4 py-2 disabled:opacity-50">{status.connected ? "Reconnect Instagram" : "Connect Instagram"}</button>
      {status.connected && <><button type="button" disabled={busy} onClick={() => act("sync")} className="rounded-full border px-4 py-2">Refresh insights</button><button type="button" disabled={busy} onClick={() => act("disconnect")} className="rounded-full border px-4 py-2">Disconnect & delete synced insights</button></>}
    </div>}
    {analytics && <>
      <p className="text-sm">@{analytics.username} · {analytics.followers.toLocaleString()} followers · Updated {new Date(analytics.synced_at).toLocaleString()}</p>
      <p className="text-sm">Average engagement by followers (likes + comments): {analytics.engagement_rate == null ? "Unavailable" : `${analytics.engagement_rate}%`} · 30-day reach: {analytics.account.reach ?? "Unavailable"}</p>
      <p className="text-xs text-muted-foreground">Latest {analytics.posts.length} posts, up to 50 comments per post. Missing metrics are unavailable, not zero. Refresh is limited to once every five minutes.</p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{analytics.posts.map((post) => <article key={post.id} className="rounded-xl border p-3 space-y-2">
        <a href={post.permalink} target="_blank" rel="noreferrer" className="font-semibold underline">{post.caption?.slice(0, 90) || post.media_type}</a>
        <p className="text-sm">Views: {post.insights.views ?? "Unavailable"} · Reach: {post.insights.reach ?? "Unavailable"}</p>
        <p className="text-sm">Likes: {post.like_count ?? "Unavailable"} · Comments: {post.comments_count ?? "Unavailable"} · Saves: {post.insights.saved ?? "Unavailable"} · Shares: {post.insights.shares ?? "Unavailable"}</p>
        {post.comments?.slice(0, 3).map((comment) => <p key={comment.id} className="text-xs text-muted-foreground">{comment.text}</p>)}
      </article>)}</div>
      {!!analytics.warnings?.length && <p className="text-xs text-muted-foreground">Some insights or comments could not be imported. Check permissions or reconnect.</p>}
    </>}
  </section>;
}
