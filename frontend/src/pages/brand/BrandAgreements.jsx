import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ScrollText, Plus, X as XIcon, Loader2, Search, IndianRupee, CalendarDays,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StatusChip, EmptyState } from "@/components/State";

export default function BrandAgreements() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/agreements");
      setItems(data.agreements || []);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-6" data-testid="brand-agreements">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">Digital Agreements</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Send a professional, signable agreement to a creator. Captures deliverables, timeline, payment, platform fee and cancellation policy.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          data-testid="new-agreement"
          className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap"
        >
          <Plus className="h-4 w-4" /> New agreement
        </button>
      </div>

      {loading ? (
        <div className="text-muted-foreground">Loading…</div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No agreements yet"
          description="Send your first digital agreement to lock in a creator with clear terms."
          action={
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold"
            >
              <Plus className="h-4 w-4" /> New agreement
            </button>
          }
          testId="brand-agreements-empty"
        />
      ) : (
        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-accent/40 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-3">Creator</th>
                <th className="text-left px-4 py-3">Campaign</th>
                <th className="text-right px-4 py-3">Amount</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((a) => (
                <tr key={a.id} className="hover:bg-accent/30" data-testid={`agreement-row-${a.id}`}>
                  <td className="px-4 py-3 font-semibold text-primary dark:text-white">{a.influencer_name}</td>
                  <td className="px-4 py-3 text-muted-foreground truncate max-w-[260px]">{a.campaign || "—"}</td>
                  <td className="px-4 py-3 text-right font-medium">₹{Number(a.payment_amount || 0).toLocaleString()}</td>
                  <td className="px-4 py-3"><StatusChip value={a.status} /></td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/agreements/${a.id}`}
                      data-testid={`agreement-view-${a.id}`}
                      className="inline-flex items-center gap-1 rounded-full border border-border hover:bg-accent px-3 py-1 text-xs font-semibold"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <NewAgreementModal
          onClose={() => setCreating(false)}
          onCreated={(a) => { setItems((arr) => [a, ...arr]); setCreating(false); navigate(`/agreements/${a.id}`); }}
        />
      )}
    </div>
  );
}

function NewAgreementModal({ onClose, onCreated }) {
  const [creators, setCreators] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    influencer_user_id: "",
    influencer_name: "",
    brand_name: "",
    campaign: "",
    campaign_id: "",
    deliverables_text: "",
    timeline: "",
    payment_amount: "",
    platform_fee_pct: "10",
    cancellation_policy: "",
    terms: "",
  });

  useEffect(() => {
    let alive = true;
    setSearching(true);
    (async () => {
      try {
        const [inf, cm, b] = await Promise.all([
          api.get("/influencers", { params: { q: search || undefined, limit: 20 } }),
          api.get("/campaigns").catch(() => ({ data: { campaigns: [] } })),
          api.get("/brands/me").catch(() => ({ data: { brand: null } })),
        ]);
        if (!alive) return;
        setCreators(inf.data.influencers || []);
        setCampaigns(cm.data.campaigns || []);
        const brand = b.data?.brand;
        if (brand && !form.brand_name) {
          setForm((f) => ({ ...f, brand_name: brand.company_name || "" }));
        }
      } catch (_) {}
      if (alive) setSearching(false);
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const fee = useMemo(() => {
    const amount = Number(form.payment_amount || 0);
    const pct = Number(form.platform_fee_pct || 0);
    return {
      platform_fee: Math.round((amount * pct) / 100 * 100) / 100,
      net: Math.round((amount - (amount * pct) / 100) * 100) / 100,
    };
  }, [form.payment_amount, form.platform_fee_pct]);

  const pickCreator = (cr) => {
    setForm((f) => ({
      ...f,
      influencer_user_id: cr.user_id,
      influencer_name: cr.username || cr.name || "Creator",
    }));
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!form.influencer_user_id) return toast.error("Pick a creator");
    if (!form.brand_name.trim()) return toast.error("Brand name is required");
    if (!form.influencer_name.trim()) return toast.error("Influencer name is required");
    if (!form.payment_amount || Number(form.payment_amount) < 0) return toast.error("Payment amount is required");
    setSubmitting(true);
    try {
      const payload = {
        influencer_user_id: form.influencer_user_id,
        brand_name: form.brand_name.trim(),
        influencer_name: form.influencer_name.trim(),
        campaign: form.campaign?.trim() || null,
        campaign_id: form.campaign_id || null,
        deliverables: form.deliverables_text.split("\n").map((s) => s.trim()).filter(Boolean),
        timeline: form.timeline || null,
        payment_amount: Number(form.payment_amount),
        platform_fee_pct: Number(form.platform_fee_pct || 10),
        cancellation_policy: form.cancellation_policy || null,
        terms: form.terms || null,
      };
      const { data } = await api.post("/agreements", payload);
      toast.success("Agreement sent for signature.");
      onCreated?.(data.agreement);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setSubmitting(false);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose} data-testid="new-agreement-modal">
      <div className="bg-card w-full max-w-3xl rounded-2xl border border-border p-6 max-h-[92vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-display text-primary dark:text-white">New digital agreement</h3>
          <button type="button" onClick={onClose} className="h-9 w-9 rounded-full hover:bg-accent flex items-center justify-center">
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="mt-5 space-y-4">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Select creator</label>
            <div className="relative mt-1">
              <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search creators…" className="pl-9" />
            </div>
            <div className="mt-2 max-h-44 overflow-y-auto rounded-xl border border-border divide-y divide-border">
              {searching && <div className="p-3 text-xs text-muted-foreground">Searching…</div>}
              {!searching && creators.length === 0 && <div className="p-3 text-xs text-muted-foreground">No creators found.</div>}
              {creators.map((cr) => (
                <button
                  key={cr.id}
                  type="button"
                  onClick={() => pickCreator(cr)}
                  data-testid={`agreement-pick-${cr.id}`}
                  className={`w-full text-left flex items-center gap-3 px-3 py-2.5 ${form.influencer_user_id === cr.user_id ? "bg-accent" : "hover:bg-accent/60"}`}
                >
                  <CreatorAvatar creator={cr} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold truncate">{cr.username || "Creator"}</div>
                    <div className="text-[11px] text-muted-foreground truncate">{cr.category || "—"}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Brand name">
              <Input value={form.brand_name} onChange={(e) => setForm({ ...form, brand_name: e.target.value })} placeholder="Acme Pvt Ltd" />
            </Field>
            <Field label="Influencer name">
              <Input value={form.influencer_name} onChange={(e) => setForm({ ...form, influencer_name: e.target.value })} placeholder="@creator" />
            </Field>
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Campaign title">
              <Input value={form.campaign} onChange={(e) => setForm({ ...form, campaign: e.target.value })} placeholder="Summer Drop · Reel #1" />
            </Field>
            <Field label="Link to existing campaign (optional)">
              <select
                value={form.campaign_id}
                onChange={(e) => {
                  const id = e.target.value;
                  const c = campaigns.find((x) => x.id === id);
                  setForm((f) => ({ ...f, campaign_id: id, campaign: c?.title || f.campaign }));
                }}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">— None —</option>
                {campaigns.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </select>
            </Field>
          </div>

          <Field label="Deliverables (one per line)">
            <Textarea rows={3} value={form.deliverables_text} onChange={(e) => setForm({ ...form, deliverables_text: e.target.value })} placeholder="1 Instagram Reel (≥30s)\n3 Stories with brand link\n1 YouTube Shorts cut-down" />
          </Field>

          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Timeline">
              <Input value={form.timeline} onChange={(e) => setForm({ ...form, timeline: e.target.value })} placeholder="Briefing: 24 Jun · Go-live: 03 Jul" />
            </Field>
            <Field label="Payment amount (₹)">
              <Input type="number" min="0" value={form.payment_amount} onChange={(e) => setForm({ ...form, payment_amount: e.target.value })} placeholder="50000" />
            </Field>
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Platform fee %">
              <Input type="number" min="0" max="100" value={form.platform_fee_pct} onChange={(e) => setForm({ ...form, platform_fee_pct: e.target.value })} />
            </Field>
            <div className="rounded-xl border border-border bg-background p-3 text-xs flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-muted-foreground">
                <IndianRupee className="h-3.5 w-3.5 text-secondary" /> Net to creator
              </div>
              <div className="font-semibold text-primary dark:text-white">₹{fee.net.toLocaleString()}</div>
            </div>
          </div>

          <Field label="Cancellation policy (optional override)">
            <Textarea rows={3} value={form.cancellation_policy} onChange={(e) => setForm({ ...form, cancellation_policy: e.target.value })} placeholder="Leave blank to use the default BrandKrt cancellation clause." />
          </Field>

          <Field label="Additional terms (optional)">
            <Textarea rows={2} value={form.terms} onChange={(e) => setForm({ ...form, terms: e.target.value })} />
          </Field>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-4 py-2 text-sm font-semibold">Cancel</button>
            <button
              type="submit"
              disabled={submitting}
              data-testid="agreement-submit"
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold disabled:opacity-60"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />} Send for signature
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CreatorAvatar({ creator }) {
  const [broken, setBroken] = useState(false);
  const url = creator.profile_photo_url || creator.avatar_url;
  const name = creator.username || creator.name || "Creator";
  if (url && !broken) {
    return (
      <img
        src={url}
        alt={name}
        onError={() => setBroken(true)}
        className="h-9 w-9 shrink-0 rounded-full border border-border object-cover"
      />
    );
  }
  return (
    <div className="h-9 w-9 shrink-0 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center font-semibold">
      {name.slice(0, 2).toUpperCase()}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
