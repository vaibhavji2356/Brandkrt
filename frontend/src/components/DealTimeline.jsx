import React from "react";
import { motion } from "framer-motion";
import {
  Megaphone, Send, CheckCircle2, Package, Inbox, Pencil, FileCheck, Eye, ThumbsUp,
  CalendarDays, Sparkles, Trophy, XCircle,
} from "lucide-react";

/**
 * Canonical 12-step Brand ↔ Influencer pipeline.
 * Rejection / cancellation is a side branch (cancelled).
 */
export const PIPELINE = [
  { key: "campaign_created",   label: "Campaign Created",    description: "Brand published the campaign brief.",      icon: Megaphone },
  { key: "offer_sent",         label: "Invitation Sent",     description: "Brand invited the creator.",               icon: Send },
  { key: "offer_accepted",     label: "Accepted",            description: "Creator accepted the offer.",              icon: CheckCircle2 },
  { key: "product_shipped",    label: "Product Shipped",     description: "Product is on the way.",                   icon: Package },
  { key: "product_received",   label: "Product Received",    description: "Creator confirmed receipt.",               icon: Inbox },
  { key: "content_in_progress",label: "Content In Progress", description: "Creator is producing the content.",        icon: Pencil },
  { key: "content_submitted",  label: "Content Submitted",   description: "Creator submitted for brand review.",      icon: FileCheck },
  { key: "brand_review",       label: "Brand Review",        description: "Brand is reviewing the content.",          icon: Eye },
  { key: "approved",           label: "Approved",            description: "Brand approved the content.",              icon: ThumbsUp },
  { key: "scheduled",          label: "Scheduled",           description: "Creator scheduled the post.",              icon: CalendarDays },
  { key: "published",          label: "Published",           description: "The content is live on the platform.",     icon: Sparkles },
  { key: "completed",          label: "Completed",           description: "Deal closed and payment released.",        icon: Trophy },
];

const PIPELINE_INDEX = PIPELINE.reduce((m, s, i) => { m[s.key] = i; return m; }, {});

// Legacy → canonical mapping (so older deals still render cleanly)
const LEGACY_MAP = {
  promotion_pending: "scheduled",
  promotion_live: "published",
};

export function canonicalStatus(s) {
  if (!s) return "campaign_created";
  return LEGACY_MAP[s] || s;
}

export function pipelineIndex(status) {
  // campaign_created is the implicit "step 0" — any existing deal is at least at offer_sent.
  const canon = canonicalStatus(status);
  if (canon === "cancelled") return -1;
  return PIPELINE_INDEX[canon] ?? 1;
}

/**
 * <DealTimeline status="content_submitted" />
 *
 * - `direction="vertical"` (default) or `direction="horizontal"`
 * - Renders the full 12-step pipeline + a side note when cancelled.
 */
export default function DealTimeline({ status, direction = "vertical", className = "" }) {
  const canon = canonicalStatus(status);
  const activeIdx = pipelineIndex(canon);
  const isCancelled = canon === "cancelled";

  if (direction === "horizontal") {
    return (
      <div className={`relative ${className}`} data-testid="deal-timeline-h">
        <div className="flex gap-2 overflow-x-auto pb-2">
          {PIPELINE.map((step, i) => {
            const state = stateFor(i, activeIdx, isCancelled);
            return <Node key={step.key} step={step} state={state} index={i} compact />;
          })}
        </div>
        {isCancelled && <CancelledBanner />}
      </div>
    );
  }

  return (
    <div className={`relative ${className}`} data-testid="deal-timeline">
      <div className="absolute left-[15px] top-1 bottom-1 w-px bg-border" />
      <ol className="space-y-3">
        {PIPELINE.map((step, i) => {
          const state = stateFor(i, activeIdx, isCancelled);
          return <Node key={step.key} step={step} state={state} index={i} />;
        })}
      </ol>
      {isCancelled && <CancelledBanner />}
    </div>
  );
}

function stateFor(i, activeIdx, isCancelled) {
  if (isCancelled) return i === 0 ? "done" : "cancelled";
  if (i < activeIdx) return "done";
  if (i === activeIdx) return "active";
  return "pending";
}

function Node({ step, state, index, compact = false }) {
  const Icon = step.icon;
  const dot =
    state === "done" ? "bg-secondary text-secondary-foreground border-secondary"
    : state === "active" ? "bg-primary text-primary-foreground border-primary shadow-luxe-sm"
    : state === "cancelled" ? "bg-muted text-muted-foreground border-border opacity-50"
    : "bg-background text-muted-foreground border-border";

  if (compact) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: index * 0.03 }}
        className="shrink-0 w-[140px] text-center"
        data-testid={`step-${step.key}`}
      >
        <div className={`mx-auto h-9 w-9 rounded-full border flex items-center justify-center ${dot}`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className={`mt-2 text-[11px] font-semibold ${state === "active" ? "text-primary dark:text-white" : "text-muted-foreground"}`}>
          {step.label}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.li
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.04 }}
      className="relative pl-12"
      data-testid={`step-${step.key}`}
    >
      <div className={`absolute left-0 top-0 h-8 w-8 rounded-full border flex items-center justify-center ${dot}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className={`rounded-xl border ${state === "active" ? "border-secondary/40 bg-accent" : "border-border bg-card"} p-3`}>
        <div className="flex items-center justify-between gap-2">
          <span className={`text-sm font-semibold ${state === "active" ? "text-primary dark:text-white" : "text-foreground/90"}`}>
            {step.label}
          </span>
          {state === "active" && <span className="text-[10px] font-semibold uppercase tracking-wider text-secondary">In progress</span>}
          {state === "done" && <span className="text-[10px] font-semibold uppercase tracking-wider text-success">Done</span>}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{step.description}</p>
      </div>
    </motion.li>
  );
}

function CancelledBanner() {
  return (
    <div className="mt-4 flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" data-testid="timeline-cancelled">
      <XCircle className="h-4 w-4" />
      This deal was cancelled. The remaining steps are not applicable.
    </div>
  );
}

/* ---------- Progress bar variant ---------- */
export function DealProgressBar({ status, className = "" }) {
  const canon = canonicalStatus(status);
  const isCancelled = canon === "cancelled";
  const idx = isCancelled ? 0 : pipelineIndex(canon);
  const pct = Math.round((idx / (PIPELINE.length - 1)) * 100);
  return (
    <div className={`w-full ${className}`} data-testid="deal-progress">
      <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
        <span>{isCancelled ? "Cancelled" : PIPELINE[idx]?.label}</span>
        <span>{isCancelled ? "—" : `${pct}%`}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: isCancelled ? "100%" : `${pct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={`h-full ${isCancelled ? "bg-destructive/60" : "bg-secondary"}`}
        />
      </div>
    </div>
  );
}
