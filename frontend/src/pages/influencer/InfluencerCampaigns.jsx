import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Lock, Loader2, MessageSquare } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { StatusChip, EmptyState } from "@/components/State";
import { formatApiError } from "@/lib/api";
import InfluencerAPI from "@/lib/influencerApi";

const ALL = "all";
const TABS = [
  { value: ALL, label: "All" },
  { value: "offer_sent", label: "Offers" },
  { value: "offer_accepted", label: "Accepted" },
  { value: "product_shipped", label: "Shipped" },
  { value: "promotion_live", label: "Live" },
  { value: "completed", label: "Completed" },
];

export default function InfluencerCampaigns() {
  const [tab, setTab] = useState(ALL);
  const [deals, setDeals] = useState([]);
  const [campaigns, setCampaigns] = useState({}); // id -> campaign doc
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const list = await InfluencerAPI.listDeals();
      setDeals(list);
      const ids = Array.from(new Set(list.map((d) => d.campaign_id).filter(Boolean)));
      const fetched = await Promise.all(
        ids.map((id) =>
          InfluencerAPI.getCampaign(id)
            .then((c) => [id, c])
            .catch(() => [id, null])
        )
      );
      const map = {};
      fetched.forEach(([id, c]) => {
        if (c) map[id] = c;
      });
      setCampaigns(map);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(
    () => (tab === ALL ? deals : deals.filter((d) => d.status === tab)),
    [tab, deals]
  );

  const updateStatus = async (id, status) => {
    setBusyId(id);
    try {
      await InfluencerAPI.setDealStatus(id, status);
      setDeals((arr) =>
        arr.map((d) => (d.id === id ? { ...d, status } : d))
      );
      toast.success(`Deal moved to "${status.replace(/_/g, " ")}"`);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="influencer-campaigns-page">
      <div>
        <h2 className="text-2xl sm:text-3xl font-display font-light text-primary dark:text-white">
          Campaigns
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage every offer from invitation to payout.
        </p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList
          className="flex flex-wrap h-auto gap-1"
          data-testid="campaigns-tabs"
        >
          {TABS.map((t) => (
            <TabsTrigger
              key={t.value}
              value={t.value}
              data-testid={`campaigns-tab-${t.value}`}
              className="text-xs sm:text-sm"
            >
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value={tab} className="mt-6 space-y-3">
          {loading ? (
            <div
              className="flex items-center justify-center py-16"
              data-testid="campaigns-loading"
            >
              <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              title="No campaigns here yet"
              description={
                tab === ALL
                  ? "Once a brand sends you an offer, it will appear here."
                  : "Nothing in this status right now."
              }
              testId="campaigns-empty"
            />
          ) : (
            filtered.map((d) => (
              <DealCard
                key={d.id}
                deal={d}
                campaign={campaigns[d.campaign_id]}
                busy={busyId === d.id}
                onUpdate={(status) => updateStatus(d.id, status)}
              />
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function DealCard({ deal, campaign, busy, onUpdate }) {
  const next = nextActions(deal.status);
  return (
    <div
      className="rounded-2xl border border-border bg-card p-5 sm:p-6"
      data-testid={`deal-card-${deal.id}`}
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="min-w-0">
          <div className="text-base font-semibold text-primary dark:text-white truncate">
            {campaign?.title || `Deal #${deal.id.slice(-6)}`}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5 capitalize">
            {campaign?.platform || "—"} · ₹
            {Number(deal.amount || 0).toLocaleString()}
          </div>
          {campaign?.product_details && (
            <p className="mt-3 text-sm text-foreground/80 line-clamp-2">
              {campaign.product_details}
            </p>
          )}
          {campaign?.deliverables?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {campaign.deliverables.map((dl, i) => (
                <span
                  key={i}
                  className="inline-flex rounded-full bg-accent text-secondary px-2.5 py-0.5 text-[11px] font-semibold"
                >
                  {dl}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex flex-col items-start sm:items-end gap-3 shrink-0">
          <StatusChip value={deal.status} />
          <span
            className="inline-flex items-center gap-1 text-xs text-muted-foreground"
            title="Messaging unlocks once payment is escrowed"
          >
            <Lock className="h-3 w-3" />
            <MessageSquare className="h-3 w-3" />
            Chat locked until escrow
          </span>
        </div>
      </div>

      {next.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {next.map((a) => (
            <button
              key={a.value}
              type="button"
              disabled={busy}
              onClick={() => onUpdate(a.value)}
              data-testid={`deal-${deal.id}-action-${a.value}`}
              className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold disabled:opacity-60 ${
                a.tone === "danger"
                  ? "border border-destructive/40 text-destructive hover:bg-destructive/5"
                  : a.tone === "ghost"
                  ? "border border-border text-foreground/80 hover:bg-accent"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              }`}
            >
              {busy && <Loader2 className="h-3 w-3 animate-spin" />}
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function nextActions(status) {
  switch (status) {
    case "offer_sent":
      return [
        { value: "offer_accepted", label: "Accept offer", tone: "primary" },
        { value: "cancelled", label: "Decline", tone: "danger" },
      ];
    case "offer_accepted":
      return [{ value: "product_shipped", label: "Mark product received", tone: "ghost" }];
    case "product_shipped":
      return [{ value: "promotion_pending", label: "Start promotion", tone: "primary" }];
    case "promotion_pending":
      return [{ value: "promotion_live", label: "Mark live", tone: "primary" }];
    case "promotion_live":
      return [{ value: "completed", label: "Mark complete", tone: "primary" }];
    default:
      return [];
  }
}
