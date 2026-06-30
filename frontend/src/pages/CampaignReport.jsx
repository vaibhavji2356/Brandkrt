import React, { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, Trophy, IndianRupee, Eye, Heart, MousePointer2, TrendingUp,
  CheckCircle2, ScrollText, MessageCircle, BadgeCheck, ShieldCheck, Sparkles,
  Calendar, Send, Pencil,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { StatusChip, EmptyState } from "@/components/State";
import StarRating from "@/components/StarRating";
import ReviewList from "@/components/ReviewList";
import ReviewForm from "@/components/ReviewForm";
import { useAuth } from "@/context/AuthContext";

export default function CampaignReport() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showReview, setShowReview] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/performance/deal/${id}/report`);
      setReport(data);
    } catch (err) {
      toast.error(formatApiError(err));
      navigate(-1);
    }
    setLoading(false);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [id]);

  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>;
  if (!report) return null;

  const { deal, campaign, brand, influencer, payment, metrics, completion_pct, reviews, history } = report;
  const isBrand = user?.role === "brand" || user?.role === "admin";
  const isInfluencer = user?.role === "influencer";

  const partnerUserId = isBrand ? influencer?.user_id : brand?.user_id;
  const partnerName = isBrand ? (influencer?.username || "Creator") : (brand?.company_name || "Brand");
  const myExistingReview = reviews?.find((r) => r.reviewer_id === user?.id);
  const reviewKind = isBrand ? "brand_to_influencer" : "influencer_to_brand";

  const openChat = async () => {
    try {
      const { data } = await api.post("/conversations", { context_type: "deal", context_id: id });
      const dest = `${isBrand ? "/brand" : "/influencer"}/messages?conversation_id=${data.conversation.id}`;
      navigate(dest);
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6" data-testid="campaign-report">
        <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-secondary" data-testid="report-back">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>

        {/* Hero */}
        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="px-6 py-5 border-b border-border bg-accent/40 flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 min-w-0">
              <div className="h-12 w-12 rounded-xl bg-primary text-primary-foreground flex items-center justify-center">
                <Trophy className="h-6 w-6" />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">BrandKrt · Campaign Completion Report</div>
                <h2 className="text-xl font-display text-primary dark:text-white truncate">{campaign?.title || "Campaign"}</h2>
                <div className="text-xs text-muted-foreground">Ref: {deal.id}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusChip value={deal.status} />
              <span className="text-xs text-muted-foreground">Completion {completion_pct}%</span>
            </div>
          </div>

          <div className="p-6 grid gap-6 md:grid-cols-2">
            <Party icon={ShieldCheck} role="Brand" name={brand?.company_name || "—"} subtitle={brand?.industry || ""} verified={brand?.verification_status === "approved"} />
            <Party icon={BadgeCheck} role="Creator" name={influencer?.username || "—"} subtitle={influencer?.category || ""} verified={influencer?.verification_status === "approved"} />
          </div>

          {/* Progress bar */}
          <div className="px-6 pb-6">
            <div className="h-2 rounded-full bg-accent overflow-hidden">
              <div className="h-full bg-secondary transition-all" style={{ width: `${completion_pct}%` }} />
            </div>
          </div>
        </div>

        {/* Performance */}
        <Section title="Performance" icon={TrendingUp}>
          {(metrics?.total_views || metrics?.reach || metrics?.engagement_total) ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Kpi label="Total views" value={Number(metrics.total_views || 0).toLocaleString()} icon={Eye} />
              <Kpi label="Reach" value={Number(metrics.reach || 0).toLocaleString()} icon={Eye} />
              <Kpi label="Engagement" value={Number(metrics.engagement_total || 0).toLocaleString()} icon={Heart} />
              <Kpi label="Engagement rate" value={`${metrics.engagement_rate || 0}%`} icon={Heart} />
              <Kpi label="Clicks" value={Number(metrics.clicks || 0).toLocaleString()} icon={MousePointer2} />
              <Kpi label="CTR" value={`${metrics.ctr || 0}%`} icon={MousePointer2} />
              <Kpi label="Estimated sales" value={`₹${Number(metrics.estimated_sales || 0).toLocaleString()}`} icon={IndianRupee} />
              <Kpi label="ROI" value={`${metrics.roi_x || 0}×`} icon={TrendingUp} hint={`${metrics.roi_pct || 0}% net`} />
            </div>
          ) : (
            <EmptyState
              icon={Sparkles}
              title="Performance not reported yet"
              description={isInfluencer
                ? "Add your insights numbers from the deal to unlock the full report."
                : "Awaiting the creator to submit performance numbers."}
              action={isInfluencer && (
                <Link to={`/deals/${id}/metrics`} className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold">
                  <Pencil className="h-4 w-4" /> Report metrics
                </Link>
              )}
              testId="report-perf-empty"
            />
          )}
        </Section>

        {/* Reach breakdown */}
        {metrics && (metrics.instagram_reel_views || metrics.youtube_views || metrics.facebook_views) > 0 && (
          <Section title="Reach by platform" icon={Eye}>
            <div className="grid grid-cols-3 gap-3">
              <PlatformPill label="Instagram Reel Views" value={metrics.instagram_reel_views} />
              <PlatformPill label="YouTube Views" value={metrics.youtube_views} />
              <PlatformPill label="Facebook Views" value={metrics.facebook_views} />
              <PlatformPill label="Likes" value={metrics.likes} />
              <PlatformPill label="Comments" value={metrics.comments} />
              <PlatformPill label="Shares" value={metrics.shares} />
              <PlatformPill label="Saves" value={metrics.saves} />
            </div>
          </Section>
        )}

        {/* Deliverables */}
        {(campaign?.deliverables?.length > 0 || deal.deliverables_links) && (
          <Section title="Deliverables" icon={CheckCircle2}>
            {campaign?.deliverables?.length > 0 && (
              <ol className="list-decimal list-inside space-y-1 text-sm">
                {campaign.deliverables.map((d, i) => <li key={i}>{d}</li>)}
              </ol>
            )}
            {deal.deliverables_links && (
              <div className="mt-3 grid sm:grid-cols-2 gap-2 text-sm">
                {Object.entries(deal.deliverables_links).filter(([_, v]) => v).map(([k, v]) => (
                  <a key={k} href={v} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-xl border border-border bg-background p-3 hover:bg-accent">
                    <span className="text-[10px] uppercase tracking-wider text-secondary w-32 shrink-0">{k.replace(/_/g, " ")}</span>
                    <span className="truncate text-xs">{String(v)}</span>
                  </a>
                ))}
              </div>
            )}
          </Section>
        )}

        {/* Payment & Escrow */}
        <Section title="Payment summary" icon={IndianRupee}>
          {payment ? (
            <div className="grid sm:grid-cols-3 gap-3 text-sm">
              <PaySlot label="Gross amount" value={`₹${Number(payment.amount || 0).toLocaleString()}`} />
              <PaySlot label="Platform fee" value={`₹${Number(payment.platform_fee || 0).toLocaleString()}`} />
              <PaySlot label="Creator earning" value={`₹${Number(payment.influencer_earning || 0).toLocaleString()}`} highlight />
              <PaySlot label="Escrow status" value={(payment.release_status || payment.status || "—")} chip />
              <PaySlot label="Transaction id" value={payment.transaction_id || "—"} mono />
              <PaySlot label="Funded at" value={payment.created_at ? new Date(payment.created_at).toLocaleString() : "—"} />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Escrow not funded for this deal.</p>
          )}
        </Section>

        {/* Timeline */}
        {history?.length > 0 && (
          <Section title="Timeline" icon={Calendar}>
            <ol className="space-y-2 text-sm">
              {history.slice().reverse().map((h, i) => (
                <li key={i} className="flex items-center justify-between gap-2 border-b border-border pb-2 last:border-b-0">
                  <div className="flex items-center gap-2">
                    <StatusChip value={h.status} />
                    <span className="text-muted-foreground capitalize text-xs">by {h.role || "—"}</span>
                  </div>
                  <span className="text-muted-foreground text-xs">{h.at ? new Date(h.at).toLocaleString() : ""}</span>
                </li>
              ))}
            </ol>
          </Section>
        )}

        {/* Reviews exchanged */}
        <Section title="Review summary" icon={ScrollText}>
          {reviews?.length > 0 ? (
            <ReviewList reviews={reviews} />
          ) : (
            <p className="text-sm text-muted-foreground">No reviews exchanged on this deal yet.</p>
          )}
        </Section>

        {/* Action bar */}
        <div className="rounded-2xl border border-border bg-card p-5 flex flex-wrap items-center justify-end gap-2 sticky bottom-2">
          {payment && (
            <button
              type="button"
              onClick={openChat}
              data-testid="report-chat"
              className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-4 py-2 text-sm font-semibold"
            >
              <MessageCircle className="h-4 w-4" /> Open chat
            </button>
          )}
          {partnerUserId && (
            <button
              type="button"
              onClick={() => setShowReview((s) => !s)}
              data-testid="report-toggle-review"
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold"
            >
              <Send className="h-4 w-4" /> {myExistingReview ? "Update my review" : `Review ${partnerName}`}
            </button>
          )}
        </div>

        {showReview && partnerUserId && (
          <Section title={`Review ${partnerName}`} icon={Pencil}>
            <ReviewForm
              targetUserId={partnerUserId}
              dealId={id}
              kind={reviewKind}
              existing={myExistingReview}
              onSubmitted={() => { setShowReview(false); load(); }}
            />
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6" data-testid={`report-section-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-secondary flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5" />} {title}
      </h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Party({ icon: Icon, role, name, subtitle, verified }) {
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-secondary">
        <Icon className="h-3.5 w-3.5" /> {role}
      </div>
      <div className="mt-1 flex items-center gap-2">
        <div className="text-lg font-semibold text-primary dark:text-white truncate">{name}</div>
        {verified && <BadgeCheck className="h-4 w-4 text-secondary" />}
      </div>
      <div className="text-xs text-muted-foreground truncate">{subtitle || "—"}</div>
    </div>
  );
}

function Kpi({ icon: Icon, label, value, hint }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
        {Icon && <Icon className="h-3.5 w-3.5 text-secondary" />}
      </div>
      <div className="mt-1 text-lg font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="text-[10px] text-muted-foreground">{hint}</div>}
    </div>
  );
}

function PaySlot({ label, value, highlight, chip, mono }) {
  return (
    <div className={`rounded-xl border ${highlight ? "border-secondary/40 bg-accent" : "border-border bg-background"} p-3`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`mt-1 text-sm font-semibold text-primary dark:text-white ${mono ? "font-mono text-xs" : ""}`}>
        {chip ? <StatusChip value={value} /> : value}
      </div>
    </div>
  );
}

function PlatformPill({ label, value }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-base font-semibold text-primary dark:text-white">{Number(value || 0).toLocaleString()}</div>
    </div>
  );
}
