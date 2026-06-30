import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Megaphone, CheckCircle2, X, Truck, Send, Sparkles, Filter } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { StatusChip, EmptyState } from "@/components/State";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "offer_sent", label: "New offers" },
  { key: "offer_accepted", label: "Accepted" },
  { key: "product_shipped", label: "In progress" },
  { key: "promotion_live", label: "Live" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

// Allowed forward transitions for the influencer
const NEXT_STEPS = {
  offer_sent: [
    { to: "offer_accepted", label: "Accept offer", icon: CheckCircle2, tone: "primary" },
    { to: "cancelled", label: "Decline", icon: X, tone: "ghost" },
  ],
  offer_accepted: [
    { to: "product_shipped", label: "Product received", icon: Truck, tone: "primary" },
  ],
  product_shipped: [
    { to: "promotion_pending", label: "Content ready", icon: Send, tone: "primary" },
  ],
  promotion_pending: [
    { to: "promotion_live", label: "Post is live", icon: Sparkles, tone: "primary" },
  ],
  promotion_live: [
    { to: "completed", label: "Mark complete", icon: CheckCircle2, tone: "primary" },
  ],
};

export default function InfluencerCampaigns() {
  const [deals, setDeals] = useState([]);
  const [campaigns, setCampaigns] = useState({}); // id -> campaign
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/deals");
      const list = data.deals || [];
      setDeals(list);
      // fetch related campaigns (unique)
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

  const filtered = useMemo(() => (
    filter === "all" ? deals : deals.filter((d) => d.status === filter)
  ), [deals, filter]);

  const setStatus = async (deal, to) => {
    setBusy(true);
    try {
      await api.patch(`/deals/${deal.id}/status`, { status: to });
      toast.success(`Status updated → ${to.replace(/_/g, " ")}`);
      setDeals((arr) => arr.map((d) => d.id === deal.id ? { ...d, status: to } : d));
      setActive((a) => a && a.id === deal.id ? { ...a, status: to } : a);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  return (
    <div className="space-y-6" data-testid="influencer-campaigns">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">Campaigns</h2>
          <p className="text-sm text-muted-foreground mt-1">Every brand collaboration in one place — accept offers, track progress, mark deliverables live.</p>
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
              onClick={() => setActive(d)}
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
                <StatusChip value={d.status} />
              </div>
              {d.note && <p className="mt-3 text-sm text-muted-foreground line-clamp-3">{d.note}</p>}
              {c?.deliverables?.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {c.deliverables.slice(0, 2).map((x, i) => (
                    <li key={i} className="text-xs text-foreground/80 truncate">• {x}</li>
                  ))}
                </ul>
              )}
              <div className="mt-4 text-[11px] text-muted-foreground">
                Tap to view details &amp; update status →
              </div>
            </button>
          );
        })}
      </div>

      <Dialog open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <DialogContent className="max-w-2xl" data-testid="deal-dialog">
          {active && (
            <>
              <DialogHeader>
                <DialogTitle className="text-2xl font-display font-light">
                  {campaigns[active.campaign_id]?.title || "Campaign offer"}
                </DialogTitle>
                <DialogDescription>
                  {campaigns[active.campaign_id]?.platform || "Platform TBD"} ·
                  &nbsp;₹{Number(active.amount || 0).toLocaleString()} payout
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <StatusChip value={active.status} />
                  {campaigns[active.campaign_id]?.deadline && (
                    <span className="text-xs text-muted-foreground">
                      Deadline: {campaigns[active.campaign_id].deadline}
                    </span>
                  )}
                </div>

                {campaigns[active.campaign_id]?.product_details && (
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Product details</div>
                    <p className="mt-1 text-sm text-foreground/90 whitespace-pre-line">{campaigns[active.campaign_id].product_details}</p>
                  </div>
                )}

                {campaigns[active.campaign_id]?.deliverables?.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Deliverables</div>
                    <ul className="mt-1 list-disc list-inside text-sm text-foreground/90 space-y-0.5">
                      {campaigns[active.campaign_id].deliverables.map((x, i) => <li key={i}>{x}</li>)}
                    </ul>
                  </div>
                )}

                {active.note && (
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Note from brand</div>
                    <p className="mt-1 text-sm text-foreground/90 whitespace-pre-line">{active.note}</p>
                  </div>
                )}

                <div className="pt-2 border-t border-border" />

                <div className="flex flex-wrap gap-2 justify-end">
                  {(NEXT_STEPS[active.status] || []).map((step) => (
                    <button
                      key={step.to}
                      onClick={() => setStatus(active, step.to)}
                      disabled={busy}
                      data-testid={`deal-action-${step.to}`}
                      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold disabled:opacity-60 ${
                        step.tone === "primary"
                          ? "bg-primary text-primary-foreground hover:bg-primary/90"
                          : "border border-border hover:bg-accent"
                      }`}
                    >
                      <step.icon className="h-4 w-4" /> {step.label}
                    </button>
                  ))}
                  {!NEXT_STEPS[active.status] && (
                    <span className="text-xs text-muted-foreground self-center">No further actions for this status.</span>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
