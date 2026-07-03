import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Megaphone, Plus, Filter, X, ImageIcon, Loader2, Calendar, IndianRupee,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StatusChip, EmptyState } from "@/components/State";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "draft", label: "Drafts" },
  { key: "active", label: "Active" },
  { key: "paused", label: "Paused" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

const PLATFORMS = ["instagram", "youtube", "facebook", "linkedin", "tiktok", "other"];
const CONTENT_TYPES = ["Reel", "Story", "Post", "Short", "Long-form video", "Live stream", "UGC", "Other"];
const PAYMENT_TYPES = ["Fixed fee", "Per post", "Product + cash", "Barter / product only", "Performance-based"];
const VISIBILITY_OPTIONS = [
  { key: "public", label: "Public — listed in the creator marketplace" },
  { key: "invite_only", label: "Invite only — visible to creators you invite" },
];
const LANGUAGES = ["English", "Hindi", "Marathi", "Tamil", "Telugu", "Bengali", "Gujarati", "Kannada", "Malayalam", "Punjabi", "Other"];

const EMPTY_CAMPAIGN = {
  title: "",
  description: "",
  platform: "instagram",
  content_type: "Reel",
  required_followers: 0,
  required_avg_views: 0,
  budget: 0,
  payment_type: "Fixed fee",
  deadline: "",
  deliverables: [],
  product_details: "",
  product_images: [],
  promotion_links: [],
  visibility: "public",
  target_categories: [],
  preferred_language: "English",
  preferred_location: "",
};

export default function BrandCampaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [params, setParams] = useSearchParams();
  const [showNew, setShowNew] = useState(params.get("new") === "1");
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/campaigns");
      setCampaigns(data.campaigns || []);
    } catch (err) { toast.error(formatApiError(err)); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);
  useEffect(() => { setShowNew(params.get("new") === "1"); }, [params]);

  const filtered = useMemo(() => (
    filter === "all" ? campaigns : campaigns.filter((c) => c.status === filter)
  ), [campaigns, filter]);

  const closeNew = () => { setShowNew(false); params.delete("new"); setParams(params, { replace: true }); };

  return (
    <div className="space-y-6" data-testid="brand-campaigns">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">Campaign Manager</h2>
          <p className="text-sm text-muted-foreground mt-1">Plan, launch and track every creator campaign in one place.</p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          data-testid="campaign-new-btn"
          className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold"
        >
          <Plus className="h-4 w-4" /> New campaign
        </button>
      </div>

      <div className="flex items-center gap-2 overflow-x-auto pb-1" data-testid="campaign-filters">
        <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            data-testid={`campaign-filter-${f.key}`}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap border transition-colors ${
              filter === f.key ? "bg-primary text-primary-foreground border-primary" : "bg-card border-border text-foreground/80 hover:bg-accent"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading && <div className="text-muted-foreground">Loading…</div>}

      {!loading && filtered.length === 0 && (
        <EmptyState
          icon={Megaphone}
          title="No campaigns yet"
          description="Create your first campaign in a minute — pick a platform, share the brief, set a budget, and invite creators."
          action={<button onClick={() => setShowNew(true)} className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold"><Plus className="h-4 w-4" /> Create campaign</button>}
          testId="campaigns-empty"
        />
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => navigate(`/brand/campaigns/${c.id}`)}
            data-testid={`campaign-card-${c.id}`}
            className="text-left rounded-2xl border border-border bg-card p-5 hover:-translate-y-0.5 hover:shadow-luxe-sm transition-all"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-primary dark:text-white truncate">{c.title}</h3>
                <p className="text-xs text-muted-foreground mt-0.5 capitalize">{c.platform} · {c.content_type || "Content"}</p>
              </div>
              <StatusChip value={c.status} />
            </div>
            {c.description && <p className="mt-3 text-sm text-muted-foreground line-clamp-2">{c.description}</p>}
            <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1"><IndianRupee className="h-3 w-3" /> {Number(c.budget || 0).toLocaleString()}</span>
              <span className="inline-flex items-center gap-1"><Calendar className="h-3 w-3" /> {c.deadline || "No deadline"}</span>
            </div>
          </button>
        ))}
      </div>

      <NewCampaignDialog open={showNew} onClose={closeNew} onCreated={(c) => { setCampaigns((arr) => [c, ...arr]); closeNew(); navigate(`/brand/campaigns/${c.id}`); }} />
    </div>
  );
}

/* ---------- New Campaign dialog ---------- */
function ChipInput({ label, value, onChange, placeholder, testId }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    if (value.includes(v)) { setDraft(""); return; }
    onChange([...value, v]);
    setDraft("");
  };
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</label>
      <div className="mt-2 flex flex-wrap gap-2">
        {value.map((v, i) => (
          <span key={i} className="inline-flex items-center gap-1 rounded-full bg-accent text-secondary px-3 py-1 text-xs font-semibold">
            {v}
            <button type="button" onClick={() => onChange(value.filter((_, k) => k !== i))} aria-label="Remove"><X className="h-3 w-3" /></button>
          </span>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={placeholder} data-testid={`${testId}-input`}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <button type="button" onClick={add} className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-2 text-xs font-semibold hover:bg-accent" data-testid={`${testId}-add`}>
          <Plus className="h-3 w-3" /> Add
        </button>
      </div>
    </div>
  );
}

function NewCampaignDialog({ open, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_CAMPAIGN);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = React.useRef(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => { if (!open) setForm(EMPTY_CAMPAIGN); }, [open]);

  const pickImages = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setUploading(true);
    try {
      const urls = await Promise.all(files.map(async (f) => {
        const fd = new FormData();
        fd.append("file", f);
        const { data } = await api.post("/uploads/products", fd, { headers: { "Content-Type": "multipart/form-data" } });
        return data.url;
      }));
      set("product_images", [...form.product_images, ...urls]);
      toast.success(`${urls.length} image(s) uploaded.`);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setUploading(false); e.target.value = ""; }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) { toast.error("Campaign title is required."); return; }
    if (Number(form.budget) <= 0) { toast.error("Set a non-zero budget."); return; }
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        budget: Number(form.budget) || 0,
        required_followers: Number(form.required_followers) || 0,
        required_avg_views: Number(form.required_avg_views) || 0,
      };
      const { data } = await api.post("/campaigns", payload);
      toast.success("Campaign created as draft. Activate it from the details page.");
      onCreated?.(data.campaign);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSubmitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="new-campaign-dialog">
        <DialogHeader>
          <DialogTitle className="text-2xl font-display font-light">Create a campaign</DialogTitle>
          <DialogDescription>Share the brief once — invite as many creators as you want from one campaign.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Campaign title *</label>
              <Input className="mt-2" value={form.title} onChange={(e) => set("title", e.target.value)} required placeholder="e.g. Launch of our new summer menu" data-testid="nc-title" />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Campaign description</label>
              <Textarea className="mt-2" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="What story should creators tell about your brand?" data-testid="nc-description" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Platform</label>
              <select value={form.platform} onChange={(e) => set("platform", e.target.value)} className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="nc-platform">
                {PLATFORMS.map((p) => <option key={p} value={p} className="capitalize">{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Content type</label>
              <select value={form.content_type} onChange={(e) => set("content_type", e.target.value)} className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="nc-content-type">
                {CONTENT_TYPES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Min. required followers</label>
              <Input className="mt-2" type="number" min="0" value={form.required_followers} onChange={(e) => set("required_followers", e.target.value)} data-testid="nc-followers" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Min. average views</label>
              <Input className="mt-2" type="number" min="0" value={form.required_avg_views} onChange={(e) => set("required_avg_views", e.target.value)} data-testid="nc-views" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Total budget (₹) *</label>
              <Input className="mt-2" type="number" min="0" value={form.budget} onChange={(e) => set("budget", e.target.value)} required data-testid="nc-budget" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Payment type</label>
              <select value={form.payment_type} onChange={(e) => set("payment_type", e.target.value)} className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="nc-payment-type">
                {PAYMENT_TYPES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Deadline</label>
              <Input className="mt-2" type="date" value={form.deadline} onChange={(e) => set("deadline", e.target.value)} data-testid="nc-deadline" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Preferred language</label>
              <select value={form.preferred_language} onChange={(e) => set("preferred_language", e.target.value)} className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="nc-language">
                {LANGUAGES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Preferred location</label>
              <Input className="mt-2" value={form.preferred_location} onChange={(e) => set("preferred_location", e.target.value)} placeholder="e.g. Pune, India" data-testid="nc-location" />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Campaign visibility</label>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                {VISIBILITY_OPTIONS.map((o) => (
                  <button
                    key={o.key}
                    type="button"
                    onClick={() => set("visibility", o.key)}
                    data-testid={`nc-visibility-${o.key}`}
                    className={`text-left rounded-xl border px-3 py-2 text-xs ${
                      form.visibility === o.key ? "border-secondary bg-accent text-secondary" : "border-border hover:bg-accent"
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <ChipInput label="Deliverables" value={form.deliverables} onChange={(v) => set("deliverables", v)} placeholder="e.g. 1 Reel + 3 stories" testId="nc-deliverables" />
          <ChipInput label="Target creator categories" value={form.target_categories} onChange={(v) => set("target_categories", v)} placeholder="e.g. Food, Lifestyle" testId="nc-categories" />
          <ChipInput label="Promotion links (optional)" value={form.promotion_links} onChange={(v) => set("promotion_links", v)} placeholder="https://yourbiz.com/landing" testId="nc-promo-links" />

          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Product details</label>
            <Textarea className="mt-2" rows={3} value={form.product_details} onChange={(e) => set("product_details", e.target.value)} placeholder="Describe the product or service creators will be promoting." data-testid="nc-product-details" />
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Product images</label>
            <div className="mt-2 grid grid-cols-3 md:grid-cols-5 gap-3">
              {form.product_images.map((u, i) => (
                <div key={i} className="relative aspect-square rounded-xl overflow-hidden border border-border">
                  <img src={u} alt="" className="w-full h-full object-cover" />
                  <button type="button" onClick={() => set("product_images", form.product_images.filter((_, k) => k !== i))} className="absolute top-1 right-1 h-6 w-6 rounded-full bg-black/60 text-white inline-flex items-center justify-center"><X className="h-3 w-3" /></button>
                </div>
              ))}
              <button type="button" onClick={() => fileRef.current?.click()} className="aspect-square rounded-xl border-2 border-dashed border-border flex items-center justify-center text-muted-foreground hover:bg-accent" data-testid="nc-upload">
                {uploading ? <Loader2 className="h-5 w-5 animate-spin" /> : <ImageIcon className="h-6 w-6" />}
              </button>
              <input ref={fileRef} type="file" accept="image/*" multiple onChange={pickImages} className="hidden" />
            </div>
          </div>

          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2 border-t border-border">
            <button type="button" onClick={onClose} className="inline-flex items-center justify-center rounded-full border border-border px-5 py-2.5 text-sm font-semibold hover:bg-accent">Cancel</button>
            <button type="submit" disabled={submitting} data-testid="nc-submit" className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 text-sm font-semibold disabled:opacity-60">
              {submitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</> : <><Plus className="h-4 w-4" /> Create campaign</>}
            </button>
          </div>

          <p className="text-xs text-muted-foreground">
            Your campaign will be saved as a <strong>draft</strong>. Move it to <strong>active</strong> from the campaign details page once you&apos;re ready. {" "}
            <Link to="/brand/discover" className="text-secondary hover:underline">Discover creators →</Link>
          </p>
        </form>
      </DialogContent>
    </Dialog>
  );
}
