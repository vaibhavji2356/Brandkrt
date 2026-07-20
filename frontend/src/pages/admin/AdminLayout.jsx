import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, ShieldCheck, Users, Banknote, Flag, ScrollText, LogOut, ChevronRight } from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";

const NAV = [
  { to: "/admin", end: true, icon: LayoutDashboard, label: "Overview" },
  { to: "/admin/users", icon: Users, label: "Users" },
  { to: "/admin/verification", icon: ShieldCheck, label: "Verification", countKey: "pending_verification" },
  { to: "/admin/escrow", icon: Banknote, label: "Escrow", countKey: "pending_escrow_releases" },
  { to: "/admin/withdrawals", icon: Banknote, label: "Withdrawals", countKey: "pending_withdrawals" },
  { to: "/admin/reports", icon: Flag, label: "Reports" },
  { to: "/admin/logs", icon: ScrollText, label: "Logs" },
];

export default function AdminLayout() {
  const { user, logout, loading } = useAuth();
  const navigate = useNavigate();
  const [attention, setAttention] = useState({});
  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) navigate("/login", { replace: true });
  }, [user, loading, navigate]);
  useEffect(() => {
    if (!user || user.role !== "admin") return undefined;
    let alive = true;
    const loadAttention = async () => {
      try {
        const { data } = await api.get("/admin/overview");
        if (alive) setAttention(data.cards || {});
      } catch (_) {}
    };
    loadAttention();
    const timer = window.setInterval(loadAttention, 30000);
    window.addEventListener("focus", loadAttention);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", loadAttention);
    };
  }, [user]);

  if (loading || !user) return <div className="min-h-screen flex items-center justify-center"><div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" /></div>;

  return (
    <div className="min-h-screen flex bg-muted/20" data-testid="admin-layout">
      <aside className="w-64 shrink-0 border-r border-border/70 bg-card/95 shadow-[1px_0_0_rgba(15,23,42,0.02)] flex flex-col" data-testid="admin-sidebar">
        <div className="h-20 flex items-center px-6 border-b border-border/70">
          <Logo />
        </div>
        <nav className="flex-1 p-4 space-y-1.5">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={`admin-nav-${item.label.toLowerCase()}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive ? "bg-primary text-primary-foreground shadow-luxe-sm" : "text-foreground/70 hover:bg-accent hover:text-primary dark:hover:text-white"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              <span className="flex-1">{item.label}</span>
              {Number(attention[item.countKey] || 0) > 0 && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-secondary px-1.5 text-[10px] font-bold text-primary">
                  {attention[item.countKey]}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border/70 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs text-muted-foreground truncate">{user.email}</div>
            <ThemeToggle />
          </div>
          <button onClick={async () => { await logout(); navigate("/"); }} data-testid="admin-logout" className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold">
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 flex flex-col">
        <div className="sticky top-0 z-30 h-16 border-b border-border/70 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 flex items-center px-8">
          <h1 className="text-lg font-display font-medium text-primary dark:text-white">Admin Console</h1>
          <ChevronRight className="h-4 w-4 mx-2 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">BrandKrt</span>
        </div>
        <div className="p-8 lg:p-10">
          <div className="mb-6 space-y-3">
            {Number(attention.pending_escrow_releases || 0) > 0 && (
              <AdminAttention count={attention.pending_escrow_releases} title="Creator payment release required" description="Completed deal payout(s) are waiting for admin release." action="Review payouts" onClick={() => navigate("/admin/escrow")} testId="admin-release-alert" />
            )}
            {Number(attention.pending_verification || 0) > 0 && (
              <AdminAttention count={attention.pending_verification} title="Verification review required" description="Brand/creator verification request(s) are pending or in progress." action="Review verification" onClick={() => navigate("/admin/verification")} testId="admin-verification-alert" />
            )}
            {Number(attention.pending_withdrawals || 0) > 0 && (
              <AdminAttention count={attention.pending_withdrawals} title="Withdrawal action required" description="Withdrawal request(s) are pending or approved but not released yet." action="Review withdrawals" onClick={() => navigate("/admin/withdrawals")} testId="admin-withdrawal-alert" />
            )}
          </div>
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function AdminAttention({ count, title, description, action, onClick, testId }) {
  return (
    <button type="button" onClick={onClick} className="flex w-full items-center justify-between gap-4 rounded-2xl border border-secondary/40 bg-secondary/10 p-4 text-left" data-testid={testId}>
      <span className="flex min-w-0 items-center gap-3">
        <span className="flex h-8 min-w-8 shrink-0 items-center justify-center rounded-full bg-destructive px-2 text-xs font-bold text-destructive-foreground">{count}</span>
        <span>
          <span className="block font-semibold text-primary dark:text-white">{title}</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">{description}</span>
        </span>
      </span>
      <span className="shrink-0 rounded-full bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground">{action}</span>
    </button>
  );
}
