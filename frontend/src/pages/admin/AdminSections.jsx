import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";

function Section({ title, children }) {
  return <div className="space-y-4"><h2 className="text-2xl font-display font-light text-primary dark:text-white">{title}</h2>{children}</div>;
}

export function AdminUsers() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(""); const [role, setRole] = useState("");
  const load = async () => {
    const r = await api.get("/admin/users", { params: { q: q || undefined, role: role || undefined } });
    setRows(r.data.users);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);
  return (
    <Section title="Users">
      <div className="flex gap-3">
        <Input placeholder="Search by name or email…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="users-search" className="max-w-sm" />
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
            {!rows.length && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No users found</td></tr>}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

export function AdminVerification() {
  const [tab, setTab] = useState("pending");
  const [rows, setRows] = useState([]); const [active, setActive] = useState(null);
  const [notes, setNotes] = useState(""); const [callAt, setCallAt] = useState("");
  const load = async (s = tab) => { const r = await api.get("/admin/verification", { params: { status: s } }); setRows(r.data.requests); };
  useEffect(() => { load(tab); }, [tab]);

  const decide = async (decision) => {
    try {
      await api.post(`/admin/verification/${active.id}/decision`, { decision, notes, schedule_call_at: callAt || null });
      toast.success(`Request ${decision}`); setActive(null); setNotes(""); setCallAt(""); load();
    } catch (e) { toast.error(formatApiError(e)); }
  };

  return (
    <Section title="Verification panel">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList><TabsTrigger value="pending" data-testid="verif-tab-pending">Pending</TabsTrigger><TabsTrigger value="approved" data-testid="verif-tab-approved">Approved</TabsTrigger><TabsTrigger value="rejected" data-testid="verif-tab-rejected">Rejected</TabsTrigger></TabsList>
        <TabsContent value={tab} className="mt-6 space-y-3">
          {rows.map((r) => (
            <div key={r.id} className="rounded-2xl border border-border bg-card p-5 flex items-center justify-between" data-testid={`verif-row-${r.id}`}>
              <div>
                <div className="text-sm font-semibold text-primary dark:text-white">{r.kind === "brand" ? "Brand" : "Influencer"} verification</div>
                <div className="text-xs text-muted-foreground">user: {r.user_id} · {r.documents?.length || 0} doc(s)</div>
                {r.notes && <p className="text-xs mt-1 text-foreground/70">"{r.notes}"</p>}
              </div>
              {tab === "pending" && (
                <Dialog>
                  <DialogTrigger asChild>
                    <button onClick={() => setActive(r)} className="rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold" data-testid={`verif-review-${r.id}`}>Review</button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>Review verification</DialogTitle></DialogHeader>
                    <div className="space-y-4">
                      <Textarea placeholder="Notes for the user…" value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="verif-notes" />
                      <Input type="datetime-local" value={callAt} onChange={(e) => setCallAt(e.target.value)} data-testid="verif-call-at" />
                    </div>
                    <DialogFooter>
                      <button onClick={() => decide("rejected")} className="rounded-full bg-destructive text-destructive-foreground px-4 py-2 text-sm font-semibold" data-testid="verif-reject">Reject</button>
                      <button onClick={() => decide("approved")} className="rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold" data-testid="verif-approve">Approve</button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              )}
            </div>
          ))}
          {!rows.length && <p className="text-muted-foreground text-sm">No requests in this state.</p>}
        </TabsContent>
      </Tabs>
    </Section>
  );
}

function SimpleList({ title, endpoint, columns, testidPrefix }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { (async () => { const r = await api.get(endpoint); setRows(r.data.requests || r.data.reports || r.data.logs || []); })(); }, [endpoint]);
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
            {!rows.length && <tr><td colSpan={columns.length} className="px-4 py-8 text-center text-muted-foreground">No records</td></tr>}
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
