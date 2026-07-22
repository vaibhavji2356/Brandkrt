import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, Archive, ArrowUpRight, BarChart3, Bookmark, Bot, Building2,
  CheckCircle2, Clock3, ExternalLink, MessageSquareText, RefreshCw,
  Search, Send, Sparkles, UserRound, Users,
} from "lucide-react";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";


const PLATFORMS = ["instagram", "youtube", "snapchat", "twitch", "x"];
const LEAD_STATUSES = [
  "new", "contact_planned", "contacted", "follow_up_required", "replied",
  "negotiating", "converted", "closed",
];

const emptyAnalytics = {
  brands_found: 0, creators_found: 0, high_priority_leads: 0, contacted: 0,
  replies: 0, converted: 0, research_volume: 0, saved_leads: 0,
  top_niches: [], top_platforms: [], recent_activity: [],
};


function title(value) {
  return String(value || "unavailable").replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function number(value) {
  return value == null ? "Unavailable" : Number(value).toLocaleString();
}

function percent(value) {
  return value == null ? "Unavailable" : `${Number(value).toFixed(2)}%`;
}

function date(value) {
  if (!value) return "Unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unavailable" : parsed.toLocaleString();
}

function list(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function optionalNumber(value) {
  if (value === "" || value == null) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}


function PageHeader({ eyebrow = "Admin intelligence", title: heading, description, actions }) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-secondary">{eyebrow}</p>
        <h2 className="mt-2 text-3xl font-display font-light text-primary dark:text-white">{heading}</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

function Panel({ children, className = "" }) {
  return <section className={`rounded-2xl border border-border bg-card p-5 shadow-sm ${className}`}>{children}</section>;
}

function Loading({ label = "Loading intelligence..." }) {
  return (
    <div className="flex min-h-40 items-center justify-center gap-3 text-sm text-muted-foreground" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-secondary border-t-transparent" /> {label}
    </div>
  );
}

function Failure({ message, retry }) {
  return (
    <Panel className="border-destructive/30 bg-destructive/5" data-testid="admin-ai-error">
      <p className="font-semibold text-destructive">Could not load this workspace</p>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      <button type="button" onClick={retry} className="mt-4 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
        Retry
      </button>
    </Panel>
  );
}

function Empty({ title: heading, message, action }) {
  return (
    <Panel className="py-12 text-center">
      <Search className="mx-auto h-8 w-8 text-secondary" />
      <h3 className="mt-3 font-semibold text-primary dark:text-white">{heading}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">{message}</p>
      {action}
    </Panel>
  );
}

function Metric({ label, value, icon: Icon = Activity }) {
  return (
    <Panel>
      <div className="flex items-center justify-between text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}<Icon className="h-4 w-4 text-secondary" />
      </div>
      <p className="mt-3 text-3xl font-display font-light text-primary dark:text-white">{number(value)}</p>
    </Panel>
  );
}

function Badge({ children, tone = "default" }) {
  const colors = tone === "high" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
    : tone === "medium" ? "bg-amber-500/10 text-amber-700 dark:text-amber-300"
      : tone === "low" ? "bg-slate-500/10 text-slate-600 dark:text-slate-300"
        : "bg-secondary/15 text-primary dark:text-secondary";
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${colors}`}>{children}</span>;
}


export function AdminLeadIntelligenceHome() {
  const [state, setState] = useState({ loading: true, error: "", data: emptyAnalytics });
  const load = async () => {
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const { data } = await api.get("/admin/lead-intelligence/analytics");
      setState({ loading: false, error: "", data });
    } catch (error) {
      setState({ loading: false, error: formatApiError(error), data: emptyAnalytics });
    }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (state.loading) return <Loading />;
  if (state.error) return <Failure message={state.error} retry={load} />;
  const data = state.data;
  return (
    <div className="space-y-7" data-testid="admin-lead-home">
      <PageHeader
        title="AI Lead Intelligence"
        description="Research factual brand and creator signals, prioritize grounded opportunities, and manage outreach from one admin-only workspace."
        actions={<>
          <Link className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground" to="/admin/brand-discovery">Discover brands</Link>
          <Link className="rounded-full border border-border px-4 py-2 text-sm font-semibold" to="/admin/creator-discovery">Discover creators</Link>
        </>}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Brands found" value={data.brands_found} icon={Building2} />
        <Metric label="Creators found" value={data.creators_found} icon={Users} />
        <Metric label="High priority" value={data.high_priority_leads} icon={Sparkles} />
        <Metric label="Saved leads" value={data.saved_leads} icon={Bookmark} />
        <Metric label="Contacted" value={data.contacted} icon={Send} />
        <Metric label="Replies" value={data.replies} icon={MessageSquareText} />
        <Metric label="Converted" value={data.converted} icon={CheckCircle2} />
        <Metric label="Research volume" value={data.research_volume} icon={BarChart3} />
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <Panel>
          <h3 className="font-semibold text-primary dark:text-white">Top niches</h3>
          <RankList items={data.top_niches} empty="Save leads to build niche intelligence." />
        </Panel>
        <Panel>
          <h3 className="font-semibold text-primary dark:text-white">Top platforms</h3>
          <RankList items={data.top_platforms} empty="Platform activity will appear after leads are saved." />
        </Panel>
        <Panel>
          <h3 className="font-semibold text-primary dark:text-white">Recent activity</h3>
          <div className="mt-4 space-y-3">
            {data.recent_activity.length ? data.recent_activity.slice(0, 6).map((item, index) => (
              <div key={`${item.action}-${index}`} className="border-b border-border/60 pb-3 last:border-0">
                <p className="text-sm font-medium">{title(item.action)}</p>
                <p className="mt-1 text-xs text-muted-foreground">{date(item.created_at)}</p>
              </div>
            )) : <p className="text-sm text-muted-foreground">No admin lead activity yet.</p>}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function RankList({ items, empty }) {
  if (!items?.length) return <p className="mt-4 text-sm text-muted-foreground">{empty}</p>;
  return <div className="mt-4 space-y-3">{items.map((item, index) => (
    <div key={item.name} className="flex items-center justify-between rounded-xl bg-muted/40 px-3 py-2">
      <span className="text-sm"><span className="mr-2 text-muted-foreground">{index + 1}</span>{title(item.name)}</span>
      <Badge>{item.count}</Badge>
    </div>
  ))}</div>;
}


const initialDiscovery = {
  research_name: "", industry: "", niche: "", categories: "", keywords: "",
  exclusions: "", location: "", language: "", minimum_followers: "",
  maximum_followers: "", minimum_engagement_rate: "", minimum_audience_quality: "",
  campaign_objective: "", minimum_budget: "", maximum_budget: "", currency: "INR",
  result_limit: "12", platforms: ["youtube"],
};

export function LeadDiscoveryPage({ entityType }) {
  const isBrand = entityType === "brand";
  const [form, setForm] = useState({ ...initialDiscovery, platforms: isBrand ? ["youtube", "x"] : ["youtube", "twitch", "x"] });
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState({});
  const [resultSearch, setResultSearch] = useState("");
  const [sortBy, setSortBy] = useState("priority");
  const [page, setPage] = useState(1);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const togglePlatform = (platform) => setForm((current) => ({
    ...current,
    platforms: current.platforms.includes(platform)
      ? current.platforms.filter((value) => value !== platform)
      : [...current.platforms, platform],
  }));

  const payload = () => {
    const result = {
      entity_type: entityType, platforms: form.platforms, result_limit: Number(form.result_limit),
      currency: form.currency, categories: list(form.categories), keywords: list(form.keywords),
      exclusions: list(form.exclusions),
    };
    ["research_name", "industry", "niche", "location", "language", "campaign_objective"].forEach((key) => {
      if (form[key].trim()) result[key] = form[key].trim();
    });
    ["minimum_followers", "maximum_followers", "minimum_engagement_rate", "minimum_audience_quality", "minimum_budget", "maximum_budget"].forEach((key) => {
      const value = optionalNumber(form[key]);
      if (value !== undefined) result[key] = value;
    });
    return result;
  };

  const poll = async (jobId) => {
    const deadline = Date.now() + 120000;
    while (alive.current && Date.now() < deadline) {
      const { data } = await api.get(`/admin/lead-intelligence/research/jobs/${jobId}`, { __maxRetries: 1 });
      if (!alive.current) return;
      setJob(data);
      if (["completed", "failed"].includes(data.status)) return data;
      await new Promise((resolve) => window.setTimeout(resolve, 900));
    }
    throw new Error("Research is still running. Open Research History to check progress or retry.");
  };

  const submit = async (event) => {
    event?.preventDefault();
    if (!form.platforms.length) {
      setError("Select at least one platform.");
      return;
    }
    setLoading(true); setError(""); setJob(null); setSaved({}); setPage(1);
    try {
      const { data } = await api.post("/admin/lead-intelligence/research/jobs", payload());
      setJob(data);
      const completed = await poll(data.id);
      if (completed.status === "failed") throw new Error(completed.warnings?.[0] || "Research failed. Please retry.");
      toast.success(`${completed.result_count} factual lead${completed.result_count === 1 ? "" : "s"} found`);
    } catch (requestError) {
      setError(formatApiError(requestError));
    } finally {
      if (alive.current) setLoading(false);
    }
  };

  const saveLead = async (result) => {
    try {
      const { data } = await api.post("/admin/lead-intelligence/leads", { research_id: job.id, entity_key: result.entity_key });
      setSaved((current) => ({ ...current, [result.entity_key]: data.id }));
      toast.success("Lead saved to the outreach workspace");
    } catch (requestError) {
      toast.error(formatApiError(requestError));
    }
  };

  const filtered = useMemo(() => {
    const term = resultSearch.trim().toLowerCase();
    const values = (job?.results || []).filter((item) => !term || [
      item.display_name, item.username, item.platform, ...(item.categories || []), ...(item.keywords || []),
    ].some((value) => String(value || "").toLowerCase().includes(term)));
    return [...values].sort((a, b) => sortBy === "confidence"
      ? b.confidence - a.confidence
      : sortBy === "followers" ? (b.follower_count ?? -1) - (a.follower_count ?? -1)
        : sortBy === "recommendation" ? b.recommendation_score - a.recommendation_score
          : b.priority.score - a.priority.score);
  }, [job, resultSearch, sortBy]);
  const pageSize = 6;
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-7" data-testid={`admin-${entityType}-discovery`}>
      <PageHeader
        title={isBrand ? "Brand Discovery" : "Creator Discovery"}
        description={isBrand
          ? "Find brands from configured factual providers. Unsupported platform fields remain unavailable rather than inferred."
          : "Find creators, compare measurable fit, inspect grounded recommendations, and estimate pricing only when factual metrics support it."}
      />
      <Panel>
        <form className="space-y-5" onSubmit={submit} data-testid="lead-discovery-form">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Field label="Research name" value={form.research_name} onChange={(value) => update("research_name", value)} placeholder="Q3 outreach shortlist" />
            {isBrand
              ? <Field label="Industry" value={form.industry} onChange={(value) => update("industry", value)} placeholder="Sustainable fashion" />
              : <Field label="Niche" value={form.niche} onChange={(value) => update("niche", value)} placeholder="Fitness, gaming, fashion" />}
            <Field label="Categories" value={form.categories} onChange={(value) => update("categories", value)} placeholder="lifestyle, technology" />
            <Field label="Keywords" value={form.keywords} onChange={(value) => update("keywords", value)} placeholder="ethical, launch" />
            <Field label="Geography" value={form.location} onChange={(value) => update("location", value)} placeholder="Mumbai, India" />
            <Field label="Language" value={form.language} onChange={(value) => update("language", value)} placeholder="en" />
            {!isBrand && <Field label="Minimum followers" type="number" value={form.minimum_followers} onChange={(value) => update("minimum_followers", value)} />}
            {!isBrand && <Field label="Maximum followers" type="number" value={form.maximum_followers} onChange={(value) => update("maximum_followers", value)} />}
            {!isBrand && <Field label="Minimum engagement %" type="number" step="0.01" value={form.minimum_engagement_rate} onChange={(value) => update("minimum_engagement_rate", value)} />}
            {!isBrand && <Field label="Minimum audience quality" type="number" value={form.minimum_audience_quality} onChange={(value) => update("minimum_audience_quality", value)} hint="Applied only when an official quality measurement exists." />}
            <Field label="Campaign objective" value={form.campaign_objective} onChange={(value) => update("campaign_objective", value)} placeholder="Brand Awareness" />
            <label className="text-sm font-medium">Currency
              <select value={form.currency} onChange={(event) => update("currency", event.target.value)} className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2.5">
                <option value="INR">INR (Indian Rupees)</option>
                <option value="USD">USD</option>
              </select>
            </label>
            <Field label={`Maximum budget (${form.currency})`} type="number" value={form.maximum_budget} onChange={(value) => update("maximum_budget", value)} />
            <Field label="Exclusions" value={form.exclusions} onChange={(value) => update("exclusions", value)} placeholder="competitor, gambling" />
            <label className="text-sm font-medium">Result limit
              <select value={form.result_limit} onChange={(event) => update("result_limit", event.target.value)} className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2.5">
                {[6, 12, 20, 30, 50].map((value) => <option key={value}>{value}</option>)}
              </select>
            </label>
          </div>
          <div>
            <p className="text-sm font-medium">Platforms</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {PLATFORMS.map((platform) => (
                <label key={platform} className={`cursor-pointer rounded-full border px-3 py-2 text-xs font-semibold ${form.platforms.includes(platform) ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>
                  <input className="sr-only" type="checkbox" checked={form.platforms.includes(platform)} onChange={() => togglePlatform(platform)} />
                  {title(platform)}
                </label>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Instagram and Snapchat return clear provider limitations until official factual adapters are configured. No scraping is used.</p>
          </div>
          {error && <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" data-testid="lead-discovery-error">{error}</div>}
          <button disabled={loading} className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60" data-testid="lead-discovery-submit">
            {loading ? <><RefreshCw className="h-4 w-4 animate-spin" /> Researching {job?.progress || 0}%</> : <><Sparkles className="h-4 w-4" /> Start factual research</>}
          </button>
        </form>
      </Panel>

      {job?.status === "completed" && <>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-primary dark:text-white">{job.result_count} normalized results</h3>
            <p className="text-xs text-muted-foreground">{title(job.reasoning_source)} · {job.confidence.toFixed(1)}% aggregate confidence</p>
          </div>
          <div className="flex gap-2">
            <input aria-label="Search results" value={resultSearch} onChange={(event) => { setResultSearch(event.target.value); setPage(1); }} placeholder="Search results" className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm sm:w-48" />
            <select aria-label="Sort results" value={sortBy} onChange={(event) => setSortBy(event.target.value)} className="rounded-xl border border-border bg-background px-3 py-2 text-sm">
              <option value="priority">Priority</option><option value="recommendation">Recommendation</option><option value="confidence">Confidence</option><option value="followers">Followers</option>
            </select>
          </div>
        </div>
        {job.warnings?.length > 0 && <Panel className="bg-amber-500/5"><p className="text-sm font-semibold">Research notes</p><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted-foreground">{job.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></Panel>}
        {visible.length ? <div className="grid gap-5 xl:grid-cols-2">{visible.map((result) => (
          <LeadResultCard key={result.entity_key} result={result} savedId={saved[result.entity_key]} onSave={() => saveLead(result)} />
        ))}</div> : <Empty title="No matching leads" message="The configured factual providers returned no profiles for these filters. Adjust the criteria or provider selection and retry." />}
        <Pagination page={page} pageSize={pageSize} total={filtered.length} onPage={setPage} />
      </>}
    </div>
  );
}

function Field({ label, value, onChange, placeholder = "", type = "text", step, hint }) {
  return <label className="text-sm font-medium">{label}
    <input type={type} min={type === "number" ? 0 : undefined} step={step} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm" />
    {hint && <span className="mt-1 block text-[11px] font-normal text-muted-foreground">{hint}</span>}
  </label>;
}

function LeadResultCard({ result, onSave, savedId }) {
  const name = result.display_name || result.username || result.entity_key;
  return (
    <Panel className="space-y-5" data-testid="lead-result-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            {result.entity_type === "brand" ? <Building2 className="h-5 w-5" /> : <UserRound className="h-5 w-5" />}
          </div>
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-primary dark:text-white">{name}</h3>
            <div className="mt-1 flex flex-wrap gap-1.5"><Badge>{title(result.platform)}</Badge><Badge tone={result.priority.priority}>{title(result.priority.priority)} priority</Badge><Badge>{title(result.verification_status)}</Badge></div>
          </div>
        </div>
        <button type="button" onClick={onSave} disabled={Boolean(savedId)} className="shrink-0 rounded-full bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-60">
          {savedId ? "Saved" : "Save lead"}
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Mini label="Priority" value={`${result.priority.score.toFixed(1)}/100`} />
        <Mini label="Recommendation" value={`${result.recommendation_score.toFixed(1)}/100`} />
        <Mini label="Confidence" value={`${result.confidence.toFixed(1)}%`} />
        <Mini label="Followers" value={number(result.follower_count)} />
        <Mini label="Engagement" value={percent(result.engagement_rate)} />
        <Mini label="Avg. views" value={number(result.average_views)} />
        <Mini label="Audience quality" value={result.audience_quality == null ? "Unavailable" : `${result.audience_quality}/100`} />
        <Mini label="Last activity" value={date(result.last_observed_activity)} />
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        {result.categories.map((item) => <Badge key={item}>{item}</Badge>)}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <TextList title="Strengths" items={result.strengths} />
        <TextList title="Weaknesses / gaps" items={result.weaknesses} />
      </div>
      <div className="rounded-xl border border-secondary/30 bg-secondary/5 p-4">
        <div className="flex items-center justify-between gap-2"><h4 className="flex items-center gap-2 text-sm font-semibold"><Bot className="h-4 w-4 text-secondary" /> Grounded AI assistance</h4><Badge>{title(result.assistance.reasoning_source)}</Badge></div>
        <p className="mt-3 text-sm leading-6">{result.assistance.why_contact}</p>
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
          <Assistance label="Campaign fit" value={result.assistance.campaign_fit} />
          <Assistance label="Outreach angle" value={result.assistance.outreach_angle} />
          <Assistance label="Conversation starter" value={result.assistance.conversation_starter} />
          <Assistance label="Negotiation guidance" value={result.assistance.negotiation_guidance} />
        </dl>
      </div>
      {result.pricing && <div className="rounded-xl bg-muted/40 p-3 text-sm"><strong>Estimated pricing:</strong> {result.pricing.selected_rate == null ? "Unavailable" : `${result.pricing.currency} ${number(result.pricing.selected_rate)}`} <span className="text-xs text-muted-foreground">({title(result.pricing.rate_type)}, {(result.pricing.confidence * 100).toFixed(0)}% confidence)</span></div>}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-xs text-muted-foreground">
        <span>Source: {result.discovery_source} · Collected {date(result.collected_at)}</span>
        <span className="flex gap-3">
          {result.website && <a href={result.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary dark:text-secondary">Website <ExternalLink className="h-3 w-3" /></a>}
          {result.profile_url && <a href={result.profile_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary dark:text-secondary">Profile <ArrowUpRight className="h-3 w-3" /></a>}
        </span>
      </div>
    </Panel>
  );
}

function Mini({ label, value }) { return <div className="rounded-xl bg-muted/40 p-3"><p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 truncate text-sm font-semibold">{value}</p></div>; }
function TextList({ title: heading, items }) { return <div><h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{heading}</h4><ul className="mt-2 list-disc space-y-1 pl-4 text-sm">{items.map((item) => <li key={item}>{item}</li>)}</ul></div>; }
function Assistance({ label, value }) { return <div><dt className="font-semibold text-primary dark:text-white">{label}</dt><dd className="mt-1 leading-5 text-muted-foreground">{value}</dd></div>; }


export function SavedLeadsPage() {
  const [filters, setFilters] = useState({ search: "", status: "", entity_type: "", platform: "", priority: "", sort_by: "updated_at", archived: false, page: 1 });
  const [state, setState] = useState({ loading: true, error: "", data: { items: [], total: 0, page: 1, page_size: 12 } });
  const [notes, setNotes] = useState({});
  const load = async () => {
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const params = { ...filters, page_size: 12 };
      Object.keys(params).forEach((key) => (params[key] === "" || params[key] == null) && delete params[key]);
      const { data } = await api.get("/admin/lead-intelligence/leads", { params });
      setState({ loading: false, error: "", data });
    } catch (error) { setState((current) => ({ ...current, loading: false, error: formatApiError(error) })); }
  };
  useEffect(() => { load(); }, [filters.status, filters.entity_type, filters.platform, filters.priority, filters.sort_by, filters.archived, filters.page]); // eslint-disable-line react-hooks/exhaustive-deps
  const mutate = async (id, action, payload) => {
    try {
      if (action === "status") await api.patch(`/admin/lead-intelligence/leads/${id}`, { status: payload });
      if (action === "note") await api.post(`/admin/lead-intelligence/leads/${id}/notes`, { note: payload });
      if (action === "archive") await api.post(`/admin/lead-intelligence/leads/${id}/archive`);
      setNotes((current) => ({ ...current, [id]: "" })); await load();
      toast.success(action === "note" ? "Internal note added" : "Lead workspace updated");
    } catch (error) { toast.error(formatApiError(error)); }
  };
  return <div className="space-y-7" data-testid="admin-saved-leads">
    <PageHeader title="Saved Leads & Outreach" description="Plan human outreach, track lead status, and keep admin-only notes. BrandKrt never sends messages automatically." />
    <Panel>
      <form onSubmit={(event) => { event.preventDefault(); setFilters((current) => ({ ...current, page: 1 })); load(); }} className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <input aria-label="Search saved leads" value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Search leads" className="rounded-xl border border-border bg-background px-3 py-2 text-sm" />
        <FilterSelect label="Status" value={filters.status} values={LEAD_STATUSES} onChange={(value) => setFilters((current) => ({ ...current, status: value, page: 1 }))} />
        <FilterSelect label="Type" value={filters.entity_type} values={["creator", "brand"]} onChange={(value) => setFilters((current) => ({ ...current, entity_type: value, page: 1 }))} />
        <FilterSelect label="Platform" value={filters.platform} values={PLATFORMS} onChange={(value) => setFilters((current) => ({ ...current, platform: value, page: 1 }))} />
        <FilterSelect label="Priority" value={filters.priority} values={["high", "medium", "low"]} onChange={(value) => setFilters((current) => ({ ...current, priority: value, page: 1 }))} />
        <button className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">Search</button>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={filters.archived} onChange={(event) => setFilters((current) => ({ ...current, archived: event.target.checked, page: 1 }))} /> Show archived</label>
        <select aria-label="Sort saved leads" value={filters.sort_by} onChange={(event) => setFilters((current) => ({ ...current, sort_by: event.target.value, page: 1 }))} className="rounded-xl border border-border bg-background px-3 py-2 text-sm">
          <option value="updated_at">Recently updated</option><option value="priority">Priority</option><option value="recommendation">Recommendation</option><option value="created_at">Recently saved</option>
        </select>
      </form>
    </Panel>
    {state.loading ? <Loading label="Loading saved leads..." /> : state.error ? <Failure message={state.error} retry={load} /> : state.data.items.length ? <>
      <div className="grid gap-5 xl:grid-cols-2">{state.data.items.map((lead) => <Panel key={lead.id} className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div><h3 className="font-semibold text-primary dark:text-white">{lead.result.display_name || lead.result.username || lead.result.entity_key}</h3><div className="mt-1 flex gap-2"><Badge>{title(lead.result.platform)}</Badge><Badge tone={lead.result.priority.priority}>{title(lead.result.priority.priority)}</Badge></div></div>
          <select aria-label="Lead status" value={lead.status} onChange={(event) => mutate(lead.id, "status", event.target.value)} className="rounded-xl border border-border bg-background px-2 py-2 text-xs">{LEAD_STATUSES.map((value) => <option value={value} key={value}>{title(value)}</option>)}</select>
        </div>
        <p className="text-sm leading-6">{lead.result.assistance.why_contact}</p>
        <div className="rounded-xl bg-muted/40 p-3 text-xs leading-5 text-muted-foreground"><strong className="text-foreground">Outreach angle:</strong> {lead.result.assistance.outreach_angle}</div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Internal notes</h4>
          <div className="mt-2 max-h-28 space-y-2 overflow-auto">{lead.notes.length ? lead.notes.map((note, index) => <div key={`${note.created_at}-${index}`} className="rounded-lg border border-border p-2 text-xs"><p>{note.note}</p><p className="mt-1 text-muted-foreground">{date(note.created_at)}</p></div>) : <p className="text-xs text-muted-foreground">No internal notes.</p>}</div>
          <div className="mt-2 flex gap-2"><input aria-label="Internal note" value={notes[lead.id] || ""} onChange={(event) => setNotes((current) => ({ ...current, [lead.id]: event.target.value }))} placeholder="Add an admin-only note" className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm" /><button disabled={!notes[lead.id]?.trim()} onClick={() => mutate(lead.id, "note", notes[lead.id])} className="rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-50">Add</button></div>
        </div>
        {!lead.archived && <button onClick={() => mutate(lead.id, "archive")} className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground"><Archive className="h-3 w-3" /> Archive lead</button>}
      </Panel>)}</div>
      <Pagination page={filters.page} pageSize={state.data.page_size} total={state.data.total} onPage={(page) => setFilters((current) => ({ ...current, page }))} />
    </> : <Empty title="No saved leads" message="Save a factual brand or creator result to start the outreach workflow." action={<Link to="/admin/creator-discovery" className="mt-4 inline-flex rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">Discover creators</Link>} />}
  </div>;
}

function FilterSelect({ label, value, values, onChange }) { return <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className="rounded-xl border border-border bg-background px-3 py-2 text-sm"><option value="" label={`All ${label.toLowerCase()}`} />{values.map((item) => <option key={item} value={item} label={title(item)} />)}</select>; }


export function ResearchHistoryPage() {
  const [filters, setFilters] = useState({ search: "", entity_type: "", platform: "", status: "", sort_by: "created_at", page: 1 });
  const [state, setState] = useState({ loading: true, error: "", data: { items: [], total: 0, page_size: 15 } });
  const [selected, setSelected] = useState(null);
  const load = async () => {
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const params = { ...filters, page_size: 15 };
      Object.keys(params).forEach((key) => !params[key] && delete params[key]);
      const { data } = await api.get("/admin/lead-intelligence/research/history", { params });
      setState({ loading: false, error: "", data });
    } catch (error) { setState((current) => ({ ...current, loading: false, error: formatApiError(error) })); }
  };
  useEffect(() => { load(); }, [filters.entity_type, filters.platform, filters.status, filters.sort_by, filters.page]); // eslint-disable-line react-hooks/exhaustive-deps
  const open = async (id) => { try { setSelected((await api.get(`/admin/lead-intelligence/research/jobs/${id}`)).data); } catch (error) { toast.error(formatApiError(error)); } };
  const rerun = async (id) => { try { const { data } = await api.post(`/admin/lead-intelligence/research/history/${id}/rerun`); toast.success("Research rerun queued"); await open(data.id); await load(); } catch (error) { toast.error(formatApiError(error)); } };
  return <div className="space-y-7" data-testid="admin-research-history">
    <PageHeader title="Research History" description="Search previous factual sessions, review grounded explanations, identify duplicates, and rerun the same validated criteria." />
    <Panel><form onSubmit={(event) => { event.preventDefault(); setFilters((current) => ({ ...current, page: 1 })); load(); }} className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
      <input aria-label="Search research" value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Search sessions" className="rounded-xl border border-border bg-background px-3 py-2 text-sm" />
      <FilterSelect label="Type" value={filters.entity_type} values={["creator", "brand", "both"]} onChange={(value) => setFilters((current) => ({ ...current, entity_type: value, page: 1 }))} />
      <FilterSelect label="Platform" value={filters.platform} values={PLATFORMS} onChange={(value) => setFilters((current) => ({ ...current, platform: value, page: 1 }))} />
      <FilterSelect label="Status" value={filters.status} values={["queued", "running", "completed", "failed"]} onChange={(value) => setFilters((current) => ({ ...current, status: value, page: 1 }))} />
      <select value={filters.sort_by} onChange={(event) => setFilters((current) => ({ ...current, sort_by: event.target.value, page: 1 }))} className="rounded-xl border border-border bg-background px-3 py-2 text-sm"><option value="created_at">Newest</option><option value="results">Result count</option><option value="confidence">Confidence</option></select>
      <button className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">Search</button>
    </form></Panel>
    {state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={load} /> : state.data.items.length ? <Panel className="overflow-x-auto p-0"><table className="min-w-full text-left text-sm"><thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground"><tr><th className="p-4">Session</th><th className="p-4">Type</th><th className="p-4">Status</th><th className="p-4">Results</th><th className="p-4">Confidence</th><th className="p-4">Actions</th></tr></thead><tbody>{state.data.items.map((item) => <tr key={item.id} className="border-t border-border"><td className="p-4"><p className="font-medium">{item.research_name || item.query_summary}</p><p className="mt-1 text-xs text-muted-foreground">{date(item.created_at)}</p></td><td className="p-4">{title(item.entity_type)}</td><td className="p-4"><Badge>{title(item.status)}</Badge></td><td className="p-4">{item.result_count}</td><td className="p-4">{item.confidence.toFixed(1)}%</td><td className="p-4"><div className="flex gap-2"><button onClick={() => open(item.id)} className="text-xs font-semibold text-primary dark:text-secondary">View</button><button onClick={() => rerun(item.id)} className="text-xs font-semibold text-primary dark:text-secondary">Rerun</button></div></td></tr>)}</tbody></table></Panel> : <Empty title="No research history" message="Completed and failed research sessions will appear here." />}
    <Pagination page={filters.page} pageSize={state.data.page_size} total={state.data.total} onPage={(page) => setFilters((current) => ({ ...current, page }))} />
    {selected && <Panel className="space-y-4" data-testid="research-history-detail"><div className="flex items-start justify-between"><div><h3 className="text-lg font-semibold">{selected.research_name || selected.query_summary}</h3><p className="text-xs text-muted-foreground">{title(selected.reasoning_source)} · {selected.result_count} results</p></div><button onClick={() => setSelected(null)} className="text-xs font-semibold">Close</button></div>{selected.warnings?.length > 0 && <TextList title="Warnings" items={selected.warnings} />}<div className="grid gap-3 md:grid-cols-2">{selected.results.map((result) => <div key={result.entity_key} className="rounded-xl border border-border p-3"><div className="flex justify-between"><strong>{result.display_name || result.username || result.entity_key}</strong><Badge tone={result.priority.priority}>{title(result.priority.priority)}</Badge></div><p className="mt-2 text-xs leading-5 text-muted-foreground">{result.assistance.why_contact}</p>{result.possible_duplicates.length > 0 && <p className="mt-2 text-xs text-amber-700">Possible exact-signal duplicate: {result.possible_duplicates.join(", ")}</p>}</div>)}</div></Panel>}
  </div>;
}


export function AdminAIActivityPage() {
  const [page, setPage] = useState(1);
  const [state, setState] = useState({ loading: true, error: "", data: { items: [], total: 0, page_size: 20 } });
  const load = async () => { try { setState((current) => ({ ...current, loading: true, error: "" })); const { data } = await api.get("/admin/lead-intelligence/activity", { params: { page, page_size: 20 } }); setState({ loading: false, error: "", data }); } catch (error) { setState((current) => ({ ...current, loading: false, error: formatApiError(error) })); } };
  useEffect(() => { load(); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps
  return <div className="space-y-7" data-testid="admin-ai-activity"><PageHeader title="AI Activity" description="Review grounded reasoning outcomes and deterministic fallbacks without exposing prompts, responses, tokens, or internal chain-of-thought." />{state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={load} /> : state.data.items.length ? <div className="grid gap-4 lg:grid-cols-2">{state.data.items.map((item) => <Panel key={item.research_id}><div className="flex items-start justify-between"><div><h3 className="font-semibold">{item.research_name || `${title(item.entity_type)} research`}</h3><p className="mt-1 text-xs text-muted-foreground">{date(item.completed_at || item.created_at)}</p></div><Badge>{title(item.status)}</Badge></div><div className="mt-4 grid grid-cols-2 gap-3"><Mini label="Reasoning" value={title(item.reasoning_source)} /><Mini label="Results" value={item.result_count} /></div><p className="mt-3 text-xs text-muted-foreground">{item.degraded ? "Deterministic grounded fallback was used." : "Grounded AI enrichment completed."}</p></Panel>)}</div> : <Empty title="No AI activity" message="AI and deterministic reasoning outcomes appear after research runs." />}<Pagination page={page} pageSize={state.data.page_size} total={state.data.total} onPage={setPage} /></div>;
}


export function AdminCommercialIntelligencePage() {
  const [state, setState] = useState({ loading: true, error: "", profiles: [], performance: [], analytics: null });
  const load = async () => {
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const [profiles, performance, analytics] = await Promise.all([
        api.get("/creator-commercial/profiles", { params: { limit: 50 } }),
        api.get("/campaign-performance", { params: { limit: 50 } }),
        api.get("/creator-commercial/analytics/summary", { params: { limit: 100 } }),
      ]);
      setState({ loading: false, error: "", profiles: profiles.data, performance: performance.data, analytics: analytics.data });
    } catch (error) { setState((current) => ({ ...current, loading: false, error: formatApiError(error) })); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <div className="space-y-7" data-testid="admin-commercial-intelligence"><PageHeader title="Commercial Intelligence" description="Authorized, tenant-safe review of creator rates, campaign performance, and aggregate commercial evidence. Private internal notes are not displayed." />{state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={load} /> : <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Commercial profiles" value={state.profiles.length} icon={Users} /><Metric label="Performance records" value={state.performance.length} icon={BarChart3} /><Metric label="Campaign count" value={state.analytics?.campaign_count ?? state.performance.length} icon={Activity} /><Metric label="Verified records" value={state.profiles.filter((item) => item.rate_verification_status === "verified").length} icon={CheckCircle2} /></div><Panel className="overflow-x-auto p-0"><table className="min-w-full text-left text-sm"><thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground"><tr><th className="p-4">Creator</th><th className="p-4">Platform</th><th className="p-4">Known rate</th><th className="p-4">Negotiated rate</th><th className="p-4">Verification</th></tr></thead><tbody>{state.profiles.map((profile) => <tr key={profile.id} className="border-t border-border"><td className="p-4 font-medium">{profile.username || profile.platform_id}</td><td className="p-4">{title(profile.platform)}</td><td className="p-4">{profile.current_known_rate == null ? "Unavailable" : `${profile.currency} ${number(profile.current_known_rate)}`}</td><td className="p-4">{profile.current_negotiated_rate == null ? "Unavailable" : `${profile.currency} ${number(profile.current_negotiated_rate)}`}</td><td className="p-4"><Badge>{title(profile.rate_verification_status)}</Badge></td></tr>)}</tbody></table>{!state.profiles.length && <p className="p-8 text-center text-sm text-muted-foreground">No commercial profiles are available.</p>}</Panel></>}</div>;
}


export function AdminOperationsDashboard() {
  const [state, setState] = useState({ loading: true, error: "", diagnostics: null, metrics: "" });
  const load = async () => { try { setState((current) => ({ ...current, loading: true, error: "" })); const [diagnostics, metrics] = await Promise.all([api.get("/admin/operations/diagnostics"), api.get("/admin/operations/metrics")]); setState({ loading: false, error: "", diagnostics: diagnostics.data, metrics: metrics.data }); } catch (error) { setState((current) => ({ ...current, loading: false, error: formatApiError(error) })); } };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (state.loading) return <Loading label="Loading operational health..." />;
  if (state.error) return <Failure message={state.error} retry={load} />;
  const d = state.diagnostics;
  return <div className="space-y-7" data-testid="admin-operations-dashboard"><PageHeader title="Operations Dashboard" description="Admin-safe readiness, storage, index, rate-limit, accounting, and low-cardinality metrics. Secrets and infrastructure addresses are excluded." actions={<button onClick={load} className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm font-semibold"><RefreshCw className="h-4 w-4" /> Refresh</button>} /><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Application ready" value={d.ready ? 1 : 0} icon={CheckCircle2} /><Metric label="Database ready" value={d.database_ready ? 1 : 0} icon={Activity} /><Metric label="Uptime seconds" value={Math.floor(d.uptime_seconds || 0)} icon={Clock3} /><Metric label="Evidence inconsistencies" value={Object.values(d.evidence_consistency_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0)} icon={Archive} /></div><div className="grid gap-5 lg:grid-cols-2"><Panel><h3 className="font-semibold">Runtime backends</h3><dl className="mt-4 space-y-3 text-sm"><Row label="Environment" value={d.environment} /><Row label="Commit" value={d.commit} /><Row label="Storage" value={`${d.storage?.provider} (${d.storage?.durable ? "durable" : "development"})`} /><Row label="Rate limiting" value={d.rate_limit_backend} /><Row label="AI accounting" value={d.ai_usage_backend} /></dl></Panel><Panel><h3 className="font-semibold">Components</h3><div className="mt-4 space-y-2">{Object.entries(d.components || {}).map(([name, value]) => <div key={name} className="flex items-center justify-between rounded-xl bg-muted/40 p-3 text-sm"><span>{title(name)}</span><Badge tone={value.ready ? "high" : "low"}>{value.ready ? "Ready" : "Unavailable"}</Badge></div>)}</div></Panel></div><Panel><h3 className="font-semibold">Prometheus metrics</h3><pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{state.metrics || "No metrics recorded."}</pre></Panel></div>;
}


export function AdminAISettingsPage() {
  const [state, setState] = useState({ loading: true, error: "", data: null });
  const load = async () => { try { setState((current) => ({ ...current, loading: true, error: "" })); setState({ loading: false, error: "", data: (await api.get("/admin/operations/diagnostics")).data }); } catch (error) { setState({ loading: false, error: formatApiError(error), data: null }); } };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <div className="space-y-7" data-testid="admin-ai-settings"><PageHeader title="AI & Operations Settings" description="Read-only deployment configuration status. Secrets and raw environment values are never returned to the browser." />{state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={load} /> : <div className="grid gap-5 lg:grid-cols-2"><Panel><h3 className="font-semibold">Runtime</h3><dl className="mt-4 space-y-3 text-sm"><Row label="Environment" value={state.data.environment} /><Row label="Version" value={state.data.version} /><Row label="Commit" value={state.data.commit} /><Row label="Ready" value={state.data.ready ? "Yes" : "No"} /></dl></Panel><Panel><h3 className="font-semibold">Configured backends</h3><dl className="mt-4 space-y-3 text-sm"><Row label="Storage" value={state.data.storage?.provider} /><Row label="Durable storage" value={state.data.storage?.durable ? "Yes" : "No"} /><Row label="Rate limiting" value={state.data.rate_limit_backend} /><Row label="AI usage accounting" value={state.data.ai_usage_backend} /></dl></Panel><Panel className="lg:col-span-2"><h3 className="font-semibold">Provider policy</h3><p className="mt-3 text-sm leading-6 text-muted-foreground">Lead research uses configured official factual adapters. Instagram and Snapchat remain unavailable in production until official adapters exist. AI may explain normalized facts, but it cannot create platform metrics, verification, identity, or external validation.</p></Panel></div>}</div>;
}

function Row({ label, value }) { return <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-2 last:border-0"><dt className="text-muted-foreground">{label}</dt><dd className="max-w-[60%] truncate font-medium">{String(value ?? "Unavailable")}</dd></div>; }

function Pagination({ page, pageSize, total, onPage }) {
  if (!total || total <= pageSize) return null;
  const pages = Math.ceil(total / pageSize);
  return <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">Page {page} of {pages} · {total} results</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => onPage(page - 1)} className="rounded-full border border-border px-3 py-1.5 disabled:opacity-40">Previous</button><button disabled={page >= pages} onClick={() => onPage(page + 1)} className="rounded-full border border-border px-3 py-1.5 disabled:opacity-40">Next</button></div></div>;
}
