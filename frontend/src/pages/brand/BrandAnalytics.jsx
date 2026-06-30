import React, { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell,
  ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";
import { Activity, IndianRupee, Users, Eye, Heart, TrendingUp } from "lucide-react";
import api from "@/lib/api";

const COLORS = ["#D4AF37", "#0A1F44", "#3B82F6", "#10B981", "#EF4444", "#8B5CF6", "#F59E0B"];
const NAVY = "#0A1F44";
const GOLD = "#D4AF37";

function weekBucket(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  // ISO week start (Mon)
  const dayMs = 24 * 60 * 60 * 1000;
  const dow = (d.getUTCDay() + 6) % 7; // 0=Mon
  const monday = new Date(d.getTime() - dow * dayMs);
  monday.setUTCHours(0, 0, 0, 0);
  return monday.toISOString().slice(0, 10);
}

function last12WeeksKeys() {
  const out = [];
  const now = new Date();
  const dayMs = 24 * 60 * 60 * 1000;
  const dow = (now.getUTCDay() + 6) % 7;
  const thisMon = new Date(now.getTime() - dow * dayMs);
  thisMon.setUTCHours(0, 0, 0, 0);
  for (let i = 11; i >= 0; i--) {
    const d = new Date(thisMon.getTime() - i * 7 * dayMs);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

function shortLabel(iso) {
  const d = new Date(iso);
  return `${d.toLocaleString("default", { month: "short" })} ${d.getUTCDate()}`;
}

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
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-primary dark:text-white">{title}</h3>
          {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="h-64 mt-4">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const TOOLTIP_STYLE = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 };

export default function BrandAnalytics() {
  const [campaigns, setCampaigns] = useState([]);
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, d, p] = await Promise.all([
          api.get("/campaigns"),
          api.get("/deals"),
          api.get("/payments"),
        ]);
        setCampaigns(c.data.campaigns || []);
        setDeals(d.data.deals || []);
        setPayments(p.data.payments || []);
      } catch (_) { /* noop */ }
      setLoading(false);
    })();
  }, []);

  const dealIds = useMemo(() => new Set(deals.map((d) => d.id)), [deals]);
  const myPayments = useMemo(() => payments.filter((p) => dealIds.has(p.deal_id)), [payments, dealIds]);

  const weeks = useMemo(() => last12WeeksKeys(), []);

  // Weekly campaign performance + spend
  const weekly = useMemo(() => {
    const map = {};
    weeks.forEach((w) => { map[w] = { week: w, label: shortLabel(w), launched: 0, completed: 0, spend: 0, deals: 0, creators: new Set() }; });
    campaigns.forEach((c) => {
      const w = weekBucket(c.created_at);
      if (w && map[w]) map[w].launched += 1;
      if (c.status === "completed") {
        const w2 = weekBucket(c.updated_at || c.created_at);
        if (w2 && map[w2]) map[w2].completed += 1;
      }
    });
    deals.forEach((d) => {
      const w = weekBucket(d.created_at);
      if (w && map[w]) { map[w].deals += 1; if (d.influencer_id) map[w].creators.add(d.influencer_id); }
    });
    myPayments.forEach((p) => {
      const w = weekBucket(p.created_at);
      if (w && map[w]) map[w].spend += Number(p.amount || 0);
    });
    return weeks.map((w) => ({ ...map[w], creators: map[w].creators.size }));
  }, [weeks, campaigns, deals, myPayments]);

  // Creator growth (cumulative unique influencers engaged)
  const creatorGrowth = useMemo(() => {
    const seen = new Set();
    return weeks.map((w) => {
      deals
        .filter((d) => d.influencer_id && weekBucket(d.created_at) === w)
        .forEach((d) => seen.add(d.influencer_id));
      return { week: w, label: shortLabel(w), total_creators: seen.size };
    });
  }, [weeks, deals]);

  // Status mix
  const statusMix = useMemo(() => {
    const m = {};
    campaigns.forEach((c) => { m[c.status] = (m[c.status] || 0) + 1; });
    return Object.entries(m).map(([k, v]) => ({ name: k, value: v }));
  }, [campaigns]);

  // Headline KPIs
  const totalSpend = myPayments.reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const totalReach = useMemo(() => weekly.reduce((s, w) => s + w.deals * 4500, 0), [weekly]); // heuristic
  const engagementRate = useMemo(() => (totalReach ? Math.round((totalReach * 0.038)) : 0), [totalReach]); // ~3.8% engagement heuristic
  const roi = useMemo(() => (totalSpend > 0 ? ((engagementRate * 4) / totalSpend).toFixed(2) : "0.00"), [engagementRate, totalSpend]);
  const uniqueCreators = useMemo(() => new Set(deals.map((d) => d.influencer_id).filter(Boolean)).size, [deals]);

  if (loading) return <div className="text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-8" data-testid="brand-analytics">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Analytics</h2>
        <p className="text-sm text-muted-foreground mt-1">A real-time look at your campaign performance, spend and creator network.</p>
      </div>

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Activity} label="Campaigns Run" value={campaigns.length} hint={`${campaigns.filter((c) => c.status === "completed").length} completed`} testId="kpi-campaigns" />
        <StatCard icon={IndianRupee} label="Total Spend" value={`₹${totalSpend.toLocaleString()}`} hint={`${myPayments.length} payments`} testId="kpi-spend" />
        <StatCard icon={Users} label="Creators Engaged" value={uniqueCreators} hint={`${deals.length} total invites`} testId="kpi-creators" />
        <StatCard icon={TrendingUp} label="Est. ROI" value={`${roi}×`} hint="Engagement value ÷ spend" testId="kpi-roi" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Campaign performance" subtitle="Launched vs completed campaigns per week" testId="chart-performance">
          <BarChart data={weekly}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} allowDecimals={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="launched" name="Launched" fill={GOLD} radius={[6, 6, 0, 0]} />
            <Bar dataKey="completed" name="Completed" fill={NAVY} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Money spent" subtitle="Total campaign spend per week (gross)" testId="chart-spend">
          <AreaChart data={weekly}>
            <defs>
              <linearGradient id="gSpend" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={GOLD} stopOpacity={0.5} />
                <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`₹${Number(v).toLocaleString()}`, "Spend"]} />
            <Area type="monotone" dataKey="spend" stroke={GOLD} strokeWidth={2} fill="url(#gSpend)" />
          </AreaChart>
        </ChartCard>

        <ChartCard title="Creator growth" subtitle="Cumulative unique creators you've engaged" testId="chart-creator-growth">
          <LineChart data={creatorGrowth}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} allowDecimals={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Line type="monotone" dataKey="total_creators" name="Creators" stroke={NAVY} strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>

        <ChartCard title="Estimated reach" subtitle="Per-week reach based on deal volume" testId="chart-reach">
          <LineChart data={weekly.map((w) => ({ ...w, reach: w.deals * 4500 }))}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toLocaleString(), "Reach"]} />
            <Line type="monotone" dataKey="reach" stroke={GOLD} strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>

        <ChartCard title="Engagement" subtitle="Estimated likes + comments + shares per week" testId="chart-engagement">
          <BarChart data={weekly.map((w) => ({ ...w, engagement: Math.round(w.deals * 4500 * 0.038) }))}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toLocaleString(), "Engagements"]} />
            <Bar dataKey="engagement" fill={NAVY} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="ROI trend" subtitle="Estimated engagement value vs spend" testId="chart-roi">
          <LineChart data={weekly.map((w) => ({ ...w, roi: w.spend > 0 ? Number(((w.deals * 4500 * 0.038 * 4) / w.spend).toFixed(2)) : 0 }))}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${Number(v).toFixed(2)}×`, "ROI"]} />
            <Line type="monotone" dataKey="roi" stroke={GOLD} strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>
      </div>

      {statusMix.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="rounded-2xl border border-border bg-card p-6 lg:col-span-1" data-testid="chart-status-mix">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Campaign status mix</h3>
            <div className="h-64 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={statusMix} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={3}>
                    {statusMix.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 lg:col-span-2 flex flex-col gap-4" data-testid="analytics-callouts">
            <h3 className="text-sm font-semibold text-primary dark:text-white">At a glance</h3>
            <div className="grid grid-cols-2 gap-3">
              <Mini icon={Eye} label="Estimated reach" value={totalReach.toLocaleString()} hint="≈ 4.5K avg / deal" />
              <Mini icon={Heart} label="Estimated engagements" value={engagementRate.toLocaleString()} hint="≈ 3.8% engagement" />
              <Mini icon={Users} label="Unique creators" value={uniqueCreators} hint="Engaged with your brand" />
              <Mini icon={Activity} label="Deals raised" value={deals.length} hint={`${deals.filter((d) => d.status === "completed").length} completed`} />
            </div>
            <p className="text-[11px] text-muted-foreground">
              Reach &amp; engagement are estimates derived from deal volume — exact numbers will appear here once platform analytics ingestion goes live.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function Mini({ icon: Icon, label, value, hint }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><Icon className="h-3.5 w-3.5 text-secondary" /> {label}</div>
      <div className="mt-1 text-lg font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="text-[10px] text-muted-foreground">{hint}</div>}
    </div>
  );
}
