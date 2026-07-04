import React, { useEffect, useState } from "react";
import { Bell, Check } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import api from "@/lib/api";

export default function NotificationBell() {
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

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
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
          <div key={n.id} className={`px-3 py-3 border-b border-border last:border-b-0 ${n.read ? "" : "bg-accent/40"}`} data-testid={`notif-${n.id}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium text-primary dark:text-white truncate">{n.title}</div>
                {n.body && <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.body}</div>}
                <div className="text-[10px] uppercase tracking-wider text-secondary mt-1">{n.type}</div>
              </div>
              {!n.read && (
                <button onClick={() => markRead(n.id)} className="text-secondary hover:text-primary" title="Mark read" data-testid={`notif-read-${n.id}`}>
                  <Check className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
