import React from "react";
import { Wallet, ShieldCheck, Lock, CheckCircle2, IndianRupee } from "lucide-react";

/**
 * Escrow lifecycle visual:
 *   Pending → Funded → Locked → Released
 *
 * Props:
 *   payment   — payment object from /api/payments (or null if not yet funded)
 *   amount    — fallback amount (the deal.amount) when payment is null
 *   role      — "brand" | "influencer"
 *   onFund?   — () => void (brand-only)
 *   onRelease?— () => void (brand/admin-only)
 *   busy      — disables actions
 */
export default function EscrowSummary({ payment, amount = 0, role = "brand", onFund, onRelease, busy = false }) {
  const status = payment?.release_status || payment?.status || "pending";
  const stage = stageFromStatus(status);
  const stages = [
    { key: "pending", label: "Escrow Pending", description: "Brand needs to fund the escrow.", icon: Wallet, active: stage === "pending" },
    { key: "funded", label: "Escrow Funded", description: "Funds are safely held by BrandKrt.", icon: ShieldCheck, active: stage === "funded" },
    { key: "locked", label: "Work & Brand Review", description: "Messaging is unlocked. Creator can deliver work.", icon: Lock, active: stage === "locked" },
    { key: "release_requested", label: "Release Requested", description: "Brand approved the work. Admin releases payout next.", icon: ShieldCheck, active: stage === "release_requested" },
    { key: "released", label: "Payment Released", description: "Creator earnings paid out.", icon: CheckCircle2, active: stage === "released" },
  ];

  const gross = Number(payment?.amount ?? amount ?? 0);
  const fee = Number(payment?.platform_fee ?? (gross * 0.10).toFixed(2));
  const net = Number(payment?.influencer_earning ?? Math.max(0, gross - fee));

  return (
    <div className="rounded-2xl border border-border bg-card p-6" data-testid="escrow-summary">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-primary dark:text-white inline-flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-secondary" /> Escrow &amp; payout
        </h3>
        {payment?.transaction_id && <span className="text-[10px] font-mono text-muted-foreground">TXN {payment.transaction_id}</span>}
      </div>

      <div className="mt-4 grid gap-2">
        {stages.map((s, i) => {
          const done = stageOrder(s.key) < stageOrder(stage);
          const active = s.active;
          const tone =
            done ? "bg-secondary/15 border-secondary/40 text-secondary" :
            active ? "bg-accent border-secondary/40 text-primary dark:text-white" :
            "bg-card border-border text-muted-foreground";
          return (
            <div key={s.key} className={`flex items-center gap-3 rounded-xl border p-3 ${tone}`} data-testid={`escrow-stage-${s.key}`}>
              <div className={`h-8 w-8 rounded-full flex items-center justify-center ${
                done ? "bg-secondary text-secondary-foreground" :
                active ? "bg-primary text-primary-foreground" :
                "bg-background border border-border text-muted-foreground"
              }`}>
                <s.icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{s.label}</div>
                <div className="text-[11px] opacity-80">{s.description}</div>
              </div>
              {done && <span className="text-[10px] font-semibold uppercase tracking-wider text-success">Done</span>}
              {active && !done && <span className="text-[10px] font-semibold uppercase tracking-wider text-secondary">Now</span>}
              <span className="sr-only">step {i + 1}</span>
            </div>
          );
        })}
      </div>

      <div className="mt-5 grid grid-cols-3 gap-2">
        <Money label="Gross amount" value={gross} />
        <Money label="Platform fee (10%)" value={fee} tone="muted" />
        <Money label="Creator earnings" value={net} tone="gold" />
      </div>

      {role === "brand" && stage === "pending" && onFund && (
        <button
          type="button"
          onClick={onFund}
          disabled={busy}
          data-testid="escrow-fund"
          className="mt-5 w-full inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold disabled:opacity-60"
        >
          <ShieldCheck className="h-4 w-4" /> Fund escrow (₹{gross.toLocaleString()})
        </button>
      )}

      {role === "admin" && stage !== "released" && stage !== "pending" && onRelease && (
        <button
          type="button"
          onClick={onRelease}
          disabled={busy}
          data-testid="escrow-release"
          className="mt-5 w-full inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold disabled:opacity-60"
        >
          <CheckCircle2 className="h-4 w-4" /> Release payment to creator
        </button>
      )}

      {role === "influencer" && stage === "pending" && (
        <p className="mt-5 text-xs text-muted-foreground">Waiting for the brand to fund escrow. Messaging unlocks the moment escrow is funded.</p>
      )}
      {role === "influencer" && stage !== "pending" && stage !== "released" && (
        <p className="mt-5 text-xs text-muted-foreground">Funds are safely held by BrandKrt. Your earnings of INR {net.toLocaleString()} release after brand approval and admin payout.</p>
      )}
    </div>
  );
}

function Money({ label, value, tone = "default" }) {
  const cls = tone === "gold" ? "border-secondary/40 bg-accent" : tone === "muted" ? "" : "";
  return (
    <div className={`rounded-xl border border-border p-3 ${cls}`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-base font-display font-light text-primary dark:text-white inline-flex items-center gap-1">
        <IndianRupee className="h-3.5 w-3.5 text-secondary" /> {Number(value || 0).toLocaleString()}
      </div>
    </div>
  );
}

function stageFromStatus(s) {
  if (!s || s === "pending") return "pending";
  if (s === "released") return "released";
  if (s === "release_requested") return "release_requested";
  if (s === "escrowed" || s === "held") return "locked";
  return "locked";
}

function stageOrder(k) {
  return { pending: 0, funded: 1, locked: 2, release_requested: 3, released: 4 }[k] ?? 0;
}
