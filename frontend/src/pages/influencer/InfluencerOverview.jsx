import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Wallet,
  Megaphone,
  ShieldCheck,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { StatusChip, EmptyState } from "@/components/State";
import InfluencerAPI from "@/lib/influencerApi";

function StatCard({ label, value, icon: Icon, hint, testId }) {
  return (
    <div
      className="rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all"
      data-testid={testId}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-2xl sm:text-3xl font-display font-light text-primary dark:text-white">
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function profileCompletion(p) {
  if (!p) return 0;
  const keys = [
    "username",
    "phone",
    "country",
    "bio",
    "instagram",
    "category",
    "collab_price",
    "upi",
  ];
  const filled = keys.filter((k) => {
    const v = p[k];
    return v !== undefined && v !== null && v !== "" && v !== 0;
  }).length;
  return Math.round((filled / keys.length) * 100);
}

export default function InfluencerOverview() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [deals, setDeals] = useState([]);
  const [notifs, setNotifs] = useState([]);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [p, d, n, pay] = await Promise.all([
          InfluencerAPI.getProfile().catch(() => null),
          InfluencerAPI.listDeals().catch(() => []),
          InfluencerAPI.listNotifications().catch(() => []),
          InfluencerAPI.listPayments().catch(() => []),
        ]);
        if (!alive) return;
        setProfile(p);
        setDeals(d);
        setNotifs(n);
        setPayments(pay);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const completion = useMemo(() => profileCompletion(profile), [profile]);
  const activeDeals = deals.filter(
    (d) => d.status !== "completed" && d.status !== "cancelled"
  );
  const dealIds = new Set(deals.map((d) => d.id));
  const myPayments = payments.filter((p) => dealIds.has(p.deal_id));
  const totalEarned = myPayments
    .filter((p) => p.release_status === "released")
    .reduce((s, p) => s + (p.influencer_earning || 0), 0);
  const pendingEarnings = myPayments
    .filter((p) => p.release_status !== "released")
    .reduce((s, p) => s + (p.influencer_earning || 0), 0);
  const verifStatus = profile?.verification_status || "pending";

  if (loading) {
    return (
      <div
        className="flex items-center justify-center py-20"
        data-testid="overview-loading"
      >
        <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="influencer-overview">
      {/* Hero */}
      <div>
        <h2 className="text-2xl sm:text-3xl font-display font-light text-primary dark:text-white">
          Hi {user?.name?.split(" ")[0] || "creator"} 👋
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Here&apos;s how your collaborations are tracking today.
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Earned"
          value={`₹${totalEarned.toLocaleString()}`}
          icon={Wallet}
          hint="Released to your wallet"
          testId="stat-total-earned"
        />
        <StatCard
          label="Pending"
          value={`₹${pendingEarnings.toLocaleString()}`}
          icon={Clock}
          hint="Awaiting release"
          testId="stat-pending-earnings"
        />
        <StatCard
          label="Active Deals"
          value={activeDeals.length}
          icon={Megaphone}
          hint={`${deals.length} total`}
          testId="stat-active-deals"
        />
        <StatCard
          label="Verification"
          value={verifStatus === "approved" ? "Verified" : verifStatus}
          icon={ShieldCheck}
          hint={profile ? "Identity status" : "Profile not started"}
          testId="stat-verification"
        />
      </div>

      {/* Profile completion banner */}
      {completion < 100 && (
        <div
          className="rounded-2xl border border-secondary/30 bg-accent p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-4"
          data-testid="profile-completion-banner"
        >
          <div className="flex-1">
            <div className="flex items-center gap-2 text-sm font-semibold text-primary dark:text-white">
              <Sparkles className="h-4 w-4 text-secondary" />
              Complete your profile — {completion}%
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Brands prioritise creators with complete profiles. Add socials,
              pricing and a bio to start getting offers.
            </p>
            <div className="mt-3 h-1.5 w-full rounded-full bg-border overflow-hidden">
              <div
                className="h-full bg-secondary transition-all"
                style={{ width: `${completion}%` }}
              />
            </div>
          </div>
          <Link
            to="/influencer/profile"
            data-testid="overview-complete-profile-cta"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold whitespace-nowrap"
          >
            Complete profile <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}

      {/* Recent deals + notifications */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div
          className="rounded-2xl border border-border bg-card p-6 lg:col-span-2"
          data-testid="overview-recent-deals"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">
              Recent campaigns
            </h3>
            <Link
              to="/influencer/campaigns"
              className="text-xs text-secondary hover:underline"
              data-testid="overview-view-all-campaigns"
            >
              View all
            </Link>
          </div>
          {deals.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                title="No campaigns yet"
                description="Once a brand sends you an offer, it will appear here."
                testId="overview-empty-deals"
              />
            </div>
          ) : (
            <div className="mt-4 divide-y divide-border">
              {deals.slice(0, 5).map((d) => (
                <div
                  key={d.id}
                  className="py-3 flex items-center justify-between gap-3"
                  data-testid={`recent-deal-${d.id}`}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-primary dark:text-white truncate">
                      Deal #{d.id.slice(-6)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      ₹{Number(d.amount || 0).toLocaleString()}
                    </div>
                  </div>
                  <StatusChip value={d.status} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div
          className="rounded-2xl border border-border bg-card p-6"
          data-testid="overview-recent-notifs"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">
              Recent activity
            </h3>
            <Link
              to="/influencer/notifications"
              className="text-xs text-secondary hover:underline"
              data-testid="overview-view-all-notifs"
            >
              View all
            </Link>
          </div>
          {notifs.length === 0 ? (
            <div className="mt-6 text-sm text-muted-foreground flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-secondary" />
              You&apos;re all caught up.
            </div>
          ) : (
            <ul className="mt-4 space-y-3">
              {notifs.slice(0, 5).map((n) => (
                <li
                  key={n.id}
                  className="text-sm"
                  data-testid={`overview-notif-${n.id}`}
                >
                  <div className="font-medium text-primary dark:text-white line-clamp-1">
                    {n.title}
                  </div>
                  {n.body && (
                    <div className="text-xs text-muted-foreground line-clamp-2">
                      {n.body}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
