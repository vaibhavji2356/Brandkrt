import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Search, Filter, Bookmark, BookmarkCheck, Send, Star, Users, MapPin, IndianRupee,
  Instagram, Youtube, Facebook, Globe, BadgeCheck, X as XIcon, Loader2,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/State";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useAuth } from "@/context/AuthContext";
import { readSaved, toggleSaved } from "@/lib/savedInfluencers";

const CATEGORIES = [
  "Fashion & Beauty", "Food & Beverage", "Fitness & Health", "Lifestyle", "Travel",
  "Technology", "Education & Coaching", "Parenting", "Home & Decor", "Business & Finance",
  "Entertainment", "Gaming", "Local & City",
];
const PLATFORMS = ["instagram", "youtube", "facebook", "linkedin"];
const FOLLOWER_BUCKETS = [
  { key: "any", label: "Any", min: 0, max: Infinity },
  { key: "nano", label: "Nano (1K–10K)", min: 1000, max: 10000 },
  { key: "micro", label: "Micro (10K–100K)", min: 10000, max: 100000 },
  { key: "mid", label: "Mid (100K–500K)", min: 100000, max: 500000 },
  { key: "macro", label: "Macro (500K+)", min: 500000, max: Infinity },
];
const SORTS = [
  { key: "newest", label: "Newest" },
  { key: "followers", label: "Followers" },
  { key: "views", label: "Avg views" },
  { key: "rating", label: "Rating" },
];

const PLATFORM_FIELDS = {
  instagram: "instagram",
  youtube: "youtube",
  facebook: "facebook",
  linkedin: "linkedin",
};

export default function BrandDiscover() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [bucket, setBucket] = useState("any");
  const [minViews, setMinViews] = useState("");
  const [platform, setPlatform] = useState("");
  const [location, setLocation] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sort, setSort] = useState("newest");
  const [saved, setSaved] = useState({});
  const [profileOpen, setProfileOpen] = useState(null);
  const [inviteOpen, setInviteOpen] = useState(null);

  const userId = user?.id;
  useEffect(() => { setSaved(readSaved(userId)); }, [userId]);

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (q.trim()) params.q = q.trim();
      if (category) params.category = category;
      const { data } = await api.get("/influencers", { params });
      setList(data.influencers || []);
    } catch (err) { toast.error(formatApiError(err)); }
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, []);

  const filtered = useMemo(() => {
    const b = FOLLOWER_BUCKETS.find((x) => x.key === bucket) || FOLLOWER_BUCKETS[0];
    const mv = Number(minViews) || 0;
    return list.filter((inf) => {
      const f = Number(inf.followers) || 0;
      if (f < b.min || f > b.max) return false;
      if (mv && (Number(inf.avg_reel_views) || 0) < mv) return false;
      if (platform && !inf[PLATFORM_FIELDS[platform]]) return false;
      if (location) {
        const loc = location.toLowerCase();
        const hit = [inf.city, inf.state, inf.country].filter(Boolean).some((x) => x.toLowerCase().includes(loc));
        if (!hit) return false;
      }
      if (verifiedOnly && !["approved", "verified"].includes(inf.verification_status)) return false;
      return true;
    });
  }, [list, bucket, minViews, platform, location, verifiedOnly]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    if (sort === "followers") arr.sort((a, b) => (Number(b.followers) || 0) - (Number(a.followers) || 0));
    else if (sort === "views") arr.sort((a, b) => (Number(b.avg_reel_views) || 0) - (Number(a.avg_reel_views) || 0));
    else if (sort === "rating") arr.sort((a, b) => (Number(b.rating || 5) || 0) - (Number(a.rating || 5) || 0));
    else arr.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    return arr;
  }, [filtered, sort]);

  const toggle = (inf) => {
    const next = toggleSaved(userId, inf);
    setSaved(next);
    toast.success(next[inf.id] ? "Saved to your shortlist." : "Removed from saved.");
  };

  const resetFilters = () => {
    setQ(""); setCategory(""); setBucket("any"); setMinViews("");
    setPlatform(""); setLocation(""); setVerifiedOnly(false); setSort("newest");
  };

  return (
    <div className="space-y-6" data-testid="brand-discover">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Discover Influencers</h2>
        <p className="text-sm text-muted-foreground mt-1">Search verified creators by niche, reach, platform and city. Save shortlists, invite to any campaign.</p>
      </div>

      <div className="rounded-2xl border border-border bg-card p-4 md:p-6 space-y-4" data-testid="discover-filters">
        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") load(); }} placeholder="Search by handle / username" className="pl-9" data-testid="discover-q" />
          </div>
          <button onClick={load} disabled={loading} data-testid="discover-search" className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold disabled:opacity-60">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Search
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Category</label>
            <select value={category} onChange={(e) => { setCategory(e.target.value); setTimeout(load, 0); }} className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="filter-category">
              <option value="">All</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Followers</label>
            <select value={bucket} onChange={(e) => setBucket(e.target.value)} className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="filter-followers">
              {FOLLOWER_BUCKETS.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Min avg views</label>
            <Input type="number" min="0" value={minViews} onChange={(e) => setMinViews(e.target.value)} placeholder="0" className="mt-1" data-testid="filter-views" />
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Platform</label>
            <select value={platform} onChange={(e) => setPlatform(e.target.value)} className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="filter-platform">
              <option value="">All</option>
              {PLATFORMS.map((p) => <option key={p} value={p} className="capitalize">{p}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Location</label>
            <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="City / state" className="mt-1" data-testid="filter-location" />
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Sort by</label>
            <select value={sort} onChange={(e) => setSort(e.target.value)} className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="filter-sort">
              {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 mt-5 text-sm" data-testid="filter-verified-wrap">
            <input type="checkbox" checked={verifiedOnly} onChange={(e) => setVerifiedOnly(e.target.checked)} className="h-4 w-4 accent-current" data-testid="filter-verified" />
            <span className="inline-flex items-center gap-1"><BadgeCheck className="h-3.5 w-3.5 text-secondary" /> Verified only</span>
          </label>
          <button type="button" onClick={resetFilters} className="mt-5 text-xs font-semibold text-muted-foreground hover:text-secondary inline-flex items-center gap-1" data-testid="filter-reset">
            <Filter className="h-3 w-3" /> Reset filters
          </button>
        </div>
      </div>

      <p className="text-sm text-muted-foreground" data-testid="discover-count">{sorted.length} creators</p>

      {!loading && sorted.length === 0 && (
        <EmptyState
          icon={Search}
          title="No creators match your filters"
          description="Loosen a filter or two to widen your search. Verified, on-budget creators usually show up after a small reset."
          action={<button onClick={resetFilters} className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent">Reset filters</button>}
          testId="discover-empty"
        />
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="discover-results">
        {sorted.map((inf) => (
          <InfluencerCard
            key={inf.id}
            inf={inf}
            isSaved={!!saved[inf.id]}
            onToggleSave={() => toggle(inf)}
            onOpen={() => setProfileOpen(inf)}
            onInvite={() => setInviteOpen(inf)}
          />
        ))}
      </div>

      <ProfileDialog open={!!profileOpen} influencer={profileOpen} onClose={() => setProfileOpen(null)}
        isSaved={profileOpen ? !!saved[profileOpen.id] : false}
        onToggleSave={() => profileOpen && toggle(profileOpen)}
        onInvite={() => { setInviteOpen(profileOpen); setProfileOpen(null); }} />

      <InviteDialog open={!!inviteOpen} influencer={inviteOpen} onClose={() => setInviteOpen(null)} />
    </div>
  );
}

export function InfluencerCard({ inf, isSaved, onToggleSave, onOpen, onInvite, hideInvite = false }) {
  const initials = (inf.username || inf.category || "C").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className="rounded-2xl border border-border bg-card p-5 flex flex-col gap-4 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all" data-testid={`inf-card-${inf.id}`}>
      <div className="flex items-start gap-4">
        <div className="h-14 w-14 rounded-2xl bg-secondary text-secondary-foreground flex items-center justify-center overflow-hidden text-lg font-display font-semibold shrink-0">
          {inf.profile_photo_url
            ? <img src={inf.profile_photo_url} alt="" className="h-full w-full object-cover" />
            : initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-primary dark:text-white truncate">{inf.username || "Creator"}</h3>
            {["approved", "verified"].includes(inf.verification_status) && <BadgeCheck className="h-4 w-4 text-secondary shrink-0" />}
          </div>
          <p className="text-xs text-muted-foreground truncate">{inf.category || "—"}</p>
          {(inf.city || inf.country) && (
            <p className="text-[11px] text-muted-foreground mt-0.5 inline-flex items-center gap-1"><MapPin className="h-3 w-3" /> {[inf.city, inf.country].filter(Boolean).join(", ")}</p>
          )}
        </div>
        <button onClick={onToggleSave} aria-label="Save creator" data-testid={`save-${inf.id}`}
          className="h-9 w-9 rounded-full border border-border bg-background hover:bg-accent flex items-center justify-center">
          {isSaved ? <BookmarkCheck className="h-4 w-4 text-secondary" /> : <Bookmark className="h-4 w-4 text-muted-foreground" />}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <Mini label="Followers" value={shortNum(inf.followers)} />
        <Mini label="Avg views" value={shortNum(inf.avg_reel_views)} />
        <Mini label="Rate" value={inf.collab_price ? `₹${shortNum(inf.collab_price)}` : "—"} />
      </div>

      <div className="flex items-center gap-2 text-muted-foreground text-xs">
        {inf.instagram && <Instagram className="h-3.5 w-3.5" />}
        {inf.youtube && <Youtube className="h-3.5 w-3.5" />}
        {inf.facebook && <Facebook className="h-3.5 w-3.5" />}
        {inf.website && <Globe className="h-3.5 w-3.5" />}
        <span className="ml-auto inline-flex items-center gap-1 text-xs"><Star className="h-3 w-3 text-secondary fill-current" /> {Number(inf.rating || 4.8).toFixed(1)}</span>
      </div>

      <div className="flex gap-2 mt-auto">
        <button onClick={onOpen} className="flex-1 rounded-full border border-border hover:bg-accent px-3 py-2 text-xs font-semibold" data-testid={`open-${inf.id}`}>
          View profile
        </button>
        {!hideInvite && (
          <button onClick={onInvite} className="flex-1 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-3 py-2 text-xs font-semibold inline-flex items-center justify-center gap-1" data-testid={`invite-${inf.id}`}>
            <Send className="h-3.5 w-3.5" /> Invite
          </button>
        )}
      </div>
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="rounded-xl border border-border bg-background p-2">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-sm font-semibold text-primary dark:text-white">{value}</div>
    </div>
  );
}

function shortNum(n) {
  const v = Number(n) || 0;
  if (v >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`;
  if (v >= 1e5) return `${(v / 1e5).toFixed(1)}L`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toString();
}

function ProfileDialog({ open, influencer, onClose, isSaved, onToggleSave, onInvite }) {
  if (!influencer) return null;
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="profile-dialog">
        <DialogHeader>
          <DialogTitle className="text-2xl font-display font-light flex items-center gap-2">
            {influencer.username || "Creator"}
            {["approved", "verified"].includes(influencer.verification_status) && <BadgeCheck className="h-5 w-5 text-secondary" />}
          </DialogTitle>
          <DialogDescription>{influencer.category || "—"} · {[influencer.city, influencer.country].filter(Boolean).join(", ") || "Location TBD"}</DialogDescription>
        </DialogHeader>
        {influencer.cover_photo_url && (
          <div className="h-32 rounded-xl overflow-hidden border border-border bg-cover bg-center" style={{ backgroundImage: `url(${influencer.cover_photo_url})` }} />
        )}
        {influencer.bio && <p className="text-sm text-foreground/90 whitespace-pre-line">{influencer.bio}</p>}
        <div className="grid grid-cols-3 gap-3 text-center">
          <Mini label="Followers" value={shortNum(influencer.followers)} />
          <Mini label="Avg views" value={shortNum(influencer.avg_reel_views)} />
          <Mini label="Monthly reach" value={shortNum(influencer.monthly_reach)} />
        </div>
        <div className="grid sm:grid-cols-2 gap-3 text-sm">
          {influencer.collab_price && <div className="inline-flex items-center gap-2"><IndianRupee className="h-4 w-4 text-secondary" /> Collab rate ₹{Number(influencer.collab_price).toLocaleString()}</div>}
          {influencer.instagram && <a href={influencer.instagram} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-secondary hover:underline"><Instagram className="h-4 w-4" /> Instagram</a>}
          {influencer.youtube && <a href={influencer.youtube} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-secondary hover:underline"><Youtube className="h-4 w-4" /> YouTube</a>}
          {influencer.facebook && <a href={influencer.facebook} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-secondary hover:underline"><Facebook className="h-4 w-4" /> Facebook</a>}
          {influencer.website && <a href={influencer.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-secondary hover:underline"><Globe className="h-4 w-4" /> Website</a>}
        </div>
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2 border-t border-border">
          <button onClick={onToggleSave} className="inline-flex items-center justify-center gap-2 rounded-full border border-border hover:bg-accent px-5 py-2.5 text-sm font-semibold">
            {isSaved ? <><BookmarkCheck className="h-4 w-4" /> Saved</> : <><Bookmark className="h-4 w-4" /> Save creator</>}
          </button>
          <button onClick={onInvite} className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold">
            <Send className="h-4 w-4" /> Invite to campaign
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function InviteDialog({ open, influencer, onClose }) {
  const [campaigns, setCampaigns] = useState([]);
  const [campaignId, setCampaignId] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loadingC, setLoadingC] = useState(true);

  useEffect(() => {
    if (!open) return;
    setLoadingC(true);
    api.get("/campaigns").then(({ data }) => {
      const list = (data.campaigns || []).filter((c) => c.status === "active" || c.status === "draft");
      setCampaigns(list);
      if (list.length > 0) {
        setCampaignId(list[0].id);
        setAmount(String(influencer?.collab_price || list[0].budget || 0));
      }
    }).catch(() => {}).finally(() => setLoadingC(false));
  }, [open, influencer]);

  const submit = async (e) => {
    e.preventDefault();
    if (!campaignId) { toast.error("Select a campaign first."); return; }
    if (!Number(amount)) { toast.error("Enter a non-zero amount."); return; }
    setSubmitting(true);
    try {
      await api.post("/deals", {
        campaign_id: campaignId,
        influencer_id: influencer.id,
        amount: Number(amount),
        note,
      });
      toast.success("Invite sent! The creator will be notified.");
      onClose();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSubmitting(false); }
  };

  if (!influencer) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="invite-dialog">
        <DialogHeader>
          <DialogTitle className="text-xl font-display font-light">Invite {influencer.username || "creator"}</DialogTitle>
          <DialogDescription>Send a paid collaboration offer linked to one of your campaigns.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Campaign</label>
            {loadingC ? (
              <div className="mt-2 text-sm text-muted-foreground">Loading campaigns…</div>
            ) : campaigns.length === 0 ? (
              <div className="mt-2 rounded-xl border border-dashed border-border p-3 text-sm">
                You don&apos;t have an active or draft campaign yet. <Users className="inline h-3 w-3" /> Create a campaign first.
              </div>
            ) : (
              <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)} className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="invite-campaign">
                {campaigns.map((c) => <option key={c.id} value={c.id}>{c.title} ({c.status})</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Offer amount (₹)</label>
            <Input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} className="mt-2" data-testid="invite-amount" />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Personal note</label>
            <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Hi! We loved your last food reel — would you like to collab on our new menu launch?" className="mt-2" data-testid="invite-note" />
          </div>
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <button type="button" onClick={onClose} className="inline-flex items-center justify-center rounded-full border border-border px-5 py-2.5 text-sm font-semibold hover:bg-accent"><XIcon className="h-4 w-4 mr-1" /> Cancel</button>
            <button type="submit" disabled={submitting || campaigns.length === 0} data-testid="invite-submit" className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold disabled:opacity-60">
              {submitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending…</> : <><Send className="h-4 w-4" /> Send invite</>}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
