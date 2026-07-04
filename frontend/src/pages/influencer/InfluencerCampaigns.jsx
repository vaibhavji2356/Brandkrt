import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Megaphone, Filter, ArrowRight } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { StatusChip, EmptyState } from "@/components/State";
import { DealProgressBar, canonicalStatus } from "@/components/DealTimeline";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "offer_sent", label: "New offers" },
  { key: "offer_accepted", label: "Accepted" },
  { key: "in_progress", label: "In progress" },     // synthetic group
  { key: "content_submitted", label: "Submitted" },
  { key: "published", label: "Live" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

const IN_PROGRESS_SET = new Set([
  "product_shipped", "product_received",
  "content_in_progress", "brand_review",
  "approved", "scheduled",
  // legacy
  "promotion_pending",
]);

export default function InfluencerCampaigns() {
  const navigate = useNavigate();
  const [deals, setDeals] = useState([]);
  const [campaigns, setCampaigns] = useState({}); // id -> campaign
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/deals");
      const list = data.deals || [];
      setDeals(list);
      const ids = Array.from(new Set(list.map((d) => d.campaign_id).filter(Boolean)));
      const fetched = {};
      await Promise.all(ids.map(async (cid) => {
        try {
          const r = await api.get(`/campaigns/${cid}`);
          fetched[cid] = r.data.campaign;
        } catch (_) { /* may not have access */ }
      }));
      setCampaigns(fetched);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const isCancelled = (d) => canonicalStatus(d.status) === "cancelled" || campaigns[d.campaign_id]?.status === "cancelled";
    if (filter === "all") return deals.filter((d) => !isCancelled(d));
    if (filter === "cancelled") return deals.filter(isCancelled);
    if (filter === "in_progress") return deals.filter((d) => !isCancelled(d) && IN_PROGRESS_SET.has(canonicalStatus(d.status)));
    if (filter === "published") return deals.filter((d) => !isCancelled(d) && ["published", "promotion_live"].includes(canonicalStatus(d.status)));
    return deals.filter((d) => !isCancelled(d) && canonicalStatus(d.status) === filter);
  }, [deals, filter, campaigns]);

  return (
    <div className="space-y-6" data-testid="influencer-campaigns">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">Campaigns</h2>
          <p className="text-sm text-muted-foreground mt-1">Every brand collaboration in one place. Tap a deal to open the full lifecycle and upload deliverables.</p>
        </div>
      </div>

      <div className="flex items-center gap-2 overflow-x-auto pb-1" data-testid="campaign-filters">
        <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            data-testid={`filter-${f.key}`}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap border transition-colors ${
              filter === f.key ? "bg-primary text-primary-foreground border-primary" : "bg-card border-border text-foreground/80 hover:bg-accent"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading && <div className="text-muted-foreground">Loading…</div>}

      {!loading && filtered.length === 0 && (
        <EmptyState
          icon={Megaphone}
          title="No campaigns here yet"
          description="Once a brand sends you an offer it will appear here. Make sure your profile is complete to attract more invites."
          testId="campaigns-empty"
        />
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((d) => {
          const c = campaigns[d.campaign_id];
          return (
            <button
              type="button"
              key={d.id}
              onClick={() => navigate(`/influencer/deals/${d.id}`)}
              data-testid={`deal-card-${d.id}`}
              className="text-left rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-base font-semibold text-primary dark:text-white truncate">
                    {c?.title || "Brand campaign offer"}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5 capitalize">
                    {c?.platform || "platform"} · ₹{Number(d.amount || 0).toLocaleString()}
                  </p>
                </div>
                <StatusChip value={campaigns[d.campaign_id]?.status === "cancelled" ? "cancelled" : d.status} />
              </div>
              {d.note && <p className="mt-3 text-sm text-muted-foreground line-clamp-3">{d.note}</p>}
              <div className="mt-4">
                <DealProgressBar status={campaigns[d.campaign_id]?.status === "cancelled" ? "cancelled" : d.status} />
              </div>
              <div className="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-secondary">
                Open deal <ArrowRight className="h-3 w-3" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
