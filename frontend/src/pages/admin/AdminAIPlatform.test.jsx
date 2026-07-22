import React, { act } from "react";
import { createRoot } from "react-dom/client";
import {
  AdminLeadIntelligenceHome, LeadDiscoveryPage, ResearchHistoryPage, SavedLeadsPage,
} from "./AdminAIPlatform";


const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: (...args) => mockGet(...args),
    post: (...args) => mockPost(...args),
    patch: (...args) => mockPatch(...args),
  },
  formatApiError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("react-router-dom", () => ({
  Link: ({ children, to, ...props }) => <a href={to} {...props}>{children}</a>,
}), { virtual: true });
jest.mock("lucide-react", () => {
  const Icon = () => null;
  return {
    Activity: Icon, Archive: Icon, ArrowUpRight: Icon, BarChart3: Icon, Bookmark: Icon,
    Bot: Icon, Building2: Icon, CheckCircle2: Icon, Clock3: Icon, ExternalLink: Icon,
    MessageSquareText: Icon, RefreshCw: Icon, Search: Icon, Send: Icon, Sparkles: Icon,
    UserRound: Icon, Users: Icon,
  };
});

const mockToast = require("sonner").toast;


const RESULT = {
  entity_key: "instagram:creator-1", entity_type: "creator", platform: "instagram",
  platform_id: "creator-1", username: "ethical_creator", display_name: "Ethical Creator",
  profile_url: "https://instagram.com/ethical_creator", biography: "Sustainable fashion creator.",
  website: "https://ethical.example.com", public_social_profiles: [], available_platforms: ["instagram"],
  categories: ["sustainable fashion"], keywords: ["ethical"], location: "Mumbai, India", language: "en",
  follower_count: 30000, content_count: 180, average_views: 9000, engagement_rate: 5.14,
  audience_quality: null, marketing_signals: ["Reported followers: 30,000"],
  estimated_collaboration_activity: null, verification_status: "verified", last_observed_activity: null,
  collected_at: "2026-07-22T10:00:00Z", discovery_source: "mock:instagram", confidence: 82,
  recommendation_score: 88, strengths: ["Strong category relevance."],
  weaknesses: ["Audience demographics are unavailable."], why_recommended: ["Deterministic fit is strong."],
  priority: { score: 84, priority: "high", components: {}, explanation: ["Grounded score."] },
  assistance: {
    why_contact: "Strong factual fit for the requested niche.", campaign_fit: "Supports an awareness pilot.",
    outreach_angle: "Reference the creator's public sustainability focus.",
    conversation_starter: "Would you review a concise campaign brief?",
    negotiation_guidance: "Confirm the current rate directly.", reasoning_source: "deterministic_fallback",
    degraded: true,
  },
  pricing: { estimated_rate: 252, selected_rate: 252, currency: "USD", rate_type: "estimated", confidence: 0.58, source: "benchmark", warnings: [] },
  commercial_history: { available: false, currency: null, known_rate: null, negotiated_rate: null, verification_status: null },
  possible_duplicates: [], warnings: [],
};

const JOB = {
  id: "64b64c64b64c64b64c64b64c", research_name: "Creator shortlist", entity_type: "creator",
  platforms: ["instagram"], query_summary: "sustainable fashion", status: "completed", progress: 100,
  result_count: 1, confidence: 82, reasoning_source: "deterministic_fallback", degraded: true,
  error_code: null, created_at: "2026-07-22T10:00:00Z", started_at: "2026-07-22T10:00:00Z",
  completed_at: "2026-07-22T10:00:01Z", criteria: {}, results: [RESULT], warnings: [],
  missing_information: [], source_summary: [],
};

const LEAD = {
  id: "64b64c64b64c64b64c64b64d", research_id: JOB.id, fingerprint: "a".repeat(64), status: "new",
  archived: false, result: RESULT, notes: [], created_at: JOB.created_at, updated_at: JOB.completed_at,
};


describe("Admin AI Lead Intelligence UI", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockGet.mockReset(); mockPost.mockReset(); mockPatch.mockReset();
    mockToast.success.mockReset(); mockToast.error.mockReset();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  test("dashboard exposes lead analytics and direct discovery actions", async () => {
    mockGet.mockResolvedValue({ data: {
      brands_found: 4, creators_found: 9, high_priority_leads: 3, contacted: 2,
      replies: 1, converted: 1, research_volume: 5, saved_leads: 6,
      top_niches: [{ name: "fashion", count: 3 }], top_platforms: [{ name: "youtube", count: 4 }],
      recent_activity: [],
    } });
    await act(async () => root.render(<AdminLeadIntelligenceHome />));
    expect(container.textContent).toContain("AI Lead Intelligence");
    expect(container.textContent).toContain("Brands found");
    expect(container.querySelector('a[href="/admin/brand-discovery"]')).not.toBeNull();
    expect(container.querySelector('a[href="/admin/creator-discovery"]')).not.toBeNull();
  });

  test("creator discovery runs a job, renders grounded assistance, and saves a lead", async () => {
    mockPost.mockResolvedValueOnce({ data: { ...JOB, status: "queued", progress: 0, results: undefined } });
    mockGet.mockResolvedValueOnce({ data: JOB });
    mockPost.mockResolvedValueOnce({ data: LEAD });
    await act(async () => root.render(<LeadDiscoveryPage entityType="creator" />));
    const form = container.querySelector('[data-testid="lead-discovery-form"]');
    await act(async () => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
    expect(container.textContent).toContain("Ethical Creator");
    expect(container.textContent).toContain("Grounded AI assistance");
    expect(container.textContent).toContain("Audience qualityUnavailable");
    const save = [...container.querySelectorAll("button")].find((button) => button.textContent === "Save lead");
    await act(async () => save.click());
    expect(mockPost).toHaveBeenLastCalledWith("/admin/lead-intelligence/leads", {
      research_id: JOB.id, entity_key: RESULT.entity_key,
    });
    expect(container.textContent).toContain("Saved");
  });

  test("failed discovery is retryable and always resets loading", async () => {
    mockPost.mockRejectedValueOnce(new Error("Research service unavailable"));
    await act(async () => root.render(<LeadDiscoveryPage entityType="brand" />));
    const form = container.querySelector('[data-testid="lead-discovery-form"]');
    await act(async () => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
    const submit = container.querySelector('[data-testid="lead-discovery-submit"]');
    expect(submit.disabled).toBe(false);
    expect(submit.textContent).toContain("Start factual research");
    expect(container.querySelector('[data-testid="lead-discovery-error"]').textContent).toContain("unavailable");
  });

  test("saved-lead outreach workspace changes status without sending messages", async () => {
    mockGet.mockResolvedValue({ data: { items: [LEAD], total: 1, page: 1, page_size: 12 } });
    mockPatch.mockResolvedValue({ data: { ...LEAD, status: "contacted" } });
    await act(async () => root.render(<SavedLeadsPage />));
    const status = container.querySelector('select[aria-label="Lead status"]');
    await act(async () => {
      status.value = "contacted";
      status.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(mockPatch).toHaveBeenCalledWith(`/admin/lead-intelligence/leads/${LEAD.id}`, { status: "contacted" });
    expect(container.textContent).toContain("never sends messages automatically");
  });

  test("research history displays previous explanations and supports rerun", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [JOB], total: 1, page: 1, page_size: 15 } });
    mockGet.mockResolvedValueOnce({ data: JOB });
    mockPost.mockResolvedValueOnce({ data: { ...JOB, id: "74b64c64b64c64b64c64b64c", status: "queued" } });
    await act(async () => root.render(<ResearchHistoryPage />));
    const view = [...container.querySelectorAll("button")].find((button) => button.textContent === "View");
    await act(async () => view.click());
    expect(container.textContent).toContain("Strong factual fit");
  });
});
