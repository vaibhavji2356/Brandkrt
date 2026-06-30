import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bookmark, Search } from "lucide-react";
import { EmptyState } from "@/components/State";
import { useAuth } from "@/context/AuthContext";
import { readSaved, toggleSaved } from "@/lib/savedInfluencers";
import { InfluencerCard, InviteDialog } from "@/pages/brand/BrandDiscover";

export default function BrandSaved() {
  const { user } = useAuth();
  const [saved, setSaved] = useState({});
  const [inviteOpen, setInviteOpen] = useState(null);

  useEffect(() => { setSaved(readSaved(user?.id)); }, [user?.id]);

  const list = useMemo(() => Object.values(saved).sort((a, b) => (b.saved_at || "").localeCompare(a.saved_at || "")), [saved]);

  const toggle = (inf) => { const next = toggleSaved(user?.id, inf); setSaved(next); };

  return (
    <div className="space-y-6" data-testid="brand-saved">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-display font-light text-primary dark:text-white">Saved Influencers</h2>
          <p className="text-sm text-muted-foreground mt-1">Your private shortlist. Invite any of them to a campaign in one click.</p>
        </div>
        <Link to="/brand/discover" className="inline-flex items-center gap-2 rounded-full border border-border bg-card hover:bg-accent px-4 py-2 text-sm font-semibold" data-testid="saved-discover-link">
          <Search className="h-4 w-4" /> Discover more
        </Link>
      </div>

      {list.length === 0 ? (
        <EmptyState
          icon={Bookmark}
          title="No saved creators yet"
          description="Browse creators on the Discover page and tap the bookmark icon to add them to your shortlist."
          action={<Link to="/brand/discover" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold">Discover creators</Link>}
          testId="saved-empty"
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="saved-list">
          {list.map((inf) => (
            <InfluencerCard
              key={inf.id}
              inf={inf}
              isSaved
              onToggleSave={() => toggle(inf)}
              onOpen={() => setInviteOpen(inf)}
              onInvite={() => setInviteOpen(inf)}
            />
          ))}
        </div>
      )}

      <InviteDialog open={!!inviteOpen} influencer={inviteOpen} onClose={() => setInviteOpen(null)} />
    </div>
  );
}
