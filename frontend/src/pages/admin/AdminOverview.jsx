import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { LineChart, Line, BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { Users, Building2, Sparkles, DollarSign, ShieldCheck, Banknote, Activity, CheckCircle2, XCircle } from "lucide-react";
import { Link } from "react-router-dom";

const ICONS = { total_users: Users, total_brands: Building2, total_influencers: Sparkles, revenue_today: DollarSign,
  revenue_month: DollarSign, pending_verification: ShieldCheck, pending_withdrawals: Banknote,
  pending_escrow_releases: Banknote,
  running_campaigns: Activity, completed_campaigns: CheckCircle2, cancelled_campaigns: XCircle };

const LABELS = { total_users: "Total Users", total_brands: "Brands", total_influencers: "Influencers",
  revenue_today: "Revenue Today", revenue_month: "Revenue (MTD)", pending_verification: "Pending KYC",
  pending_withdrawals: "Pending Payouts", running_campaigns: "Running Campaigns",
  pending_escrow_releases: "Release Payments",
  completed_campaigns: "Completed", cancelled_campaigns: "Cancelled" };

function Card({ k, v }) {
  const Icon = ICONS[k] || Activity;
  const isMoney = k.startsWith("revenue");
  return (
    <div className="rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all" data-testid={`stat-${k}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{LABELS[k]}</span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-3xl font-display font-light text-primary dark:text-white">
        {isMoney ? `$${Number(v).toLocaleString()}` : Number(v).toLocaleString()}
      </div>
    </div>
  );
}

export default function AdminOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/admin/overview");
      setData(response.data);
    } catch (requestError) {
      setError(formatApiError(requestError));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="text-muted-foreground" role="status">Loading platform overview...</div>;
  if (error) return <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-5"><p className="font-semibold text-destructive">Overview unavailable</p><p className="mt-1 text-sm text-muted-foreground">{error}</p><button onClick={load} className="mt-4 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">Retry</button></div>;

  if (!data) return <div className="text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-8" data-testid="admin-overview">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Platform overview</h2>
        <p className="text-sm text-muted-foreground mt-1">Real-time snapshot of BrandKrt across users, campaigns and revenue.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <AdminAIEntry to="/admin/brand-discovery" title="Discover brands" description="Research factual public brand signals." />
        <AdminAIEntry to="/admin/creator-discovery" title="Discover creators" description="Compare fit, pricing signals and recommendations." />
        <AdminAIEntry to="/admin/saved-leads" title="Outreach workspace" description="Plan contact, track replies and add internal notes." />
      </div>
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-5">
        {Object.entries(data.cards).map(([k, v]) => <Card key={k} k={k} v={v} />)}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-card p-6">
          <h3 className="text-sm font-semibold text-primary dark:text-white">User growth (12 weeks)</h3>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.charts.weekly}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
                <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Line type="monotone" dataKey="users" stroke="#D4AF37" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="campaigns" stroke="#0A1F44" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-card p-6">
          <h3 className="text-sm font-semibold text-primary dark:text-white">Revenue (platform fee, 12 weeks)</h3>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.charts.weekly}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
                <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Bar dataKey="revenue" fill="#D4AF37" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

function AdminAIEntry({ to, title, description }) {
  return <Link to={to} className="group rounded-2xl border border-secondary/30 bg-secondary/5 p-5 transition hover:-translate-y-0.5 hover:shadow-luxe-sm">
    <div className="flex items-center justify-between"><Sparkles className="h-5 w-5 text-secondary" /><span className="text-xs font-semibold text-primary dark:text-secondary">Open</span></div>
    <h3 className="mt-4 font-semibold text-primary dark:text-white">{title}</h3>
    <p className="mt-1 text-sm text-muted-foreground">{description}</p>
  </Link>;
}
