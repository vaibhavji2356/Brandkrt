import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Handshake, Plus, IndianRupee, Calendar, Tag, Eye, Send, CheckCircle2,
  ThumbsDown, MessageCircle, X as XIcon, Loader2, Search,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StatusChip, EmptyState } from "@/components/State";

const PLATFORMS = ["instagram", "youtube", "facebook", "linkedin", "tiktok", "other"];

export default function InfluencerCollaborations() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [tab, setTab] = useState("inbox"); // inbox | sent
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/collaborations");
      setItems(data.collaborations || []);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const visible = useMemo(() => items, [items]); // eslint-disable-line no-unused-vars
  const inbox = items.filter((c) => c._isInbox !== false); // eslint-disable-line no-unused-vars
  const [currentUserId, setCurrentUserId] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        setCurrentUserId(data.user?.id || null);
      } catch (_) {}
    })();
  }, []);

  const inboxItems = items.filter((c) => c.invited_user_id === currentUserId);
  const sentItems = items.filter((c) => c.owner_user_id === currentUserId);
  const list = tab === "inbox" ? inboxItems : sentItems;

  const setStatus = async (id, status, confirmText) => {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusyId(id);
    try {
      const { data } = await api.patch(`/collaborations/${id}/status`, { status });
      toast.success(`Collaboration ${status}`);
      setItems((arr) => arr.map((x) => (x.id === id ? data.collaboration : x)));
      if (status === "accepted") {
        // open chat
        try {
          const res = await api.post("/conversations", { context_type: "collab", context_id: id });
          if (res.data?.conversation?.id) {
            navigate(`/influencer/messages?conversation_id=${res.data.conversation.id}`);
            return;
          }
        } catch (_) { /* non-blocking */ }
      }
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusyId(null);
  };

  const openChat = async (collab) => {
    try {
      const { data } = await api.post("/conversations", { context_type: "collab", context_id: collab.id });
      navigate(`/influencer/messages?conversation_id=${data.conversation.id}`);
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  return (
    <div className="space-y-6" data-testid="influencer-collaborations">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">Creator Collaborations</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Team up with other creators on joint content, swaps and barters. Invite a creator or accept incoming requests.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          data-testid="new-collab"
          className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold whitespace-nowrap"
        >
          <Plus className="h-4 w-4" /> New collaboration
        </button>
      </div>

      <div className="inline-flex rounded-full border border-border bg-card p-1" data-testid="collab-tabs">
        {["inbox", "sent"].map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            data-testid={`collab-tab-${t}`}
            className={`px-4 py-1.5 text-xs font-semibold rounded-full capitalize ${
              tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-primary dark:hover:text-white"
            }`}
          >
            {t} ({t === "inbox" ? inboxItems.length : sentItems.length})
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-muted-foreground">Loading…</div>
      ) : list.length === 0 ? (
        <EmptyState
          icon={Handshake}
          title={tab === "inbox" ? "No collaboration requests yet" : "You haven't sent any requests"}
          description={
            tab === "inbox"
              ? "When another creator invites you, requests will land here."
              : "Discover creators and send them a collaboration brief — joint reels, swaps or co-hosted streams."
          }
          action={
            tab === "sent" ? (
              <button
                type="button"
                onClick={() => setCreating(true)}
                className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold"
              >
                <Plus className="h-4 w-4" /> New collaboration
              </button>
            ) : null
          }
          testId={`collab-empty-${tab}`}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {list.map((c) => (
            <CollabCard
              key={c.id}
              c={c}
              isOwner={c.owner_user_id === currentUserId}
              busy={busyId === c.id}
              onAccept={() => setStatus(c.id, "accepted")}
              onReject={() => setStatus(c.id, "rejected", "Decline this collaboration request?")}
              onCancel={() => setStatus(c.id, "cancelled", "Cancel this collaboration request?")}
              onChat={() => openChat(c)}
            />
          ))}
        </div>
      )}

      {creating && (
        <NewCollabModal
          onClose={() => setCreating(false)}
          onCreated={(c) => { setItems((arr) => [c, ...arr]); setCreating(false); setTab("sent"); }}
        />
      )}
    </div>
  );
}

function CollabCard({ c, isOwner, busy, onAccept, onReject, onCancel, onChat }) {
  const showAcceptReject = !isOwner && c.status === "pending";
  const showCancel = isOwner && c.status === "pending";
  const canChat = c.status === "accepted";

  return (
    <div className="rounded-2xl border border-border bg-card p-5 flex flex-col" data-testid={`collab-card-${c.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-display text-lg text-primary dark:text-white truncate">{c.title}</h3>
          <p className="text-xs text-muted-foreground capitalize mt-0.5">
            {c.platform} · {c.category || "—"} · by {c.owner_name || "Creator"}
          </p>
        </div>
        <StatusChip value={c.status} />
      </div>

      {c.description && <p className="mt-3 text-sm text-foreground/90 line-clamp-3">{c.description}</p>}

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <Pill icon={IndianRupee} label="Budget" value={`₹${Number(c.budget || 0).toLocaleString()}`} />
        <Pill icon={Calendar} label="Deadline" value={c.deadline || "—"} />
        <Pill icon={Tag} label="Category" value={c.category || "—"} />
        <Pill icon={Eye} label="Expected views" value={Number(c.expected_views || 0).toLocaleString()} />
      </div>

      {c.deliverables?.length > 0 && (
        <ul className="mt-3 text-xs text-foreground/90 list-disc list-inside space-y-0.5">
          {c.deliverables.slice(0, 4).map((d, i) => <li key={i} className="truncate">{d}</li>)}
        </ul>
      )}

      <div className="mt-auto pt-4 flex flex-wrap gap-2">
        {showAcceptReject && (
          <>
            <button
              type="button"
              onClick={onAccept}
              disabled={busy}
              data-testid={`collab-accept-${c.id}`}
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} Accept
            </button>
            <button
              type="button"
              onClick={onReject}
              disabled={busy}
              data-testid={`collab-reject-${c.id}`}
              className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
            >
              <ThumbsDown className="h-3.5 w-3.5" /> Decline
            </button>
          </>
        )}
        {showCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            data-testid={`collab-cancel-${c.id}`}
            className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
          >
            <XIcon className="h-3.5 w-3.5" /> Cancel request
          </button>
        )}
        {canChat && (
          <button
            type="button"
            onClick={onChat}
            data-testid={`collab-chat-${c.id}`}
            className="inline-flex items-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-3 py-1.5 text-xs font-semibold"
          >
            <MessageCircle className="h-3.5 w-3.5" /> Open chat
          </button>
        )}
      </div>
    </div>
  );
}

function Pill({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-border bg-background p-2">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3 text-secondary" /> {label}
      </div>
      <div className="text-sm font-semibold text-primary dark:text-white truncate mt-0.5">{value}</div>
    </div>
  );
}

function NewCollabModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: "",
    description: "",
    platform: "instagram",
    budget: "",
    deadline: "",
    category: "",
    expected_views: "",
    deliverables_text: "",
    invited_influencer_id: "",
  });
  const [creators, setCreators] = useState([]);
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let alive = true;
    setSearching(true);
    (async () => {
      try {
        const { data } = await api.get("/influencers", { params: { q: search || undefined, limit: 20 } });
        if (alive) setCreators(data.influencers || []);
      } catch (_) { /* ignore */ }
      if (alive) setSearching(false);
    })();
    return () => { alive = false; };
  }, [search]);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!form.invited_influencer_id) return toast.error("Pick a creator to invite");
    if (!form.title.trim()) return toast.error("Title is required");
    if (!form.budget || Number(form.budget) < 0) return toast.error("Budget is required");
    setSubmitting(true);
    try {
      const payload = {
        invited_influencer_id: form.invited_influencer_id,
        title: form.title.trim(),
        description: form.description.trim(),
        platform: form.platform,
        budget: Number(form.budget),
        deadline: form.deadline || null,
        category: form.category || null,
        expected_views: Number(form.expected_views || 0),
        deliverables: form.deliverables_text.split("\n").map((s) => s.trim()).filter(Boolean),
      };
      const { data } = await api.post("/collaborations", payload);
      toast.success("Collaboration request sent.");
      onCreated?.(data.collaboration);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setSubmitting(false);
  };

  const selectedCreator = creators.find((c) => c.id === form.invited_influencer_id);

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose} data-testid="new-collab-modal">
      <div className="bg-card w-full max-w-2xl rounded-2xl border border-border p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-display text-primary dark:text-white">New collaboration</h3>
          <button type="button" onClick={onClose} className="h-9 w-9 rounded-full hover:bg-accent flex items-center justify-center" data-testid="modal-close">
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="mt-5 space-y-4">
          {/* Creator picker */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Invite creator</label>
            <div className="relative mt-1">
              <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search creators by handle or name…"
                className="pl-9"
                data-testid="collab-search-creators"
              />
            </div>
            <div className="mt-2 max-h-44 overflow-y-auto rounded-xl border border-border divide-y divide-border">
              {searching && <div className="p-3 text-xs text-muted-foreground">Searching…</div>}
              {!searching && creators.length === 0 && <div className="p-3 text-xs text-muted-foreground">No creators found.</div>}
              {creators.map((cr) => (
                <button
                  key={cr.id}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, invited_influencer_id: cr.id }))}
                  data-testid={`collab-pick-${cr.id}`}
                  className={`w-full text-left flex items-center gap-3 px-3 py-2.5 ${
                    form.invited_influencer_id === cr.id ? "bg-accent" : "hover:bg-accent/60"
                  }`}
                >
                  <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center font-semibold">
                    {(cr.username || "U").slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold truncate">{cr.username || "Creator"}</div>
                    <div className="text-[11px] text-muted-foreground truncate">
                      {cr.category || "—"} · {cr.followers ? `${Number(cr.followers).toLocaleString()} followers` : ""}
                    </div>
                  </div>
                  {form.invited_influencer_id === cr.id && <CheckCircle2 className="h-4 w-4 text-secondary" />}
                </button>
              ))}
            </div>
            {selectedCreator && (
              <p className="mt-1 text-[11px] text-secondary">Inviting: {selectedCreator.username || "creator"}</p>
            )}
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Collaboration title">
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Joint reel · Mumbai foodie tour" data-testid="collab-field-title" />
            </Field>
            <Field label="Platform">
              <select
                value={form.platform}
                onChange={(e) => setForm({ ...form, platform: e.target.value })}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                data-testid="collab-field-platform"
              >
                {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Budget (₹)">
              <Input type="number" min="0" value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })} placeholder="0 for barter" data-testid="collab-field-budget" />
            </Field>
            <Field label="Deadline">
              <Input type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} data-testid="collab-field-deadline" />
            </Field>
            <Field label="Category">
              <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="Food, Travel, Fashion…" data-testid="collab-field-category" />
            </Field>
            <Field label="Expected views">
              <Input type="number" min="0" value={form.expected_views} onChange={(e) => setForm({ ...form, expected_views: e.target.value })} placeholder="50000" data-testid="collab-field-views" />
            </Field>
          </div>

          <Field label="Description">
            <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What's the idea? Who handles what?" data-testid="collab-field-description" />
          </Field>

          <Field label="Deliverables (one per line)">
            <Textarea rows={3} value={form.deliverables_text} onChange={(e) => setForm({ ...form, deliverables_text: e.target.value })} placeholder="1 Instagram Reel\n1 cross-post Story\n1 YouTube Shorts cut-down" data-testid="collab-field-deliverables" />
          </Field>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="inline-flex items-center gap-2 rounded-full border border-border hover:bg-accent px-4 py-2 text-sm font-semibold">
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              data-testid="collab-submit"
              className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold disabled:opacity-60"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Send request
            </button>
          </div>
        </form>
      </div>
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
