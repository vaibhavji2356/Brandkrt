import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Wallet, Banknote, Loader2 } from "lucide-react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { StatusChip, EmptyState } from "@/components/State";
import { formatApiError } from "@/lib/api";
import InfluencerAPI from "@/lib/influencerApi";

function StatCard({ label, value, icon: Icon, hint, testId }) {
  return (
    <div
      className="rounded-2xl border border-border bg-card p-5"
      data-testid={testId}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-2xl sm:text-3xl font-display font-light text-primary dark:text-white">
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

export default function InfluencerEarnings() {
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);

  // Withdrawal form
  const [open, setOpen] = useState(false);
  const [method, setMethod] = useState("upi");
  const [amount, setAmount] = useState("");
  const [upi, setUpi] = useState("");
  const [acc, setAcc] = useState("");
  const [ifsc, setIfsc] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [d, p, w] = await Promise.all([
        InfluencerAPI.listDeals().catch(() => []),
        InfluencerAPI.listPayments().catch(() => []),
        InfluencerAPI.myWithdrawals().catch(() => []),
      ]);
      setDeals(d);
      setPayments(p);
      setWithdrawals(w);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const dealIds = useMemo(() => new Set(deals.map((d) => d.id)), [deals]);
  const myPayments = useMemo(
    () => payments.filter((p) => dealIds.has(p.deal_id)),
    [payments, dealIds]
  );
  const totalReleased = myPayments
    .filter((p) => p.release_status === "released")
    .reduce((s, p) => s + (p.influencer_earning || 0), 0);
  const totalPending = myPayments
    .filter((p) => p.release_status !== "released")
    .reduce((s, p) => s + (p.influencer_earning || 0), 0);
  const requested = withdrawals
    .filter((w) => w.status === "pending" || w.status === "approved")
    .reduce((s, w) => s + (w.amount || 0), 0);
  const available = Math.max(0, totalReleased - requested);

  const chartData = useMemo(() => buildWeeklySeries(myPayments), [myPayments]);

  const submitWithdrawal = async () => {
    const amt = Number(amount);
    if (!amt || amt <= 0) {
      toast.error("Enter an amount greater than 0.");
      return;
    }
    if (amt > available) {
      toast.error("Amount exceeds your available balance.");
      return;
    }
    const details =
      method === "upi"
        ? { upi }
        : { account_number: acc, ifsc };
    if (method === "upi" && !upi) {
      toast.error("Please enter your UPI ID.");
      return;
    }
    if (method === "bank" && (!acc || !ifsc)) {
      toast.error("Please enter both account number and IFSC.");
      return;
    }
    setSubmitting(true);
    try {
      await InfluencerAPI.requestWithdrawal({ amount: amt, method, details });
      toast.success("Withdrawal request submitted.");
      setOpen(false);
      setAmount("");
      setUpi("");
      setAcc("");
      setIfsc("");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-8" data-testid="influencer-earnings-page">
      <div>
        <h2 className="text-2xl sm:text-3xl font-display font-light text-primary dark:text-white">
          Earnings
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Track payouts and request withdrawals to your UPI or bank account.
        </p>
      </div>

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Earned"
          value={`₹${totalReleased.toLocaleString()}`}
          icon={Wallet}
          hint="Released into your wallet"
          testId="earnings-stat-total"
        />
        <StatCard
          label="Pending"
          value={`₹${totalPending.toLocaleString()}`}
          icon={Loader2}
          hint="Held in escrow"
          testId="earnings-stat-pending"
        />
        <StatCard
          label="Requested"
          value={`₹${requested.toLocaleString()}`}
          icon={Banknote}
          hint="In-flight withdrawals"
          testId="earnings-stat-requested"
        />
        <StatCard
          label="Available"
          value={`₹${available.toLocaleString()}`}
          icon={Wallet}
          hint="Ready to withdraw"
          testId="earnings-stat-available"
        />
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h3 className="text-sm font-semibold text-primary dark:text-white">
          Earnings — last 12 weeks
        </h3>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <button
              type="button"
              data-testid="earnings-request-withdrawal"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold w-fit"
            >
              <Banknote className="h-4 w-4" /> Request withdrawal
            </button>
          </DialogTrigger>
          <DialogContent data-testid="withdrawal-dialog">
            <DialogHeader>
              <DialogTitle>Request a withdrawal</DialogTitle>
              <DialogDescription>
                Funds are paid out within 2 business days after admin review.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="text-xs text-muted-foreground">
                Available balance:{" "}
                <span className="font-semibold text-primary dark:text-white">
                  ₹{available.toLocaleString()}
                </span>
              </div>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Amount (₹)
                </span>
                <Input
                  type="number"
                  min={1}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  data-testid="withdrawal-amount"
                  className="mt-2"
                />
              </label>
              <div className="flex gap-2">
                {["upi", "bank"].map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMethod(m)}
                    data-testid={`withdrawal-method-${m}`}
                    className={`flex-1 rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-wider ${
                      method === m
                        ? "bg-primary text-primary-foreground"
                        : "border border-border text-foreground/70"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
              {method === "upi" ? (
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    UPI ID
                  </span>
                  <Input
                    value={upi}
                    onChange={(e) => setUpi(e.target.value)}
                    placeholder="yourhandle@upi"
                    data-testid="withdrawal-upi"
                    className="mt-2"
                  />
                </label>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      Account #
                    </span>
                    <Input
                      value={acc}
                      onChange={(e) => setAcc(e.target.value)}
                      data-testid="withdrawal-account"
                      className="mt-2"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      IFSC
                    </span>
                    <Input
                      value={ifsc}
                      onChange={(e) => setIfsc(e.target.value)}
                      data-testid="withdrawal-ifsc"
                      className="mt-2"
                    />
                  </label>
                </div>
              )}
            </div>
            <DialogFooter>
              <button
                onClick={() => setOpen(false)}
                className="rounded-full border border-border px-4 py-2 text-sm"
                data-testid="withdrawal-cancel"
              >
                Cancel
              </button>
              <button
                onClick={submitWithdrawal}
                disabled={submitting}
                data-testid="withdrawal-submit"
                className="rounded-full bg-primary text-primary-foreground px-5 py-2 text-sm font-semibold disabled:opacity-60 inline-flex items-center gap-2"
              >
                {submitting && <Loader2 className="h-3 w-3 animate-spin" />}
                Submit
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-2xl border border-border bg-card p-4 sm:p-6">
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                stroke="hsl(var(--muted-foreground))"
                fontSize={11}
              />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                }}
              />
              <Line
                type="monotone"
                dataKey="earnings"
                stroke="#D4AF37"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-card p-6">
          <h3 className="text-sm font-semibold text-primary dark:text-white">
            Payments
          </h3>
          {loading ? (
            <div className="mt-4 text-sm text-muted-foreground">Loading…</div>
          ) : myPayments.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                title="No payments yet"
                description="Payments will show up once a brand escrows funds for your deal."
                testId="payments-empty"
              />
            </div>
          ) : (
            <div className="mt-4 divide-y divide-border">
              {myPayments.map((p) => (
                <div
                  key={p.id}
                  className="py-3 flex items-center justify-between gap-3"
                  data-testid={`payment-row-${p.id}`}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-primary dark:text-white truncate">
                      ₹{Number(p.influencer_earning || 0).toLocaleString()}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      Tx {p.transaction_id || p.id.slice(-6)} · fee ₹
                      {Number(p.platform_fee || 0).toLocaleString()}
                    </div>
                  </div>
                  <StatusChip value={p.release_status || p.status} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-card p-6">
          <h3 className="text-sm font-semibold text-primary dark:text-white">
            Withdrawals
          </h3>
          {loading ? (
            <div className="mt-4 text-sm text-muted-foreground">Loading…</div>
          ) : withdrawals.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                title="No withdrawals yet"
                description="Use the button above to request your first payout."
                testId="withdrawals-empty"
              />
            </div>
          ) : (
            <div className="mt-4 divide-y divide-border">
              {withdrawals.map((w) => (
                <div
                  key={w.id}
                  className="py-3 flex items-center justify-between gap-3"
                  data-testid={`withdrawal-row-${w.id}`}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-primary dark:text-white truncate">
                      ₹{Number(w.amount || 0).toLocaleString()}
                    </div>
                    <div className="text-xs text-muted-foreground truncate capitalize">
                      {w.method} ·{" "}
                      {(w.created_at || "").slice(0, 10)}
                    </div>
                  </div>
                  <StatusChip value={w.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function buildWeeklySeries(payments) {
  const now = new Date();
  const buckets = [];
  for (let i = 11; i >= 0; i--) {
    const start = new Date(now);
    start.setDate(now.getDate() - (i + 1) * 7);
    const end = new Date(now);
    end.setDate(now.getDate() - i * 7);
    const label = `${start.toLocaleString("en", { month: "short" })} ${start.getDate()}`;
    const earnings = payments
      .filter((p) => {
        const t = new Date(p.created_at);
        return t >= start && t < end && p.release_status === "released";
      })
      .reduce((s, p) => s + (p.influencer_earning || 0), 0);
    buckets.push({ label, earnings });
  }
  return buckets;
}
