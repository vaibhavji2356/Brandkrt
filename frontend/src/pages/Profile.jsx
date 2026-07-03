import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import SiteLayout from "@/components/SiteLayout";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Mail, BadgeCheck, Camera, LayoutDashboard } from "lucide-react";
import { Link } from "react-router-dom";

function ProfileAvatar({ src, name }) {
  const [imgError, setImgError] = useState(false);
  const safeSrc = typeof src === "string" && src.trim() ? src.trim() : "";
  const initials = (name || "U").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();

  useEffect(() => {
    setImgError(false);
  }, [safeSrc]);

  return (
    <Avatar className="h-24 w-24 rounded-2xl border-4 border-background bg-secondary text-secondary-foreground shadow-luxe-sm overflow-hidden">
      {safeSrc && !imgError ? <AvatarImage src={safeSrc} alt="" onError={() => setImgError(true)} /> : null}
      <AvatarFallback className="rounded-2xl bg-secondary text-secondary-foreground text-2xl font-display font-semibold">{initials}</AvatarFallback>
    </Avatar>
  );
}

export default function Profile() {
  const { user, refresh } = useAuth();
  const fileRef = useRef(null);
  const [name, setName] = useState(user?.name || "");
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(user?.avatar_url || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAvatarPreview(user?.avatar_url || "");
  }, [user?.avatar_url]);

  useEffect(() => {
    if (!avatarFile) return undefined;
    const reader = new FileReader();
    reader.onload = () => setAvatarPreview(reader.result || "");
    reader.readAsDataURL(avatarFile);
    return () => {
      if (reader.readyState === 1) reader.abort();
    };
  }, [avatarFile]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { name };
      if (avatarFile) {
        const fd = new FormData();
        fd.append("file", avatarFile);
        const { data } = await api.post("/uploads/profiles", fd, { headers: { "Content-Type": "multipart/form-data" } });
        payload.avatar_url = data.url;
      }
      await api.patch("/profile", payload);
      await refresh();
      toast.success("Profile updated.");
      setAvatarFile(null);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const resend = async () => {
    try {
      await api.post("/auth/resend-verification");
      toast.success("Verification email sent. Please check your inbox.");
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const initials = (user?.name || user?.email || "U").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
  const dashboardPath = user?.role === "admin" ? "/admin" : user?.role === "brand" ? "/brand" : user?.role === "influencer" ? "/influencer" : "/profile";

  return (
    <SiteLayout>
      <section className="section-y" data-testid="profile-page">
        <div className="container-luxe max-w-4xl">
          <div className="relative overflow-hidden rounded-2xl border border-border bg-card">
            <div className="h-40 bg-primary" style={{ backgroundImage: "radial-gradient(circle at 20% 50%, rgba(212,175,55,0.4), transparent 50%)" }} />
              <div className="px-8 pb-8">
                <div className="flex flex-col sm:flex-row sm:items-end sm:gap-6 -mt-12">
                <div data-testid="profile-avatar">
                  <ProfileAvatar src={avatarPreview} name={user?.name || user?.email} />
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
                <Link
                  to={dashboardPath}
                  className="mt-5 inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-5 py-2.5 text-sm font-semibold"
                  data-testid="profile-dashboard-link"
                >
                  <LayoutDashboard className="h-4 w-4" /> Open dashboard
                </Link>
              </div>

              <form onSubmit={save} className="mt-10 grid sm:grid-cols-2 gap-5" data-testid="profile-form">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Display name</label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-2" data-testid="profile-name-input" />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Avatar</label>
                  <div className="mt-2 flex flex-col gap-3">
                    <button
                      type="button"
                      onClick={() => fileRef.current?.click()}
                      className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-accent"
                      data-testid="profile-avatar-upload-btn"
                    >
                      <Camera className="h-4 w-4" /> Upload profile photo
                    </button>
                    <input
                      ref={fileRef}
                      type="file"
                      accept="image/*"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (!file) return;
                        setAvatarFile(file);
                      }}
                      className="hidden"
                      data-testid="profile-avatar-input"
                    />
                    {avatarPreview ? (
                      <img src={avatarPreview} alt="Avatar preview" className="h-24 w-24 rounded-2xl object-cover border border-border" />
                    ) : (
                      <div className="h-24 w-24 rounded-2xl border border-dashed border-border bg-background flex items-center justify-center text-sm text-muted-foreground">Preview appears here</div>
                    )}
                  </div>
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
