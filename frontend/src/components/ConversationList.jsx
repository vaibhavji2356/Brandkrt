import React from "react";
import { Search, Inbox } from "lucide-react";
import { Input } from "@/components/ui/input";
import UserAvatar from "@/components/UserAvatar";

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const diffDays = Math.floor((today - d) / 86400000);
  if (diffDays < 7) return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString();
}

export default function ConversationList({
  conversations = [],
  selectedId,
  onSelect,
  search,
  onSearch,
  loading,
}) {
  return (
    <aside className="w-full md:w-80 shrink-0 border-r border-border bg-card flex flex-col" data-testid="conversation-list">
      <div className="p-4 border-b border-border">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Messages</h2>
        <div className="mt-3 relative">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => onSearch?.(e.target.value)}
            placeholder="Search conversations…"
            className="pl-9"
            data-testid="conversation-search"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-6 text-sm text-muted-foreground">Loading…</div>
        ) : conversations.length === 0 ? (
          <div className="p-10 text-center" data-testid="conversation-empty">
            <Inbox className="h-10 w-10 mx-auto text-muted-foreground" />
            <h3 className="mt-3 text-sm font-medium text-primary dark:text-white">No conversations yet</h3>
            <p className="mt-1 text-xs text-muted-foreground max-w-[240px] mx-auto">
              Chats unlock when a collaboration is accepted, an agreement is signed, or escrow is funded on a deal.
            </p>
          </div>
        ) : (
          conversations.map((c) => {
            const peer = c.peers?.[0];
            const name = peer?.name || c.title || "Conversation";
            const initials = (name || "?").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
            const isActive = c.id === selectedId;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelect?.(c)}
                data-testid={`conv-item-${c.id}`}
                className={`w-full text-left px-4 py-3 border-b border-border flex items-start gap-3 transition-colors ${
                  isActive ? "bg-accent" : "hover:bg-accent/60"
                }`}
              >
                <UserAvatar src={peer?.avatar_url} initials={initials} className="h-10 w-10 shrink-0 rounded-full text-sm font-semibold" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-primary dark:text-white truncate">{name}</div>
                    <div className="text-[10px] text-muted-foreground whitespace-nowrap">{formatTime(c.last_message_at)}</div>
                  </div>
                  <div className="flex items-center justify-between gap-2 mt-0.5">
                    <div className="text-xs text-muted-foreground truncate">
                      {c.last_message || (
                        <span className="italic">Say hello 👋</span>
                      )}
                    </div>
                    {c.unread_count > 0 && (
                      <span className="ml-2 min-w-[18px] h-[18px] px-1 rounded-full bg-secondary text-secondary-foreground text-[10px] font-bold flex items-center justify-center">
                        {c.unread_count > 99 ? "99+" : c.unread_count}
                      </span>
                    )}
                  </div>
                  {c.context_type && c.context_type !== "direct" && (
                    <div className="mt-1 inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-secondary">
                      {c.context_type}
                    </div>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
