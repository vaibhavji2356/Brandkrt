import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, UserCircle2, Megaphone, Wallet, Bell, LogOut, ChevronRight,
  Handshake, MessageCircle, ScrollText, BarChart3,
} from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import NotificationBell from "@/components/NotificationBell";
import UserAvatar from "@/components/UserAvatar";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const NAV = [
  { to: "/influencer", end: true, icon: LayoutDashboard, label: "Overview" },
  { to: "/influencer/profile", icon: UserCircle2, label: "Profile Builder" },
  { to: "/influencer/campaigns", icon: Megaphone, label: "Campaigns" },
  { to: "/influencer/collaborations", icon: Handshake, label: "Collaborations" },
  { to: "/influencer/messages", icon: MessageCircle, label: "Messages" },
  { to: "/influencer/agreements", icon: ScrollText, label: "Agreements" },
  { to: "/influencer/analytics", icon: BarChart3, label: "Performance" },
  { to: "/influencer/earnings", icon: Wallet, label: "Earnings" },
  { to: "/influencer/notifications", icon: Bell, label: "Notifications" },
];

export default function InfluencerLayout() {
  const { user, logout, loading } = useAuth();
  const navigate = useNavigate();
  const [avatarUrl, setAvatarUrl] = useState("");

  useEffect(() => {
    if (loading) return;
    if (!user) {
      navigate("/login?from=/influencer", { replace: true });
    } else if (user.role === "admin") {
      navigate("/admin", { replace: true });
    } else if (user.role !== "influencer") {
      navigate("/profile", { replace: true });
    }
  }, [user, loading, navigate]);

  useEffect(() => {
    if (!user || user.role !== "influencer") return undefined;
    let alive = true;

    const loadAvatar = async () => {
      try {
        const { data } = await api.get("/influencers/me");
        const nextUrl = data?.influencer?.profile_photo_url || user.avatar_url || "";
        if (alive) setAvatarUrl(nextUrl);
      } catch (_) {
        if (alive) setAvatarUrl(user.avatar_url || "");
      }
    };

    const onAvatarUpdated = (event) => {
      if (event.detail?.role === "influencer") {
        setAvatarUrl(event.detail.avatarUrl || "");
      }
    };

    loadAvatar();
    window.addEventListener("brandkrt:profile-image-updated", onAvatarUpdated);
    return () => {
      alive = false;
      window.removeEventListener("brandkrt:profile-image-updated", onAvatarUpdated);
    };
  }, [user]);

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
      </div>
    );
  }

  const initials = (user?.name || user?.email || "U").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
  const headerAvatar = avatarUrl || user?.avatar_url || "";

  return (
    <div className="min-h-screen flex bg-background" data-testid="influencer-layout">
      {/* Sidebar (desktop) */}
      <aside className="hidden md:flex w-64 shrink-0 border-r border-border bg-card flex-col" data-testid="influencer-sidebar">
        <div className="h-16 flex items-center px-6 border-b border-border">
          <Logo />
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={`influencer-nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
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
            data-testid="influencer-logout"
            className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 flex flex-col">
        {/* Top bar */}
        <div className="h-16 border-b border-border flex items-center px-4 md:px-8 gap-3">
          <div className="md:hidden">
            <Logo />
          </div>
          <div className="hidden md:flex items-center min-w-0">
            <h1 className="text-lg font-display font-medium text-primary dark:text-white">Creator Studio</h1>
            <ChevronRight className="h-4 w-4 mx-2 text-muted-foreground" />
            <span className="text-sm text-muted-foreground truncate">{user.name || user.email}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <UserAvatar
              src={headerAvatar}
              initials={initials}
              className="hidden md:flex h-9 w-9 rounded-full bg-primary text-white text-sm font-semibold items-center justify-center"
              testId="influencer-avatar"
            />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="md:hidden h-9 w-9 rounded-full bg-primary text-white text-sm font-semibold flex items-center justify-center" data-testid="influencer-mobile-menu">
                  {headerAvatar ? <img src={headerAvatar} alt="" className="h-full w-full rounded-full object-cover" /> : initials}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64 max-h-[75vh] overflow-auto">
                <DropdownMenuLabel className="flex flex-col">
                  <span className="text-sm font-semibold">{user.name || "Creator"}</span>
                  <span className="text-xs text-muted-foreground">{user.email}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {NAV.map((item) => (
                  <DropdownMenuItem key={item.to} onClick={() => navigate(item.to)} data-testid={`influencer-mobile-menu-${item.label.toLowerCase().replace(/\s+/g, "-")}`}>
                    <item.icon className="mr-2 h-4 w-4" /> {item.label}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={async () => { await logout(); navigate("/"); }} data-testid="influencer-mobile-logout">
                  <LogOut className="mr-2 h-4 w-4" /> Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="p-4 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
