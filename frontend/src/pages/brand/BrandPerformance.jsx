import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Activity, IndianRupee, TrendingUp, Star, Trophy, BadgeCheck, Users, Award, Sparkles,
} from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";
import api, { formatApiError } from "@/lib/api";
import { EmptyState } from "@/components/State";
import StarRating from "@/components/StarRating";
import ReviewList from "@/components/ReviewList";

const NAVY = "#0A1F44";
const GOLD = "#D4AF37";
const TOOLTIP_STYLE = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 };

function StatCard({ icon: Icon, label, value, hint, testId }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5" data-testid={testId}>
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

export default function BrandPerformance() {
  const [perf, setPerf] = useState(null);
  const [trends, setTrends] = useState([]);
  const [topCampaigns, setTopCampaigns] = useState([]);
  const [topCreators, setTopCreators] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [p, t, tc, tcr, me] = await Promise.all([
          api.get("/performance/brand/me"),
          api.get("/performance/trends"),
          api.get("/performance/top-campaigns"),
          api.get("/performance/top-creators"),
          api.get("/auth/me"),
        ]);
        setPerf(p.data || null);
        setTrends(t.data.series || []);
        setTopCampaigns(tc.data.top_campaigns || []);
        setTopCreators(tcr.data.top_creators || []);
        const uid = me.data?.user?.id;
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

  const hasData = (perf?.total_campaigns || 0) > 0 || (perf?.total_deals || 0) > 0;

  return (
    <div className="space-y-8" data-testid="brand-performance">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Performance</h2>
        <p className="text-sm text-muted-foreground mt-1">Deep-dive into your campaign ROI, top creators and rating from the creator network.</p>
      </div>

      {/* Brand identity card */}
      <div className="rounded-2xl border border-border bg-card p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4" data-testid="brand-hero">
        <div className="flex items-start gap-4 min-w-0">
          <div className="h-16 w-16 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center text-lg font-semibold">
            {(perf?.brand?.company_name || "B").slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-xl font-display text-primary dark:text-white truncate">
                {perf?.brand?.company_name || "Your brand"}
              </h3>
              {perf?.verified && (
                <span className="inline-flex items-center gap-1 rounded-full bg-secondary/15 text-secondary px-2 py-0.5 text-[10px] font-semibold">
                  <BadgeCheck className="h-3 w-3" /> Verified
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <StarRating value={perf?.average_creator_rating || 0} size={16} />
              <span className="text-sm font-semibold">{(perf?.average_creator_rating || 0).toFixed(1)}</span>
              <span className="text-xs text-muted-foreground">({perf?.total_reviews || 0} creator reviews)</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{perf?.brand?.industry || "—"}</p>
          </div>
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Activity} label="Total campaigns" value={perf?.total_campaigns || 0} hint={`${perf?.active_campaigns || 0} active · ${perf?.completed_campaigns || 0} completed`} testId="bp-stat-campaigns" />
        <StatCard icon={IndianRupee} label="Total spend" value={`₹${Number(perf?.total_spend || 0).toLocaleString()}`} hint="Across all campaigns" testId="bp-stat-spend" />
        <StatCard icon={TrendingUp} label="Average ROI" value={`${perf?.average_roi || 0}×`} hint="Estimated sales ÷ spend" testId="bp-stat-roi" />
        <StatCard icon={Star} label="Creator rating" value={(perf?.average_creator_rating || 0).toFixed(1)} hint={`${perf?.total_reviews || 0} reviews`} testId="bp-stat-rating" />
      </div>

      {!hasData && (
        <EmptyState
          icon={Sparkles}
          title="No campaigns yet"
          description="Launch your first campaign and invite creators — performance analytics will start populating here automatically."
          action={
            <Link to="/brand/campaigns" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold">
              Create campaign
            </Link>
          }
          testId="bp-empty"
        />
      )}

      {/* Trend charts */}
      {trends.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard title="Performance trend" subtitle="Deals raised vs completed per week" testId="bp-chart-perf">
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

          <ChartCard title="Reach trend" subtitle="Real reach from creator metrics" testId="bp-chart-reach">
            <AreaChart data={trends}>
              <defs>
                <linearGradient id="bpReach" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={GOLD} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toLocaleString(), "Reach"]} />
              <Area type="monotone" dataKey="reach" stroke={GOLD} strokeWidth={2} fill="url(#bpReach)" />
            </AreaChart>
          </ChartCard>

          <ChartCard title="Engagement trend" subtitle="Likes + comments + shares + saves" testId="bp-chart-engagement">
            <BarChart data={trends}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toLocaleString(), "Engagement"]} />
              <Bar dataKey="engagement" fill={NAVY} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ChartCard>

          <ChartCard title="ROI trend" subtitle="Estimated sales vs spend per week" testId="bp-chart-roi">
            <LineChart data={trends}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${Number(v).toFixed(2)}×`, "ROI"]} />
              <Line type="monotone" dataKey="roi" stroke={GOLD} strokeWidth={2} dot={false} />
            </LineChart>
          </ChartCard>
        </div>
      )}

      {/* Top performing campaigns */}
      {topCampaigns.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-6" data-testid="bp-top-campaigns">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Top performing campaigns</h3>
            <Trophy className="h-4 w-4 text-secondary" />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {topCampaigns.slice(0, 6).map((c) => (
              <Link
                key={c.campaign_id}
                to={`/brand/campaigns/${c.campaign_id}`}
                className="rounded-xl border border-border bg-background p-4 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all"
                data-testid={`bp-top-campaign-${c.campaign_id}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-primary dark:text-white truncate">{c.title}</div>
                    <div className="text-[10px] uppercase tracking-wider text-secondary mt-0.5">{c.platform || "—"}</div>
                  </div>
                  <Award className="h-4 w-4 text-secondary" />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
                  <Mini label="Reach" value={Number(c.reach).toLocaleString()} />
                  <Mini label="Engagement" value={Number(c.engagement).toLocaleString()} />
                  <Mini label="Deals" value={c.deals} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Top performing creators */}
      {topCreators.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-6" data-testid="bp-top-creators">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Top performing creators</h3>
            <Users className="h-4 w-4 text-secondary" />
          </div>
          <div className="mt-4 divide-y divide-border">
            {topCreators.slice(0, 8).map((c, i) => (
              <div key={c.influencer_id} className="py-3 flex items-center gap-3" data-testid={`bp-top-creator-${c.influencer_id}`}>
                <div className="h-9 w-9 rounded-full bg-primary text-primary-foreground text-xs font-semibold flex items-center justify-center">
                  {c.profile_photo_url ? (
                    <img src={c.profile_photo_url} alt={c.username} className="h-full w-full rounded-full object-cover" />
                  ) : (
                    `#${i + 1}`
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-primary dark:text-white truncate">{c.username}</div>
                  <div className="text-[11px] text-muted-foreground truncate flex items-center gap-1">
                    <span>{c.category || "—"}</span>
                    {c.total_reviews > 0 && (
                      <>
                        <span>·</span>
                        <StarRating value={c.average_rating} size={11} />
                        <span>{c.average_rating.toFixed(1)}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div className="font-semibold text-primary dark:text-white">{Number(c.reach).toLocaleString()} reach</div>
                  <div className="text-muted-foreground text-[11px]">{c.deals} deals</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reviews for this brand */}
      <div data-testid="bp-reviews">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-primary dark:text-white">What creators say</h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Star className="h-3.5 w-3.5 text-secondary" /> {(perf?.average_creator_rating || 0).toFixed(1)} · {perf?.total_reviews || 0} reviews
          </div>
        </div>
        <ReviewList reviews={reviews} emptyTitle="No creator reviews yet" emptyDescription="Once campaigns close, creator feedback about your brand appears here." />
      </div>
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-card p-2">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-xs font-semibold text-primary dark:text-white">{value}</div>
    </div>
  );
}
