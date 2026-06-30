import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Megaphone, CheckCircle2, Wallet, BadgeCheck, ArrowRight, Sparkles, Clock,
} from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatusChip, EmptyState } from "@/components/State";

function StatCard({ icon: Icon, label, value, hint, testId }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all" data-testid={testId}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-3xl font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const ACTIVE_STATUSES = new Set(["offer_sent", "offer_accepted", "product_shipped", "promotion_pending", "promotion_live"]);

export default function InfluencerOverview() {
  const { user } = useAuth();
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [influencer, setInfluencer] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [d, p, n, me] = await Promise.all([
          api.get("/deals"),
          api.get("/payments"),
          api.get("/notifications"),
          api.get("/influencers/me"),
        ]);
        setDeals(d.data.deals || []);
        setPayments(p.data.payments || []);
        setNotifications(n.data.notifications || []);
        setInfluencer(me.data.influencer || null);
      } catch (_) { /* noop */ }
      setLoading(false);
    })();
  }, []);

  const dealIds = useMemo(() => new Set(deals.map((d) => d.id)), [deals]);
  const myPayments = useMemo(() => payments.filter((p) => dealIds.has(p.deal_id)), [payments, dealIds]);

  const totalEarned = useMemo(
    () => myPayments
      .filter((p) => (p.release_status === "released" || p.status === "released"))
      .reduce((s, p) => s + (Number(p.influencer_earning) || 0), 0),
    [myPayments],
  );
  const pendingEscrow = useMemo(
    () => myPayments
      .filter((p) => (p.release_status === "held" || p.status === "escrowed"))
      .reduce((s, p) => s + (Number(p.influencer_earning) || 0), 0),
    [myPayments],
  );

  const activeCount = deals.filter((d) => ACTIVE_STATUSES.has(d.status)).length;
  const completedCount = deals.filter((d) => d.status === "completed").length;
  const unread = notifications.filter((n) => !n.read).length;
  const profileReady = !!influencer;

  if (loading) {
    return <div className="text-muted-foreground">Loading…</div>;
  }

  const recentDeals = deals.slice(0, 5);
  const recentNotifs = notifications.slice(0, 5);

  return (
    <div className="space-y-8" data-testid="influencer-overview">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">
            Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""} <span className="gold-text font-semibold">✨</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Here&apos;s your creator snapshot — campaigns, earnings and alerts in one place.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/influencer/profile" data-testid="overview-edit-profile" className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:bg-accent">
            <UserIcon /> Edit profile
          </Link>
          <Link to="/influencer/campaigns" data-testid="overview-view-campaigns" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold">
            View campaigns <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {!profileReady && (
        <div className="rounded-2xl border border-secondary/40 bg-accent p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-3" data-testid="overview-profile-banner">
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-secondary mt-0.5" />
            <div>
              <div className="font-semibold text-primary dark:text-white">Finish your Creator Profile</div>
              <div className="text-sm text-muted-foreground">Brands can only discover you once your profile is complete — bio, social handles, category and rate card.</div>
            </div>
          </div>
          <Link to="/influencer/profile" className="inline-flex items-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap">
            Complete profile <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Megaphone} label="Active Campaigns" value={activeCount} testId="stat-active-campaigns" />
        <StatCard icon={CheckCircle2} label="Completed" value={completedCount} testId="stat-completed" />
        <StatCard icon={Wallet} label="Total Earned" value={`₹${totalEarned.toLocaleString()}`} hint="Released payouts" testId="stat-total-earned" />
        <StatCard icon={Clock} label="In Escrow" value={`₹${pendingEscrow.toLocaleString()}`} hint="Awaiting release" testId="stat-pending-escrow" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6" data-testid="overview-recent-deals">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Recent campaign offers</h3>
            <Link to="/influencer/campaigns" className="text-xs font-semibold text-secondary hover:underline">View all</Link>
          </div>
          <div className="mt-4 divide-y divide-border">
            {recentDeals.length === 0 && (
              <EmptyState
                icon={Megaphone}
                title="No campaign offers yet"
                description="Brands will reach out once you complete your Creator Profile. Make sure your handles and rate card are filled in."
                action={<Link to="/influencer/profile" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold">Complete profile</Link>}
                testId="overview-no-deals"
              />
            )}
            {recentDeals.map((d) => (
              <div key={d.id} className="py-3 flex items-center justify-between gap-3" data-testid={`overview-deal-${d.id}`}>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-primary dark:text-white truncate">Campaign offer · ₹{Number(d.amount || 0).toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground truncate">{d.note || "No note from the brand."}</div>
                </div>
                <StatusChip value={d.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6" data-testid="overview-recent-notifs">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Recent alerts</h3>
            <Link to="/influencer/notifications" className="text-xs font-semibold text-secondary hover:underline">All ({unread} unread)</Link>
          </div>
          <div className="mt-4 space-y-3">
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

      <div className="rounded-2xl border border-border bg-card p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4" data-testid="overview-verification-card">
        <div className="flex items-start gap-3">
          <BadgeCheck className="h-5 w-5 text-secondary mt-0.5" />
          <div>
            <div className="font-semibold text-primary dark:text-white">
              {influencer?.verification_status === "approved" ? "You're a verified creator" : "Become a verified creator"}
            </div>
            <div className="text-sm text-muted-foreground">
              {influencer?.verification_status === "approved"
                ? "Your profile has the verified badge — brands trust you instantly."
                : "Verified creators get up to 3× more campaign invites. Submit your ID + handle proof from settings."}
            </div>
          </div>
        </div>
        <Link to="/settings" className="inline-flex items-center gap-2 rounded-full border border-border bg-background hover:bg-accent px-4 py-2 text-sm font-semibold whitespace-nowrap">
          Open settings <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function UserIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}
