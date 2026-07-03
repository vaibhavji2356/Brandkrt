import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Megaphone, CheckCircle2, ShieldCheck, Wallet, Clock, ArrowRight,
  Calendar, Activity, Sparkles,
} from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatusChip, EmptyState } from "@/components/State";

function StatCard({ icon: Icon, label, value, hint, testId, tone = "default" }) {
  const cls = tone === "gold" ? "border-secondary/40 bg-accent" : "";
  return (
    <div className={`rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all ${cls}`} data-testid={testId}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-3xl font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const RUNNING_CAMPAIGN_STATUSES = new Set(["active", "draft"]);
const ACTIVE_DEAL_STATUSES = new Set([
  "offer_sent", "offer_accepted", "product_shipped", "promotion_pending", "promotion_live",
]);

function daysUntil(iso) {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return Math.ceil((t - Date.now()) / (1000 * 60 * 60 * 24));
}

export default function BrandOverview() {
  const { user } = useAuth();
  const [brand, setBrand] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [b, c, d, p, n] = await Promise.all([
          api.get("/brands/me"),
          api.get("/campaigns"),
          api.get("/deals"),
          api.get("/payments"),
          api.get("/notifications"),
        ]);
        setBrand(b.data?.brand || null);
        setCampaigns(c.data.campaigns || []);
        setDeals(d.data.deals || []);
        setPayments(p.data.payments || []);
        setNotifications(n.data.notifications || []);
      } catch (_) { /* noop */ }
      setLoading(false);
    })();
  }, []);

  const campaignIds = useMemo(() => new Set(campaigns.map((c) => c.id)), [campaigns]);
  const myDeals = useMemo(() => deals.filter((d) => campaignIds.has(d.campaign_id) || d.brand_id === brand?.id), [deals, campaignIds, brand]);
  const dealIds = useMemo(() => new Set(myDeals.map((d) => d.id)), [myDeals]);
  const myPayments = useMemo(() => payments.filter((p) => dealIds.has(p.deal_id)), [payments, dealIds]);

  const running = campaigns.filter((c) => RUNNING_CAMPAIGN_STATUSES.has(c.status)).length;
  const completed = campaigns.filter((c) => c.status === "completed").length;
  const pendingRequests = myDeals.filter((d) => d.status === "offer_sent").length;
  const activeDeals = myDeals.filter((d) => ACTIVE_DEAL_STATUSES.has(d.status)).length;
  const totalSpend = myPayments.reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const monthStart = new Date(); monthStart.setDate(1); monthStart.setHours(0, 0, 0, 0);
  const monthlySpend = myPayments
    .filter((p) => p.created_at && new Date(p.created_at) >= monthStart)
    .reduce((s, p) => s + (Number(p.amount) || 0), 0);

  // Upcoming deadlines from campaigns with deadlines in next 30 days
  const upcoming = useMemo(() => (
    campaigns
      .map((c) => ({ ...c, _days: daysUntil(c.deadline) }))
      .filter((c) => c._days !== null && c._days >= -1 && c._days <= 30)
      .sort((a, b) => a._days - b._days)
      .slice(0, 5)
  ), [campaigns]);

  const recentDeals = myDeals.slice(0, 6);
  const recentNotifs = notifications.slice(0, 5);

  if (loading) return <div className="text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-8" data-testid="brand-overview">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">
            Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""} <span className="gold-text font-semibold">✨</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Your brand HQ — campaigns, creators, spend and performance, all in one view.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/brand/discover" className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:bg-accent" data-testid="overview-discover">
            <Sparkles className="h-4 w-4" /> Discover creators
          </Link>
          <Link to="/brand/campaigns?new=1" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold" data-testid="overview-new-campaign">
            New campaign <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {!brand && (
        <div className="rounded-2xl border border-secondary/40 bg-accent p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-3" data-testid="brand-profile-banner">
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-secondary mt-0.5" />
            <div>
              <div className="font-semibold text-primary dark:text-white">Complete your Business Profile</div>
              <div className="text-sm text-muted-foreground">Add your business details and logo so creators trust your invites and our team can verify your account faster.</div>
            </div>
          </div>
          <Link to="/brand/profile" className="inline-flex items-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap">
            Set up profile <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Megaphone} label="Running Campaigns" value={running} testId="stat-running" tone="gold" />
        <StatCard icon={CheckCircle2} label="Completed Campaigns" value={completed} testId="stat-completed" />
        <StatCard icon={Clock} label="Pending Requests" value={pendingRequests} hint={`${activeDeals} active deals`} testId="stat-pending-requests" />
        <StatCard icon={ShieldCheck} label="Verified Influencers" value={myDeals.filter((d) => d.influencer_id).length ? new Set(myDeals.map((d) => d.influencer_id)).size : 0} hint="Engaged with your campaigns" testId="stat-verified-inf" />
      </div>

      <div className="grid gap-4 grid-cols-1 lg:grid-cols-3">
        <StatCard icon={Wallet} label="Total Spend" value={`₹${totalSpend.toLocaleString()}`} hint={`${myPayments.length} payments`} testId="stat-total-spend" />
        <StatCard icon={Wallet} label="This Month" value={`₹${monthlySpend.toLocaleString()}`} hint="MTD" testId="stat-month-spend" />
        <StatCard icon={Activity} label="Active Deals" value={activeDeals} hint="In progress right now" testId="stat-active-deals" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6" data-testid="overview-recent-deals">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Recent activity</h3>
            <Link to="/brand/campaigns" className="text-xs font-semibold text-secondary hover:underline">View campaigns</Link>
          </div>
          <div className="mt-4 divide-y divide-border">
            {recentDeals.length === 0 && (
              <EmptyState
                icon={Megaphone}
                title="No campaign activity yet"
                description="Create your first campaign and invite verified creators to get started."
                action={<Link to="/brand/campaigns?new=1" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold">New campaign</Link>}
                testId="overview-no-activity"
              />
            )}
            {recentDeals.map((d) => (
              <div key={d.id} className="py-3 flex items-center justify-between gap-3" data-testid={`overview-deal-${d.id}`}>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-primary dark:text-white truncate">
                    ₹{Number(d.amount || 0).toLocaleString()} · creator deal
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {d.note || "Awaiting creator response."}
                  </div>
                </div>
                <StatusChip value={d.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6" data-testid="overview-deadlines">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Upcoming deadlines</h3>
            <Calendar className="h-4 w-4 text-secondary" />
          </div>
          <div className="mt-4 space-y-3">
            {upcoming.length === 0 && <p className="text-sm text-muted-foreground">No deadlines in the next 30 days.</p>}
            {upcoming.map((c) => (
              <Link
                key={c.id}
                to={`/brand/campaigns/${c.id}`}
                className="block rounded-xl border border-border p-3 hover:bg-accent transition-colors"
                data-testid={`deadline-${c.id}`}
              >
                <div className="text-sm font-medium text-primary dark:text-white truncate">{c.title}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Due {c.deadline} {c._days != null && (
                    <span className={`ml-1 inline-block px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${c._days <= 3 ? "bg-destructive/10 text-destructive" : "bg-secondary/15 text-secondary"}`}>
                      {c._days < 0 ? "Overdue" : c._days === 0 ? "Today" : `${c._days}d`}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-6" data-testid="overview-notifs">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-primary dark:text-white">Latest notifications</h3>
          <span className="text-xs text-muted-foreground">{notifications.filter((n) => !n.read).length} unread</span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {recentNotifs.length === 0 && <p className="text-sm text-muted-foreground">You&apos;re all caught up.</p>}
          {recentNotifs.map((n) => (
            <div key={n.id} className={`rounded-xl border border-border p-3 ${n.read ? "" : "bg-accent/40"}`} data-testid={`overview-notif-${n.id}`}>
              <div className="text-sm font-medium text-primary dark:text-white truncate">{n.title}</div>
              {n.body && <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.body}</div>}
              <div className="text-[10px] uppercase tracking-wider text-secondary mt-1">{n.type}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
