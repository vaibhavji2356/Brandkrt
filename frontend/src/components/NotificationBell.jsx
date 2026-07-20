import React, { useEffect, useState } from "react";
import { Bell, Check } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import api from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

function notificationPath(notification, role) {
  const meta = notification?.meta || {};
  if (meta.deal_id) return `/${role === "brand" ? "brand" : "influencer"}/deals/${meta.deal_id}`;
  if (meta.agreement_id) return `/agreements/${meta.agreement_id}`;
  if (meta.conversation_id) return `/${role === "brand" ? "brand" : "influencer"}/messages?conversation_id=${meta.conversation_id}`;
  if (meta.campaign_id && role === "brand") return `/brand/campaigns/${meta.campaign_id}`;
  if (notification?.type?.startsWith("verification.")) return `/${role === "brand" ? "brand" : "influencer"}/verification`;
  return `/${role === "brand" ? "brand" : "influencer"}/notifications`;
}

export default function NotificationBell() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const unread = items.filter((n) => !n.read).length;

  const load = async () => {
    try { const r = await api.get("/notifications"); setItems(r.data.notifications || []); }
    catch (_) { /* not logged in */ }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(t);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  const markRead = async (id) => {
    await api.post(`/notifications/${id}/read`);
    setItems((arr) => arr.map((n) => n.id === id ? { ...n, read: true } : n));
  };

  const openNotification = async (notification) => {
    if (!notification.read) await markRead(notification.id);
    setOpen(false);
    navigate(notificationPath(notification, user?.role));
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen} modal={false}>
      <DropdownMenuTrigger asChild>
        <button data-testid="notification-bell" aria-label="Notifications" className="relative h-9 w-9 rounded-full border border-border bg-background hover:bg-accent flex items-center justify-center">
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span data-testid="notification-unread-count" className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-secondary text-secondary-foreground text-[10px] font-bold flex items-center justify-center">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-h-96 overflow-auto" data-testid="notification-panel">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>Notifications</span>
          <span className="text-xs text-muted-foreground">{unread} unread</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {items.length === 0 && <div className="p-6 text-center text-sm text-muted-foreground">You're all caught up.</div>}
        {items.map((n) => (
          <div key={n.id} role="button" tabIndex={0} onClick={() => openNotification(n)} onKeyDown={(e) => e.key === "Enter" && openNotification(n)} className={`cursor-pointer px-3 py-3 border-b border-border last:border-b-0 ${n.read ? "" : "bg-accent/40"}`} data-testid={`notif-${n.id}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium text-primary dark:text-white truncate">{n.title}</div>
                {n.body && <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.body}</div>}
                {(n.meta?.reference || n.meta?.screenshot_url) && (
                  <div className="mt-2 space-y-1 rounded-lg border border-border bg-background/70 px-2 py-1.5 text-[11px]">
                    {n.meta?.reference && (
                      <div className="break-all">
                        <span className="font-semibold text-muted-foreground">Ref: </span>
                        <span className="text-foreground">{n.meta.reference}</span>
                      </div>
                    )}
                    {n.meta?.screenshot_url && (
                      <a
                        href={n.meta.screenshot_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex font-semibold text-secondary hover:underline"
                      >
                        View screenshot
                      </a>
                    )}
                  </div>
                )}
                <div className="text-[10px] uppercase tracking-wider text-secondary mt-1">{n.type}</div>
              </div>
              {!n.read && (
                <button onClick={(e) => { e.stopPropagation(); markRead(n.id); }} className="text-secondary hover:text-primary" title="Mark read" data-testid={`notif-read-${n.id}`}>
                  <Check className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        <button onClick={() => { setOpen(false); navigate(`/${user?.role === "brand" ? "brand" : "influencer"}/notifications`); }} className="w-full px-4 py-3 text-sm font-semibold text-secondary hover:bg-accent">Open notification centre</button>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
