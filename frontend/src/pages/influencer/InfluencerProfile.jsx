import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, Save, BadgeCheck, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatApiError } from "@/lib/api";
import InfluencerAPI from "@/lib/influencerApi";

const CATEGORIES = [
  "Lifestyle",
  "Fashion",
  "Beauty",
  "Tech",
  "Gaming",
  "Food",
  "Travel",
  "Fitness",
  "Finance",
  "Education",
  "Parenting",
  "Other",
];

const EMPTY = {
  username: "",
  phone: "",
  country: "",
  state: "",
  city: "",
  bio: "",
  instagram: "",
  youtube: "",
  facebook: "",
  linkedin: "",
  website: "",
  category: "",
  followers: 0,
  avg_reel_views: 0,
  monthly_reach: 0,
  collab_price: 0,
  upi: "",
  gst: "",
};

export default function InfluencerProfile() {
  const [form, setForm] = useState(EMPTY);
  const [verifStatus, setVerifStatus] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submittingVerif, setSubmittingVerif] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const p = await InfluencerAPI.getProfile();
        if (p) {
          setForm((f) => ({ ...f, ...stripNulls(p) }));
          setVerifStatus(p.verification_status || "pending");
        }
      } catch (err) {
        toast.error(formatApiError(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const onChange = (key) => (e) => {
    const v = e.target.value;
    setForm((f) => ({
      ...f,
      [key]: ["followers", "avg_reel_views", "monthly_reach", "collab_price"].includes(
        key
      )
        ? Number(v || 0)
        : v,
    }));
  };

  const save = async (e) => {
    e?.preventDefault?.();
    setSaving(true);
    try {
      const updated = await InfluencerAPI.updateProfile(form);
      setVerifStatus(updated?.verification_status || verifStatus);
      toast.success("Profile saved.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const submitForVerification = async () => {
    setSubmittingVerif(true);
    try {
      await InfluencerAPI.submitVerification({
        kind: "influencer",
        documents: [],
        notes: form.bio || "Submitted from creator profile.",
      });
      toast.success("Verification request submitted.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSubmittingVerif(false);
    }
  };

  if (loading) {
    return (
      <div
        className="flex items-center justify-center py-20"
        data-testid="profile-loading"
      >
        <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="influencer-profile-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl sm:text-3xl font-display font-light text-primary dark:text-white">
            Your creator profile
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Complete every field so brands can discover you and send the right
            offers.
          </p>
        </div>
        <span
          className="inline-flex items-center gap-1.5 rounded-full bg-accent text-secondary px-3 py-1 text-xs font-semibold capitalize w-fit"
          data-testid="profile-verif-badge"
        >
          {verifStatus === "approved" ? (
            <BadgeCheck className="h-3.5 w-3.5" />
          ) : (
            <ShieldCheck className="h-3.5 w-3.5" />
          )}
          {verifStatus}
        </span>
      </div>

      <form
        onSubmit={save}
        className="space-y-8"
        data-testid="influencer-profile-form"
      >
        <Section title="Basics">
          <Field label="Handle / username">
            <Input
              value={form.username}
              onChange={onChange("username")}
              placeholder="@yourhandle"
              data-testid="profile-username"
            />
          </Field>
          <Field label="Phone">
            <Input
              value={form.phone}
              onChange={onChange("phone")}
              placeholder="+91 ..."
              data-testid="profile-phone"
            />
          </Field>
          <Field label="Country">
            <Input
              value={form.country}
              onChange={onChange("country")}
              data-testid="profile-country"
            />
          </Field>
          <Field label="State">
            <Input
              value={form.state}
              onChange={onChange("state")}
              data-testid="profile-state"
            />
          </Field>
          <Field label="City">
            <Input
              value={form.city}
              onChange={onChange("city")}
              data-testid="profile-city"
            />
          </Field>
          <Field label="Category">
            <select
              value={form.category}
              onChange={onChange("category")}
              data-testid="profile-category"
              className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="">Select a category</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
        </Section>

        <Section title="About you" cols={1}>
          <Field label="Short bio">
            <Textarea
              rows={4}
              value={form.bio}
              onChange={onChange("bio")}
              placeholder="What kind of content do you make? Who is your audience?"
              data-testid="profile-bio"
            />
          </Field>
        </Section>

        <Section title="Socials">
          <Field label="Instagram">
            <Input
              value={form.instagram}
              onChange={onChange("instagram")}
              placeholder="@handle"
              data-testid="profile-instagram"
            />
          </Field>
          <Field label="YouTube">
            <Input
              value={form.youtube}
              onChange={onChange("youtube")}
              placeholder="channel URL"
              data-testid="profile-youtube"
            />
          </Field>
          <Field label="Facebook">
            <Input
              value={form.facebook}
              onChange={onChange("facebook")}
              data-testid="profile-facebook"
            />
          </Field>
          <Field label="LinkedIn">
            <Input
              value={form.linkedin}
              onChange={onChange("linkedin")}
              data-testid="profile-linkedin"
            />
          </Field>
          <Field label="Personal website">
            <Input
              value={form.website}
              onChange={onChange("website")}
              data-testid="profile-website"
            />
          </Field>
        </Section>

        <Section title="Reach & pricing">
          <Field label="Followers">
            <Input
              type="number"
              min={0}
              value={form.followers}
              onChange={onChange("followers")}
              data-testid="profile-followers"
            />
          </Field>
          <Field label="Avg reel views">
            <Input
              type="number"
              min={0}
              value={form.avg_reel_views}
              onChange={onChange("avg_reel_views")}
              data-testid="profile-avg-reel-views"
            />
          </Field>
          <Field label="Monthly reach">
            <Input
              type="number"
              min={0}
              value={form.monthly_reach}
              onChange={onChange("monthly_reach")}
              data-testid="profile-monthly-reach"
            />
          </Field>
          <Field label="Collab price (₹)">
            <Input
              type="number"
              min={0}
              value={form.collab_price}
              onChange={onChange("collab_price")}
              data-testid="profile-collab-price"
            />
          </Field>
        </Section>

        <Section title="Payouts">
          <Field label="UPI">
            <Input
              value={form.upi}
              onChange={onChange("upi")}
              placeholder="yourhandle@upi"
              data-testid="profile-upi"
            />
          </Field>
          <Field label="GST (optional)">
            <Input
              value={form.gst}
              onChange={onChange("gst")}
              data-testid="profile-gst"
            />
          </Field>
        </Section>

        <div className="flex flex-col sm:flex-row gap-3 justify-end pt-2">
          <button
            type="button"
            onClick={submitForVerification}
            disabled={submittingVerif}
            data-testid="profile-submit-verification"
            className="inline-flex items-center justify-center gap-2 rounded-full border border-secondary text-secondary hover:bg-accent px-5 py-2.5 text-sm font-semibold disabled:opacity-60"
          >
            {submittingVerif ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ShieldCheck className="h-4 w-4" />
            )}
            Submit for verification
          </button>
          <button
            type="submit"
            disabled={saving}
            data-testid="profile-save"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-2.5 text-sm font-semibold disabled:opacity-60"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save changes
          </button>
        </div>
      </form>
    </div>
  );
}

function Section({ title, cols = 2, children }) {
  const grid = cols === 1 ? "grid-cols-1" : "grid-cols-1 md:grid-cols-2";
  return (
    <div className="rounded-2xl border border-border bg-card p-5 sm:p-7">
      <h3 className="text-sm font-semibold text-primary dark:text-white">
        {title}
      </h3>
      <div className={`mt-5 grid gap-4 ${grid}`}>{children}</div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

function stripNulls(obj) {
  const out = {};
  Object.entries(obj || {}).forEach(([k, v]) => {
    if (v !== null && v !== undefined) out[k] = v;
  });
  return out;
}
