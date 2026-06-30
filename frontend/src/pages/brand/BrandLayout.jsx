import React, { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Building2, Megaphone, Search, Bookmark, BarChart3, LogOut, ChevronRight,
} from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import NotificationBell from "@/components/NotificationBell";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/brand", end: true, icon: LayoutDashboard, label: "Overview" },
  { to: "/brand/profile", icon: Building2, label: "Business Profile" },
  { to: "/brand/campaigns", icon: Megaphone, label: "Campaigns" },
  { to: "/brand/discover", icon: Search, label: "Discover" },
  { to: "/brand/saved", icon: Bookmark, label: "Saved" },
  { to: "/brand/analytics", icon: BarChart3, label: "Analytics" },
];

export default function BrandLayout() {
  const { user, logout, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      navigate("/login?from=/brand", { replace: true });
    } else if (user.role !== "brand" && user.role !== "admin") {
      navigate("/profile", { replace: true });
    }
  }, [user, loading, navigate]);

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
      </div>
    );
  }

  const initials = (user?.name || user?.email || "U").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="min-h-screen flex bg-background" data-testid="brand-layout">
      <aside className="hidden md:flex w-64 shrink-0 border-r border-border bg-card flex-col" data-testid="brand-sidebar">
        <div className="h-16 flex items-center px-6 border-b border-border">
          <Logo />
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={`brand-nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? "bg-accent text-secondary" : "text-foreground/70 hover:bg-accent hover:text-primary dark:hover:text-white"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs text-muted-foreground truncate">{user.email}</div>
            <ThemeToggle />
          </div>
          <button
            onClick={async () => { await logout(); navigate("/"); }}
            data-testid="brand-logout"
            className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 flex flex-col">
        <div className="h-16 border-b border-border flex items-center px-4 md:px-8 gap-3">
          <div className="md:hidden">
            <Logo />
          </div>
          <div className="hidden md:flex items-center min-w-0">
            <h1 className="text-lg font-display font-medium text-primary dark:text-white">Brand Studio</h1>
            <ChevronRight className="h-4 w-4 mx-2 text-muted-foreground" />
            <span className="text-sm text-muted-foreground truncate">{user.name || user.email}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <div className="h-9 w-9 rounded-full bg-primary text-white text-sm font-semibold flex items-center justify-center" data-testid="brand-avatar">
              {initials}
            </div>
          </div>
        </div>

        <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 border-t border-border bg-card flex justify-between px-1 py-1" data-testid="brand-mobile-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium ${
                  isActive ? "text-secondary" : "text-muted-foreground"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              <span className="truncate max-w-[64px]">{item.label.split(" ")[0]}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 md:p-8 pb-24 md:pb-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
