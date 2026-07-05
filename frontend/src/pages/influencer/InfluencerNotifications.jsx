import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Bell, CheckCheck, Inbox } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { EmptyState } from "@/components/State";

const TABS = [
  { key: "all", label: "All" },
  { key: "unread", label: "Unread" },
];

function timeAgo(iso) {
  if (!iso) return "";
  try {
    const t = new Date(iso).getTime();
    const diff = Math.max(0, Date.now() - t);
    const m = Math.floor(diff / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 30) return `${d}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch (_) { return ""; }
}

export default function InfluencerNotifications() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/notifications");
      setItems(data.notifications || []);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => (
    tab === "unread" ? items.filter((n) => !n.read) : items
  ), [items, tab]);
  const unreadCount = items.filter((n) => !n.read).length;

  const markOne = async (id) => {
    setItems((arr) => arr.map((n) => n.id === id ? { ...n, read: true } : n));
    try { await api.post(`/notifications/${id}/read`); }
    catch (err) { toast.error(formatApiError(err)); load(); }
  };

  const markAll = async () => {
    if (unreadCount === 0) return;
    setBusy(true);
    const unread = items.filter((n) => !n.read);
    setItems((arr) => arr.map((n) => ({ ...n, read: true })));
    try {
      await Promise.all(unread.map((n) => api.post(`/notifications/${n.id}/read`)));
      toast.success("All notifications marked as read.");
    } catch (err) {
      toast.error(formatApiError(err));
      load();
    }
    setBusy(false);
  };

  return (
    <div className="space-y-6" data-testid="influencer-notifications">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">Notifications</h2>
          <p className="text-sm text-muted-foreground mt-1">Campaign offers, payment releases, verification updates and brand messages — all in one inbox.</p>
        </div>
        <button
          onClick={markAll}
          disabled={unreadCount === 0 || busy}
          data-testid="notif-mark-all"
          className="inline-flex items-center gap-2 rounded-full border border-border bg-card hover:bg-accent px-4 py-2 text-sm font-semibold disabled:opacity-50"
        >
          <CheckCheck className="h-4 w-4" /> Mark all read{unreadCount > 0 ? ` (${unreadCount})` : ""}
        </button>
      </div>

      <div className="flex items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            data-testid={`notif-tab-${t.key}`}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
              tab === t.key ? "bg-primary text-primary-foreground border-primary" : "bg-card border-border text-foreground/80 hover:bg-accent"
            }`}
          >
            {t.label}{t.key === "unread" && unreadCount > 0 ? ` · ${unreadCount}` : ""}
          </button>
        ))}
      </div>

      {loading && <div className="text-muted-foreground">Loading…</div>}

      {!loading && filtered.length === 0 && (
        <EmptyState
          icon={tab === "unread" ? CheckCheck : Inbox}
          title={tab === "unread" ? "You're all caught up" : "No notifications yet"}
          description={tab === "unread" ? "All your alerts have been read." : "When a brand sends a new offer or a payment is released, you'll see it here."}
          testId="notifications-empty"
        />
      )}

      <div className="space-y-3">
        {filtered.map((n) => (
          <div
            key={n.id}
            className={`rounded-2xl border p-5 flex items-start gap-4 transition-colors ${
              n.read ? "border-border bg-card" : "border-secondary/40 bg-accent"
            }`}
            data-testid={`notif-row-${n.id}`}
          >
            <div className="h-10 w-10 rounded-full bg-background border border-border flex items-center justify-center shrink-0">
              <Bell className="h-4 w-4 text-secondary" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-primary dark:text-white">{n.title}</span>
                <span className="text-[10px] uppercase tracking-wider text-secondary">{n.type}</span>
                {!n.read && <span className="text-[10px] uppercase tracking-wider text-secondary">• new</span>}
              </div>
              {n.body && <p className="mt-1 text-sm text-muted-foreground">{n.body}</p>}
              {(n.meta?.reference || n.meta?.screenshot_url) && (
                <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-background/70 px-3 py-2 text-xs">
                  {n.meta?.reference && (
                    <span className="min-w-0">
                      <span className="font-semibold text-muted-foreground">Reference: </span>
                      <span className="break-all text-foreground">{n.meta.reference}</span>
                    </span>
                  )}
                  {n.meta?.screenshot_url && (
                    <a
                      href={n.meta.screenshot_url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-semibold text-secondary hover:underline"
                    >
                      View payment screenshot
                    </a>
                  )}
                </div>
              )}
              <p className="mt-2 text-xs text-muted-foreground">{timeAgo(n.created_at)}</p>
            </div>
            {!n.read && (
              <button
                onClick={() => markOne(n.id)}
                data-testid={`notif-mark-${n.id}`}
                className="text-xs font-semibold text-secondary hover:underline whitespace-nowrap"
              >
                Mark read
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
