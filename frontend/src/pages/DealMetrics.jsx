import React, { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, Save, Loader2, Instagram, Youtube, Facebook, Heart, MessageSquare,
  Share2, Bookmark, Eye, MousePointer2, IndianRupee, BarChart3, FileText, TrendingUp,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StatusChip } from "@/components/State";
import { useAuth } from "@/context/AuthContext";

const METRIC_FIELDS = [
  { key: "instagram_reel_views", label: "Instagram Reel Views", icon: Instagram },
  { key: "youtube_views", label: "YouTube Views", icon: Youtube },
  { key: "facebook_views", label: "Facebook Views", icon: Facebook },
  { key: "likes", label: "Likes", icon: Heart },
  { key: "comments", label: "Comments", icon: MessageSquare },
  { key: "shares", label: "Shares", icon: Share2 },
  { key: "saves", label: "Saves", icon: Bookmark },
  { key: "reach", label: "Reach", icon: Eye },
  { key: "clicks", label: "Clicks", icon: MousePointer2 },
];

export default function DealMetrics() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [deal, setDeal] = useState(null);
  const [campaign, setCampaign] = useState(null);
  const [metrics, setMetrics] = useState(null); // computed (server)
  const [form, setForm] = useState(() => Object.fromEntries(METRIC_FIELDS.map((f) => [f.key, 0])));
  const [sales, setSales] = useState(0);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const isInfluencer = user?.role === "influencer";

  const load = async () => {
    setLoading(true);
    try {
      const [d, m] = await Promise.all([
        api.get("/deals"),
        api.get(`/deals/${id}/metrics`).catch(() => ({ data: { metrics: {} } })),
      ]);
      const found = (d.data.deals || []).find((x) => x.id === id);
      if (!found) {
        toast.error("Deal not found");
        navigate(-1);
        return;
      }
      setDeal(found);
      if (found.campaign_id) {
        try {
          const c = await api.get(`/campaigns/${found.campaign_id}`);
          setCampaign(c.data.campaign);
        } catch (_) { /* ignore */ }
      }
      const cm = m.data.metrics || {};
      setMetrics(cm);
      setForm((prev) => {
        const next = { ...prev };
        METRIC_FIELDS.forEach((f) => { next[f.key] = cm[f.key] || 0; });
        return next;
      });
      setSales(cm.estimated_sales || 0);
      setNotes(cm.notes || "");
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [id]);

  const save = async (e) => {
    e?.preventDefault?.();
    setSaving(true);
    try {
      const payload = {
        ...Object.fromEntries(METRIC_FIELDS.map((f) => [f.key, Number(form[f.key]) || 0])),
        estimated_sales: Number(sales) || 0,
        notes: notes.trim() || null,
      };
      const { data } = await api.post(`/deals/${id}/metrics`, payload);
      setMetrics(data.metrics);
      toast.success("Performance metrics saved.");
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setSaving(false);
  };

  if (loading) return <div className="text-muted-foreground">Loading…</div>;
  if (!deal) return null;

  const totalViews = METRIC_FIELDS
    .filter((f) => f.key.includes("views"))
    .reduce((s, f) => s + (Number(form[f.key]) || 0), 0);

  return (
    <div className="space-y-6 max-w-5xl mx-auto" data-testid="deal-metrics">
      <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-secondary">
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <h2 className="text-2xl font-display text-primary dark:text-white truncate">
              {campaign?.title || "Campaign performance"}
            </h2>
            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <StatusChip value={deal.status} />
              <span>· Deal payout ₹{Number(deal.amount || 0).toLocaleString()}</span>
            </div>
          </div>
          <Link
            to={`/deals/${id}/report`}
            className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-4 py-2 text-sm font-semibold"
            data-testid="metrics-open-report"
          >
            <FileText className="h-4 w-4" /> View completion report
          </Link>
        </div>
      </div>

      {/* Computed KPIs */}
      {metrics && (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <Kpi icon={Eye} label="Total views" value={Number(metrics.total_views || 0).toLocaleString()} />
          <Kpi icon={BarChart3} label="Engagement rate" value={`${metrics.engagement_rate || 0}%`} />
          <Kpi icon={MousePointer2} label="CTR" value={`${metrics.ctr || 0}%`} />
          <Kpi icon={TrendingUp} label="ROI" value={`${metrics.roi_x || 0}×`} hint={`${metrics.roi_pct || 0}% net`} />
        </div>
      )}

      {/* Input form */}
      <form onSubmit={save} className="rounded-2xl border border-border bg-card p-6 space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-primary dark:text-white">Report performance</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {isInfluencer
              ? "Enter the latest numbers from your insights. The brand sees these in their completion report."
              : "Read-only — only the creator can update these numbers."}
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {METRIC_FIELDS.map((f) => (
            <MetricField
              key={f.key}
              icon={f.icon}
              label={f.label}
              value={form[f.key]}
              onChange={(v) => setForm((p) => ({ ...p, [f.key]: v }))}
              disabled={!isInfluencer}
              testId={`metric-${f.key}`}
            />
          ))}
          <MetricField
            icon={IndianRupee}
            label="Estimated sales (₹)"
            value={sales}
            onChange={setSales}
            disabled={!isInfluencer}
            testId="metric-sales"
          />
        </div>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Notes</span>
          <Textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={!isInfluencer}
            placeholder="Any context for these numbers — e.g. screenshot date, peak engagement window…"
            className="mt-1"
            data-testid="metric-notes"
          />
        </label>

        <div className="text-xs text-muted-foreground">Live total views: <strong className="text-primary dark:text-white">{Number(totalViews).toLocaleString()}</strong></div>

        {isInfluencer && (
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              data-testid="metric-save"
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2 text-sm font-semibold disabled:opacity-60"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save metrics
            </button>
          </div>
        )}
      </form>
    </div>
  );
}

function MetricField({ icon: Icon, label, value, onChange, disabled, testId }) {
  return (
    <label className="block rounded-xl border border-border bg-background p-3" data-testid={testId}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-secondary" /> {label}
      </div>
      <Input
        type="number"
        min="0"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2"
      />
    </label>
  );
}

function Kpi({ icon: Icon, label, value, hint }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-2xl font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}
