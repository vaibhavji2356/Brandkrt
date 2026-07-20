import React, { useEffect, useMemo, useState } from "react";
import { BarChart3, CalendarClock, CheckCircle2, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const EMPTY_FILES = { instagram: [], youtube: [], facebook: [] };

function formatCountdown(seconds) {
  const safe = Math.max(0, Number(seconds || 0));
  const days = Math.floor(safe / 86400);
  const hours = Math.floor((safe % 86400) / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  return `${days}d ${hours}h ${minutes}m`;
}

function indiaDate(value) {
  if (!value) return "Not updated yet";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  }).format(new Date(value));
}

export default function CreatorInsights() {
  const [status, setStatus] = useState(null);
  const [seconds, setSeconds] = useState(0);
  const [files, setFiles] = useState(EMPTY_FILES);
  const [form, setForm] = useState({ followers: "", avg_reel_views: "", monthly_reach: "", notes: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [s, me] = await Promise.all([api.get("/influencers/insights/status"), api.get("/influencers/me")]);
      setStatus(s.data);
      setSeconds(s.data.seconds_remaining || 0);
      const profile = me.data.influencer || {};
      setForm((current) => ({
        ...current,
        followers: current.followers || String(profile.followers || ""),
        avg_reel_views: current.avg_reel_views || String(profile.avg_reel_views || ""),
        monthly_reach: current.monthly_reach || String(profile.monthly_reach || ""),
      }));
    } catch (error) {
      toast.error(formatApiError(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((value) => Math.max(0, value - 60)), 60000);
    return () => window.clearInterval(timer);
  }, []);

  const canUpdate = Boolean(status?.can_update || seconds === 0);
  const selectedCount = useMemo(() => Object.values(files).reduce((total, list) => total + list.length, 0), [files]);

  const selectFiles = (platform, list) => {
    const selected = Array.from(list || []).slice(0, 4);
    if ((list?.length || 0) > 4) toast.error("Maximum 4 screenshots per platform.");
    setFiles((current) => ({ ...current, [platform]: selected }));
  };

  const submit = async () => {
    if (!canUpdate) return toast.error("Monthly insight update is not due yet.");
    if (!selectedCount) return toast.error("Upload at least one platform insight screenshot.");
    setSaving(true);
    try {
      const upload = async (file, platform, index) => {
        const body = new FormData();
        body.append("file", file);
        const { data } = await api.post("/uploads/verification", body, { headers: { "Content-Type": "multipart/form-data" } });
        return { type: `${platform}_monthly_insights`, label: `${platform} monthly insights`, name: file.name, index, url: data.url };
      };
      const documents = (await Promise.all(Object.entries(files).flatMap(([platform, list]) => list.map((file, index) => upload(file, platform, index + 1))))).filter(Boolean);
      const numberOrNull = (value) => value === "" ? null : Number(value);
      const { data } = await api.post("/influencers/insights", {
        documents,
        followers: numberOrNull(form.followers),
        avg_reel_views: numberOrNull(form.avg_reel_views),
        monthly_reach: numberOrNull(form.monthly_reach),
        notes: form.notes.trim() || null,
      });
      setStatus(data);
      setSeconds(data.seconds_remaining || 0);
      setFiles(EMPTY_FILES);
      setForm((current) => ({ ...current, notes: "" }));
      toast.success("Monthly insights updated. Next update opens in 30 days.");
    } catch (error) {
      toast.error(formatApiError(error));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-muted-foreground">Loading monthly insights…</div>;

  return (
    <div className="space-y-6" data-testid="creator-monthly-insights">
      <div>
        <h2 className="text-3xl font-display font-light text-primary dark:text-white">Monthly Insights</h2>
        <p className="mt-1 text-sm text-muted-foreground">Keep your audience and performance data fresh for brands. This is only required for verified creators.</p>
      </div>

      {!status?.verified ? (
        <div className="rounded-2xl border border-warning/40 bg-warning/10 p-5 text-sm">Complete creator verification before submitting monthly insights.</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground"><CalendarClock className="h-4 w-4 text-secondary" /> Next update</div>
              <div className="mt-3 text-3xl font-display text-primary dark:text-white">{canUpdate ? "Update available" : formatCountdown(seconds)}</div>
              <p className="mt-1 text-xs text-muted-foreground">Due: {indiaDate(status.next_update_at)}</p>
            </div>
            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground"><CheckCircle2 className="h-4 w-4 text-secondary" /> Last update</div>
              <div className="mt-3 text-lg font-semibold text-primary dark:text-white">{indiaDate(status.last_updated_at)}</div>
              <p className="mt-1 text-xs text-muted-foreground">The next upload opens every 30 days.</p>
            </div>
          </div>

          <div className={`rounded-2xl border border-border bg-card p-6 ${canUpdate ? "" : "opacity-60"}`}>
            <div className="flex items-center gap-2"><BarChart3 className="h-5 w-5 text-secondary" /><h3 className="font-semibold text-primary dark:text-white">Update current performance</h3></div>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <Field label="Followers"><Input type="number" min="0" value={form.followers} onChange={(e) => setForm({ ...form, followers: e.target.value })} disabled={!canUpdate} /></Field>
              <Field label="Average reel views"><Input type="number" min="0" value={form.avg_reel_views} onChange={(e) => setForm({ ...form, avg_reel_views: e.target.value })} disabled={!canUpdate} /></Field>
              <Field label="Monthly reach"><Input type="number" min="0" value={form.monthly_reach} onChange={(e) => setForm({ ...form, monthly_reach: e.target.value })} disabled={!canUpdate} /></Field>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              {[["instagram", "Instagram insights"], ["youtube", "YouTube insights"], ["facebook", "Facebook insights"]].map(([platform, label]) => (
                <Field key={platform} label={label}>
                  <Input type="file" accept="image/*,.pdf" multiple disabled={!canUpdate} onChange={(e) => selectFiles(platform, e.target.files)} />
                  <p className="mt-1 text-xs text-muted-foreground">Up to 4 screenshots or PDFs.</p>
                </Field>
              ))}
            </div>
            <div className="mt-5"><Field label="Note"><Textarea rows={3} value={form.notes} disabled={!canUpdate} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Mention recent growth, viral posts, audience changes, or campaign performance." /></Field></div>
            <button type="button" onClick={submit} disabled={!canUpdate || saving} className="mt-5 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}{saving ? "Uploading…" : `Submit monthly update${selectedCount ? ` (${selectedCount})` : ""}`}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return <label className="block"><span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</span><div className="mt-2">{children}</div></label>;
}
