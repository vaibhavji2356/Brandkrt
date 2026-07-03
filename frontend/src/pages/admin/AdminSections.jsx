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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);
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
            <tr><th className="px-4 py-3">Name</th><th className="px-4 py-3">Email</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Verified</th><th className="px-4 py-3">Created</th></tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id} className="border-t border-border" data-testid={`user-row-${u.id}`}>
                <td className="px-4 py-3 font-medium text-primary dark:text-white">{u.name}</td>
                <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                <td className="px-4 py-3 capitalize">{u.role}</td>
                <td className="px-4 py-3">{u.email_verified ? "Yes" : "No"}</td>
                <td className="px-4 py-3 text-muted-foreground">{(u.created_at || "").slice(0, 10)}</td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">{loading ? "Loading users..." : "No users found"}</td></tr>}
          </tbody>
        </table>
      </div>
    </Section>
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

export const AdminWithdrawals = () => <SimpleList title="Withdrawal requests" endpoint="/admin/withdrawals" testidPrefix="wd-row" columns={[
  { key: "user_id", label: "User" }, { key: "amount", label: "Amount" }, { key: "method", label: "Method" }, { key: "status", label: "Status" }, { key: "created_at", label: "Created" },
]} />;

export const AdminReports = () => <SimpleList title="Reports" endpoint="/admin/reports" testidPrefix="report-row" columns={[
  { key: "reporter_id", label: "Reporter" }, { key: "target_user_id", label: "Target" }, { key: "reason", label: "Reason" }, { key: "status", label: "Status" }, { key: "created_at", label: "Created" },
]} />;

export const AdminLogs = () => <SimpleList title="Admin audit logs" endpoint="/admin/logs?kind=admin&limit=200" testidPrefix="log-row" columns={[
  { key: "admin_id", label: "Admin" }, { key: "action", label: "Action" }, { key: "target", label: "Target" }, { key: "created_at", label: "When" },
]} />;
