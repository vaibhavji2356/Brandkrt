import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import SiteLayout from "@/components/SiteLayout";
import { Input } from "@/components/ui/input";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Mail, BadgeCheck } from "lucide-react";
import { Link } from "react-router-dom";

export default function Profile() {
  const { user, refresh } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [avatar, setAvatar] = useState(user?.avatar_url || "");
  const [saving, setSaving] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.patch("/profile", { name, avatar_url: avatar || null });
      await refresh();
      toast.success("Profile updated.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const resend = async () => {
    try {
      await api.post("/auth/resend-verification");
      toast.success("Verification email sent (check backend logs in development).");
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const initials = (user?.name || user?.email || "U").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();

  return (
    <SiteLayout>
      <section className="section-y" data-testid="profile-page">
        <div className="container-luxe max-w-4xl">
          <div className="relative overflow-hidden rounded-2xl border border-border bg-card">
            <div className="h-40 bg-primary" style={{ backgroundImage: "radial-gradient(circle at 20% 50%, rgba(212,175,55,0.4), transparent 50%)" }} />
            <div className="px-8 pb-8">
              <div className="flex flex-col sm:flex-row sm:items-end sm:gap-6 -mt-12">
                <div className="h-24 w-24 rounded-2xl border-4 border-background bg-secondary text-secondary-foreground flex items-center justify-center text-2xl font-display font-semibold shadow-luxe-sm" data-testid="profile-avatar">
                  {avatar ? <img src={avatar} alt="" className="h-full w-full object-cover rounded-2xl" /> : initials}
                </div>
                <div className="mt-4 sm:mt-0">
                  <h1 className="text-2xl md:text-3xl font-display font-light tracking-tight text-primary dark:text-white" data-testid="profile-name">{user?.name}</h1>
                  <p className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                    <Mail className="h-3.5 w-3.5" /> {user?.email}
                    {user?.email_verified ? (
                      <span className="inline-flex items-center gap-1 text-success ml-2"><BadgeCheck className="h-3.5 w-3.5" /> verified</span>
                    ) : (
                      <button onClick={resend} data-testid="profile-resend-verify" className="ml-2 text-secondary hover:underline">resend verification</button>
                    )}
                  </p>
                  <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-accent text-secondary px-3 py-1 text-xs font-semibold capitalize">
                    <ShieldCheck className="h-3.5 w-3.5" /> {user?.role}
                  </span>
                </div>
              </div>

              <form onSubmit={save} className="mt-10 grid sm:grid-cols-2 gap-5" data-testid="profile-form">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Display name</label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-2" data-testid="profile-name-input" />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Avatar URL</label>
                  <Input value={avatar} onChange={(e) => setAvatar(e.target.value)} placeholder="https://..." className="mt-2" data-testid="profile-avatar-input" />
                </div>
                <div className="sm:col-span-2 flex justify-end">
                  <button type="submit" disabled={saving} data-testid="profile-save" className="rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold disabled:opacity-60">
                    {saving ? "Saving..." : "Save changes"}
                  </button>
                </div>
              </form>

              <div className="mt-8 text-sm">
                Looking for advanced controls? <Link to="/settings" className="text-secondary font-semibold hover:underline">Open Settings →</Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </SiteLayout>
  );
}
