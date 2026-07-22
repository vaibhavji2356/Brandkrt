import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, Banknote, Bookmark, Brain, BriefcaseBusiness, Building2,
  ChevronRight, Flag, History, LayoutDashboard, LogOut, Menu, ScrollText,
  Search, Settings as SettingsIcon, ShieldCheck, Sparkles, Users, X,
} from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";

const NAV = [
  { to: "/admin", end: true, icon: LayoutDashboard, label: "Overview" },
  { to: "/admin/lead-intelligence", icon: Sparkles, label: "AI Lead Intelligence" },
  { to: "/admin/brand-discovery", icon: Building2, label: "Brand Discovery" },
  { to: "/admin/creator-discovery", icon: Search, label: "Creator Discovery" },
  { to: "/admin/saved-leads", icon: Bookmark, label: "Saved Leads" },
  { to: "/admin/research-history", icon: History, label: "Research History" },
  { to: "/admin/commercial-intelligence", icon: BriefcaseBusiness, label: "Commercial Intelligence" },
  { to: "/admin/ai-activity", icon: Brain, label: "AI Activity" },
  { to: "/admin/operations", icon: Activity, label: "Operations" },
  { to: "/admin/ai-settings", icon: SettingsIcon, label: "Settings" },
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
  const location = useLocation();
  const [attention, setAttention] = useState({});
  const [mobileOpen, setMobileOpen] = useState(false);
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
  useEffect(() => setMobileOpen(false), [location.pathname]);

  if (loading || !user) return <div className="min-h-screen flex items-center justify-center"><div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" /></div>;

  return (
    <div className="min-h-screen flex bg-muted/20" data-testid="admin-layout">
      {mobileOpen && <button aria-label="Close admin navigation" onClick={() => setMobileOpen(false)} className="fixed inset-0 z-40 bg-slate-950/45 md:hidden" />}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-72 shrink-0 flex-col border-r border-border/70 bg-card shadow-xl transition-transform md:static md:w-64 md:translate-x-0 md:shadow-[1px_0_0_rgba(15,23,42,0.02)] ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`} data-testid="admin-sidebar">
        <div className="h-20 flex items-center px-6 border-b border-border/70">
          <Logo />
          <button aria-label="Close navigation" onClick={() => setMobileOpen(false)} className="ml-auto rounded-lg p-2 md:hidden"><X className="h-5 w-5" /></button>
        </div>
        <nav className="flex-1 space-y-1.5 overflow-y-auto p-4">
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
        <div className="sticky top-0 z-30 flex h-16 items-center border-b border-border/70 bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:px-8">
          <button aria-label="Open admin navigation" onClick={() => setMobileOpen(true)} className="mr-3 rounded-lg border border-border p-2 md:hidden"><Menu className="h-4 w-4" /></button>
          <h1 className="text-lg font-display font-medium text-primary dark:text-white">Admin Console</h1>
          <ChevronRight className="h-4 w-4 mx-2 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">BrandKrt</span>
        </div>
        <div className="p-4 sm:p-6 lg:p-10">
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
