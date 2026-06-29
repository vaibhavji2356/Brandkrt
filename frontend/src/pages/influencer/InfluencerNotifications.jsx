import React, { useEffect, useMemo, useState } from "react";
import { Check, Bell } from "lucide-react";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EmptyState } from "@/components/State";
import { formatApiError } from "@/lib/api";
import InfluencerAPI from "@/lib/influencerApi";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
];

export default function InfluencerNotifications() {
  const [items, setItems] = useState([]);
  const [tab, setTab] = useState("all");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const list = await InfluencerAPI.listNotifications();
      setItems(list);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(
    () => (tab === "unread" ? items.filter((n) => !n.read) : items),
    [tab, items]
  );
  const unreadCount = items.filter((n) => !n.read).length;

  const markOne = async (id) => {
    setBusyId(id);
    try {
      await InfluencerAPI.markNotificationRead(id);
      setItems((arr) => arr.map((n) => (n.id === id ? { ...n, read: true } : n)));
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  const markAll = async () => {
    const unread = items.filter((n) => !n.read);
    if (unread.length === 0) return;
    try {
      await Promise.all(
        unread.map((n) => InfluencerAPI.markNotificationRead(n.id))
      );
      setItems((arr) => arr.map((n) => ({ ...n, read: true })));
      toast.success("All notifications marked as read.");
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  return (
    <div className="space-y-6" data-testid="influencer-notifications-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl sm:text-3xl font-display font-light text-primary dark:text-white">
            Notifications
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {unreadCount > 0
              ? `${unreadCount} unread — stay on top of brand activity.`
              : "You're all caught up."}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={markAll}
            data-testid="notifications-mark-all"
            className="inline-flex items-center gap-2 rounded-full border border-border bg-card hover:bg-accent px-4 py-2 text-xs font-semibold w-fit"
          >
            <Check className="h-3.5 w-3.5" /> Mark all read
          </button>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          {FILTERS.map((f) => (
            <TabsTrigger
              key={f.value}
              value={f.value}
              data-testid={`notif-filter-${f.value}`}
            >
              {f.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value={tab} className="mt-6 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={Bell}
              title="Nothing here"
              description={
                tab === "unread"
                  ? "You don't have any unread notifications."
                  : "Notifications about your offers, payments and verification will appear here."
              }
              testId="notifications-empty"
            />
          ) : (
            filtered.map((n) => (
              <div
                key={n.id}
                className={`rounded-2xl border p-4 sm:p-5 flex items-start gap-4 ${
                  n.read
                    ? "border-border bg-card"
                    : "border-secondary/40 bg-accent"
                }`}
                data-testid={`notif-row-${n.id}`}
              >
                <div className="h-9 w-9 shrink-0 rounded-full bg-secondary/10 text-secondary flex items-center justify-center">
                  <Bell className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-primary dark:text-white">
                    {n.title}
                  </div>
                  {n.body && (
                    <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                      {n.body}
                    </p>
                  )}
                  <div className="mt-2 text-[10px] uppercase tracking-wider text-secondary">
                    {n.type}
                  </div>
                </div>
                {!n.read && (
                  <button
                    type="button"
                    disabled={busyId === n.id}
                    onClick={() => markOne(n.id)}
                    data-testid={`notif-mark-${n.id}`}
                    className="inline-flex items-center gap-1.5 text-xs text-secondary hover:underline disabled:opacity-60"
                  >
                    <Check className="h-3.5 w-3.5" /> Mark read
                  </button>
                )}
              </div>
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
