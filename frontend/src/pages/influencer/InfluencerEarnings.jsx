import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Wallet, Banknote, Clock, ArrowDownToLine, Loader2 } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { StatusChip, EmptyState } from "@/components/State";

function StatCard({ icon: Icon, label, value, hint, testId, tone = "default" }) {
  const toneCls = tone === "gold" ? "border-secondary/40 bg-accent" : "";
  return (
    <div className={`rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all ${toneCls}`} data-testid={testId}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-3xl font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const EMPTY_WD = { amount: "", method: "upi", upi: "", account_name: "", account_number: "", ifsc: "", bank_name: "" };

export default function InfluencerEarnings() {
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wd, setWd] = useState(EMPTY_WD);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [d, p, w, profileResult] = await Promise.all([
        api.get("/deals"),
        api.get("/payments"),
        api.get("/withdrawals/mine"),
        api.get("/influencers/me"),
      ]);
      setDeals(d.data.deals || []);
      setPayments(p.data.payments || []);
      setWithdrawals(w.data.requests || []);
      const profile = profileResult.data.influencer || {};
      setWd((current) => ({
        ...current,
        upi: current.upi || profile.upi || "",
        account_name: current.account_name || profile.bank_details?.account_name || "",
        account_number: current.account_number || profile.bank_details?.account_number || "",
        ifsc: current.ifsc || profile.bank_details?.ifsc || "",
        bank_name: current.bank_name || profile.bank_details?.bank_name || "",
      }));
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const dealIds = useMemo(() => new Set(deals.map((d) => d.id)), [deals]);
  const myPayments = useMemo(() => payments.filter((p) => dealIds.has(p.deal_id)), [payments, dealIds]);

  const released = useMemo(
    () => myPayments.filter((p) => (p.release_status === "released" || p.status === "released")),
    [myPayments],
  );
  const held = useMemo(
    () => myPayments.filter((p) => (p.release_status === "held" || p.status === "escrowed")),
    [myPayments],
  );

  const totalReleased = released.reduce((s, p) => s + (Number(p.influencer_earning) || 0), 0);
  const totalHeld = held.reduce((s, p) => s + (Number(p.influencer_earning) || 0), 0);

  const withdrawn = withdrawals
    .filter((w) => w.status === "approved" || w.status === "released")
    .reduce((s, w) => s + (Number(w.amount) || 0), 0);
  const wdPending = withdrawals
    .filter((w) => w.status === "pending")
    .reduce((s, w) => s + (Number(w.amount) || 0), 0);

  const available = Math.max(0, totalReleased - withdrawn - wdPending);

  const submit = async (e) => {
    e.preventDefault();
    const amount = Number(wd.amount);
    if (!amount || amount <= 0) { toast.error("Enter a valid withdrawal amount."); return; }
    if (amount > available) { toast.error(`You can withdraw up to ₹${available.toLocaleString()}.`); return; }
    setSubmitting(true);
    try {
      const details = wd.method === "upi"
        ? { upi: wd.upi }
        : { account_name: wd.account_name, account_number: wd.account_number, ifsc: wd.ifsc, bank_name: wd.bank_name };
      await api.post("/withdrawals", { amount, method: wd.method, details });
      toast.success("Withdrawal request submitted. We'll review it shortly.");
      setWd(EMPTY_WD);
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setSubmitting(false);
  };

  return (
    <div className="space-y-8" data-testid="influencer-earnings">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Earnings</h2>
        <p className="text-sm text-muted-foreground mt-1">Track every payout, see what&apos;s still in escrow, and request a withdrawal to your bank or UPI.</p>
      </div>

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Wallet} label="Available to withdraw" value={`₹${available.toLocaleString()}`} hint="Released minus pending withdrawals" testId="stat-available" tone="gold" />
        <StatCard icon={Banknote} label="Lifetime earnings" value={`₹${totalReleased.toLocaleString()}`} hint={`${released.length} released payments`} testId="stat-lifetime" />
        <StatCard icon={Clock} label="In escrow" value={`₹${totalHeld.toLocaleString()}`} hint="Awaiting release" testId="stat-escrow" />
        <StatCard icon={ArrowDownToLine} label="Withdrawn" value={`₹${withdrawn.toLocaleString()}`} hint={`${wdPending > 0 ? `₹${wdPending.toLocaleString()} pending` : "All settled"}`} testId="stat-withdrawn" />
      </div>

      {loading && <div className="text-muted-foreground">Loading…</div>}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Withdraw form */}
        <form onSubmit={submit} className="lg:col-span-1 rounded-2xl border border-border bg-card p-6 space-y-4" data-testid="withdraw-form">
          <div>
            <h3 className="text-base font-semibold text-primary dark:text-white">Request a payout</h3>
            <p className="text-xs text-muted-foreground mt-1">Funds are sent within 24–48 hours after admin review.</p>
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Amount (₹)</label>
            <Input type="number" min="1" max={available} value={wd.amount} onChange={(e) => setWd({ ...wd, amount: e.target.value })} className="mt-2" placeholder={available > 0 ? `Max ₹${available.toLocaleString()}` : "₹0"} data-testid="wd-amount" />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Method</label>
            <select value={wd.method} onChange={(e) => setWd({ ...wd, method: e.target.value })} data-testid="wd-method" className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
              <option value="upi">Saved UPI ID{wd.upi ? ` · ${wd.upi}` : ""}</option>
              <option value="bank">Saved bank account{wd.account_number ? ` · ••••${wd.account_number.slice(-4)}` : ""}</option>
            </select>
          </div>
          {wd.method === "upi" ? (
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">UPI ID</label>
              <Input value={wd.upi} onChange={(e) => setWd({ ...wd, upi: e.target.value })} placeholder="yourname@upi" className="mt-2" data-testid="wd-upi" />
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Account holder</label>
                <Input value={wd.account_name} onChange={(e) => setWd({ ...wd, account_name: e.target.value })} className="mt-2" data-testid="wd-acc-name" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Bank</label>
                  <Input value={wd.bank_name} onChange={(e) => setWd({ ...wd, bank_name: e.target.value })} className="mt-2" data-testid="wd-bank" />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">IFSC</label>
                  <Input value={wd.ifsc} onChange={(e) => setWd({ ...wd, ifsc: e.target.value })} className="mt-2" data-testid="wd-ifsc" />
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Account number</label>
                <Input value={wd.account_number} onChange={(e) => setWd({ ...wd, account_number: e.target.value })} className="mt-2" data-testid="wd-acc-num" />
              </div>
            </div>
          )}
          <button
            type="submit"
            disabled={submitting || available <= 0}
            data-testid="wd-submit"
            className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-3 text-sm font-semibold disabled:opacity-60"
          >
            {submitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Submitting…</> : <><ArrowDownToLine className="h-4 w-4" /> Request payout</>}
          </button>
          {available <= 0 && (
            <p className="text-xs text-muted-foreground">You&apos;ll be able to withdraw once a brand releases your first escrow payment.</p>
          )}
        </form>

        {/* Payment history */}
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6 space-y-4" data-testid="earnings-history">
          <h3 className="text-base font-semibold text-primary dark:text-white">Payments &amp; payouts</h3>

          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Campaign payments</div>
            <div className="mt-2 divide-y divide-border">
              {myPayments.length === 0 && (
                <EmptyState
                  icon={Banknote}
                  title="No payments yet"
                  description="Once a brand funds escrow for one of your campaigns it will appear here."
                  testId="earnings-no-payments"
                />
              )}
              {myPayments.map((p) => (
                <div key={p.id} className="py-3 flex items-center justify-between gap-3" data-testid={`payment-${p.id}`}>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-primary dark:text-white truncate">
                      ₹{Number(p.influencer_earning || 0).toLocaleString()} <span className="text-xs text-muted-foreground font-normal">net (gross ₹{Number(p.amount || 0).toLocaleString()}, fee ₹{Number(p.platform_fee || 0).toLocaleString()})</span>
                    </div>
                    <div className="text-xs text-muted-foreground truncate">TXN {p.transaction_id || p.id}</div>
                  </div>
                  <StatusChip value={p.release_status || p.status} />
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-border" />

          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Withdrawal requests</div>
            <div className="mt-2 divide-y divide-border">
              {withdrawals.length === 0 && (
                <p className="py-4 text-sm text-muted-foreground">No withdrawals yet.</p>
              )}
              {withdrawals.map((w) => (
                <div key={w.id} className="py-3 flex items-start justify-between gap-3" data-testid={`withdrawal-${w.id}`}>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-primary dark:text-white truncate">
                      ₹{Number(w.amount).toLocaleString()} via {w.method?.toUpperCase()}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {w.created_at ? new Date(w.created_at).toLocaleString() : ""}
                    </div>
                    {(w.payout_status || w.payout_id || w.manual_payout?.reference || w.manual_payout?.screenshot_url || w.manual_payout?.note) && (
                      <div className="mt-2 space-y-1 rounded-xl border border-border bg-accent/40 px-3 py-2 text-xs">
                        {w.payout_status && (
                          <div className="flex flex-wrap gap-1">
                            <span className="font-semibold text-muted-foreground">Payout status:</span>
                            <span className="capitalize text-foreground">{String(w.payout_status).replaceAll("_", " ")}</span>
                          </div>
                        )}
                        {w.payout_id && (
                          <div className="flex flex-wrap gap-1">
                            <span className="font-semibold text-muted-foreground">Payout ID:</span>
                            <span className="break-all text-foreground">{w.payout_id}</span>
                          </div>
                        )}
                        {w.manual_payout?.reference && (
                          <div className="flex flex-wrap gap-1">
                            <span className="font-semibold text-muted-foreground">Payment reference:</span>
                            <span className="break-all text-foreground">{w.manual_payout.reference}</span>
                          </div>
                        )}
                        {w.manual_payout?.note && (
                          <div className="flex flex-wrap gap-1">
                            <span className="font-semibold text-muted-foreground">Admin note:</span>
                            <span className="text-foreground">{w.manual_payout.note}</span>
                          </div>
                        )}
                        {w.manual_payout?.screenshot_url && (
                          <a href={w.manual_payout.screenshot_url} target="_blank" rel="noreferrer" className="inline-flex font-semibold text-secondary hover:underline">
                            View payment screenshot
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                  <StatusChip value={w.status} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
