import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ScrollText } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { StatusChip, EmptyState } from "@/components/State";

export default function InfluencerAgreements() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/agreements");
        setItems(data.agreements || []);
      } catch (err) {
        toast.error(formatApiError(err));
      }
      setLoading(false);
    })();
  }, []);

  return (
    <div className="space-y-6" data-testid="influencer-agreements">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Agreements</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Review and sign campaign agreements sent to you by brands.
        </p>
      </div>

      {loading ? (
        <div className="text-muted-foreground">Loading…</div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No agreements yet"
          description="When a brand sends you a digital agreement, it'll show up here for review and signing."
          testId="influencer-agreements-empty"
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((a) => (
            <Link
              key={a.id}
              to={`/agreements/${a.id}`}
              data-testid={`agreement-${a.id}`}
              className="rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="font-display text-lg text-primary dark:text-white truncate">{a.brand_name}</h3>
                  <p className="text-xs text-muted-foreground truncate">{a.campaign || "Campaign"}</p>
                </div>
                <StatusChip value={a.status} />
              </div>
              <div className="mt-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Payment</span>
                  <span className="font-semibold">₹{Number(a.payment_amount || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-muted-foreground">Net to you</span>
                  <span className="font-semibold">₹{Number(a.net_to_influencer || 0).toLocaleString()}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
