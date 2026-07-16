import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, ShieldCheck, Users, Banknote, Flag, ScrollText, LogOut, ChevronRight } from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/admin", end: true, icon: LayoutDashboard, label: "Overview" },
  { to: "/admin/users", icon: Users, label: "Users" },
  { to: "/admin/verification", icon: ShieldCheck, label: "Verification" },
  { to: "/admin/escrow", icon: Banknote, label: "Escrow" },
  { to: "/admin/withdrawals", icon: Banknote, label: "Withdrawals" },
  { to: "/admin/reports", icon: Flag, label: "Reports" },
  { to: "/admin/logs", icon: ScrollText, label: "Logs" },
];

export default function AdminLayout() {
  const { user, logout, loading } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) navigate("/login", { replace: true });
  }, [user, loading, navigate]);

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
              {item.label}
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
          <Outlet />
        </div>
      </main>
    </div>
  );
}
