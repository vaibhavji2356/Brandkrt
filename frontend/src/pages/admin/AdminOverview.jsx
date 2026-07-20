import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { LineChart, Line, BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { Users, Building2, Sparkles, DollarSign, ShieldCheck, Banknote, Activity, CheckCircle2, XCircle } from "lucide-react";

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
  useEffect(() => {
    (async () => {
      const r = await api.get("/admin/overview");
      setData(r.data);
    })();
  }, []);

  if (!data) return <div className="text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-8" data-testid="admin-overview">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Platform overview</h2>
        <p className="text-sm text-muted-foreground mt-1">Real-time snapshot of BrandKrt across users, campaigns and revenue.</p>
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
