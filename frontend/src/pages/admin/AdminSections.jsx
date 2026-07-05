import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { StatusChip } from "@/components/State";

function Section({ title, children }) {
  return <div className="space-y-4"><h2 className="text-2xl font-display font-light text-primary dark:text-white">{title}</h2>{children}</div>;
}

export function AdminUsers() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(null);
  const [detail, setDetail] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const r = await api.get("/admin/users", { params: { q: q || undefined, role: role || undefined } });
      setRows(r.data.users || []);
    } catch (e) {
      setRows([]);
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  const openUser = async (u) => {
    try {
      setBusy(true);
      setActive(u);
      setOpen(true);
      const { data } = await api.get(`/admin/users/${u.id}`);
      setDetail(data);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const suspendUser = async (suspended) => {
    if (!active) return;
    try {
      setBusy(true);
      const { data } = await api.post(`/admin/users/${active.id}/suspend`, { suspended });
      setDetail(data);
      setActive(data.user);
      setRows((list) => list.map((u) => (u.id === data.user.id ? data.user : u)));
      toast.success(suspended ? "User suspended." : "User reactivated.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteUser = async () => {
    if (!active) return;
    if (!window.confirm(`Permanently delete ${active.email}? This cannot be undone.`)) return;
    try {
      setBusy(true);
      await api.delete(`/admin/users/${active.id}`);
      setRows((list) => list.filter((u) => u.id !== active.id));
      setOpen(false);
      setActive(null);
      setDetail(null);
      toast.success("User deleted.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  const history = detail?.history || {};
  const profile = detail?.profile || {};
  const currentUser = detail?.user || active;

  return (
    <Section title="Users">
      <div className="flex gap-3">
        <Input placeholder="Search by name or email..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="users-search" className="max-w-sm" />
        <select value={role} onChange={(e) => setRole(e.target.value)} data-testid="users-role-filter" className="rounded-lg border border-border bg-background px-3 text-sm">
          <option value="">All roles</option><option value="admin">Admin</option><option value="brand">Brand</option><option value="influencer">Influencer</option>
        </select>
        <button onClick={load} className="rounded-full bg-primary text-primary-foreground px-5 py-2 text-sm font-semibold" data-testid="users-search-btn">Search</button>
      </div>
      <div className="rounded-2xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-accent dark:bg-card text-left">
            <tr><th className="px-4 py-3">Name</th><th className="px-4 py-3">Email</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Verified</th><th className="px-4 py-3">Created</th></tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id} onClick={() => openUser(u)} className="border-t border-border cursor-pointer hover:bg-accent/60" data-testid={`user-row-${u.id}`}>
                <td className="px-4 py-3 font-medium text-primary dark:text-white">{u.name}</td>
                <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                <td className="px-4 py-3 capitalize">{u.role}</td>
                <td className="px-4 py-3"><StatusChip value={u.status || "active"} /></td>
                <td className="px-4 py-3">{u.email_verified ? "Yes" : "No"}</td>
                <td className="px-4 py-3 text-muted-foreground">{(u.created_at || "").slice(0, 10)}</td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">{loading ? "Loading users..." : "No users found"}</td></tr>}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-auto" data-testid="admin-user-detail">
          <DialogHeader><DialogTitle>User profile</DialogTitle></DialogHeader>
          {currentUser && (
            <div className="space-y-6">
              <div className="flex flex-col gap-4 rounded-2xl border border-border bg-background p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-xl font-semibold text-primary dark:text-white">{currentUser.name || "Unnamed user"}</div>
                  <div className="text-sm text-muted-foreground">{currentUser.email}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <StatusChip value={currentUser.role} />
                    <StatusChip value={currentUser.status || "active"} />
                    <StatusChip value={currentUser.email_verified ? "email_verified" : "email_unverified"} />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(currentUser.status || "active") === "suspended" ? (
                    <button onClick={() => suspendUser(false)} disabled={busy} className="rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold disabled:opacity-60">Reactivate</button>
                  ) : (
                    <button onClick={() => suspendUser(true)} disabled={busy} className="rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent disabled:opacity-60">Suspend</button>
                  )}
                  <button onClick={deleteUser} disabled={busy} className="rounded-full bg-destructive text-destructive-foreground px-4 py-2 text-sm font-semibold disabled:opacity-60">Delete permanently</button>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-sm font-semibold text-primary dark:text-white">Account details</div>
                  <dl className="mt-3 space-y-2 text-sm">
                    <InfoRow label="User ID" value={currentUser.id} />
                    <InfoRow label="Role" value={currentUser.role} />
                    <InfoRow label="Created" value={currentUser.created_at} />
                    <InfoRow label="Email verified" value={currentUser.email_verified ? "Yes" : "No"} />
                  </dl>
                </div>
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-sm font-semibold text-primary dark:text-white">Profile details</div>
                  {profile ? (
                    <dl className="mt-3 space-y-2 text-sm">
                      {Object.entries(profile).filter(([key]) => !["_id", "id", "user_id", "created_at", "updated_at"].includes(key)).slice(0, 12).map(([key, value]) => (
                        <InfoRow key={key} label={key.replaceAll("_", " ")} value={typeof value === "object" ? JSON.stringify(value) : value} />
                      ))}
                    </dl>
                  ) : <p className="mt-3 text-sm text-muted-foreground">No profile created yet.</p>}
                </div>
              </div>

              <HistoryBlock title="Activity logs" rows={history.activity_logs} fields={["action", "entity", "entity_id", "created_at"]} />
              <HistoryBlock title="Admin actions" rows={history.admin_logs} fields={["action", "target", "created_at"]} />
              <div className="grid gap-4 md:grid-cols-2">
                <HistoryBlock title="Verification requests" rows={history.verification_requests} fields={["kind", "status", "schedule_call_at", "created_at"]} compact />
                <HistoryBlock title="Withdrawals" rows={history.withdrawals} fields={["amount", "method", "status", "created_at"]} compact />
                <HistoryBlock title="Campaigns" rows={history.campaigns} fields={["title", "status", "budget", "created_at"]} compact />
                <HistoryBlock title="Deals" rows={history.deals} fields={["campaign_id", "status", "amount", "created_at"]} compact />
              </div>
            </div>
          )}
          {!currentUser && <p className="text-sm text-muted-foreground">{busy ? "Loading user..." : "No user selected."}</p>}
        </DialogContent>
      </Dialog>
    </Section>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="capitalize text-muted-foreground">{label}</dt>
      <dd className="max-w-[65%] break-words text-right text-foreground/90">{String(value ?? "-")}</dd>
    </div>
  );
}

function HistoryBlock({ title, rows = [], fields, compact = false }) {
  return (
    <div className="rounded-2xl border border-border p-4">
      <div className="text-sm font-semibold text-primary dark:text-white">{title}</div>
      <div className={`mt-3 space-y-2 ${compact ? "max-h-56" : "max-h-72"} overflow-auto`}>
        {rows.map((row) => (
          <div key={row.id} className="rounded-xl bg-accent/60 px-3 py-2 text-xs">
            {fields.map((field) => (
              <div key={field} className="flex justify-between gap-3">
                <span className="capitalize text-muted-foreground">{field.replaceAll("_", " ")}</span>
                <span className="max-w-[65%] break-words text-right">{String(row[field] ?? "-")}</span>
              </div>
            ))}
          </div>
        ))}
        {!rows.length && <p className="text-sm text-muted-foreground">No records.</p>}
      </div>
    </div>
  );
}

export function AdminVerification() {
  const [tab, setTab] = useState("pending");
  const [rows, setRows] = useState([]);
  const [active, setActive] = useState(null);
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [callAt, setCallAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingRows, setLoadingRows] = useState(false);

  const load = async (s = tab) => {
    try {
      setLoadingRows(true);
      const r = await api.get("/admin/verification", { params: { status: s } });
      setRows(r.data.requests || []);
    } catch (e) {
      setRows([]);
      toast.error(formatApiError(e));
    } finally {
      setLoadingRows(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(tab); }, [tab]);

  const openRequest = async (request) => {
    setBusy(true);
    try {
      if (request.status === "pending") {
        const { data } = await api.post(`/admin/verification/${request.id}/decision`, { decision: "in_progress" });
        const updated = data.request || { ...request, status: "in_progress" };
        setActive(updated);
        setCallAt(updated.schedule_call_at || "");
        setNotes(updated.admin_notes || "");
        setTab("in_progress");
        await load("in_progress");
        toast.success("Request moved to In Progress.");
      } else {
        setActive(request);
        setCallAt(request.schedule_call_at || "");
        setNotes(request.admin_notes || "");
      }
      setOpen(true);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const updateRequest = async (decision, extra = {}) => {
    if (!active) return;
    if (decision === "in_progress" && !callAt) {
      toast.error("Select a WhatsApp video call date and time.");
      return;
    }
    try {
      setBusy(true);
      const { data } = await api.post(`/admin/verification/${active.id}/decision`, {
        decision,
        notes,
        schedule_call_at: callAt || null,
        ...extra,
      });
      const updated = data.request || { ...active, status: decision, schedule_call_at: callAt || null, admin_notes: notes };
      setActive(updated);
      toast.success(decision === "verified" ? "Influencer marked verified." : "Verification request updated.");
      if (decision === "verified" || decision === "rejected") {
        setOpen(false);
        setActive(null);
        setNotes("");
        setCallAt("");
        setTab(decision);
        await load(decision);
      } else {
        await load("in_progress");
      }
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title="Verification panel">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="pending" data-testid="verif-tab-pending">Pending</TabsTrigger>
          <TabsTrigger value="in_progress" data-testid="verif-tab-in-progress">In Progress</TabsTrigger>
          <TabsTrigger value="verified" data-testid="verif-tab-verified">Verified</TabsTrigger>
          <TabsTrigger value="rejected" data-testid="verif-tab-rejected">Rejected</TabsTrigger>
        </TabsList>
        <TabsContent value={tab} className="mt-6 space-y-3">
          {rows.map((r) => (
            <div key={r.id} className="rounded-2xl border border-border bg-card p-5 flex items-center justify-between" data-testid={`verif-row-${r.id}`}>
              <div>
                <div className="flex items-center gap-2">
                  <div className="text-sm font-semibold text-primary dark:text-white">
                    {r.profile?.name || r.user?.name || (r.kind === "brand" ? "Brand" : "Influencer")} verification
                  </div>
                  <StatusChip value={r.status} />
                </div>
                <div className="text-xs text-muted-foreground">
                  {r.user?.email || r.user_id} {r.user?.phone ? `- ${r.user.phone}` : ""} - {r.documents?.length || 0} doc(s)
                </div>
                {r.schedule_call_at && <div className="text-xs text-secondary mt-1">WhatsApp call: {new Date(r.schedule_call_at).toLocaleString()}</div>}
                {r.notes && <p className="text-xs mt-1 text-foreground/70">"{r.notes}"</p>}
              </div>
              <button onClick={() => openRequest(r)} disabled={busy} className="rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold disabled:opacity-60" data-testid={`verif-review-${r.id}`}>
                {r.status === "pending" ? "Start review" : "Open"}
              </button>
            </div>
          ))}
          {!loadingRows && !rows.length && <p className="text-muted-foreground text-sm">No requests in this state.</p>}
          {loadingRows && <p className="text-muted-foreground text-sm">Loading requests...</p>}
        </TabsContent>
      </Tabs>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" data-testid="admin-verification-dialog">
          <DialogHeader><DialogTitle>Review verification</DialogTitle></DialogHeader>
          {active && (
            <div className="space-y-5">
              <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-background p-3">
                <div>
                  <div className="text-sm font-semibold text-primary dark:text-white">
                    {active.profile?.name || active.user?.name || `${active.kind} verification`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {active.user?.email || active.user_id} {active.user?.phone ? `- ${active.user.phone}` : ""}
                  </div>
                  {active.profile?.phone && active.profile.phone !== active.user?.phone && (
                    <div className="text-xs text-muted-foreground">Profile phone: {active.profile.phone}</div>
                  )}
                </div>
                <StatusChip value={active.status} />
              </div>

              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Submitted documents</div>
                <div className="mt-2 space-y-2">
                  {(active.documents || []).map((doc, index) => {
                    const url = typeof doc === "string" ? doc : doc.url;
                    const label = typeof doc === "string" ? `Document ${index + 1}` : doc.label || doc.type || `Document ${index + 1}`;
                    return (
                      <a key={`${url}-${index}`} href={url} target="_blank" rel="noreferrer" className="block rounded-xl border border-border px-3 py-2 text-sm text-secondary hover:bg-accent">
                        {label}
                      </a>
                    );
                  })}
                  {!(active.documents || []).length && <p className="text-sm text-muted-foreground">No documents uploaded.</p>}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">WhatsApp video call date and time</label>
                <Input type="datetime-local" value={callAt} onChange={(e) => setCallAt(e.target.value)} data-testid="verif-call-at" className="mt-2" />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Admin notes</label>
                <Textarea placeholder="Notes for the user..." value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="verif-notes" className="mt-2" />
              </div>
            </div>
          )}
          <DialogFooter>
            {active?.status === "in_progress" && (
              <button onClick={() => updateRequest("rejected")} disabled={busy} className="rounded-full bg-destructive text-destructive-foreground px-4 py-2 text-sm font-semibold disabled:opacity-60" data-testid="verif-reject">Reject</button>
            )}
            {active?.status === "in_progress" && (
              <button onClick={() => updateRequest("in_progress")} disabled={busy} className="rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent disabled:opacity-60" data-testid="verif-schedule-call">Save call time</button>
            )}
            {active?.status === "in_progress" && (
              <button onClick={() => updateRequest("verified", { call_completed: true })} disabled={busy || !callAt} className="rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold disabled:opacity-60" data-testid="verif-verify">Confirm Call & Verify</button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Section>
  );
}

function SimpleList({ title, endpoint, columns, testidPrefix }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const r = await api.get(endpoint);
        setRows(r.data.requests || r.data.reports || r.data.logs || []);
      } catch (e) {
        setRows([]);
        toast.error(formatApiError(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [endpoint]);
  return (
    <Section title={title}>
      <div className="rounded-2xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-accent dark:bg-card text-left"><tr>{columns.map((c) => <th key={c.key} className="px-4 py-3">{c.label}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.id || i} className="border-t border-border" data-testid={`${testidPrefix}-${row.id || i}`}>
                {columns.map((c) => <td key={c.key} className="px-4 py-3 text-foreground/80">{String(row[c.key] ?? "")}</td>)}
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={columns.length} className="px-4 py-8 text-center text-muted-foreground">{loading ? "Loading records..." : "No records"}</td></tr>}
          </tbody>
        </table>
      </div>
    </Section>
  );
}


function money(value) {
  return `INR ${Number(value || 0).toLocaleString()}`;
}

function profileName(profile, user, fallback) {
  return profile?.company_name || profile?.username || profile?.name || user?.name || fallback || "-";
}

export function AdminEscrow() {
  const [tab, setTab] = useState("held");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async (status = tab) => {
    try {
      setLoading(true);
      const { data } = await api.get("/admin/escrow", { params: { status } });
      setRows(data.payments || []);
    } catch (e) {
      setRows([]);
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(tab); }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  const release = async (payment) => {
    if (!payment) return;
    if (!window.confirm("Release creator payout now? BrandKrt platform fee will stay recorded.")) return;
    try {
      setBusy(true);
      await api.post(`/payments/${payment.id}/release`);
      toast.success("Creator payout released.");
      setActive(null);
      await load(tab);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const tabs = [
    ["held", "Held"],
    ["release_requested", "Release requested"],
    ["released", "Released"],
    ["all", "All"],
  ];

  return (
    <Section title="Escrow control">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          {tabs.map(([value, label]) => <TabsTrigger key={value} value={value}>{label}</TabsTrigger>)}
        </TabsList>
        <TabsContent value={tab} className="mt-6 space-y-3">
          {rows.map((p) => (
            <div key={p.id} className="rounded-2xl border border-border bg-card p-5" data-testid={`escrow-row-${p.id}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-primary dark:text-white">{p.campaign?.title || p.agreement?.campaign_name || "Escrow payment"}</h3>
                    <StatusChip value={p.release_status || p.status} />
                  </div>
                  <div className="grid gap-2 text-sm text-foreground/80 md:grid-cols-2">
                    <InfoRow label="Brand" value={`${profileName(p.brand, p.brand_user, p.agreement?.brand_name)} (${p.brand_user?.email || "no email"})`} />
                    <InfoRow label="Creator" value={`${profileName(p.creator, p.creator_user, p.agreement?.influencer_name)} (${p.creator_user?.email || "no email"})`} />
                    <InfoRow label="Deal" value={p.deal_id || "-"} />
                    <InfoRow label="Agreement" value={p.agreement_id || "-"} />
                    <InfoRow label="Campaign" value={p.campaign_id || p.campaign?.id || "-"} />
                    <InfoRow label="Transaction" value={p.transaction_id || "-"} />
                  </div>
                </div>
                <button onClick={() => setActive(p)} className="rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent">Open details</button>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <Metric label="Gross amount" value={money(p.amount)} />
                <Metric label="Platform fee" value={money(p.platform_fee)} />
                <Metric label="Creator payout" value={money(p.influencer_earning)} tone="gold" />
              </div>
            </div>
          ))}
          {!rows.length && <p className="text-sm text-muted-foreground">{loading ? "Loading escrow records..." : "No escrow records in this state."}</p>}
        </TabsContent>
      </Tabs>

      <Dialog open={!!active} onOpenChange={(open) => !open && setActive(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-auto" data-testid="admin-escrow-detail">
          <DialogHeader><DialogTitle>Escrow details</DialogTitle></DialogHeader>
          {active && (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-3">
                <Metric label="Gross amount" value={money(active.amount)} />
                <Metric label="Platform fee retained" value={money(active.platform_fee)} />
                <Metric label="Creator payout" value={money(active.influencer_earning)} tone="gold" />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <DetailCard title="Brand" rows={[
                  ["Name", profileName(active.brand, active.brand_user, active.agreement?.brand_name)],
                  ["Email", active.brand_user?.email],
                  ["Phone", active.brand?.phone || active.brand_user?.phone],
                  ["Business", active.brand?.business_category],
                ]} />
                <DetailCard title="Creator payout details" rows={[
                  ["Name", profileName(active.creator, active.creator_user, active.agreement?.influencer_name)],
                  ["Email", active.creator_user?.email],
                  ["Phone", active.creator?.phone || active.creator_user?.phone],
                  ["UPI", active.creator?.upi],
                  ["Account holder", active.creator?.bank_details?.account_name],
                  ["Bank", active.creator?.bank_details?.bank_name],
                  ["Account number", active.creator?.bank_details?.account_number],
                  ["IFSC", active.creator?.bank_details?.ifsc],
                ]} />
              </div>
              <DetailCard title="Campaign and escrow" rows={[
                ["Campaign", active.campaign?.title || active.agreement?.campaign_name],
                ["Deliverables", active.agreement?.deliverables || active.campaign?.deliverables],
                ["Timeline", active.agreement?.timeline || active.campaign?.deadline],
                ["Deal status", active.deal?.status],
                ["Payment status", active.status],
                ["Release status", active.release_status],
                ["Paid at", active.verified_at || active.created_at],
                ["Release requested", active.release_requested_at],
              ]} />
              {(active.release_status === "release_requested" || active.release_status === "held") && active.status === "escrowed" && (
                <button onClick={() => release(active)} disabled={busy} className="w-full rounded-full bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60" data-testid="admin-release-escrow">
                  Release creator payout
                </button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Section>
  );
}

function Metric({ label, value, tone = "default" }) {
  return (
    <div className={`rounded-xl border border-border p-4 ${tone === "gold" ? "bg-accent border-secondary/40" : "bg-background"}`}>
      <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold text-primary dark:text-white">{value}</div>
    </div>
  );
}

function DetailCard({ title, rows }) {
  return (
    <div className="rounded-2xl border border-border bg-background p-4">
      <div className="text-sm font-semibold text-primary dark:text-white">{title}</div>
      <dl className="mt-3 space-y-2 text-sm">
        {rows.map(([label, value]) => <InfoRow key={label} label={label} value={value || "-"} />)}
      </dl>
    </div>
  );
}
export function AdminWithdrawals() {
  const [tab, setTab] = useState("pending");
  const [rows, setRows] = useState([]);
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState({ reference: "", screenshot_url: "", note: "" });

  const load = async (status = tab) => {
    try {
      setLoading(true);
      const { data } = await api.get("/admin/withdrawals", { params: { status } });
      setRows(data.requests || []);
    } catch (e) {
      setRows([]);
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(tab); }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  const decide = async (request, decision) => {
    if (!request) return;
    try {
      setBusy(true);
      const { data } = await api.post(`/admin/withdrawals/${request.id}/decision`, {
        decision,
        note: decision === "approved" ? "Approved for RazorpayX payout" : "Rejected by admin",
      });
      toast.success(decision === "approved" ? "Withdrawal approved." : "Withdrawal rejected.");
      if (active?.id === request.id) setActive(data.request || null);
      await load(tab);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const pay = async (request) => {
    if (!request) return;
    const detail = payoutSummary(request);
    if (!window.confirm(`Send ${money(request.amount)} to ${profileName(request.creator, request.user, request.user_id)} via ${detail}?`)) return;
    try {
      setBusy(true);
      const { data } = await api.post(`/admin/withdrawals/${request.id}/payout`);
      toast.success("RazorpayX payout triggered.");
      if (active?.id === request.id) setActive(data.request || null);
      await load(tab);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const markManual = async (request) => {
    if (!request) return;
    if (!manual.reference && !window.confirm("No UTR/reference added. Mark this payout as manually paid anyway?")) return;
    try {
      setBusy(true);
      const { data } = await api.post(`/admin/withdrawals/${request.id}/manual-payout`, manual);
      toast.success("Manual payout marked successful.");
      setManual({ reference: "", screenshot_url: "", note: "" });
      if (active?.id === request.id) setActive(data.request || null);
      await load(tab);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const openDetails = (request) => {
    setActive(request);
    setManual({
      reference: request.manual_payout?.reference || "",
      screenshot_url: request.manual_payout?.screenshot_url || "",
      note: request.manual_payout?.note || "",
    });
  };

  const tabs = [
    ["pending", "Pending"],
    ["approved", "Approved"],
    ["released", "Released"],
    ["rejected", "Rejected"],
    ["failed", "Failed"],
    ["all", "All"],
  ];

  return (
    <Section title="Withdrawal payouts">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          {tabs.map(([value, label]) => <TabsTrigger key={value} value={value}>{label}</TabsTrigger>)}
        </TabsList>
        <TabsContent value={tab} className="mt-6 space-y-3">
          {rows.map((request) => (
            <div key={request.id} className="rounded-2xl border border-border bg-card p-5" data-testid={`wd-row-${request.id}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-primary dark:text-white">{profileName(request.creator, request.user, "Creator payout")}</h3>
                    <StatusChip value={request.status} />
                    {request.payout_status && <StatusChip value={request.payout_status} />}
                  </div>
                  <div className="grid gap-2 text-sm text-foreground/80 md:grid-cols-2">
                    <InfoRow label="Email" value={request.user?.email || "-"} />
                    <InfoRow label="Phone" value={request.creator?.phone || request.user?.phone || "-"} />
                    <InfoRow label="Method" value={request.method === "upi" ? "UPI" : "Bank transfer"} />
                    <InfoRow label="Destination" value={payoutSummary(request)} />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => openDetails(request)} className="rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent">Open details</button>
                  {request.status === "pending" && (
                    <button onClick={() => decide(request, "approved")} disabled={busy} className="rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent disabled:opacity-60">
                      Approve
                    </button>
                  )}
                  {["pending", "approved"].includes(request.status) && (
                    <button onClick={() => pay(request)} disabled={busy} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-60" data-testid={`wd-pay-${request.id}`}>
                      Pay via RazorpayX
                    </button>
                  )}
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <Metric label="Amount to creator" value={money(request.amount)} tone="gold" />
                <Metric label="Requested on" value={(request.created_at || "").slice(0, 10) || "-"} />
                <Metric label="Payout id" value={request.payout_id || "-"} />
              </div>
            </div>
          ))}
          {!rows.length && <p className="text-sm text-muted-foreground">{loading ? "Loading withdrawals..." : "No withdrawal requests in this state."}</p>}
        </TabsContent>
      </Tabs>

      <Dialog open={!!active} onOpenChange={(open) => !open && setActive(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-auto" data-testid="admin-withdrawal-detail">
          <DialogHeader><DialogTitle>Withdrawal payout</DialogTitle></DialogHeader>
          {active && (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-3">
                <Metric label="Amount" value={money(active.amount)} tone="gold" />
                <Metric label="Status" value={active.status || "-"} />
                <Metric label="Provider status" value={active.payout_status || "-"} />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <DetailCard title="Creator" rows={[
                  ["Name", profileName(active.creator, active.user, active.user_id)],
                  ["Email", active.user?.email],
                  ["Phone", active.creator?.phone || active.user?.phone],
                  ["User ID", active.user_id],
                ]} />
                <DetailCard title="Payout details" rows={[
                  ["Method", active.method === "upi" ? "UPI" : "Bank transfer"],
                  ["UPI", active.payout_details?.upi],
                  ["Account holder", active.payout_details?.account_name],
                  ["Bank", active.payout_details?.bank_name],
                  ["Account number", active.payout_details?.account_number],
                  ["IFSC", active.payout_details?.ifsc],
                ]} />
              </div>
              <DetailCard title="RazorpayX payout" rows={[
                ["Payout ID", active.payout_id],
                ["Payout mode", active.payout_mode],
                ["Fund account ID", active.payout_fund_account_id],
                ["Contact ID", active.payout_contact_id],
                ["Processed at", active.processed_at],
                ["Admin note", active.admin_note],
              ]} />
              <div className="rounded-2xl border border-border bg-background p-4">
                <div className="text-sm font-semibold text-primary dark:text-white">Manual payment proof</div>
                <p className="mt-1 text-xs text-muted-foreground">Use this after paying the creator from UPI/bank app. The creator will see the payout as successful.</p>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">UTR / Reference</label>
                    <Input value={manual.reference} onChange={(e) => setManual({ ...manual, reference: e.target.value })} placeholder="UPI ref / bank UTR" className="mt-2" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Screenshot URL</label>
                    <Input value={manual.screenshot_url} onChange={(e) => setManual({ ...manual, screenshot_url: e.target.value })} placeholder="Payment screenshot link" className="mt-2" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Note</label>
                    <Input value={manual.note} onChange={(e) => setManual({ ...manual, note: e.target.value })} placeholder="Paid manually after bank/UPI transfer" className="mt-2" />
                  </div>
                </div>
                {active.manual_payout?.screenshot_url && (
                  <a href={active.manual_payout.screenshot_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-sm font-semibold text-secondary">
                    Open saved screenshot
                  </a>
                )}
              </div>
              <DialogFooter>
                {active.status === "pending" && (
                  <button onClick={() => decide(active, "rejected")} disabled={busy} className="rounded-full bg-destructive px-4 py-2 text-sm font-semibold text-destructive-foreground disabled:opacity-60">
                    Reject
                  </button>
                )}
                {active.status === "pending" && (
                  <button onClick={() => decide(active, "approved")} disabled={busy} className="rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent disabled:opacity-60">
                    Approve
                  </button>
                )}
                {["pending", "approved"].includes(active.status) && (
                  <button onClick={() => pay(active)} disabled={busy} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-60">
                    Pay via RazorpayX
                  </button>
                )}
                {["pending", "approved"].includes(active.status) && (
                  <button onClick={() => markManual(active)} disabled={busy} className="rounded-full bg-secondary px-4 py-2 text-sm font-semibold text-secondary-foreground disabled:opacity-60">
                    Mark paid manually
                  </button>
                )}
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Section>
  );
}

function payoutSummary(request) {
  const details = request?.payout_details || {};
  if (request?.method === "upi") return details.upi || "UPI missing";
  const ending = details.account_number ? `A/C ${String(details.account_number).slice(-4)}` : "account missing";
  return `${details.bank_name || "Bank"} - ${ending}${details.ifsc ? ` - ${details.ifsc}` : ""}`;
}

export const AdminReports = () => <SimpleList title="Reports" endpoint="/admin/reports" testidPrefix="report-row" columns={[
  { key: "reporter_id", label: "Reporter" }, { key: "target_user_id", label: "Target" }, { key: "reason", label: "Reason" }, { key: "status", label: "Status" }, { key: "created_at", label: "Created" },
]} />;

export const AdminLogs = () => <SimpleList title="Admin audit logs" endpoint="/admin/logs?kind=admin&limit=200" testidPrefix="log-row" columns={[
  { key: "admin_id", label: "Admin" }, { key: "action", label: "Action" }, { key: "target", label: "Target" }, { key: "created_at", label: "When" },
]} />;
