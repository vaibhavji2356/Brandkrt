import React, { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Send, Paperclip, Image as ImageIcon, Search, X as XIcon, Loader2, CheckCheck, MessageCircle,
  FileText, Download, ArrowLeft,
} from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";

const ASSET_BASE = process.env.REACT_APP_BACKEND_URL || "";

function fullUrl(maybeRelative) {
  if (!maybeRelative) return "";
  if (/^https?:\/\//i.test(maybeRelative)) return maybeRelative;
  return `${ASSET_BASE}${maybeRelative}`;
}

function timestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString([], { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
}

function dayLabel(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const yest = new Date(today); yest.setDate(yest.getDate() - 1);
  if (d >= today) return "Today";
  if (d >= yest) return "Yesterday";
  return d.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}

export default function ChatWindow({ conversation, onBack, onUpdated }) {
  const { user } = useAuth();
  const meId = user?.id;
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [body, setBody] = useState("");
  const [pending, setPending] = useState([]);   // attachments before send
  const [sending, setSending] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [query, setQuery] = useState("");
  const [typingPeers, setTypingPeers] = useState([]);
  const fileRef = useRef(null);
  const imageRef = useRef(null);
  const scrollRef = useRef(null);
  const typingTimerRef = useRef(null);

  const peer = conversation?.peers?.[0];

  const load = async () => {
    if (!conversation?.id) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/conversations/${conversation.id}/messages`, { params: { q: query || undefined } });
      setMessages(data.messages || []);
      // mark as read
      api.post(`/conversations/${conversation.id}/read`).catch(() => {});
      onUpdated?.();
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setLoading(false);
  };

  useEffect(() => {
    if (!conversation?.id) return;
    load();
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation?.id, query]);

  // poll typing every 4s
  useEffect(() => {
    if (!conversation?.id) return;
    let alive = true;
    const tick = async () => {
      try {
        const { data } = await api.get(`/conversations/${conversation.id}/typing`);
        if (alive) setTypingPeers(data.typing || []);
      } catch (_) { /* ignore */ }
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => { alive = false; clearInterval(id); };
  }, [conversation?.id]);

  // auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleTyping = () => {
    if (!conversation?.id) return;
    if (typingTimerRef.current) return; // throttle to once per ~3s
    api.post(`/conversations/${conversation.id}/typing`).catch(() => {});
    typingTimerRef.current = setTimeout(() => { typingTimerRef.current = null; }, 3000);
  };

  const uploadFile = async (file, kindHint) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/chat/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const att = { url: fullUrl(data.url), name: data.name, kind: kindHint || data.kind, size: data.size };
      setPending((arr) => [...arr, att]);
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const onPickFiles = async (e, hint) => {
    const files = Array.from(e.target.files || []);
    for (const f of files) {
      // eslint-disable-next-line no-await-in-loop
      await uploadFile(f, hint);
    }
    e.target.value = "";
  };

  const send = async () => {
    if (!conversation?.id) return;
    const text = body.trim();
    if (!text && pending.length === 0) return;
    setSending(true);
    try {
      await api.post(`/conversations/${conversation.id}/messages`, { body: text, attachments: pending });
      setBody("");
      setPending([]);
      await load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setSending(false);
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    } else {
      handleTyping();
    }
  };

  const grouped = useMemo(() => {
    const out = [];
    let lastDay = "";
    for (const m of messages) {
      const dl = dayLabel(m.created_at);
      if (dl !== lastDay) {
        out.push({ kind: "divider", label: dl, key: `d-${dl}-${m.id}` });
        lastDay = dl;
      }
      out.push({ kind: "msg", ...m, key: m.id });
    }
    return out;
  }, [messages]);

  if (!conversation) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background" data-testid="chat-empty">
        <div className="text-center max-w-sm px-6">
          <MessageCircle className="h-12 w-12 mx-auto text-muted-foreground" />
          <h3 className="mt-3 text-lg font-medium text-primary dark:text-white">Pick a conversation</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose any chat from the list to start messaging. New conversations open automatically when a collaboration or agreement is accepted.
          </p>
        </div>
      </div>
    );
  }

  const headerName = peer?.name || conversation.title || "Conversation";
  const initials = (headerName || "?").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
  const typingActive = typingPeers.length > 0;

  return (
    <div className="flex-1 min-w-0 flex flex-col bg-background" data-testid="chat-window">
      {/* Header */}
      <div className="h-16 border-b border-border bg-card flex items-center px-4 gap-3">
        <button type="button" onClick={onBack} className="md:hidden -ml-1 h-9 w-9 rounded-full hover:bg-accent flex items-center justify-center" data-testid="chat-back">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="h-10 w-10 rounded-full bg-primary text-primary-foreground text-sm font-semibold flex items-center justify-center">
          {peer?.avatar_url ? <img src={peer.avatar_url} alt={headerName} className="h-full w-full rounded-full object-cover" /> : initials}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-primary dark:text-white truncate">{headerName}</div>
          <div className="text-xs text-muted-foreground truncate">
            {typingActive ? (
              <span className="text-secondary inline-flex items-center gap-1">
                <span className="inline-flex gap-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-secondary animate-bounce [animation-delay:-0.2s]" />
                  <span className="h-1.5 w-1.5 rounded-full bg-secondary animate-bounce [animation-delay:-0.1s]" />
                  <span className="h-1.5 w-1.5 rounded-full bg-secondary animate-bounce" />
                </span>
                typing…
              </span>
            ) : (
              conversation.context_type !== "direct" ? `${conversation.context_type}` : (peer?.role || "")
            )}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowSearch((s) => !s)}
            data-testid="chat-toggle-search"
            className={`h-9 w-9 rounded-full border border-border flex items-center justify-center ${showSearch ? "bg-accent" : "bg-background hover:bg-accent"}`}
            title="Search messages"
          >
            <Search className="h-4 w-4" />
          </button>
        </div>
      </div>

      {showSearch && (
        <div className="px-4 py-2 border-b border-border bg-card">
          <div className="relative">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search this conversation…"
              className="pl-9"
              autoFocus
              data-testid="chat-search-input"
            />
          </div>
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-2" data-testid="chat-scroll">
        {loading && messages.length === 0 && (
          <div className="text-center text-sm text-muted-foreground">Loading messages…</div>
        )}
        {!loading && messages.length === 0 && (
          <div className="text-center py-10" data-testid="chat-thread-empty">
            <MessageCircle className="h-10 w-10 mx-auto text-muted-foreground" />
            <p className="mt-3 text-sm text-muted-foreground">No messages yet. Send the first message to get started.</p>
          </div>
        )}
        {grouped.map((item) => {
          if (item.kind === "divider") {
            return (
              <div key={item.key} className="flex items-center justify-center my-4">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground bg-card border border-border rounded-full px-3 py-1">
                  {item.label}
                </span>
              </div>
            );
          }
          const isMine = item.sender_id === meId;
          const readByPeer = (item.read_by || []).some((id) => id !== meId);
          return (
            <div key={item.key} className={`flex ${isMine ? "justify-end" : "justify-start"}`} data-testid={`chat-msg-${item.id}`}>
              <div className={`max-w-[78%] md:max-w-[68%] rounded-2xl px-3.5 py-2.5 ${
                isMine ? "bg-primary text-primary-foreground rounded-tr-sm" : "bg-card border border-border rounded-tl-sm"
              }`}>
                {!isMine && (
                  <div className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5">{item.sender_name}</div>
                )}
                {item.body && <div className="text-sm whitespace-pre-wrap break-words">{item.body}</div>}
                {item.attachments?.length > 0 && (
                  <div className={`mt-2 grid gap-2 ${item.attachments.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
                    {item.attachments.map((att, i) => (
                      <AttachmentPreview key={i} att={att} mine={isMine} />
                    ))}
                  </div>
                )}
                <div className={`mt-1 flex items-center gap-1 text-[10px] ${isMine ? "text-primary-foreground/70 justify-end" : "text-muted-foreground"}`}>
                  <span>{timestamp(item.created_at)}</span>
                  {isMine && <CheckCheck className={`h-3 w-3 ${readByPeer ? "text-secondary" : "opacity-50"}`} title={readByPeer ? "Read" : "Sent"} />}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pending attachments */}
      {pending.length > 0 && (
        <div className="px-4 py-2 border-t border-border bg-card flex gap-2 flex-wrap" data-testid="chat-pending">
          {pending.map((p, i) => (
            <div key={i} className="relative h-16 w-16 rounded-lg border border-border overflow-hidden bg-background">
              {p.kind === "image" ? (
                <img src={p.url} alt={p.name} className="h-full w-full object-cover" />
              ) : (
                <div className="h-full w-full flex flex-col items-center justify-center text-[10px] text-muted-foreground p-1 text-center">
                  <FileText className="h-4 w-4 text-secondary" />
                  <span className="truncate w-full">{p.name}</span>
                </div>
              )}
              <button
                type="button"
                onClick={() => setPending((arr) => arr.filter((_, idx) => idx !== i))}
                className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-destructive text-white flex items-center justify-center"
                data-testid={`pending-remove-${i}`}
              >
                <XIcon className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Composer */}
      <div className="border-t border-border bg-card p-3 flex items-end gap-2">
        <button
          type="button"
          onClick={() => imageRef.current?.click()}
          className="h-10 w-10 rounded-full border border-border bg-background hover:bg-accent flex items-center justify-center"
          title="Attach image"
          data-testid="chat-attach-image"
        >
          <ImageIcon className="h-4 w-4" />
        </button>
        <input ref={imageRef} type="file" accept="image/*" multiple onChange={(e) => onPickFiles(e, "image")} className="hidden" />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="h-10 w-10 rounded-full border border-border bg-background hover:bg-accent flex items-center justify-center"
          title="Attach file"
          data-testid="chat-attach-file"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        <input ref={fileRef} type="file" multiple onChange={(e) => onPickFiles(e)} className="hidden" />

        <Textarea
          rows={1}
          value={body}
          onChange={(e) => { setBody(e.target.value); handleTyping(); }}
          onKeyDown={onKey}
          placeholder="Type a message…"
          className="flex-1 min-h-[40px] max-h-[140px] resize-none"
          data-testid="chat-input"
        />
        <button
          type="button"
          onClick={send}
          disabled={sending || (!body.trim() && pending.length === 0)}
          className="h-10 w-10 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center"
          data-testid="chat-send"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function AttachmentPreview({ att, mine }) {
  if (att.kind === "image") {
    return (
      <a href={att.url} target="_blank" rel="noreferrer" className="block rounded-xl overflow-hidden border border-border bg-background">
        <img src={att.url} alt={att.name || "image"} className="max-h-64 w-full object-cover" />
      </a>
    );
  }
  return (
    <a
      href={att.url}
      target="_blank"
      rel="noreferrer"
      className={`flex items-center gap-2 rounded-xl px-3 py-2 border ${
        mine ? "bg-primary-foreground/10 border-primary-foreground/30" : "bg-background border-border"
      }`}
    >
      <FileText className="h-4 w-4 shrink-0 text-secondary" />
      <span className="text-xs truncate flex-1">{att.name || "Attachment"}</span>
      <Download className="h-3.5 w-3.5 opacity-60" />
    </a>
  );
}
