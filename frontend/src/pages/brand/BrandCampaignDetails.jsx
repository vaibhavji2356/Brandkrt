import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, Calendar, IndianRupee, Globe2, Tag, Users, ImageIcon, Link as LinkIcon,
  Play, Pause, X as XIcon, CheckCircle2, Lock,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { StatusChip, EmptyState } from "@/components/State";

const CAMPAIGN_TRANSITIONS = {
  draft: [
    { to: "active", label: "Activate", icon: Play, tone: "primary" },
    { to: "cancelled", label: "Cancel", icon: XIcon, tone: "ghost" },
  ],
  active: [
    { to: "paused", label: "Pause", icon: Pause, tone: "ghost" },
    { to: "completed", label: "Mark complete", icon: CheckCircle2, tone: "primary" },
    { to: "cancelled", label: "Cancel", icon: XIcon, tone: "ghost" },
  ],
  paused: [
    { to: "active", label: "Resume", icon: Play, tone: "primary" },
    { to: "cancelled", label: "Cancel", icon: XIcon, tone: "ghost" },
  ],
  completed: [],
  cancelled: [],
};

export default function BrandCampaignDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState(null);
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [agreements, setAgreements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [c, d, p, a] = await Promise.all([
        api.get(`/campaigns/${id}`),
        api.get("/deals"),
        api.get("/payments"),
        api.get("/agreements").catch(() => ({ data: { agreements: [] } })),
      ]);
      setCampaign(c.data.campaign);
      setDeals((d.data.deals || []).filter((x) => x.campaign_id === id));
      setPayments(p.data.payments || []);
      setAgreements(a.data.agreements || []);
    } catch (err) {
      toast.error(formatApiError(err));
      navigate("/brand/campaigns");
    }
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [id]);

  const dealIds = useMemo(() => new Set(deals.map((d) => d.id)), [deals]);
  const agreementIds = useMemo(() => {
    const dealAmounts = new Set(deals.map((d) => Number(d.amount || 0)));
    return new Set(agreements
      .filter((a) => (
        a.campaign_id === id
        || a.campaign === campaign?.title
        || a.campaign_name === campaign?.title
        || dealAmounts.has(Number(a.payment_amount || 0))
      ))
      .map((a) => a.id));
  }, [agreements, deals, campaign, id]);
  const myPayments = useMemo(() => payments.filter((p) => (
    dealIds.has(p.deal_id)
    || agreementIds.has(p.agreement_id)
    || p.campaign_id === id
  )), [payments, dealIds, agreementIds, id]);

  const escrowed = myPayments
    .filter((p) => p.status === "escrowed" || ["held", "pending", "release_requested"].includes(p.release_status))
    .reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const released = myPayments
    .filter((p) => p.status === "released" || p.release_status === "released")
    .reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const totalSpend = escrowed + released;

  const setStatus = async (to) => {
    setBusy(true);
    try {
      await api.patch(`/campaigns/${id}/status`, null, { params: { status: to } });
      toast.success(`Campaign moved to ${to}.`);
      setCampaign((c) => ({ ...c, status: to }));
    } catch (err) { toast.error(formatApiError(err)); }
    setBusy(false);
  };

  if (loading) return <div className="text-muted-foreground">Loading…</div>;
  if (!campaign) return null;

  const acts = CAMPAIGN_TRANSITIONS[campaign.status] || [];

  return (
    <div className="space-y-8" data-testid="campaign-details">
      <div>
        <button onClick={() => navigate("/brand/campaigns")} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-secondary" data-testid="back-to-campaigns">
          <ArrowLeft className="h-4 w-4" /> Back to campaigns
        </button>
      </div>

      <div className="rounded-2xl border border-border bg-card p-6 md:p-8">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-3xl font-display font-light text-primary dark:text-white">{campaign.title}</h2>
              <StatusChip value={campaign.status} />
            </div>
            <p className="text-sm text-muted-foreground mt-1 capitalize">
              {campaign.platform} · {campaign.content_type || "Content"} · {campaign.payment_type || "Fixed fee"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {acts.map((a) => (
              <button
                key={a.to}
                onClick={() => setStatus(a.to)}
                disabled={busy}
                data-testid={`campaign-action-${a.to}`}
                className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold disabled:opacity-60 ${
                  a.tone === "primary" ? "bg-primary text-primary-foreground hover:bg-primary/90" : "border border-border hover:bg-accent"
                }`}
              >
                <a.icon className="h-4 w-4" /> {a.label}
              </button>
            ))}
            <Link to="/brand/discover" className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-4 py-2 text-sm font-semibold" data-testid="invite-creator-btn">
              <Users className="h-4 w-4" /> Invite creators
            </Link>
          </div>
        </div>

        {campaign.description && (
          <p className="mt-5 text-sm text-foreground/90 whitespace-pre-line">{campaign.description}</p>
        )}

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <Fact icon={IndianRupee} label="Budget" value={`₹${Number(campaign.budget || 0).toLocaleString()}`} />
          <Fact icon={Calendar} label="Deadline" value={campaign.deadline || "—"} />
          <Fact icon={Users} label="Min followers" value={Number(campaign.required_followers || 0).toLocaleString()} />
          <Fact icon={Globe2} label="Language" value={campaign.preferred_language || "—"} />
        </div>

        {(campaign.target_categories?.length || campaign.preferred_location || campaign.visibility) && (
          <div className="mt-4 flex flex-wrap gap-2">
            {campaign.visibility && (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent text-secondary px-3 py-1 text-xs font-semibold">
                {campaign.visibility === "invite_only" ? <Lock className="h-3 w-3" /> : <Globe2 className="h-3 w-3" />}
                {campaign.visibility.replace(/_/g, " ")}
              </span>
            )}
            {campaign.preferred_location && (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent text-secondary px-3 py-1 text-xs font-semibold">
                <Globe2 className="h-3 w-3" /> {campaign.preferred_location}
              </span>
            )}
            {(campaign.target_categories || []).map((c) => (
              <span key={c} className="inline-flex items-center gap-1 rounded-full bg-accent text-secondary px-3 py-1 text-xs font-semibold">
                <Tag className="h-3 w-3" /> {c}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <SmallStat label="Invited Creators" value={deals.length} />
        <SmallStat label="Accepted" value={deals.filter((d) => d.status !== "offer_sent" && d.status !== "cancelled").length} />
        <SmallStat label="In Escrow" value={`₹${escrowed.toLocaleString()}`} />
        <SmallStat label="Released" value={`₹${released.toLocaleString()}`} hint={`Total spend ₹${totalSpend.toLocaleString()}`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6">
          <h3 className="text-sm font-semibold text-primary dark:text-white">Creator deals on this campaign</h3>
          <div className="mt-4 divide-y divide-border">
            {deals.length === 0 && (
              <EmptyState
                icon={Users}
                title="No creator invites yet"
                description="Discover verified creators and invite them to this campaign."
                action={<Link to="/brand/discover" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold">Discover creators</Link>}
                testId="campaign-no-deals"
              />
            )}
            {deals.map((d) => (
              <div key={d.id} className="py-4" data-testid={`campaign-deal-${d.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                  <div className="text-sm font-semibold text-primary dark:text-white truncate">
                    ₹{Number(d.amount || 0).toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {d.note || "Open the deal to view its complete lifecycle."}
                  </div>
                  </div>
                  <StatusChip value={d.status} />
                </div>
                <button
                  type="button"
                  onClick={() => navigate(`/brand/deals/${d.id}`)}
                  className="mt-3 inline-flex w-full items-center justify-center rounded-full border border-primary px-4 py-2 text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground sm:w-auto"
                  data-testid={`campaign-deal-details-${d.id}`}
                >
                  View details
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6">
          <h3 className="text-sm font-semibold text-primary dark:text-white">Escrow &amp; payouts</h3>
          <div className="mt-4 space-y-3">
            {myPayments.length === 0 && (
              <p className="text-sm text-muted-foreground">No payments yet. Fund escrow from a deal to unlock messaging with the creator.</p>
            )}
            {myPayments.map((p) => (
              <div key={p.id} className="rounded-xl border border-border p-3" data-testid={`payment-${p.id}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-primary dark:text-white">₹{Number(p.amount).toLocaleString()}</div>
                  <StatusChip value={p.release_status || p.status} />
                </div>
                <div className="text-xs text-muted-foreground mt-1">TXN {p.transaction_id || p.id}</div>
                {(p.release_status === "held" || p.status === "escrowed") && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Held in escrow. After brand approval, admin releases creator payout.
                  </p>
                )}
                {p.release_status === "release_requested" && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Release requested. Admin needs to review this payout.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {(campaign.deliverables?.length || campaign.product_images?.length || campaign.promotion_links?.length || campaign.product_details) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {campaign.deliverables?.length > 0 && (
            <Card title="Deliverables">
              <ul className="space-y-2 text-sm text-foreground/90">
                {campaign.deliverables.map((d, i) => <li key={i} className="flex items-start gap-2"><CheckCircle2 className="h-4 w-4 mt-0.5 text-secondary" /> {d}</li>)}
              </ul>
            </Card>
          )}
          {campaign.product_details && (
            <Card title="Product details">
              <p className="text-sm text-foreground/90 whitespace-pre-line">{campaign.product_details}</p>
            </Card>
          )}
          {campaign.product_images?.length > 0 && (
            <Card title="Product images" full>
              <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
                {campaign.product_images.map((u, i) => (
                  <a key={i} href={u} target="_blank" rel="noreferrer" className="aspect-square rounded-xl overflow-hidden border border-border block">
                    <img src={u} alt="" className="w-full h-full object-cover" />
                  </a>
                ))}
              </div>
            </Card>
          )}
          {campaign.promotion_links?.length > 0 && (
            <Card title="Promotion links" full>
              <ul className="space-y-2 text-sm">
                {campaign.promotion_links.map((u, i) => (
                  <li key={i} className="flex items-center gap-2 truncate">
                    <LinkIcon className="h-4 w-4 text-secondary" />
                    <a href={u} target="_blank" rel="noreferrer" className="text-secondary hover:underline truncate">{u}</a>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function Fact({ icon: Icon, label, value }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><Icon className="h-3.5 w-3.5 text-secondary" /> {label}</div>
      <div className="mt-1 text-sm font-semibold text-primary dark:text-white truncate">{value}</div>
    </div>
  );
}

function SmallStat({ label, value, hint }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}

function Card({ title, children, full = false }) {
  return (
    <div className={`rounded-2xl border border-border bg-card p-6 ${full ? "lg:col-span-2" : ""}`}>
      <h3 className="text-sm font-semibold text-primary dark:text-white flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-secondary opacity-0" /> {title}
      </h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}
