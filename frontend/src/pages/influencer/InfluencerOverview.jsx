import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Megaphone, CheckCircle2, Wallet, BadgeCheck, ArrowRight, Sparkles, Clock, Loader2,
} from "lucide-react";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatusChip, EmptyState } from "@/components/State";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

function StatCard({ icon: Icon, label, value, hint, testId }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all" data-testid={testId}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-secondary" />
      </div>
      <div className="mt-3 text-3xl font-display font-light text-primary dark:text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const ACTIVE_STATUSES = new Set(["offer_sent", "offer_accepted", "product_shipped", "promotion_pending", "promotion_live"]);
const MAX_VERIFICATION_FILES = 4;

export default function InfluencerOverview({ verificationOnly = false }) {
  const { user } = useAuth();
  const [deals, setDeals] = useState([]);
  const [payments, setPayments] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [influencer, setInfluencer] = useState(null);
  const [verificationRequests, setVerificationRequests] = useState([]);
  const [startingVerification, setStartingVerification] = useState(false);
  const [verificationOpen, setVerificationOpen] = useState(false);
  const [verificationFiles, setVerificationFiles] = useState({ aadhaar: [], instagram: [], youtube: [], facebook: [] });
  const [verificationContact, setVerificationContact] = useState({ name: "", phone: "" });
  const [verificationNotes, setVerificationNotes] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async ({ quiet = false } = {}) => {
    try {
      const [d, p, n, me, v] = await Promise.all([
        api.get("/deals"),
        api.get("/payments"),
        api.get("/notifications"),
        api.get("/influencers/me"),
        api.get("/verification/mine"),
      ]);
      setDeals(d.data.deals || []);
      setPayments(p.data.payments || []);
      setNotifications(n.data.notifications || []);
      const savedInfluencer = me.data.influencer || null;
      setInfluencer(savedInfluencer);
      setVerificationRequests(v.data.requests || []);
      setVerificationContact((current) => ({
        name: current.name || savedInfluencer?.username || user?.name || "",
        phone: current.phone || savedInfluencer?.phone || user?.phone || "",
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

  const dealIds = useMemo(() => new Set(deals.map((d) => d.id)), [deals]);
  const myPayments = useMemo(() => payments.filter((p) => dealIds.has(p.deal_id)), [payments, dealIds]);

  const totalEarned = useMemo(
    () => myPayments
      .filter((p) => (p.release_status === "released" || p.status === "released"))
      .reduce((s, p) => s + (Number(p.influencer_earning) || 0), 0),
    [myPayments],
  );
  const pendingEscrow = useMemo(
    () => myPayments
      .filter((p) => (p.release_status === "held" || p.status === "escrowed"))
      .reduce((s, p) => s + (Number(p.influencer_earning) || 0), 0),
    [myPayments],
  );

  const activeCount = deals.filter((d) => ACTIVE_STATUSES.has(d.status)).length;
  const completedCount = deals.filter((d) => d.status === "completed").length;
  const unread = notifications.filter((n) => !n.read).length;
  const profileReady = !!influencer;
  const latestVerification = verificationRequests.find((r) => r.kind === "influencer");
  const verificationStatus = ["approved", "verified"].includes(influencer?.verification_status)
    ? "verified"
    : latestVerification?.status || "not_started";
  const hasPendingVerification = verificationStatus === "pending";
  const isVerificationInProgress = verificationStatus === "in_progress";
  const callTime = latestVerification?.schedule_call_at;

  useEffect(() => {
    if (verificationOnly && !loading && verificationStatus === "not_started") setVerificationOpen(true);
  }, [verificationOnly, loading, verificationStatus]);

  const submitVerification = async () => {
    if (!profileReady) {
      toast.error("Please complete your Creator Profile before starting verification.");
      return;
    }
    const hasInsights = ["instagram", "youtube", "facebook"].some((key) => verificationFiles[key].length > 0);
    if (verificationFiles.aadhaar.length === 0 || !hasInsights) {
      toast.error("Please upload Aadhaar and at least one platform insight.");
      return;
    }
    if (!verificationContact.name.trim() || !verificationContact.phone.trim()) {
      toast.error("Please enter your name and WhatsApp phone number.");
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
        ...uploadGroup(verificationFiles.aadhaar, "aadhaar_card", "Aadhaar card"),
        ...uploadGroup(verificationFiles.instagram, "instagram_insights", "Instagram insights"),
        ...uploadGroup(verificationFiles.youtube, "youtube_insights", "YouTube insights"),
        ...uploadGroup(verificationFiles.facebook, "facebook_insights", "Facebook insights"),
      ])).filter(Boolean);
      const { data } = await api.post("/verification", {
        kind: "influencer",
        documents,
        contact_name: verificationContact.name.trim(),
        contact_phone: verificationContact.phone.trim(),
        notes: verificationNotes || "Influencer submitted verification documents from the dashboard.",
      });
      if (data.request) {
        setVerificationRequests((rows) => [data.request, ...rows.filter((row) => row.id !== data.request.id)]);
      }
      setVerificationOpen(false);
      setVerificationFiles({ aadhaar: [], instagram: [], youtube: [], facebook: [] });
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

  if (loading) {
    return <div className="text-muted-foreground">Loading…</div>;
  }

  const recentDeals = deals.slice(0, 5);
  const recentNotifs = notifications.slice(0, 5);

  return (
    <div className="space-y-8" data-testid="influencer-overview">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">
            Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""} <span className="gold-text font-semibold">✨</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Here&apos;s your creator snapshot — campaigns, earnings and alerts in one place.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/influencer/profile" data-testid="overview-edit-profile" className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold hover:bg-accent">
            <UserIcon /> Edit profile
          </Link>
          <Link to="/influencer/campaigns" data-testid="overview-view-campaigns" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold">
            View campaigns <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {!profileReady && (
        <div className="rounded-2xl border border-secondary/40 bg-accent p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-3" data-testid="overview-profile-banner">
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-secondary mt-0.5" />
            <div>
              <div className="font-semibold text-primary dark:text-white">Finish your Creator Profile</div>
              <div className="text-sm text-muted-foreground">Brands can only discover you once your profile is complete — bio, social handles, category and rate card.</div>
            </div>
          </div>
          <Link to="/influencer/profile" className="inline-flex items-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap">
            Complete profile <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Megaphone} label="Active Campaigns" value={activeCount} testId="stat-active-campaigns" />
        <StatCard icon={CheckCircle2} label="Completed" value={completedCount} testId="stat-completed" />
        <StatCard icon={Wallet} label="Total Earned" value={`₹${totalEarned.toLocaleString()}`} hint="Released payouts" testId="stat-total-earned" />
        <StatCard icon={Clock} label="In Escrow" value={`₹${pendingEscrow.toLocaleString()}`} hint="Awaiting release" testId="stat-pending-escrow" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6" data-testid="overview-recent-deals">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Recent campaign offers</h3>
            <Link to="/influencer/campaigns" className="text-xs font-semibold text-secondary hover:underline">View all</Link>
          </div>
          <div className="mt-4 divide-y divide-border">
            {recentDeals.length === 0 && (
              <EmptyState
                icon={Megaphone}
                title="No campaign offers yet"
                description="Brands will reach out once you complete your Creator Profile. Make sure your handles and rate card are filled in."
                action={<Link to="/influencer/profile" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold">Complete profile</Link>}
                testId="overview-no-deals"
              />
            )}
            {recentDeals.map((d) => (
              <div key={d.id} className="py-3 flex items-center justify-between gap-3" data-testid={`overview-deal-${d.id}`}>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-primary dark:text-white truncate">Campaign offer · ₹{Number(d.amount || 0).toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground truncate">{d.note || "No note from the brand."}</div>
                </div>
                <StatusChip value={d.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6" data-testid="overview-recent-notifs">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-primary dark:text-white">Recent alerts</h3>
            <Link to="/influencer/notifications" className="text-xs font-semibold text-secondary hover:underline">All ({unread} unread)</Link>
          </div>
          <div className="mt-4 space-y-3">
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
      </div>

      <div className="rounded-2xl border border-border bg-card p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4" data-testid="overview-verification-card">
        <div className="flex items-start gap-3">
          <BadgeCheck className="h-5 w-5 text-secondary mt-0.5" />
          <div>
            <div className="font-semibold text-primary dark:text-white">
              {verificationStatus === "verified" ? "You're a verified creator" : isVerificationInProgress ? "Verification in progress" : hasPendingVerification ? "Verification pending" : "Become a verified creator"}
            </div>
            <div className="text-sm text-muted-foreground">
              {verificationStatus === "verified"
                ? "Your profile has the verified badge. Brands trust you instantly."
                : isVerificationInProgress && callTime
                  ? `WhatsApp video call scheduled for ${new Date(callTime).toLocaleString()}.`
                  : isVerificationInProgress
                    ? "Admin is reviewing your documents. Your WhatsApp video call will be scheduled here."
                    : hasPendingVerification
                      ? "Your documents are waiting for admin review."
                      : "Upload Aadhaar and account insights for admin review."}
            </div>
          </div>
        </div>
        {verificationStatus === "verified" ? (
          <Link to="/influencer/profile" className="inline-flex items-center gap-2 rounded-full border border-border bg-background hover:bg-accent px-4 py-2 text-sm font-semibold whitespace-nowrap">
            View profile <ArrowRight className="h-4 w-4" />
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => setVerificationOpen(true)}
            disabled={startingVerification || hasPendingVerification || isVerificationInProgress || !profileReady}
            className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed"
            data-testid="start-verification-btn"
          >
            {startingVerification ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
            {isVerificationInProgress ? "In Progress" : hasPendingVerification ? "Request pending" : "Start Verification"}
          </button>
        )}
      </div>

      <Dialog open={verificationOpen} onOpenChange={setVerificationOpen}>
        <DialogContent className="max-h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] max-w-xl overflow-y-auto sm:max-h-[90vh]" data-testid="verification-dialog">
          <DialogHeader className="sticky top-0 z-20 -mx-6 -mt-6 border-b border-border bg-background px-6 py-4 pr-12">
            <DialogTitle>Creator Verification</DialogTitle>
            <p className="text-sm text-muted-foreground">Submit your identity and social insights for BrandKrt admin review.</p>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Full name *</label>
                <Input
                  value={verificationContact.name}
                  onChange={(event) => setVerificationContact((contact) => ({ ...contact, name: event.target.value }))}
                  className="mt-2"
                  placeholder={user?.name || "Your full name"}
                  data-testid="verification-contact-name"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">WhatsApp phone *</label>
                <Input
                  value={verificationContact.phone}
                  onChange={(event) => setVerificationContact((contact) => ({ ...contact, phone: event.target.value }))}
                  className="mt-2"
                  placeholder="+91 98765 43210"
                  data-testid="verification-contact-phone"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Aadhaar card *</label>
              <Input
                type="file"
                accept="image/*,.pdf"
                multiple
                className="mt-2"
                onChange={(event) => selectVerificationFiles("aadhaar", event.target.files)}
                data-testid="verification-aadhaar-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">Upload redacted Aadhaar. Up to 4 images or PDFs.</p>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Instagram insights</label>
              <Input
                type="file"
                accept="image/*,.pdf"
                multiple
                className="mt-2"
                onChange={(event) => selectVerificationFiles("instagram", event.target.files)}
                data-testid="verification-instagram-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">Reach, audience, recent reel/post screenshots. Up to 4 files.</p>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">YouTube insights</label>
              <Input
                type="file"
                accept="image/*,.pdf"
                multiple
                className="mt-2"
                onChange={(event) => selectVerificationFiles("youtube", event.target.files)}
                data-testid="verification-youtube-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">Analytics, channel/recent video proof. Up to 4 files.</p>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Facebook insights</label>
              <Input
                type="file"
                accept="image/*,.pdf"
                multiple
                className="mt-2"
                onChange={(event) => selectVerificationFiles("facebook", event.target.files)}
                data-testid="verification-facebook-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">Page/profile insights and reach proof. Up to 4 files.</p>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Notes for admin</label>
              <Textarea
                rows={3}
                value={verificationNotes}
                onChange={(event) => setVerificationNotes(event.target.value)}
                className="mt-2"
                placeholder="Share your primary handle, niche, or anything the admin should check."
                data-testid="verification-notes-input"
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
              data-testid="verification-submit-btn"
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

function UserIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}
