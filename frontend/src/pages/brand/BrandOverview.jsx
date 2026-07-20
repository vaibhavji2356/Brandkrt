import React, { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  Megaphone, CheckCircle2, ShieldCheck, Wallet, Clock, ArrowRight,
  Calendar, Activity, Sparkles, BadgeCheck, Loader2,
} from "lucide-react";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatusChip, EmptyState } from "@/components/State";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

function StatCard({ icon: Icon, label, value, hint, testId, tone = "default" }) {
  const cls = tone === "gold" ? "border-secondary/40 bg-accent" : "";
  return (
    <div className={`rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all ${cls}`} data-testid={testId}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-3xl font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const RUNNING_CAMPAIGN_STATUSES = new Set(["active", "draft"]);
const ACTIVE_DEAL_STATUSES = new Set([
  "offer_sent", "offer_accepted", "product_shipped", "promotion_pending", "promotion_live",
]);
const MAX_VERIFICATION_FILES = 4;

function daysUntil(iso) {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return Math.ceil((t - Date.now()) / (1000 * 60 * 60 * 24));
}

export default function BrandOverview({ verificationOnly = false }) {
  const { user } = useAuth();
  const [brand, setBrand] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [verificationRequests, setVerificationRequests] = useState([]);
  const [verificationOpen, setVerificationOpen] = useState(false);
  const [verificationFiles, setVerificationFiles] = useState({ business: [], ownerAadhaar: [], other: [] });
  const [verificationContact, setVerificationContact] = useState({ name: "", phone: "" });
  const [verificationNotes, setVerificationNotes] = useState("");
  const [startingVerification, setStartingVerification] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async ({ quiet = false } = {}) => {
    try {
      const [b, c, d, p, n, v] = await Promise.all([
        api.get("/brands/me"),
        api.get("/campaigns"),
        api.get("/deals"),
        api.get("/payments"),
        api.get("/notifications"),
        api.get("/verification/mine"),
      ]);
      const savedBrand = b.data?.brand || null;
      setBrand(savedBrand);
      setCampaigns(c.data.campaigns || []);
      setDeals(d.data.deals || []);
      setPayments(p.data.payments || []);
      setNotifications(n.data.notifications || []);
      setVerificationRequests(v.data.requests || []);
      setVerificationContact((current) => ({
        name: current.name || savedBrand?.owner_name || user?.name || "",
        phone: current.phone || savedBrand?.phone || user?.phone || "",
      }));
    } catch (err) {
      if (!quiet) toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(() => load({ quiet: true }), 8000);
    const onFocus = () => load({ quiet: true });
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(t);
      window.removeEventListener("focus", onFocus);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const campaignIds = useMemo(() => new Set(campaigns.map((c) => c.id)), [campaigns]);
  const myDeals = useMemo(() => deals.filter((d) => campaignIds.has(d.campaign_id) || d.brand_id === brand?.id), [deals, campaignIds, brand]);
  const dealIds = useMemo(() => new Set(myDeals.map((d) => d.id)), [myDeals]);
  const myPayments = useMemo(() => payments.filter((p) => dealIds.has(p.deal_id)), [payments, dealIds]);

  const running = campaigns.filter((c) => RUNNING_CAMPAIGN_STATUSES.has(c.status)).length;
  const completed = campaigns.filter((c) => c.status === "completed").length;
  const pendingRequests = myDeals.filter((d) => d.status === "offer_sent").length;
  const activeDeals = myDeals.filter((d) => ACTIVE_DEAL_STATUSES.has(d.status)).length;
  const totalSpend = myPayments.reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const monthStart = new Date(); monthStart.setDate(1); monthStart.setHours(0, 0, 0, 0);
  const monthlySpend = myPayments
    .filter((p) => p.created_at && new Date(p.created_at) >= monthStart)
    .reduce((s, p) => s + (Number(p.amount) || 0), 0);

  // Upcoming deadlines from campaigns with deadlines in next 30 days
  const upcoming = useMemo(() => (
    campaigns
      .map((c) => ({ ...c, _days: daysUntil(c.deadline) }))
      .filter((c) => c._days !== null && c._days >= -1 && c._days <= 30)
      .sort((a, b) => a._days - b._days)
      .slice(0, 5)
  ), [campaigns]);

  const recentDeals = myDeals.slice(0, 6);
  const recentNotifs = notifications.slice(0, 5);
  const latestVerification = verificationRequests.find((r) => r.kind === "brand");
  const verificationStatus = ["approved", "verified"].includes(brand?.verification_status)
    ? "verified"
    : latestVerification?.status || "not_started";
  const hasPendingVerification = verificationStatus === "pending";
  const isVerificationInProgress = verificationStatus === "in_progress";
  const callTime = latestVerification?.schedule_call_at;

  useEffect(() => {
    if (verificationOnly && !loading && verificationStatus === "not_started") setVerificationOpen(true);
  }, [verificationOnly, loading, verificationStatus]);

  const submitVerification = async () => {
    if (!brand) {
      toast.error("Please save your Business Profile before starting verification.");
      return;
    }
    if (verificationFiles.business.length === 0 || verificationFiles.ownerAadhaar.length === 0) {
      toast.error("Please upload business proof and owner Aadhaar card.");
      return;
    }
    if (!verificationContact.name.trim() || !verificationContact.phone.trim()) {
      toast.error("Please enter your contact name and WhatsApp phone number.");
      return;
    }

    setStartingVerification(true);
    try {
      const uploadDoc = async (file, type, label, index) => {
        if (!file) return null;
        const fd = new FormData();
        fd.append("file", file);
        const { data } = await api.post("/uploads/verification", fd, { headers: { "Content-Type": "multipart/form-data" } });
        return { type, label, url: data.url, name: file.name, index };
      };
      const uploadGroup = (files, type, label) => files.map((file, index) => uploadDoc(file, type, label, index + 1));
      const documents = (await Promise.all([
        ...uploadGroup(verificationFiles.business, "business_proof", "Business proof"),
        ...uploadGroup(verificationFiles.ownerAadhaar, "owner_aadhaar", "Owner Aadhaar card"),
        ...uploadGroup(verificationFiles.other, "supporting_document", "Supporting document"),
      ])).filter(Boolean);
      const { data } = await api.post("/verification", {
        kind: "brand",
        documents,
        contact_name: verificationContact.name.trim(),
        contact_phone: verificationContact.phone.trim(),
        notes: verificationNotes || "Brand submitted business verification documents from the dashboard.",
      });
      if (data.request) {
        setVerificationRequests((rows) => [data.request, ...rows.filter((row) => row.id !== data.request.id)]);
        setBrand((current) => current ? { ...current, verification_status: data.request.status || "pending" } : current);
      }
      setVerificationOpen(false);
      setVerificationFiles({ business: [], ownerAadhaar: [], other: [] });
      setVerificationContact({ name: "", phone: "" });
      setVerificationNotes("");
      toast.success(data.already_pending ? "Verification request is already pending." : "Verification request sent to admin.");
      load({ quiet: true });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setStartingVerification(false);
    }
  };

  const selectVerificationFiles = (key, list) => {
    const files = Array.from(list || []).slice(0, MAX_VERIFICATION_FILES);
    if ((list?.length || 0) > MAX_VERIFICATION_FILES) {
      toast.error(`Maximum ${MAX_VERIFICATION_FILES} files allowed for one section.`);
    }
    setVerificationFiles((current) => ({ ...current, [key]: files }));
  };

  if (loading) return <div className="text-muted-foreground">Loading…</div>;
  if (verificationOnly && verificationStatus === "verified") return <Navigate to="/brand" replace />;

  return (
    <div className="space-y-8" data-testid="brand-overview">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">
            Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""} <span className="gold-text font-semibold">✨</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Your brand HQ — campaigns, creators, spend and performance, all in one view.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/brand/discover" className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:bg-accent" data-testid="overview-discover">
            <Sparkles className="h-4 w-4" /> Discover creators
          </Link>
          <Link to="/brand/campaigns?new=1" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold" data-testid="overview-new-campaign">
            New campaign <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {!brand && (
        <div className="rounded-2xl border border-secondary/40 bg-accent p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-3" data-testid="brand-profile-banner">
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-secondary mt-0.5" />
            <div>
              <div className="font-semibold text-primary dark:text-white">Complete your Business Profile</div>
              <div className="text-sm text-muted-foreground">Add your business details and logo so creators trust your invites and our team can verify your account faster.</div>
            </div>
          </div>
          <Link to="/brand/profile" className="inline-flex items-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap">
            Set up profile <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}

      {brand && verificationStatus !== "verified" && (
        <div className="rounded-2xl border border-border bg-card p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4" data-testid="brand-verification-card">
          <div className="flex items-start gap-3">
            <BadgeCheck className="h-5 w-5 text-secondary mt-0.5" />
            <div>
              <div className="font-semibold text-primary dark:text-white">
                {verificationStatus === "verified" ? "You're a verified business" : isVerificationInProgress ? "Business verification in progress" : hasPendingVerification ? "Business verification pending" : "Verify your business"}
              </div>
              <div className="text-sm text-muted-foreground">
                {verificationStatus === "verified"
                  ? "Your brand has the verified badge. Creators can trust campaign invites from your team."
                  : isVerificationInProgress && callTime
                    ? `WhatsApp video call scheduled for ${new Date(callTime).toLocaleString()}.`
                    : isVerificationInProgress
                      ? "Admin is reviewing your documents. Your WhatsApp video call will be scheduled here."
                      : hasPendingVerification
                        ? "Your documents are waiting for admin review."
                        : "Upload business proof and owner Aadhaar for admin review."}
              </div>
            </div>
          </div>
          {verificationStatus === "verified" ? (
            <Link to="/brand/profile" className="inline-flex items-center gap-2 rounded-full border border-border bg-background hover:bg-accent px-4 py-2 text-sm font-semibold whitespace-nowrap">
              View profile <ArrowRight className="h-4 w-4" />
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => setVerificationOpen(true)}
              disabled={startingVerification || hasPendingVerification || isVerificationInProgress}
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed"
              data-testid="brand-start-verification-btn"
            >
              {startingVerification ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
              {isVerificationInProgress ? "In Progress" : hasPendingVerification ? "Request pending" : "Start Verification"}
            </button>
          )}
        </div>
      )}

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Megaphone} label="Running Campaigns" value={running} testId="stat-running" tone="gold" />
        <StatCard icon={CheckCircle2} label="Completed Campaigns" value={completed} testId="stat-completed" />
        <StatCard icon={Clock} label="Pending Requests" value={pendingRequests} hint={`${activeDeals} active deals`} testId="stat-pending-requests" />
        <StatCard icon={ShieldCheck} label="Verified Influencers" value={myDeals.filter((d) => d.influencer_id).length ? new Set(myDeals.map((d) => d.influencer_id)).size : 0} hint="Engaged with your campaigns" testId="stat-verified-inf" />
      </div>

      <div className="grid gap-4 grid-cols-1 lg:grid-cols-3">
        <StatCard icon={Wallet} label="Total Spend" value={`₹${totalSpend.toLocaleString()}`} hint={`${myPayments.length} payments`} testId="stat-total-spend" />
        <StatCard icon={Wallet} label="This Month" value={`₹${monthlySpend.toLocaleString()}`} hint="MTD" testId="stat-month-spend" />
        <StatCard icon={Activity} label="Active Deals" value={activeDeals} hint="In progress right now" testId="stat-active-deals" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6" data-testid="overview-recent-deals">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Recent activity</h3>
            <Link to="/brand/campaigns" className="text-xs font-semibold text-secondary hover:underline">View campaigns</Link>
          </div>
          <div className="mt-4 divide-y divide-border">
            {recentDeals.length === 0 && (
              <EmptyState
                icon={Megaphone}
                title="No campaign activity yet"
                description="Create your first campaign and invite verified creators to get started."
                action={<Link to="/brand/campaigns?new=1" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold">New campaign</Link>}
                testId="overview-no-activity"
              />
            )}
            {recentDeals.map((d) => (
              <div key={d.id} className="py-3 flex items-center justify-between gap-3" data-testid={`overview-deal-${d.id}`}>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-primary dark:text-white truncate">
                    ₹{Number(d.amount || 0).toLocaleString()} · creator deal
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {d.note || "Awaiting creator response."}
                  </div>
                </div>
                <StatusChip value={d.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6" data-testid="overview-deadlines">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Upcoming deadlines</h3>
            <Calendar className="h-4 w-4 text-secondary" />
          </div>
          <div className="mt-4 space-y-3">
            {upcoming.length === 0 && <p className="text-sm text-muted-foreground">No deadlines in the next 30 days.</p>}
            {upcoming.map((c) => (
              <Link
                key={c.id}
                to={`/brand/campaigns/${c.id}`}
                className="block rounded-xl border border-border p-3 hover:bg-accent transition-colors"
                data-testid={`deadline-${c.id}`}
              >
                <div className="text-sm font-medium text-primary dark:text-white truncate">{c.title}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Due {c.deadline} {c._days != null && (
                    <span className={`ml-1 inline-block px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${c._days <= 3 ? "bg-destructive/10 text-destructive" : "bg-secondary/15 text-secondary"}`}>
                      {c._days < 0 ? "Overdue" : c._days === 0 ? "Today" : `${c._days}d`}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-6" data-testid="overview-notifs">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-primary dark:text-white">Latest notifications</h3>
          <span className="text-xs text-muted-foreground">{notifications.filter((n) => !n.read).length} unread</span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {recentNotifs.length === 0 && <p className="text-sm text-muted-foreground">You&apos;re all caught up.</p>}
          {recentNotifs.map((n) => (
            <div key={n.id} className={`rounded-xl border border-border p-3 ${n.read ? "" : "bg-accent/40"}`} data-testid={`overview-notif-${n.id}`}>
              <div className="text-sm font-medium text-primary dark:text-white truncate">{n.title}</div>
              {n.body && <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.body}</div>}
              <div className="text-[10px] uppercase tracking-wider text-secondary mt-1">{n.type}</div>
            </div>
          ))}
        </div>
      </div>

      <Dialog open={verificationOpen} onOpenChange={setVerificationOpen}>
        <DialogContent className="max-h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] max-w-xl overflow-y-auto sm:max-h-[90vh]" data-testid="brand-verification-dialog">
          <DialogHeader className="-mx-6 -mt-6 border-b border-border px-6 py-4 pr-12">
            <DialogTitle>Business Verification</DialogTitle>
            <p className="text-sm text-muted-foreground">Submit business ownership documents for BrandKrt admin review.</p>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Contact name *</label>
                <Input
                  value={verificationContact.name}
                  onChange={(event) => setVerificationContact((contact) => ({ ...contact, name: event.target.value }))}
                  className="mt-2"
                  placeholder={brand?.owner_name || user?.name || "Owner or manager name"}
                  data-testid="brand-verification-contact-name"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">WhatsApp phone *</label>
                <Input
                  value={verificationContact.phone}
                  onChange={(event) => setVerificationContact((contact) => ({ ...contact, phone: event.target.value }))}
                  className="mt-2"
                  placeholder={brand?.phone || "+91 98765 43210"}
                  data-testid="brand-verification-contact-phone"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Business proof *</label>
              <Input
                type="file"
                accept="image/*,.pdf"
                multiple
                className="mt-2"
                onChange={(event) => selectVerificationFiles("business", event.target.files)}
                data-testid="brand-verification-business-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">GST certificate, registration proof, shop license, or equivalent. Up to 4 files.</p>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Owner Aadhaar card *</label>
              <Input
                type="file"
                accept="image/*,.pdf"
                multiple
                className="mt-2"
                onChange={(event) => selectVerificationFiles("ownerAadhaar", event.target.files)}
                data-testid="brand-verification-owner-aadhaar-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">Upload owner redacted Aadhaar. Up to 4 images or PDFs.</p>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Other supporting document</label>
              <Input
                type="file"
                accept="image/*,.pdf"
                multiple
                className="mt-2"
                onChange={(event) => selectVerificationFiles("other", event.target.files)}
                data-testid="brand-verification-other-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">Optional extra documents. Up to 4 files.</p>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Notes for admin</label>
              <Textarea
                rows={3}
                value={verificationNotes}
                onChange={(event) => setVerificationNotes(event.target.value)}
                className="mt-2"
                placeholder="Share business context, registered entity name, or anything the admin should check."
                data-testid="brand-verification-notes-input"
              />
            </div>
          </div>
          <DialogFooter className="sticky bottom-0 z-20 -mx-6 -mb-6 border-t border-border bg-background px-6 py-4">
            <button
              type="button"
              onClick={() => setVerificationOpen(false)}
              className="rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={submitVerification}
              disabled={startingVerification}
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold disabled:opacity-60"
              data-testid="brand-verification-submit-btn"
            >
              {startingVerification && <Loader2 className="h-4 w-4 animate-spin" />}
              Submit for Review
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
