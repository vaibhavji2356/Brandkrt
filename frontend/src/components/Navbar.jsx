import React, { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Menu, X, LogOut, User as UserIcon, Settings as SettingsIcon } from "lucide-react";
import Logo from "./Logo";
import ThemeToggle from "./ThemeToggle";
import NotificationBell from "./NotificationBell";
import { useAuth } from "@/context/AuthContext";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";

const links = [
  { to: "/", label: "Home" },
  { to: "/#features", label: "Features" },
  { to: "/#pricing", label: "Pricing" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const initials = (user?.name || user?.email || "U")
    .split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();

  return (
    <header
      data-testid="site-navbar"
      className={`sticky top-0 z-50 transition-all ${scrolled ? "glass" : "bg-transparent border-b border-transparent"}`}
    >
      <div className="container-luxe flex h-16 md:h-20 items-center justify-between">
        <Link to="/" data-testid="navbar-logo-link" className="flex items-center">
          <Logo />
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              data-testid={`nav-link-${l.label.toLowerCase()}`}
              className={({ isActive }) =>
                `text-sm font-medium transition-colors ${isActive ? "text-primary dark:text-white" : "text-muted-foreground hover:text-primary dark:hover:text-white"}`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <ThemeToggle />
          {user ? (
            <>
              <NotificationBell />
              <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="navbar-user-menu" className="h-9 w-9 rounded-full bg-primary text-white text-sm font-semibold flex items-center justify-center">
                  {initials}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="flex flex-col">
                  <span className="text-sm font-semibold">{user.name}</span>
                  <span className="text-xs text-muted-foreground">{user.email}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem data-testid="menu-profile" onClick={() => navigate("/profile")}>
                  <UserIcon className="mr-2 h-4 w-4" /> Profile
                </DropdownMenuItem>
                <DropdownMenuItem data-testid="menu-settings" onClick={() => navigate("/settings")}>
                  <SettingsIcon className="mr-2 h-4 w-4" /> Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem data-testid="menu-logout" onClick={async () => { await logout(); navigate("/"); }}>
                  <LogOut className="mr-2 h-4 w-4" /> Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            </>
          ) : (
            <>
              <Link
                to="/login"
                data-testid="navbar-login-btn"
                className="text-sm font-medium text-primary dark:text-white hover:opacity-80 px-4 py-2"
              >
                Login
              </Link>
              <Link
                to="/register"
                data-testid="navbar-register-btn"
                className="text-sm font-semibold rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 transition-colors"
              >
                Get Started
              </Link>
            </>
          )}
        </div>

        <button
          className="md:hidden inline-flex h-10 w-10 items-center justify-center rounded-md text-foreground"
          onClick={() => setOpen((v) => !v)}
          data-testid="navbar-mobile-toggle"
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-border bg-background" data-testid="navbar-mobile-panel">
          <div className="container-luxe py-4 flex flex-col gap-3">
            {links.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                onClick={() => setOpen(false)}
                className="py-2 text-base text-foreground"
                data-testid={`mobile-nav-${l.label.toLowerCase()}`}
              >
                {l.label}
              </Link>
            ))}
            <div className="flex items-center justify-between pt-2">
              <ThemeToggle />
              {user ? (
                <button onClick={async () => { await logout(); setOpen(false); navigate("/"); }} className="text-sm font-semibold rounded-full bg-primary text-primary-foreground px-5 py-2.5">
                  Log out
                </button>
              ) : (
                <div className="flex gap-2">
                  <Link to="/login" onClick={() => setOpen(false)} className="text-sm font-medium px-4 py-2">Login</Link>
                  <Link to="/register" onClick={() => setOpen(false)} className="text-sm font-semibold rounded-full bg-primary text-primary-foreground px-5 py-2.5">Get Started</Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
