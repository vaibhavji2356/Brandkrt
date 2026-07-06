import React, { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, BadgeCheck, Save, Loader2, Plus, X, FileText, ImageIcon } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";

const INDUSTRIES = [
  "Restaurant / Café", "Salon / Spa", "Gym / Fitness", "Clothing / Apparel", "Beauty / Cosmetics",
  "Food & Beverage", "Coaching / Education", "D2C Brand", "Home Business", "Local Shop",
  "Healthcare", "Real Estate", "Travel & Hospitality", "Technology", "Other",
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
  company_name: "", owner_name: "", phone: "", email: "",
  gst_number: "", registration_number: "", registration_proof_url: "",
  company_address: "", city: "", state: "", country: "", pin_code: "",
  industry: "", website: "", instagram: "", facebook: "", youtube: "",
  description: "", logo_url: "", cover_url: "",
  product_categories: [], product_images: [], documents: [],
  bank_details: { account_name: "", account_number: "", ifsc: "", bank_name: "" },
  upi: "",
};

const hydrateBrand = (brand = {}) => ({
  ...EMPTY,
  ...brand,
  bank_details: { ...EMPTY.bank_details, ...(brand.bank_details || {}) },
  product_categories: brand.product_categories || [],
  product_images: brand.product_images || [],
  documents: brand.documents || [],
});

export default function BrandProfile() {
  const { user } = useAuth();
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [verified, setVerified] = useState("pending");
  const [categoryDraft, setCategoryDraft] = useState("");

  const logoRef = useRef(null);
  const coverRef = useRef(null);
  const productRef = useRef(null);
  const docRef = useRef(null);
  const [uploading, setUploading] = useState({ logo: false, cover: false, product: false, doc: false });

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setBank = (k, v) => setForm((f) => ({ ...f, bank_details: { ...(f.bank_details || {}), [k]: v } }));

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/brands/me");
        const brand = data?.brand;
        if (brand) {
          setForm(hydrateBrand(brand));
          setVerified(brand.verification_status || "pending");
        } else if (user?.name) {
          set("company_name", user.name);
        }
      } catch (_) { /* not yet created */ }
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const uploadOne = async (file, folder) => {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post(`/uploads/${folder}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
    return data.url;
  };

  const pickLogo = async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    setUploading((u) => ({ ...u, logo: true }));
    try {
      const url = await uploadOne(f, "brand_logos");
      set("logo_url", url);
      window.dispatchEvent(new CustomEvent("brandkrt:profile-image-updated", {
        detail: { role: "brand", avatarUrl: url },
      }));
      toast.success("Logo updated.");
    }
    catch (err) { toast.error(formatApiError(err)); }
    finally { setUploading((u) => ({ ...u, logo: false })); e.target.value = ""; }
  };
  const pickCover = async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    setUploading((u) => ({ ...u, cover: true }));
    try { const url = await uploadOne(f, "brand_logos"); set("cover_url", url); toast.success("Cover updated."); }
    catch (err) { toast.error(formatApiError(err)); }
    finally { setUploading((u) => ({ ...u, cover: false })); e.target.value = ""; }
  };
  const pickProducts = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setUploading((u) => ({ ...u, product: true }));
    try {
      const urls = await Promise.all(files.map((f) => uploadOne(f, "products")));
      setForm((f) => ({ ...f, product_images: [...(f.product_images || []), ...urls] }));
      toast.success(`${urls.length} product image(s) uploaded.`);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setUploading((u) => ({ ...u, product: false })); e.target.value = ""; }
  };
  const pickDocs = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setUploading((u) => ({ ...u, doc: true }));
    try {
      const urls = await Promise.all(files.map((f) => uploadOne(f, "verification")));
      setForm((f) => ({ ...f, documents: [...(f.documents || []), ...urls] }));
      toast.success(`${urls.length} document(s) uploaded.`);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setUploading((u) => ({ ...u, doc: false })); e.target.value = ""; }
  };

  const removeAt = (key, idx) => setForm((f) => ({ ...f, [key]: f[key].filter((_, i) => i !== idx) }));

  const addCategory = () => {
    const v = categoryDraft.trim();
    if (!v) return;
    if (form.product_categories.includes(v)) { setCategoryDraft(""); return; }
    setForm((f) => ({ ...f, product_categories: [...f.product_categories, v] }));
    setCategoryDraft("");
  };

  const save = async (e) => {
    e.preventDefault();
    if (!form.company_name?.trim()) { toast.error("Business name is required."); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      ["id", "user_id", "status", "verification_status", "created_at", "updated_at"].forEach((k) => delete payload[k]);
      const saved = await api.put("/brands/me", payload);
      let updatedBrand = saved.data?.brand;
      try {
        const { data } = await api.get("/brands/me");
        updatedBrand = data?.brand || updatedBrand;
      } catch (_) {
        // The PUT response already contains the saved profile; avoid a false error if the follow-up read is slow.
      }
      if (!updatedBrand?.id) {
        throw new Error("Business profile could not be saved. Please try again.");
      }
      setForm(hydrateBrand(updatedBrand));
      setVerified(updatedBrand.verification_status || verified);
      toast.success("Business profile saved.");
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  };

  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <div className="h-10 w-48 rounded-full bg-muted/20 animate-pulse" />
        <div className="rounded-2xl border border-border bg-card p-6 animate-pulse space-y-4">
          <div className="h-40 rounded-2xl bg-muted/10" />
          <div className="h-24 w-full rounded-2xl bg-muted/10" />
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-20 rounded-2xl bg-muted/10" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const initials = (form.company_name || user?.name || user?.email || "B").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();

  return (
    <form onSubmit={save} className="space-y-8" data-testid="brand-profile-form">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Business Profile</h2>
        <p className="text-sm text-muted-foreground mt-1">A complete profile builds creator trust and unlocks the verified business badge.</p>
      </div>

      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <div
          className="relative h-40 md:h-48 bg-primary"
          style={form.cover_url
            ? { backgroundImage: `url(${form.cover_url})`, backgroundSize: "cover", backgroundPosition: "center" }
            : { backgroundImage: "radial-gradient(circle at 20% 50%, rgba(212,175,55,0.4), transparent 50%)" }}
          data-testid="brand-cover"
        >
          <button type="button" onClick={() => coverRef.current?.click()} className="absolute right-4 bottom-4 inline-flex items-center gap-2 rounded-full bg-background/90 backdrop-blur px-3 py-1.5 text-xs font-semibold border border-border" data-testid="upload-cover">
            {uploading.cover ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Camera className="h-3.5 w-3.5" />}
            {uploading.cover ? "Uploading…" : "Change cover"}
          </button>
          <input ref={coverRef} type="file" accept="image/*" onChange={pickCover} className="hidden" />
        </div>
        <div className="px-6 md:px-8 pb-6 md:pb-8">
          <div className="flex flex-col sm:flex-row sm:items-end sm:gap-6 -mt-12">
            <div className="relative h-24 w-24 rounded-2xl border-4 border-background bg-secondary text-secondary-foreground flex items-center justify-center text-2xl font-display font-semibold overflow-hidden shadow-luxe-sm" data-testid="brand-logo">
              {form.logo_url
                ? <img src={form.logo_url} alt="" className="h-full w-full object-cover" />
                : initials}
              <button type="button" onClick={() => logoRef.current?.click()} className="absolute inset-x-0 bottom-0 bg-black/50 text-white text-[10px] py-1 font-semibold inline-flex items-center justify-center gap-1" data-testid="upload-logo">
                {uploading.logo ? <Loader2 className="h-3 w-3 animate-spin" /> : <Camera className="h-3 w-3" />}
                {uploading.logo ? "…" : "Change"}
              </button>
              <input ref={logoRef} type="file" accept="image/*" onChange={pickLogo} className="hidden" />
            </div>
            <div className="mt-4 sm:mt-0 flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl md:text-3xl font-display font-light tracking-tight text-primary dark:text-white truncate">
                  {form.company_name || "Your business"}
                </h1>
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold capitalize ${
                  verified === "approved" ? "bg-success/10 text-success" :
                  verified === "rejected" ? "bg-destructive/10 text-destructive" : "bg-warning/10 text-warning"
                }`}>
                  <BadgeCheck className="h-3 w-3" /> {verified}
                </span>
              </div>
              <p className="text-sm text-muted-foreground mt-1 truncate">{user?.email}</p>
              <p className="text-xs text-muted-foreground mt-2">A clear logo + business description dramatically improves creator acceptance rates.</p>
            </div>
          </div>
        </div>
      </div>

      <Section title="Business information" description="The basics creators will see on every invite." testId="section-business">
        <div className="grid sm:grid-cols-2 gap-5">
          <Field label="Business name *"><Input value={form.company_name} onChange={(e) => set("company_name", e.target.value)} required data-testid="field-company" /></Field>
          <Field label="Owner name"><Input value={form.owner_name || ""} onChange={(e) => set("owner_name", e.target.value)} data-testid="field-owner" /></Field>
          <Field label="Business category">
            <select value={form.industry || ""} onChange={(e) => set("industry", e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" data-testid="field-industry">
              <option value="">Select category…</option>
              {INDUSTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Website"><Input value={form.website || ""} onChange={(e) => set("website", e.target.value)} placeholder="https://yourbusiness.com" data-testid="field-website" /></Field>
          <Field label="GST number (optional)"><Input value={form.gst_number || ""} onChange={(e) => set("gst_number", e.target.value)} placeholder="22AAAAA0000A1Z5" data-testid="field-gst" /></Field>
          <Field label="Business registration number (optional)"><Input value={form.registration_number || ""} onChange={(e) => set("registration_number", e.target.value)} data-testid="field-reg" /></Field>
          <div className="sm:col-span-2">
            <Field label="Business description" hint="Tell creators what your business does, who your customers are, and the vibe you want in the content.">
              <Textarea rows={4} value={form.description || ""} onChange={(e) => set("description", e.target.value)} data-testid="field-description" />
            </Field>
          </div>
        </div>
      </Section>

      <Section title="Contact" description="How creators and the BrandKrt team can reach you." testId="section-contact">
        <div className="grid sm:grid-cols-2 gap-5">
          <Field label="Business email"><Input type="email" value={form.email || ""} onChange={(e) => set("email", e.target.value)} placeholder="hello@yourbusiness.com" data-testid="field-email" /></Field>
          <Field label="Business phone"><Input value={form.phone || ""} onChange={(e) => set("phone", e.target.value)} placeholder="+91…" data-testid="field-phone" /></Field>
        </div>
      </Section>

      <Section title="Address" description="Useful for matching with creators near your business." testId="section-address">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <div className="sm:col-span-2 lg:col-span-3">
            <Field label="Business address"><Input value={form.company_address || ""} onChange={(e) => set("company_address", e.target.value)} data-testid="field-address" /></Field>
          </div>
          <Field label="City"><Input value={form.city || ""} onChange={(e) => set("city", e.target.value)} placeholder="Pune" data-testid="field-city" /></Field>
          <Field label="State"><Input value={form.state || ""} onChange={(e) => set("state", e.target.value)} placeholder="Maharashtra" data-testid="field-state" /></Field>
          <Field label="Country"><Input value={form.country || ""} onChange={(e) => set("country", e.target.value)} placeholder="India" data-testid="field-country" /></Field>
          <Field label="PIN code"><Input value={form.pin_code || ""} onChange={(e) => set("pin_code", e.target.value)} placeholder="411001" data-testid="field-pin" /></Field>
        </div>
      </Section>

      <Section title="Social presence" description="Optional but recommended — creators check these before accepting invites." testId="section-social">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <Field label="Instagram"><Input value={form.instagram || ""} onChange={(e) => set("instagram", e.target.value)} placeholder="https://instagram.com/yourbiz" data-testid="field-ig" /></Field>
          <Field label="Facebook"><Input value={form.facebook || ""} onChange={(e) => set("facebook", e.target.value)} placeholder="https://facebook.com/yourbiz" data-testid="field-fb" /></Field>
          <Field label="YouTube"><Input value={form.youtube || ""} onChange={(e) => set("youtube", e.target.value)} placeholder="https://youtube.com/@yourbiz" data-testid="field-yt" /></Field>
        </div>
      </Section>

      <Section title="Product / service categories" description="Helps us match you with the right creators." testId="section-categories">
        <div className="flex flex-wrap gap-2">
          {form.product_categories.map((c, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-full bg-accent text-secondary px-3 py-1 text-xs font-semibold" data-testid={`chip-cat-${i}`}>
              {c}
              <button type="button" onClick={() => removeAt("product_categories", i)} aria-label="Remove" className="hover:text-destructive"><X className="h-3 w-3" /></button>
            </span>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <Input value={categoryDraft} onChange={(e) => setCategoryDraft(e.target.value)} placeholder="e.g. Vegan desserts" data-testid="field-cat-input" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCategory(); } }} />
          <button type="button" onClick={addCategory} className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent" data-testid="field-cat-add">
            <Plus className="h-4 w-4" /> Add
          </button>
        </div>
      </Section>

      <Section title="Product images" description="Upload photos creators can reference for the campaign." testId="section-product-images">
        <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
          {form.product_images.map((url, i) => (
            <div key={i} className="relative aspect-square rounded-xl overflow-hidden border border-border" data-testid={`pi-${i}`}>
              <img src={url} alt="" className="w-full h-full object-cover" />
              <button type="button" onClick={() => removeAt("product_images", i)} className="absolute top-1 right-1 h-6 w-6 rounded-full bg-black/60 text-white inline-flex items-center justify-center"><X className="h-3 w-3" /></button>
            </div>
          ))}
          <button type="button" onClick={() => productRef.current?.click()} className="aspect-square rounded-xl border-2 border-dashed border-border flex items-center justify-center text-muted-foreground hover:bg-accent" data-testid="upload-product-btn">
            {uploading.product ? <Loader2 className="h-5 w-5 animate-spin" /> : <ImageIcon className="h-6 w-6" />}
          </button>
          <input ref={productRef} type="file" accept="image/*" multiple onChange={pickProducts} className="hidden" />
        </div>
      </Section>

      <Section title="Business documents" description="GST cert, registration proof, etc. Stays private and is used only for verification." testId="section-docs">
        <div className="space-y-2">
          {form.documents.map((url, i) => (
            <div key={i} className="flex items-center justify-between rounded-xl border border-border bg-background px-4 py-2 text-sm" data-testid={`doc-${i}`}>
              <a href={url} target="_blank" rel="noreferrer" className="flex items-center gap-2 truncate text-foreground hover:text-secondary">
                <FileText className="h-4 w-4 text-secondary shrink-0" /> <span className="truncate">{url.split("/").pop()}</span>
              </a>
              <button type="button" onClick={() => removeAt("documents", i)} className="text-muted-foreground hover:text-destructive"><X className="h-4 w-4" /></button>
            </div>
          ))}
          <button type="button" onClick={() => docRef.current?.click()} className="inline-flex items-center gap-2 rounded-full border border-dashed border-border px-4 py-2 text-sm font-semibold hover:bg-accent" data-testid="upload-doc-btn">
            {uploading.doc ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {uploading.doc ? "Uploading…" : "Add document"}
          </button>
          <input ref={docRef} type="file" accept="image/*,.pdf" multiple onChange={pickDocs} className="hidden" />
        </div>
      </Section>

      <Section title="Payout / billing" description="Used for invoicing and escrow refunds. Always kept private." testId="section-bank">
        <div className="grid sm:grid-cols-2 gap-5">
          <Field label="UPI ID"><Input value={form.upi || ""} onChange={(e) => set("upi", e.target.value)} placeholder="yourname@upi" data-testid="field-upi" /></Field>
          <Field label="Account holder name"><Input value={form.bank_details?.account_name || ""} onChange={(e) => setBank("account_name", e.target.value)} data-testid="field-bank-holder" /></Field>
          <Field label="Bank name"><Input value={form.bank_details?.bank_name || ""} onChange={(e) => setBank("bank_name", e.target.value)} data-testid="field-bank-name" /></Field>
          <Field label="Account number"><Input value={form.bank_details?.account_number || ""} onChange={(e) => setBank("account_number", e.target.value)} data-testid="field-bank-acc" /></Field>
          <Field label="IFSC"><Input value={form.bank_details?.ifsc || ""} onChange={(e) => setBank("ifsc", e.target.value)} data-testid="field-bank-ifsc" /></Field>
        </div>
      </Section>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-end gap-3">
        <p className="text-xs text-muted-foreground sm:mr-auto">Changes are saved to your business profile.</p>
        <button
          type="submit"
          disabled={saving}
          data-testid="brand-profile-save"
          className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold disabled:opacity-60"
        >
          {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <><Save className="h-4 w-4" /> Save profile</>}
        </button>
      </div>
    </form>
  );
}
