import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, IndianRupee, Calendar, Tag, Globe2, Loader2, Save, Upload, ExternalLink,
  Instagram, Youtube, Facebook, Image as ImageIcon, FileText, Send,
  CheckCircle2, Truck, Package, Pencil, Eye, ThumbsUp, ThumbsDown,
  CalendarDays, Sparkles, X as XIcon, Trophy, MessageCircle, Lock as LockIcon,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StatusChip } from "@/components/State";
import { useAuth } from "@/context/AuthContext";
import DealTimeline, { DealProgressBar, PIPELINE, canonicalStatus } from "@/components/DealTimeline";
import EscrowSummary from "@/components/EscrowSummary";

// role-based transitions for the linear pipeline
function nextActions(status, role) {
  const s = canonicalStatus(status);
  const M = {
    offer_sent: {
      influencer: [
        { to: "offer_accepted", label: "Accept offer",   icon: CheckCircle2, tone: "primary" },
        { to: "cancelled",      label: "Decline",        icon: ThumbsDown,   tone: "ghost", confirm: "Decline this campaign offer?" },
      ],
      brand: [],
    },
    offer_accepted: {
      brand: [
        { to: "product_shipped", label: "Mark product shipped", icon: Truck, tone: "primary" },
        { to: "cancelled",       label: "Cancel deal",          icon: XIcon, tone: "ghost", confirm: "Cancel this deal?" },
      ],
      influencer: [],
    },
    product_shipped: {
      influencer: [{ to: "product_received", label: "Confirm received", icon: Package, tone: "primary" }],
      brand: [],
    },
    product_received: {
      influencer: [{ to: "content_in_progress", label: "Start working on content", icon: Pencil, tone: "primary" }],
      brand: [],
    },
    content_in_progress: {
      influencer: [{ to: "content_submitted", label: "Submit content for review", icon: Send, tone: "primary" }],
      brand: [],
    },
    content_submitted: {
      brand: [
        { to: "brand_review",        label: "Start review",     icon: Eye,       tone: "primary" },
        { to: "content_in_progress", label: "Request changes",  icon: Pencil,    tone: "ghost" },
      ],
      influencer: [],
    },
    brand_review: {
      brand: [
        { to: "approved",            label: "Approve content",  icon: ThumbsUp,  tone: "primary" },
        { to: "content_in_progress", label: "Request changes",  icon: Pencil,    tone: "ghost" },
      ],
      influencer: [],
    },
    approved: {
      influencer: [{ to: "scheduled", label: "Mark scheduled", icon: CalendarDays, tone: "primary" }],
      brand: [],
    },
    scheduled: {
      influencer: [{ to: "published", label: "Mark published", icon: Sparkles, tone: "primary" }],
      brand: [],
    },
    published: {
      brand: [{ to: "completed", label: "Mark complete & finalize", icon: Trophy, tone: "primary" }],
      influencer: [],
    },
  };
  return M[s]?.[role] || [];
}

const DELIVERABLE_FIELDS = [
  { key: "instagram_reel",   label: "Instagram Reel",   icon: Instagram, placeholder: "https://www.instagram.com/reel/…" },
  { key: "youtube_video",    label: "YouTube Video",    icon: Youtube,   placeholder: "https://www.youtube.com/watch?v=…" },
  { key: "facebook_post",    label: "Facebook Post",    icon: Facebook,  placeholder: "https://www.facebook.com/yourpage/posts/…" },
  { key: "instagram_story",  label: "Instagram Story",  icon: Instagram, placeholder: "https://www.instagram.com/stories/…" },
];

const RAZORPAY_CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpayCheckout() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${RAZORPAY_CHECKOUT_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", resolve, { once: true });
      existing.addEventListener("error", reject, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = RAZORPAY_CHECKOUT_SRC;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Could not load Razorpay Checkout"));
    document.body.appendChild(script);
  });
}

export default function DealDetails() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const isBrand = user?.role === "brand" || user?.role === "admin";
  const isInfluencer = user?.role === "influencer";
  const role = isBrand ? "brand" : "influencer";

  const [deal, setDeal] = useState(null);
  const [campaign, setCampaign] = useState(null);
  const [payment, setPayment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // deliverable form state (influencer edits, brand reads)
  const [links, setLinks] = useState({ instagram_reel: "", youtube_video: "", facebook_post: "", instagram_story: "", screenshot_url: "", notes: "" });
  const [savingLinks, setSavingLinks] = useState(false);
  const [actionNote, setActionNote] = useState("");
  const screenshotRef = useRef(null);
  const [uploadingShot, setUploadingShot] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [d, p, a] = await Promise.all([
        api.get("/deals"),
        api.get("/payments"),
        api.get("/agreements").catch(() => ({ data: { agreements: [] } })),
      ]);
      const found = (d.data.deals || []).find((x) => x.id === id);
      if (!found) {
        toast.error("Deal not found or you don't have access.");
        navigate(isBrand ? "/brand/campaigns" : "/influencer/campaigns");
        return;
      }
      setDeal(found);
      setLinks({
        instagram_reel:   found.deliverables_links?.instagram_reel || "",
        youtube_video:    found.deliverables_links?.youtube_video || "",
        facebook_post:    found.deliverables_links?.facebook_post || "",
        instagram_story:  found.deliverables_links?.instagram_story || "",
        screenshot_url:   found.deliverables_links?.screenshot_url || "",
        notes:            found.deliverables_links?.notes || "",
      });
      const payments = p.data.payments || [];
      const agreements = a.data.agreements || [];
      const linkedAgreement = agreements.find((ag) => (
        ag.campaign_id && ag.campaign_id === found.campaign_id
      ) || (
        Number(ag.payment_amount || 0) === Number(found.amount || 0) && !ag.campaign_id
      ));
      const myPay = payments.find((pp) => pp.deal_id === id)
        || (found.escrow_payment_id ? payments.find((pp) => pp.id === found.escrow_payment_id) : null)
        || (linkedAgreement ? payments.find((pp) => pp.agreement_id === linkedAgreement.id) : null)
        || null;
      setPayment(myPay);
      if (found.campaign_id) {
        try {
          const c = await api.get(`/campaigns/${found.campaign_id}`);
          setCampaign(c.data.campaign);
        } catch (_) { /* no access */ }
      }
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [id]);

  const isEscrowFunded = Boolean(payment && (
    payment.status === "escrowed"
    || payment.status === "released"
    || ["held", "release_requested", "released"].includes(payment.release_status)
  ));
  const actions = useMemo(() => {
    if (!deal) return [];
    const raw = nextActions(deal.status, role);
    if (canonicalStatus(deal.status) === "offer_accepted" && isBrand && !isEscrowFunded) {
      return raw.filter((a) => a.to === "cancelled");
    }
    return raw;
  }, [deal, role, isBrand, isEscrowFunded]);

  const setStatus = async (to, confirmText) => {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(true);
    try {
      const payload = { status: to };
      if (actionNote.trim()) payload.note = actionNote.trim();
      if (to === "content_submitted" && isInfluencer) {
        payload.deliverables = Object.fromEntries(
          Object.entries(links).map(([k, v]) => [k, v?.trim() || null])
        );
      }
      const { data } = await api.patch(`/deals/${id}/status`, payload);
      if (data.deal) setDeal(data.deal); else setDeal((d) => ({ ...d, status: to }));
      setActionNote("");
      toast.success(`Status updated → ${to.replace(/_/g, " ")}`);
      await load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  const saveDeliverables = async () => {
    if (!isInfluencer) return;
    setSavingLinks(true);
    try {
      const cleaned = Object.fromEntries(Object.entries(links).map(([k, v]) => [k, v?.trim() || null]));
      const { data } = await api.patch(`/deals/${id}/status`, {
        status: deal.status,
        deliverables: cleaned,
      });
      if (data.deal) setDeal(data.deal);
      toast.success("Deliverables saved.");
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setSavingLinks(false);
  };

  const uploadScreenshot = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingShot(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/uploads/products", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const url = data.url;
      setLinks((l) => ({ ...l, screenshot_url: url }));
      toast.success("Screenshot uploaded. Don't forget to save deliverables.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setUploadingShot(false);
      e.target.value = "";
    }
  };

  const fundEscrow = async () => {
    if (!isBrand) return;
    setBusy(true);
    try {
      const { data } = await api.post("/payments/escrow", { deal_id: id, amount: Number(deal.amount) || 0 });
      const createdPayment = data.payment || null;
      const checkout = createdPayment?.checkout;
      if (checkout?.provider === "razorpay") {
        await loadRazorpayCheckout();
        await new Promise((resolve, reject) => {
          const rzp = new window.Razorpay({
            key: checkout.key_id,
            amount: checkout.amount,
            currency: checkout.currency || "INR",
            name: "BrandKrt",
            description: campaign?.title ? `Escrow for ${campaign.title}` : "BrandKrt escrow payment",
            image: `${window.location.origin}/assets/brandkrt-logo-original.jpeg`,
            order_id: checkout.order_id,
            prefill: {
              name: user?.name || "",
              email: user?.email || "",
              contact: user?.phone || "",
            },
            notes: { deal_id: id, payment_id: createdPayment.id },
            theme: { color: "#061b46" },
            handler: async (response) => {
              try {
                const verified = await api.post("/payments/razorpay/verify", {
                  payment_id: createdPayment.id,
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature,
                });
                setPayment(verified.data.payment || null);
                toast.success("Escrow funded. Messaging is now unlocked.");
                resolve();
              } catch (err) {
                reject(err);
              }
            },
            modal: {
              ondismiss: () => reject(new Error("Payment cancelled before completion.")),
            },
          });
          rzp.on("payment.failed", (response) => {
            reject(new Error(response?.error?.description || "Razorpay payment failed."));
          });
          rzp.open();
        });
      } else {
        setPayment(createdPayment);
        toast.success("Escrow funded. Messaging is now unlocked.");
      }
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  const releasePayment = async () => {
    if (!isBrand || !payment) return;
    if (!window.confirm("Release escrowed funds to the creator now?")) return;
    setBusy(true);
    try {
      await api.post(`/payments/${payment.id}/release`);
      toast.success("Payment released.");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  if (loading) return <div className="text-muted-foreground">Loading…</div>;
  if (!deal) return null;

  const backTo = isBrand ? "/brand/campaigns" : "/influencer/campaigns";
  const canon = canonicalStatus(deal.status);
  const isClosed = canon === "completed" || canon === "cancelled";

  return (
    <div className="space-y-8" data-testid="deal-details">
      <div>
        <button onClick={() => navigate(backTo)} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-secondary" data-testid="back-link">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
      </div>

      {/* Hero */}
      <div className="rounded-2xl border border-border bg-card p-6 md:p-8">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-3xl font-display font-light text-primary dark:text-white truncate">
                {campaign?.title || "Campaign deal"}
              </h2>
              <StatusChip value={deal.status} />
            </div>
            <p className="text-sm text-muted-foreground mt-1 capitalize">
              {campaign?.platform || "—"} · {campaign?.content_type || "Content"} · ₹{Number(deal.amount || 0).toLocaleString()}
            </p>
            <div className="mt-4 max-w-2xl">
              <DealProgressBar status={deal.status} />
            </div>
          </div>
          {campaign && (
            <Link
              to={isBrand ? `/brand/campaigns/${campaign.id}` : "#"}
              className={`inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-4 py-2 text-sm font-semibold whitespace-nowrap ${!isBrand ? "pointer-events-none opacity-60" : ""}`}
              data-testid="open-campaign-link"
            >
              <ExternalLink className="h-4 w-4" /> View campaign brief
            </Link>
          )}
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <Fact icon={IndianRupee} label="Payout amount" value={`₹${Number(deal.amount || 0).toLocaleString()}`} />
          <Fact icon={Calendar} label="Deadline" value={campaign?.deadline || "—"} />
          <Fact icon={Tag} label="Content type" value={campaign?.content_type || "—"} />
          <Fact icon={Globe2} label="Language" value={campaign?.preferred_language || "—"} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column — Timeline + Deliverables */}
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-2xl border border-border bg-card p-6">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Lifecycle</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Twelve-step Brand ↔ Creator pipeline. Status updates notify the other side automatically.</p>
            <div className="mt-5">
              <DealTimeline
                status={deal.status}
                actions={actions}
                busy={busy}
                onAction={(action) => setStatus(action.to, action.confirm)}
              />
            </div>
          </div>

          {/* Deliverables — influencer edit, brand read-only */}
          <div className="rounded-2xl border border-border bg-card p-6" data-testid="deliverables-section">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-primary dark:text-white">Deliverables &amp; proof of work</h3>
              {isInfluencer && (
                <button
                  type="button"
                  onClick={saveDeliverables}
                  disabled={savingLinks}
                  data-testid="save-deliverables"
                  className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-xs font-semibold disabled:opacity-60"
                >
                  {savingLinks ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  Save deliverables
                </button>
              )}
            </div>

            <div className="mt-4 grid sm:grid-cols-2 gap-3">
              {DELIVERABLE_FIELDS.map((f) => (
                <DeliverableField
                  key={f.key}
                  icon={f.icon}
                  label={f.label}
                  value={links[f.key]}
                  placeholder={f.placeholder}
                  editable={isInfluencer && !isClosed}
                  onChange={(v) => setLinks((l) => ({ ...l, [f.key]: v }))}
                  testId={`deliv-${f.key}`}
                />
              ))}

              {/* Screenshot upload */}
              <div className="rounded-xl border border-border bg-background p-3 sm:col-span-2" data-testid="deliv-screenshot">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <ImageIcon className="h-3.5 w-3.5 text-secondary" /> Screenshot proof
                </div>
                {links.screenshot_url ? (
                  <div className="mt-3 flex items-center gap-3">
                    <a href={links.screenshot_url} target="_blank" rel="noreferrer" className="block h-20 w-20 rounded-lg overflow-hidden border border-border">
                      <img src={links.screenshot_url} alt="Screenshot proof" className="h-full w-full object-cover" />
                    </a>
                    <div className="flex-1 min-w-0 text-xs text-muted-foreground break-all">{links.screenshot_url.split("/").pop()}</div>
                    {isInfluencer && !isClosed && (
                      <button type="button" onClick={() => setLinks((l) => ({ ...l, screenshot_url: "" }))} className="text-xs font-semibold text-muted-foreground hover:text-destructive">
                        Remove
                      </button>
                    )}
                  </div>
                ) : isInfluencer && !isClosed ? (
                  <>
                    <button
                      type="button"
                      onClick={() => screenshotRef.current?.click()}
                      data-testid="upload-screenshot"
                      className="mt-2 inline-flex items-center gap-2 rounded-full border border-dashed border-border px-4 py-2 text-xs font-semibold hover:bg-accent"
                    >
                      {uploadingShot ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                      {uploadingShot ? "Uploading…" : "Upload screenshot"}
                    </button>
                    <input ref={screenshotRef} type="file" accept="image/*" onChange={uploadScreenshot} className="hidden" />
                  </>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">No screenshot uploaded yet.</p>
                )}
              </div>

              <div className="sm:col-span-2 rounded-xl border border-border bg-background p-3" data-testid="deliv-notes">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <FileText className="h-3.5 w-3.5 text-secondary" /> Additional notes
                </div>
                {isInfluencer && !isClosed ? (
                  <Textarea rows={3} value={links.notes} onChange={(e) => setLinks((l) => ({ ...l, notes: e.target.value }))}
                    placeholder="Share post timing, hashtags used, any context the brand should know." className="mt-2" />
                ) : (
                  <p className="mt-2 text-sm text-foreground/90 whitespace-pre-line min-h-[1.5rem]">{links.notes || "—"}</p>
                )}
              </div>
            </div>
          </div>

          {/* Status history */}
          {deal.status_history?.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6" data-testid="status-history">
              <h3 className="text-sm font-semibold text-primary dark:text-white">Status history</h3>
              <ol className="mt-3 space-y-2 text-xs">
                {[...deal.status_history].reverse().slice(0, 12).map((h, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 border-b border-border pb-2 last:border-b-0 last:pb-0">
                    <span className="inline-flex items-center gap-2">
                      <StatusChip value={h.status} />
                      <span className="text-muted-foreground capitalize">by {h.role || "—"}</span>
                    </span>
                    <span className="text-muted-foreground">{h.at ? new Date(h.at).toLocaleString() : ""}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {/* Right column — Actions + Escrow + Brief + Messaging hint */}
        <div className="space-y-6">
          <div className="rounded-2xl border border-border bg-card p-6" data-testid="next-action">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Next action</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {actions.length > 0
                ? `You can move this deal forward. Status changes notify the other side instantly.`
                : canonicalStatus(deal.status) === "offer_accepted" && isBrand && !isEscrowFunded
                  ? "Fund escrow before shipping product or starting work."
                : isClosed
                  ? "This deal is closed. No further actions are required."
                  : "Waiting on the other party to take the next step."}
            </p>

            {actions.length > 0 && (
              <Textarea
                rows={2}
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                placeholder="Optional message to send with this status change…"
                className="mt-3"
                data-testid="action-note"
              />
            )}

            <div className="mt-3 flex flex-col gap-2">
              {actions.map((a) => (
                <button
                  key={a.to}
                  type="button"
                  onClick={() => setStatus(a.to, a.confirm)}
                  disabled={busy}
                  data-testid={`action-${a.to}`}
                  className={`w-full inline-flex items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold disabled:opacity-60 ${
                    a.tone === "primary" ? "bg-primary text-primary-foreground hover:bg-primary/90" : "border border-border hover:bg-accent"
                  }`}
                >
                  <a.icon className="h-4 w-4" /> {a.label}
                </button>
              ))}
            </div>
          </div>

          <EscrowSummary
            payment={payment}
            amount={deal.amount}
            role={role}
            onFund={isBrand ? fundEscrow : undefined}
            onRelease={undefined}
            busy={busy}
          />

          {/* Messaging hint */}
          <div className={`rounded-2xl border ${payment ? "border-secondary/40 bg-accent" : "border-border bg-card"} p-5`} data-testid="messaging-hint">
            <div className="flex items-center gap-2">
              {payment ? <MessageCircle className="h-4 w-4 text-secondary" /> : <LockIcon className="h-4 w-4 text-muted-foreground" />}
              <h3 className="text-sm font-semibold text-primary dark:text-white">In-app messaging</h3>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {payment
                ? "Escrow funded — you can now chat with the other party using the messaging APIs."
                : "Messaging unlocks the moment the brand funds escrow. This protects both sides."}
            </p>
          </div>

          {/* Brief summary */}
          {campaign && (
            <div className="rounded-2xl border border-border bg-card p-5">
              <h3 className="text-sm font-semibold text-primary dark:text-white">Campaign brief</h3>
              {campaign.description && <p className="mt-2 text-xs text-foreground/90 whitespace-pre-line line-clamp-6">{campaign.description}</p>}
              {campaign.deliverables?.length > 0 && (
                <ul className="mt-2 list-disc list-inside text-xs text-foreground/90 space-y-0.5">
                  {campaign.deliverables.slice(0, 5).map((d, i) => <li key={i}>{d}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Brand-only: read-only deliverable links recap (handy when scrolled past) */}
      {isBrand && (
        <div className="rounded-2xl border border-border bg-card p-6" data-testid="brand-deliverable-recap">
          <h3 className="text-sm font-semibold text-primary dark:text-white">Submitted by creator</h3>
          <div className="mt-3 grid sm:grid-cols-2 gap-2 text-sm">
            {DELIVERABLE_FIELDS.map((f) => {
              const v = links[f.key];
              return (
                <div key={f.key} className="flex items-center gap-2 rounded-xl border border-border p-3" data-testid={`brand-recap-${f.key}`}>
                  <f.icon className="h-4 w-4 text-secondary" />
                  <span className="text-xs font-semibold w-28 shrink-0">{f.label}</span>
                  {v
                    ? <a href={v} target="_blank" rel="noreferrer" className="text-secondary hover:underline truncate">{v}</a>
                    : <span className="text-muted-foreground text-xs">Pending</span>}
                </div>
              );
            })}
          </div>
          {!PIPELINE.find((s) => s.key === canon) && null}
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

function DeliverableField({ icon: Icon, label, value, placeholder, editable, onChange, testId }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3" data-testid={testId}>
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-secondary" /> {label}
      </div>
      {editable ? (
        <Input className="mt-2" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      ) : value ? (
        <a href={value} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-2 text-sm text-secondary hover:underline truncate max-w-full">
          <ExternalLink className="h-3.5 w-3.5" /> Open link
        </a>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">Pending</p>
      )}
    </div>
  );
}
