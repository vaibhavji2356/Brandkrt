import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, ScrollText, ShieldCheck, IndianRupee, CalendarDays, FileSignature,
  CheckCircle2, ThumbsDown, X as XIcon, Loader2, MessageCircle, AlertTriangle,
  CreditCard, Lock as LockIcon,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusChip } from "@/components/State";
import { useAuth } from "@/context/AuthContext";
import UserAvatar from "@/components/UserAvatar";

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

export default function AgreementDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [consent, setConsent] = useState(false);
  const [signatureName, setSignatureName] = useState("");
  const [payment, setPayment] = useState(null);

  const load = async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const [{ data }, paymentsResult] = await Promise.all([
        api.get(`/agreements/${id}`),
        api.get("/payments").catch(() => ({ data: { payments: [] } })),
      ]);
      const agreement = data.agreement;
      setDoc(agreement);
      setSignatureName(agreement?.influencer_signature_name || user?.name || "");
      const found = (paymentsResult.data.payments || []).find((p) => p.agreement_id === id) || null;
      setPayment(found);
    } catch (err) {
      if (!quiet) { toast.error(formatApiError(err)); navigate(-1); }
    }
    if (!quiet) setLoading(false);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    load();
    const timer = setInterval(() => load({ quiet: true }), 8000);
    const refresh = () => load({ quiet: true });
    window.addEventListener("focus", refresh);
    return () => { clearInterval(timer); window.removeEventListener("focus", refresh); };
  }, [id]);

  const isInfluencer = doc && user?.id === doc.influencer_user_id;
  const isBrand = doc && user?.id === doc.brand_user_id;
  const canSign = isInfluencer && doc.status === "pending_acceptance";
  const canCancel = doc && ["draft", "pending_acceptance", "accepted"].includes(doc.status) && (isBrand || isInfluencer);
  const accepted = doc?.status === "accepted" || doc?.status === "completed";
  const paymentFunded = ["escrowed", "released"].includes(payment?.status);
  const paymentPending = payment?.status === "pending";

  const accept = async () => {
    if (!consent) return toast.error("Please confirm digital consent before signing.");
    setBusy(true);
    try {
      const { data } = await api.post(`/agreements/${id}/accept`, { consent: true, signature_name: signatureName || user?.name });
      setDoc(data.agreement);
      toast.success("Agreement signed. Brand must fund escrow before chat starts.");
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  const reject = async () => {
    if (!window.confirm("Decline this agreement? The brand will be notified.")) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/agreements/${id}/reject`, { consent: false });
      setDoc(data.agreement);
      toast.success("Agreement declined.");
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  const cancel = async () => {
    if (!window.confirm("Cancel this agreement?")) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/agreements/${id}/cancel`);
      setDoc(data.agreement);
      toast.success("Agreement cancelled.");
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  const openChat = async () => {
    if (!paymentFunded) {
      toast.error("Chat unlocks after escrow payment.");
      return;
    }
    try {
      const { data } = await api.post("/conversations", { context_type: "agreement", context_id: id });
      const dest = (user?.role === "brand" ? "/brand" : "/influencer") + "/messages?conversation_id=" + data.conversation.id;
      navigate(dest);
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const fundEscrow = async () => {
    if (!isBrand) return toast.error("Only the brand can fund escrow.");
    setBusy(true);
    try {
      const { data } = await api.post(`/agreements/${id}/fund`);
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
            description: doc?.campaign ? `Escrow for ${doc.campaign}` : "BrandKrt agreement escrow",
            image: `${window.location.origin}/assets/brandkrt-logo-original.jpeg`,
            order_id: checkout.order_id,
            prefill: {
              name: user?.name || "",
              email: user?.email || "",
              contact: user?.phone || "",
            },
            notes: { agreement_id: id, payment_id: createdPayment.id },
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
                await load();
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
        await load();
        toast.success("Escrow funded. Messaging is now unlocked.");
      }
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>;
  if (!doc) return null;

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto p-4 md:p-8 space-y-6" data-testid="agreement-details">
        <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-secondary" data-testid="agreement-back">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>

        <AgreementFlow
          doc={doc}
          payment={payment}
          isBrand={isBrand}
          busy={busy}
          onFund={fundEscrow}
          onOpenChat={openChat}
        />

        {/* Document header */}
        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="px-6 py-5 border-b border-border bg-accent/40 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="h-10 w-10 rounded-xl bg-primary text-primary-foreground flex items-center justify-center">
                <ScrollText className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">BrandKrt · Digital Agreement</div>
                <div className="text-lg font-display text-primary dark:text-white truncate">
                  {doc.campaign || "Campaign agreement"}
                </div>
                <div className="text-xs text-muted-foreground">Ref: {doc.id}</div>
              </div>
            </div>
            <StatusChip value={doc.status} />
          </div>

          {/* Parties */}
          <div className="p-6 grid gap-6 md:grid-cols-2">
            <PartyCard role="Brand" name={doc.brand_name} avatar={doc.brand_avatar_url} signedAt={doc.brand_signed_at} signedBy={doc.brand_signature_name} />
            <PartyCard role="Influencer" name={doc.influencer_name} avatar={doc.influencer_avatar_url} signedAt={doc.influencer_signed_at} signedBy={doc.influencer_signature_name} />
          </div>

          {/* Body */}
          <div className="px-6 pb-6 space-y-5">
            <Section title="Campaign">
              <p className="text-sm">{doc.campaign || "—"}</p>
            </Section>

            <Section title="Deliverables">
              {doc.deliverables?.length > 0 ? (
                <ol className="list-decimal list-inside space-y-1 text-sm">
                  {doc.deliverables.map((d, i) => <li key={i}>{d}</li>)}
                </ol>
              ) : <p className="text-sm text-muted-foreground">No deliverables listed.</p>}
            </Section>

            <Section title="Timeline" icon={CalendarDays}>
              <p className="text-sm whitespace-pre-line">{doc.timeline || "—"}</p>
            </Section>

            <Section title="Payment" icon={IndianRupee}>
              <div className="grid sm:grid-cols-3 gap-3 text-sm">
                <Stat label="Agreed amount" value={`₹${Number(doc.payment_amount || 0).toLocaleString()}`} />
                <Stat label={`Platform fee (${doc.platform_fee_pct}%)`} value={`₹${Number(doc.platform_fee || 0).toLocaleString()}`} />
                <Stat label="Net to creator" value={`₹${Number(doc.net_to_influencer || 0).toLocaleString()}`} highlight />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Payment is held in escrow on the BrandKrt platform until the deliverables are approved per platform policy.
              </p>
            </Section>

            <Section title="Cancellation policy" icon={AlertTriangle}>
              <p className="text-sm whitespace-pre-line">{doc.cancellation_policy}</p>
            </Section>

            {doc.terms && (
              <Section title="Additional terms">
                <p className="text-sm whitespace-pre-line">{doc.terms}</p>
              </Section>
            )}

            <Section title="Acceptance & Digital Consent" icon={ShieldCheck}>
              {accepted ? (
                <div className="rounded-xl border border-success/30 bg-success/5 p-4 text-sm">
                  <div className="flex items-center gap-2 text-success font-semibold"><CheckCircle2 className="h-4 w-4" /> Signed</div>
                  <p className="mt-1 text-muted-foreground">
                    {doc.influencer_name} accepted on{" "}
                    {doc.influencer_signed_at ? new Date(doc.influencer_signed_at).toLocaleString() : ""}.
                  </p>
                </div>
              ) : canSign ? (
                <div className="rounded-xl border border-border bg-background p-4 space-y-3">
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Type your full name to sign</span>
                    <Input className="mt-1" value={signatureName} onChange={(e) => setSignatureName(e.target.value)} placeholder="Full legal name" data-testid="agreement-signature" />
                  </label>
                  <label className="flex items-start gap-2 text-sm">
                    <Checkbox checked={consent} onCheckedChange={(v) => setConsent(!!v)} data-testid="agreement-consent" />
                    <span>
                      I have read this agreement and provide my <strong>digital consent</strong> to be legally bound by its terms. I understand my electronic signature has the same effect as a handwritten signature under applicable law.
                    </span>
                  </label>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {doc.status === "rejected" ? "This agreement was declined by the creator."
                    : doc.status === "cancelled" ? "This agreement has been cancelled."
                    : "Waiting for the creator to review and sign this agreement."}
                </p>
              )}
            </Section>
          </div>

          {/* Action bar */}
          <div className="px-6 py-4 border-t border-border bg-card flex flex-wrap gap-2 justify-end">
            {accepted && (
              paymentFunded ? (
                <button
                  type="button"
                  onClick={openChat}
                  data-testid="agreement-open-chat"
                  className="inline-flex items-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-4 py-2 text-sm font-semibold"
                >
                  <MessageCircle className="h-4 w-4" /> Open chat
                </button>
              ) : (
                <button
                  type="button"
                  onClick={isBrand ? fundEscrow : undefined}
                  disabled={busy || !isBrand || paymentPending}
                  data-testid="agreement-fund-escrow"
                  className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold disabled:opacity-60"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : isBrand ? <CreditCard className="h-4 w-4" /> : <LockIcon className="h-4 w-4" />}
                  {isBrand ? (paymentPending ? "Payment pending" : "Fund escrow to unlock chat") : "Waiting for brand payment"}
                </button>
              )
            )}
            {canSign && (
              <>
                <button
                  type="button"
                  onClick={reject}
                  disabled={busy}
                  data-testid="agreement-reject"
                  className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-4 py-2 text-sm font-semibold disabled:opacity-60"
                >
                  <ThumbsDown className="h-4 w-4" /> Decline
                </button>
                <button
                  type="button"
                  onClick={accept}
                  disabled={busy || !consent || !signatureName.trim()}
                  data-testid="agreement-accept"
                  className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold disabled:opacity-60"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSignature className="h-4 w-4" />}
                  Sign & Accept
                </button>
              </>
            )}
            {canCancel && !canSign && (
              <button
                type="button"
                onClick={cancel}
                disabled={busy}
                data-testid="agreement-cancel"
                className="inline-flex items-center gap-2 rounded-full border border-destructive/40 text-destructive hover:bg-destructive/5 px-4 py-2 text-sm font-semibold disabled:opacity-60"
              >
                <XIcon className="h-4 w-4" /> Cancel agreement
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function AgreementFlow({ doc, payment, isBrand, busy, onFund, onOpenChat }) {
  const signed = doc?.status === "accepted" || doc?.status === "completed";
  const funded = ["escrowed", "released"].includes(payment?.status);
  const pending = payment?.status === "pending";
  const steps = [
    { label: "Agreement sent", done: true, active: !signed },
    { label: "Creator signs", done: signed, active: !signed },
    { label: "Brand funds escrow", done: funded, active: signed && !funded },
    { label: "Messaging unlocks", done: funded, active: funded },
    { label: "Work begins", done: false, active: funded },
  ];

  return (
    <div className="rounded-2xl border border-border bg-card p-4 md:p-5" data-testid="agreement-flow">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-secondary">Agreement flow</div>
          <h2 className="mt-1 text-lg font-semibold text-primary dark:text-white">
            {funded ? "Escrow funded. Chat is open." : signed ? "Next step: brand funds escrow" : "Waiting for creator signature"}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Chat starts only after the signed agreement has money safely held in escrow.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {signed && !funded && isBrand && (
            <button
              type="button"
              onClick={onFund}
              disabled={busy || pending}
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold disabled:opacity-60"
              data-testid="agreement-flow-fund"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
              {pending ? "Payment pending" : "Pay escrow now"}
            </button>
          )}
          {funded && (
            <button
              type="button"
              onClick={onOpenChat}
              className="inline-flex items-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-4 py-2 text-sm font-semibold"
            >
              <MessageCircle className="h-4 w-4" /> Open chat
            </button>
          )}
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-5">
        {steps.map((step, index) => (
          <div
            key={step.label}
            className={`rounded-xl border p-3 min-h-[88px] ${
              step.done
                ? "border-success/30 bg-success/5"
                : step.active
                  ? "border-secondary/50 bg-accent"
                  : "border-border bg-background"
            }`}
          >
            <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold ${
              step.done ? "bg-success text-white" : step.active ? "bg-secondary text-secondary-foreground" : "bg-muted text-muted-foreground"
            }`}>
              {step.done ? <CheckCircle2 className="h-4 w-4" /> : index + 1}
            </div>
            <div className="mt-2 text-sm font-semibold text-primary dark:text-white">{step.label}</div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              {step.done ? "Done" : step.active ? "Current step" : "Upcoming"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PartyCard({ role, name, avatar, signedAt, signedBy }) {
  const initials = (name || role).split(" ").map((part) => part[0]).join("").slice(0, 2);
  return (
    <div className="rounded-xl border border-border bg-background p-4 flex gap-3">
      <UserAvatar src={avatar} initials={initials} className="h-11 w-11 shrink-0 rounded-full" />
      <div className="min-w-0 flex-1">
      <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">{role}</div>
      <div className="text-lg font-semibold text-primary dark:text-white truncate">{name}</div>
      <div className="mt-2 text-xs text-muted-foreground">
        {signedAt
          ? <>Signed by <span className="font-semibold text-primary dark:text-white">{signedBy || name}</span> on {new Date(signedAt).toLocaleString()}</>
          : "Awaiting signature"}
      </div>
      </div>
    </div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-secondary flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5" />} {title}
      </h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Stat({ label, value, highlight }) {
  return (
    <div className={`rounded-xl border ${highlight ? "border-secondary/40 bg-accent" : "border-border bg-background"} p-3`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-base font-semibold text-primary dark:text-white">{value}</div>
    </div>
  );
}
