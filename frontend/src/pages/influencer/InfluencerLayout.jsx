import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  UserCircle2,
  Megaphone,
  Wallet,
  Bell,
  LogOut,
  ChevronRight,
  Menu,
  X,
} from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import NotificationBell from "@/components/NotificationBell";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/influencer", end: true, icon: LayoutDashboard, label: "Overview" },
  { to: "/influencer/profile", icon: UserCircle2, label: "Profile" },
  { to: "/influencer/campaigns", icon: Megaphone, label: "Campaigns" },
  { to: "/influencer/earnings", icon: Wallet, label: "Earnings" },
  { to: "/influencer/notifications", icon: Bell, label: "Notifications" },
];

export default function InfluencerLayout() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!loading && (!user || user.role !== "influencer")) {
      navigate("/login", { replace: true });
    }
  }, [user, loading, navigate]);

  if (loading || !user) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        data-testid="influencer-loading"
      >
        <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
      </div>
    );
  }

  const closeMobile = () => setMobileOpen(false);

  return (
    <div
      className="min-h-screen flex bg-background"
      data-testid="influencer-layout"
    >
      {/* Sidebar — desktop */}
      <aside
        className="hidden lg:flex w-64 shrink-0 border-r border-border bg-card flex-col"
        data-testid="influencer-sidebar"
      >
        <SidebarInner user={user} onLogout={async () => { await logout(); navigate("/"); }} />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex" data-testid="influencer-mobile-drawer">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={closeMobile}
            aria-hidden
          />
          <aside className="relative w-72 max-w-[80vw] bg-card border-r border-border flex flex-col">
            <button
              onClick={closeMobile}
              className="absolute right-3 top-3 h-9 w-9 rounded-full bg-background/80 flex items-center justify-center"
              data-testid="influencer-mobile-close"
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
            <SidebarInner
              user={user}
              onLogout={async () => { await logout(); navigate("/"); }}
              onNavigate={closeMobile}
            />
          </aside>
        </div>
      )}

      <main className="flex-1 min-w-0 flex flex-col">
        {/* Topbar */}
        <div className="h-16 border-b border-border flex items-center px-4 md:px-8 gap-3">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden h-9 w-9 rounded-md border border-border flex items-center justify-center"
            data-testid="influencer-mobile-toggle"
            aria-label="Open menu"
          >
            <Menu className="h-4 w-4" />
          </button>
          <h1 className="text-lg font-display font-medium text-primary dark:text-white">
            Creator Studio
          </h1>
          <ChevronRight className="hidden sm:block h-4 w-4 text-muted-foreground" />
          <span className="hidden sm:inline text-sm text-muted-foreground truncate">
            {user.name || user.email}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <ThemeToggle />
          </div>
        </div>

        <div className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function SidebarInner({ user, onLogout, onNavigate }) {
  return (
    <>
      <div className="h-16 flex items-center px-6 border-b border-border">
        <Logo />
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            data-testid={`influencer-nav-${item.label.toLowerCase()}`}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-accent text-secondary"
                  : "text-foreground/70 hover:bg-accent hover:text-primary dark:hover:text-white"
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-border space-y-3">
        <div className="text-xs text-muted-foreground truncate">{user.email}</div>
        <button
          onClick={onLogout}
          data-testid="influencer-logout"
          className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>
    </>
  );
}
