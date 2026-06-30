import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import ConversationList from "@/components/ConversationList";
import ChatWindow from "@/components/ChatWindow";

export default function Messages() {
  const location = useLocation();
  const [params] = useSearchParams();
  const [convs, setConvs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showListMobile, setShowListMobile] = useState(true);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/conversations", { params: { q: search || undefined } });
      const list = data.conversations || [];
      setConvs(list);
      // If a conversation_id is requested or selected stale, sync
      const requestedId = params.get("conversation_id");
      if (requestedId) {
        const match = list.find((c) => c.id === requestedId);
        if (match) {
          setSelected(match);
          setShowListMobile(false);
        }
      } else if (selected) {
        const match = list.find((c) => c.id === selected.id);
        if (match) setSelected(match);
      }
    } catch (err) {
      // 401 silent; other errors toast
      if (err?.response?.status !== 401) toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, [search, params, selected]);

  // Auto-open conversation based on query params
  useEffect(() => {
    const context_type = params.get("context_type");
    const context_id = params.get("context_id");
    const peer_user_id = params.get("peer_user_id");
    if (context_type && (context_id || peer_user_id)) {
      (async () => {
        try {
          const { data } = await api.post("/conversations", {
            context_type, context_id: context_id || undefined,
            peer_user_id: peer_user_id || undefined,
          });
          setSelected(data.conversation);
          setShowListMobile(false);
        } catch (err) {
          toast.error(formatApiError(err));
        } finally {
          load();
        }
      })();
    } else {
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  useEffect(() => {
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const handleSelect = (c) => {
    setSelected(c);
    setShowListMobile(false);
  };

  const handleBack = () => setShowListMobile(true);

  const visibleClasses = useMemo(() => ({
    list: `${showListMobile ? "flex" : "hidden"} md:flex`,
    chat: `${showListMobile ? "hidden" : "flex"} md:flex flex-1 min-w-0`,
  }), [showListMobile]);

  return (
    <div className="-mx-4 md:-mx-8 -mt-4 md:-mt-8 h-[calc(100vh-4rem)] md:h-[calc(100vh-4rem)] flex" data-testid="messages-page">
      <div className={visibleClasses.list}>
        <ConversationList
          conversations={convs}
          selectedId={selected?.id}
          onSelect={handleSelect}
          search={search}
          onSearch={setSearch}
          loading={loading}
        />
      </div>
      <div className={visibleClasses.chat}>
        <ChatWindow conversation={selected} onBack={handleBack} onUpdated={load} />
      </div>
    </div>
  );
}
