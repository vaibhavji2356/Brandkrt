import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Activity, Eye, Heart, TrendingUp, Wallet, BadgeCheck, Clock,
  Award, Star, Trophy, ArrowRight, Sparkles,
} from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";
import api, { formatApiError } from "@/lib/api";
import { StatusChip, EmptyState } from "@/components/State";
import StarRating from "@/components/StarRating";
import ReviewList from "@/components/ReviewList";

const NAVY = "#0A1F44";
const GOLD = "#D4AF37";
const TOOLTIP_STYLE = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 };

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

function ChartCard({ title, subtitle, children, testId }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6" data-testid={testId}>
      <div>
        <h3 className="text-sm font-semibold text-primary dark:text-white">{title}</h3>
        {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>
      <div className="h-64 mt-4">
        <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
      </div>
    </div>
  );
}

export default function InfluencerAnalytics() {
  const [perf, setPerf] = useState(null);
  const [trends, setTrends] = useState([]);
  const [deals, setDeals] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [topCampaigns, setTopCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [p, t, d, m, tc] = await Promise.all([
          api.get("/performance/influencer/me"),
          api.get("/performance/trends"),
          api.get("/deals"),
          api.get("/auth/me"),
          api.get("/performance/top-campaigns"),
        ]);
        setPerf(p.data || null);
        setTrends(t.data.series || []);
        setDeals(d.data.deals || []);
        setTopCampaigns(tc.data.top_campaigns || []);
        const uid = m.data?.user?.id;
        if (uid) {
          const r = await api.get(`/feedback/for/${uid}`);
          setReviews(r.data.reviews || []);
        }
      } catch (err) {
        toast.error(formatApiError(err));
      }
      setLoading(false);
    })();
  }, []);

  const completedDeals = useMemo(() => deals.filter((d) => ["published", "completed", "approved", "scheduled"].includes(d.status)), [deals]);
  const dealsWithMetrics = useMemo(() => deals.filter((d) => d.metrics && Object.keys(d.metrics || {}).length > 0), [deals]);
  const dealsMissingMetrics = useMemo(() => completedDeals.filter((d) => !d.metrics), [completedDeals]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 rounded bg-card animate-pulse" />
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 rounded-2xl bg-card animate-pulse" />)}
        </div>
        <div className="h-64 rounded-2xl bg-card animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="influencer-analytics">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Performance</h2>
        <p className="text-sm text-muted-foreground mt-1">Your creator scorecard — ratings, engagement and earnings across every campaign.</p>
      </div>

      {/* Hero: rating + verified */}
      <div className="rounded-2xl border border-border bg-card p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4" data-testid="creator-hero">
        <div className="flex items-start gap-4 min-w-0">
          <div className="h-16 w-16 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center text-lg font-semibold">
            {(perf?.influencer?.username || "C").slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-xl font-display text-primary dark:text-white truncate">
                {perf?.influencer?.username || "Your profile"}
              </h3>
              {perf?.verified && (
                <span className="inline-flex items-center gap-1 rounded-full bg-secondary/15 text-secondary px-2 py-0.5 text-[10px] font-semibold">
                  <BadgeCheck className="h-3 w-3" /> Verified
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <StarRating value={perf?.overall_rating || 0} size={16} />
              <span className="text-sm font-semibold">{(perf?.overall_rating || 0).toFixed(1)}</span>
              <span className="text-xs text-muted-foreground">({perf?.total_reviews || 0} reviews)</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1 capitalize">{perf?.influencer?.category || "—"}</p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 md:gap-4 w-full md:w-auto">
          <MiniStat label="Repeat brands" value={perf?.repeat_brands || 0} />
          <MiniStat label="Would work again" value={`${perf?.would_work_again_pct || 0}%`} />
          <MiniStat label="Success rate" value={`${perf?.success_rate || 0}%`} />
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Activity} label="Collaborations" value={perf?.total_collaborations || 0} hint={`${perf?.completion_rate || 0}% completed`} testId="ip-stat-collabs" />
        <StatCard icon={Clock} label="Avg delivery time" value={`${perf?.average_delivery_days || 0}d`} hint="From accept → complete" testId="ip-stat-delivery" />
        <StatCard icon={Heart} label="Avg engagement" value={`${perf?.average_engagement_rate || 0}%`} hint="Across reported deals" testId="ip-stat-engagement" />
        <StatCard icon={Wallet} label="Total earnings" value={`₹${Number(perf?.total_earnings || 0).toLocaleString()}`} hint="Released payouts" testId="ip-stat-earnings" />
      </div>

      {/* Charts */}
      {trends.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard title="Reach trend" subtitle="Weekly reach across reported campaigns" testId="chart-reach">
            <AreaChart data={trends}>
              <defs>
                <linearGradient id="ipReach" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={GOLD} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toLocaleString(), "Reach"]} />
              <Area type="monotone" dataKey="reach" stroke={GOLD} strokeWidth={2} fill="url(#ipReach)" />
            </AreaChart>
          </ChartCard>

          <ChartCard title="Engagement trend" subtitle="Likes + comments + shares + saves" testId="chart-engagement">
            <BarChart data={trends}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toLocaleString(), "Engagement"]} />
              <Bar dataKey="engagement" fill={NAVY} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="Views trend" subtitle="Total views (Reel + YouTube + Facebook)" testId="chart-views">
            <LineChart data={trends}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toLocaleString(), "Views"]} />
              <Line type="monotone" dataKey="views" stroke={GOLD} strokeWidth={2} dot={false} />
            </LineChart>
          </ChartCard>

          <ChartCard title="Performance trend" subtitle="Completed deals per week" testId="chart-perf">
            <BarChart data={trends}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="deals" name="Deals" fill={GOLD} radius={[6, 6, 0, 0]} />
              <Bar dataKey="completed" name="Completed" fill={NAVY} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ChartCard>
        </div>
      )}

      {/* Submit metrics CTA */}
      <div className="rounded-2xl border border-border bg-card p-6" data-testid="metrics-deals-section">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-primary dark:text-white">Report performance</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Submit views, likes, comments and reach for your published campaigns to unlock accurate analytics.</p>
          </div>
          <div className="text-xs text-secondary font-semibold">
            {dealsWithMetrics.length}/{completedDeals.length} reported
          </div>
        </div>

        {completedDeals.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="No completed campaigns yet"
            description="Once your campaigns reach Published or Completed, you can report performance here."
            testId="ip-metrics-empty"
          />
        ) : (
          <div className="mt-4 divide-y divide-border">
            {completedDeals.map((d) => {
              const hasMetrics = !!d.metrics && Object.keys(d.metrics).length > 0;
              return (
                <div key={d.id} className="py-3 flex items-center gap-3 flex-wrap" data-testid={`ip-deal-${d.id}`}>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-primary dark:text-white truncate">
                      Deal · ₹{Number(d.amount || 0).toLocaleString()}
                    </div>
                    <div className="text-xs text-muted-foreground flex items-center gap-2">
                      <StatusChip value={d.status} />
                      {hasMetrics && <span className="text-secondary text-[10px]">Reach {Number(d.metrics.reach || 0).toLocaleString()}</span>}
                    </div>
                  </div>
                  <Link
                    to={`/deals/${d.id}/metrics`}
                    data-testid={`ip-report-${d.id}`}
                    className="inline-flex items-center gap-1 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-3 py-1.5 text-xs font-semibold"
                  >
                    {hasMetrics ? "Update" : "Report"} <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                  <Link
                    to={`/deals/${d.id}/report`}
                    className="inline-flex items-center gap-1 rounded-full border border-border hover:bg-accent px-3 py-1.5 text-xs font-semibold"
                  >
                    Report
                  </Link>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Top campaigns */}
      {topCampaigns.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-6" data-testid="ip-top-campaigns">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Top performing campaigns</h3>
            <Trophy className="h-4 w-4 text-secondary" />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {topCampaigns.slice(0, 6).map((c) => (
              <div key={c.campaign_id} className="rounded-xl border border-border bg-background p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-primary dark:text-white truncate">{c.title}</div>
                    <div className="text-[10px] uppercase tracking-wider text-secondary mt-0.5">{c.platform || "—"}</div>
                  </div>
                  <Award className="h-4 w-4 text-secondary" />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
                  <Stat label="Reach" value={Number(c.reach).toLocaleString()} />
                  <Stat label="Engagement" value={Number(c.engagement).toLocaleString()} />
                  <Stat label="Views" value={Number(c.views).toLocaleString()} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reviews about me */}
      <div data-testid="ip-reviews">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-primary dark:text-white">Reviews</h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Star className="h-3.5 w-3.5 text-secondary" /> {(perf?.overall_rating || 0).toFixed(1)} · {perf?.total_reviews || 0} reviews
          </div>
        </div>
        <ReviewList reviews={reviews} emptyTitle="No reviews yet" emptyDescription="Once brands close out campaigns with you, their reviews will appear here." />
      </div>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3 text-center">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-semibold text-primary dark:text-white">{value}</div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-card p-2">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-xs font-semibold text-primary dark:text-white">{value}</div>
    </div>
  );
}
