import React, { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, BadgeCheck, Save, Loader2, Video } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";

const CATEGORIES = [
  "Fashion & Beauty", "Food & Beverage", "Fitness & Health", "Lifestyle", "Travel",
  "Technology", "Education & Coaching", "Parenting", "Home & Decor", "Business & Finance",
  "Entertainment", "Gaming", "Local & City",
];

function Section({ title, description, children, testId }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6 md:p-8" data-testid={testId}>
      <div className="mb-6">
        <h3 className="text-lg font-medium text-primary dark:text-white">{title}</h3>
        {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
      </div>
      {children}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</label>
      <div className="mt-2">{children}</div>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

const EMPTY = {
  username: "", phone: "", country: "", state: "", city: "",
  profile_photo_url: "", cover_photo_url: "", bio: "",
  instagram: "", youtube: "", facebook: "", linkedin: "", website: "",
  category: "", followers: 0, avg_reel_views: 0, monthly_reach: 0, collab_price: 0,
  upi: "", gst: "",
  bank_details: { account_name: "", account_number: "", ifsc: "", bank_name: "" },
  portfolio: [],
};

export default function InfluencerProfile() {
  const { user } = useAuth();
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [verified, setVerified] = useState("not_started");
  const avatarRef = useRef(null);
  const coverRef = useRef(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [uploadingCover, setUploadingCover] = useState(false);
  const [imageBroken, setImageBroken] = useState({ avatar: false });
  const [latestVerification, setLatestVerification] = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setBank = (k, v) => setForm((f) => ({ ...f, bank_details: { ...(f.bank_details || {}), [k]: v } }));

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/influencers/me");
        if (data.influencer) {
          const inf = data.influencer;
          setForm({
            ...EMPTY,
            ...inf,
            bank_details: { ...EMPTY.bank_details, ...(inf.bank_details || {}) },
          });
          setImageBroken({ avatar: false });
          setVerified(inf.verification_status || "not_started");
        }
      } catch (_) { /* not yet created */ }
      try {
        const { data } = await api.get("/verification/mine");
        setLatestVerification((data.requests || []).find((r) => r.kind === "influencer") || null);
      } catch (_) { /* optional */ }
      setLoading(false);
    })();
  }, []);

  const uploadFile = async (file, kind) => {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post("/uploads/profiles", fd, { headers: { "Content-Type": "multipart/form-data" } });
    const url = data.url;
    if (kind === "avatar") {
      setImageBroken((prev) => ({ ...prev, avatar: false }));
      set("profile_photo_url", url);
    } else set("cover_photo_url", url);
  };

  const onPickAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingAvatar(true);
    try { await uploadFile(file, "avatar"); toast.success("Profile photo uploaded."); }
    catch (err) { toast.error(formatApiError(err)); }
    finally { setUploadingAvatar(false); e.target.value = ""; }
  };
  const onPickCover = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingCover(true);
    try { await uploadFile(file, "cover"); toast.success("Cover photo uploaded."); }
    catch (err) { toast.error(formatApiError(err)); }
    finally { setUploadingCover(false); e.target.value = ""; }
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        followers: Number(form.followers || 0),
        avg_reel_views: Number(form.avg_reel_views || 0),
        monthly_reach: Number(form.monthly_reach || 0),
        collab_price: Number(form.collab_price || 0),
      };
      // strip non-API fields the backend doesn't accept
      ["id", "user_id", "status", "verification_status", "created_at", "updated_at"].forEach((k) => delete payload[k]);
      const { data } = await api.put("/influencers/me", payload);
      if (data.influencer) {
        setVerified(data.influencer.verification_status || verified);
      }
      toast.success("Creator profile saved.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-muted-foreground">Loading…</div>;

  const initials = (user?.name || user?.email || "U").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
  const callTime = latestVerification?.schedule_call_at;

  return (
    <form onSubmit={save} className="space-y-8" data-testid="influencer-profile-form">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Profile Builder</h2>
        <p className="text-sm text-muted-foreground mt-1">Tell brands who you are. A complete profile gets up to 3× more campaign invites.</p>
      </div>

      {latestVerification?.status === "in_progress" && callTime && (
        <div className="rounded-2xl border border-secondary/30 bg-secondary/10 p-4 flex items-start gap-3" data-testid="profile-verification-call">
          <Video className="h-5 w-5 text-secondary mt-0.5" />
          <div>
            <div className="font-semibold text-primary dark:text-white">WhatsApp verification call scheduled</div>
            <div className="text-sm text-muted-foreground">{new Date(callTime).toLocaleString()}</div>
          </div>
        </div>
      )}

      {/* Cover + Avatar */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <div
          className="relative h-40 md:h-48 bg-primary"
          style={form.cover_photo_url
            ? { backgroundImage: `url(${form.cover_photo_url})`, backgroundSize: "cover", backgroundPosition: "center" }
            : { backgroundImage: "radial-gradient(circle at 20% 50%, rgba(212,175,55,0.4), transparent 50%)" }}
          data-testid="profile-cover"
        >
          <button
            type="button"
            onClick={() => coverRef.current?.click()}
            className="absolute right-4 bottom-4 inline-flex items-center gap-2 rounded-full bg-background/90 backdrop-blur px-3 py-1.5 text-xs font-semibold border border-border"
            data-testid="upload-cover-btn"
          >
            {uploadingCover ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Camera className="h-3.5 w-3.5" />}
            {uploadingCover ? "Uploading…" : "Change cover"}
          </button>
          <input ref={coverRef} type="file" accept="image/*" onChange={onPickCover} className="hidden" />
        </div>
        <div className="px-6 md:px-8 pb-6 md:pb-8">
          <div className="flex flex-col sm:flex-row sm:items-end sm:gap-6 -mt-12">
            <div className="relative h-24 w-24 rounded-2xl border-4 border-background bg-secondary text-secondary-foreground flex items-center justify-center text-2xl font-display font-semibold overflow-hidden shadow-luxe-sm" data-testid="profile-avatar">
              {form.profile_photo_url && !imageBroken.avatar
                ? <img src={form.profile_photo_url} alt="" className="h-full w-full object-cover" onError={() => setImageBroken((prev) => ({ ...prev, avatar: true }))} />
                : initials}
              <button
                type="button"
                onClick={() => avatarRef.current?.click()}
                className="absolute inset-x-0 bottom-0 bg-black/50 text-white text-[10px] py-1 font-semibold inline-flex items-center justify-center gap-1"
                data-testid="upload-avatar-btn"
              >
                {uploadingAvatar ? <Loader2 className="h-3 w-3 animate-spin" /> : <Camera className="h-3 w-3" />}
                {uploadingAvatar ? "…" : "Change"}
              </button>
              <input ref={avatarRef} type="file" accept="image/*" onChange={onPickAvatar} className="hidden" />
            </div>
            <div className="mt-4 sm:mt-0 flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl md:text-3xl font-display font-light tracking-tight text-primary dark:text-white truncate">
                  {user?.name || "Your name"}
                </h1>
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                  ["approved", "verified"].includes(verified) ? "bg-success/10 text-success" :
                  verified === "rejected" ? "bg-destructive/10 text-destructive" : "bg-warning/10 text-warning"
                }`}>
                  <BadgeCheck className="h-3 w-3" /> {verified}
                </span>
              </div>
              <p className="text-sm text-muted-foreground mt-1 truncate">{user?.email}</p>
              <p className="text-xs text-muted-foreground mt-2">Tip: A clear face photo + bio dramatically increase brand invites.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Basics */}
      <Section title="Basics" description="Public details brands will see first." testId="section-basics">
        <div className="grid sm:grid-cols-2 gap-5">
          <Field label="Username / Handle"><Input value={form.username} onChange={(e) => set("username", e.target.value)} placeholder="@yourhandle" data-testid="field-username" /></Field>
          <Field label="Phone"><Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+91…" data-testid="field-phone" /></Field>
          <Field label="Category">
            <select value={form.category || ""} onChange={(e) => set("category", e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="field-category">
              <option value="">Select a category…</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Country"><Input value={form.country} onChange={(e) => set("country", e.target.value)} placeholder="India" data-testid="field-country" /></Field>
          <Field label="State"><Input value={form.state} onChange={(e) => set("state", e.target.value)} placeholder="Maharashtra" data-testid="field-state" /></Field>
          <Field label="City"><Input value={form.city} onChange={(e) => set("city", e.target.value)} placeholder="Pune" data-testid="field-city" /></Field>
          <div className="sm:col-span-2">
            <Field label="Bio" hint="Max 240 characters. Tell brands what makes your content unique.">
              <Textarea rows={3} value={form.bio || ""} onChange={(e) => set("bio", e.target.value.slice(0, 240))} placeholder="I'm a Pune-based food creator helping local cafés get discovered…" data-testid="field-bio" />
            </Field>
          </div>
        </div>
      </Section>

      {/* Social handles */}
      <Section title="Social handles" description="Add your public profile URLs so brands can verify your reach." testId="section-socials">
        <div className="grid sm:grid-cols-2 gap-5">
          <Field label="Instagram"><Input value={form.instagram || ""} onChange={(e) => set("instagram", e.target.value)} placeholder="https://instagram.com/yourhandle" data-testid="field-instagram" /></Field>
          <Field label="YouTube"><Input value={form.youtube || ""} onChange={(e) => set("youtube", e.target.value)} placeholder="https://youtube.com/@yourhandle" data-testid="field-youtube" /></Field>
          <Field label="Facebook"><Input value={form.facebook || ""} onChange={(e) => set("facebook", e.target.value)} placeholder="https://facebook.com/yourpage" data-testid="field-facebook" /></Field>
          <Field label="LinkedIn"><Input value={form.linkedin || ""} onChange={(e) => set("linkedin", e.target.value)} placeholder="https://linkedin.com/in/you" data-testid="field-linkedin" /></Field>
          <div className="sm:col-span-2">
            <Field label="Website / Portfolio"><Input value={form.website || ""} onChange={(e) => set("website", e.target.value)} placeholder="https://yourdomain.com" data-testid="field-website" /></Field>
          </div>
        </div>
      </Section>

      {/* Audience & rate card */}
      <Section title="Audience & rate card" description="What's your reach today, and what do you charge per collab?" testId="section-reach">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <Field label="Followers (primary platform)" hint="Combined Instagram followers if your handle is on IG.">
            <Input type="number" min="0" value={form.followers ?? 0} onChange={(e) => set("followers", e.target.value)} data-testid="field-followers" />
          </Field>
          <Field label="Avg Reel / Short Views">
            <Input type="number" min="0" value={form.avg_reel_views ?? 0} onChange={(e) => set("avg_reel_views", e.target.value)} data-testid="field-reel-views" />
          </Field>
          <Field label="Monthly Reach">
            <Input type="number" min="0" value={form.monthly_reach ?? 0} onChange={(e) => set("monthly_reach", e.target.value)} data-testid="field-monthly-reach" />
          </Field>
          <Field label="Collab Price (₹)" hint="Your indicative rate per collaboration.">
            <Input type="number" min="0" value={form.collab_price ?? 0} onChange={(e) => set("collab_price", e.target.value)} data-testid="field-collab-price" />
          </Field>
        </div>
      </Section>

      {/* Payout details */}
      <Section title="Payout details" description="Where should we release your earnings? This information is private and only used for payouts." testId="section-payout">
        <div className="grid sm:grid-cols-2 gap-5">
          <Field label="UPI ID" hint="Fastest payout option in India.">
            <Input value={form.upi || ""} onChange={(e) => set("upi", e.target.value)} placeholder="yourname@upi" data-testid="field-upi" />
          </Field>
          <Field label="GST / Tax ID (optional)">
            <Input value={form.gst || ""} onChange={(e) => set("gst", e.target.value)} placeholder="22AAAAA0000A1Z5" data-testid="field-gst" />
          </Field>
          <Field label="Account holder name">
            <Input value={form.bank_details?.account_name || ""} onChange={(e) => setBank("account_name", e.target.value)} data-testid="field-bank-name" />
          </Field>
          <Field label="Bank name">
            <Input value={form.bank_details?.bank_name || ""} onChange={(e) => setBank("bank_name", e.target.value)} data-testid="field-bank-bank" />
          </Field>
          <Field label="Account number">
            <Input value={form.bank_details?.account_number || ""} onChange={(e) => setBank("account_number", e.target.value)} data-testid="field-bank-account" />
          </Field>
          <Field label="IFSC / SWIFT">
            <Input value={form.bank_details?.ifsc || ""} onChange={(e) => setBank("ifsc", e.target.value)} data-testid="field-bank-ifsc" />
          </Field>
        </div>
      </Section>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-end gap-3 sticky bottom-16 md:bottom-0 md:static py-2">
        <p className="text-xs text-muted-foreground sm:mr-auto">All changes are saved to your private creator profile.</p>
        <button
          type="submit"
          disabled={saving}
          data-testid="profile-save"
          className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold disabled:opacity-60"
        >
          {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <><Save className="h-4 w-4" /> Save profile</>}
        </button>
      </div>
    </form>
  );
}
