import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import SiteLayout from "@/components/SiteLayout";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { LayoutDashboard } from "lucide-react";

export default function Settings() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [savingPwd, setSavingPwd] = useState(false);

  const [notifications, setNotifications] = useState({ email: true, marketing: false, product: true });
  const [language, setLanguage] = useState("en");
  const dashboardPath = user?.role === "admin" ? "/admin" : user?.role === "brand" ? "/brand" : user?.role === "influencer" ? "/influencer" : "/profile";

  const changePassword = async (e) => {
    e.preventDefault();
    if (next !== confirm) { toast.error("Passwords do not match"); return; }
    setSavingPwd(true);
    try {
      await api.post("/profile/change-password", { current_password: current, new_password: next });
      toast.success("Password updated.");
      setCurrent(""); setNext(""); setConfirm("");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSavingPwd(false);
    }
  };

  const deleteAccount = async () => {
    try {
      await api.delete("/profile");
      await logout();
      toast.success("Account deleted.");
      navigate("/");
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  return (
    <SiteLayout>
      <section className="section-y" data-testid="settings-page">
        <div className="container-luxe max-w-4xl">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-4xl font-display font-light tracking-tight text-primary dark:text-white">Settings</h1>
              <p className="mt-2 text-muted-foreground">Manage account preferences and security.</p>
            </div>
            <button
              type="button"
              onClick={() => navigate(dashboardPath)}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-5 py-2.5 text-sm font-semibold"
              data-testid="settings-dashboard-link"
            >
              <LayoutDashboard className="h-4 w-4" /> Dashboard
            </button>
          </div>

          <Tabs defaultValue="account" className="mt-10">
            <TabsList className="grid grid-cols-4 max-w-xl">
              <TabsTrigger value="account" data-testid="settings-tab-account">Account</TabsTrigger>
              <TabsTrigger value="password" data-testid="settings-tab-password">Password</TabsTrigger>
              <TabsTrigger value="notifications" data-testid="settings-tab-notifications">Notifications</TabsTrigger>
              <TabsTrigger value="appearance" data-testid="settings-tab-appearance">Appearance</TabsTrigger>
            </TabsList>

            <TabsContent value="account" className="mt-6">
              <div className="rounded-2xl border border-border bg-card p-6 space-y-5">
                <div className="grid sm:grid-cols-2 gap-5">
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Email</label>
                    <Input value={user?.email || ""} disabled className="mt-2" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Role</label>
                    <Input value={user?.role || ""} disabled className="mt-2 capitalize" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Language</label>
                    <Select value={language} onValueChange={setLanguage}>
                      <SelectTrigger className="mt-2" data-testid="settings-language"><SelectValue placeholder="Language" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="en">English</SelectItem>
                        <SelectItem value="hi">हिन्दी (Hindi)</SelectItem>
                        <SelectItem value="es">Español</SelectItem>
                        <SelectItem value="fr">Français</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <div className="mt-6 rounded-2xl border border-destructive/30 bg-destructive/5 p-6">
                <h3 className="text-lg font-medium text-destructive">Danger zone</h3>
                <p className="mt-1 text-sm text-foreground/80">Permanently delete your account and all associated data.</p>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button className="mt-4 rounded-full bg-destructive text-destructive-foreground px-5 py-2.5 text-sm font-semibold" data-testid="delete-account-btn">
                      Delete account
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete your BrandKrt account?</AlertDialogTitle>
                      <AlertDialogDescription>This action is irreversible and will remove your profile, campaigns and history.</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel data-testid="delete-cancel">Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={deleteAccount} data-testid="delete-confirm" className="bg-destructive hover:bg-destructive/90">Yes, delete</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </TabsContent>

            <TabsContent value="password" className="mt-6">
              <form onSubmit={changePassword} className="rounded-2xl border border-border bg-card p-6 space-y-5" data-testid="password-form">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Current password</label>
                  <Input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required className="mt-2" data-testid="password-current" />
                </div>
                <div className="grid sm:grid-cols-2 gap-5">
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">New password</label>
                    <Input type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} className="mt-2" data-testid="password-new" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Confirm new</label>
                    <Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} className="mt-2" data-testid="password-confirm" />
                  </div>
                </div>
                <div className="flex justify-end">
                  <button type="submit" disabled={savingPwd} className="rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold disabled:opacity-60" data-testid="password-save">
                    {savingPwd ? "Updating..." : "Update password"}
                  </button>
                </div>
              </form>
            </TabsContent>

            <TabsContent value="notifications" className="mt-6">
              <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
                {[
                  { k: "email", t: "Transactional emails", d: "Receive critical alerts about your account and campaigns." },
                  { k: "product", t: "Product updates", d: "Be the first to know about new features." },
                  { k: "marketing", t: "Marketing & tips", d: "Curated content to help you grow." },
                ].map((row) => (
                  <div key={row.k} className="flex items-center justify-between gap-6">
                    <div>
                      <div className="text-sm font-medium text-primary dark:text-white">{row.t}</div>
                      <div className="text-xs text-muted-foreground">{row.d}</div>
                    </div>
                    <Switch
                      checked={notifications[row.k]}
                      onCheckedChange={(v) => setNotifications((n) => ({ ...n, [row.k]: !!v }))}
                      data-testid={`notif-${row.k}`}
                    />
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="appearance" className="mt-6">
              <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-primary dark:text-white">Dark mode</div>
                    <div className="text-xs text-muted-foreground">Toggle the theme across the entire app.</div>
                  </div>
                  <Switch checked={theme === "dark"} onCheckedChange={(v) => setTheme(v ? "dark" : "light")} data-testid="appearance-dark" />
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </section>
    </SiteLayout>
  );
}
