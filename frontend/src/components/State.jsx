import React from "react";
import { Inbox, AlertCircle, CheckCircle2 } from "lucide-react";

export function EmptyState({ icon: Icon = Inbox, title, description, action, testId = "empty-state" }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center" data-testid={testId}>
      <Icon className="h-10 w-10 mx-auto text-muted-foreground" />
      <h3 className="mt-4 text-lg font-medium text-primary dark:text-white">{title}</h3>
      {description && <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", description, action, testId = "error-state" }) {
  return (
    <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center" data-testid={testId}>
      <AlertCircle className="h-9 w-9 mx-auto text-destructive" />
      <h3 className="mt-3 text-lg font-medium text-destructive">{title}</h3>
      {description && <p className="mt-1 text-sm text-foreground/80">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function SuccessState({ title, description, action, testId = "success-state" }) {
  return (
    <div className="rounded-2xl border border-success/30 bg-success/5 p-8 text-center" data-testid={testId}>
      <CheckCircle2 className="h-9 w-9 mx-auto text-success" />
      <h3 className="mt-3 text-lg font-medium text-primary dark:text-white">{title}</h3>
      {description && <p className="mt-1 text-sm text-foreground/80">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

const STATUS_STYLES = {
  active: "bg-success/10 text-success",
  pending: "bg-warning/10 text-warning",
  approved: "bg-success/10 text-success",
  rejected: "bg-destructive/10 text-destructive",
  cancelled: "bg-muted text-muted-foreground",
  draft: "bg-muted text-muted-foreground",
  completed: "bg-secondary/15 text-secondary",
  escrowed: "bg-secondary/15 text-secondary",
  released: "bg-success/10 text-success",
  held: "bg-warning/10 text-warning",
};

export function StatusChip({ value, className = "" }) {
  const cls = STATUS_STYLES[(value || "").toLowerCase()] || "bg-muted text-muted-foreground";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${cls} ${className}`} data-testid={`status-chip-${value}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {(value || "").replace(/_/g, " ")}
    </span>
  );
}

export default function Loading({ size = 8 }) {
  return <div className={`h-${size} w-${size} rounded-full border-2 border-secondary border-t-transparent animate-spin`} />;
}
