import React from "react";
import { ThumbsUp, ThumbsDown, Quote } from "lucide-react";
import StarRating from "@/components/StarRating";
import { EmptyState } from "@/components/State";

export default function ReviewList({ reviews = [], emptyTitle = "No reviews yet", emptyDescription }) {
  if (!reviews.length) {
    return (
      <EmptyState
        icon={Quote}
        title={emptyTitle}
        description={emptyDescription || "Reviews appear once campaigns are completed and partners share their feedback."}
        testId="reviews-empty"
      />
    );
  }
  return (
    <div className="grid gap-3 md:grid-cols-2" data-testid="review-list">
      {reviews.map((r) => (
        <div key={r.id} className="rounded-2xl border border-border bg-card p-5" data-testid={`review-${r.id}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-primary dark:text-white truncate">{r.reviewer_name || "Reviewer"}</div>
              <div className="text-[10px] uppercase tracking-wider text-secondary mt-0.5">
                {r.kind === "influencer_to_brand" ? "Creator → Brand" : "Brand → Creator"}
              </div>
            </div>
            <StarRating value={r.rating || 0} size={14} />
          </div>

          {r.comment && (
            <p className="mt-3 text-sm text-foreground/90 line-clamp-5 whitespace-pre-line">
              <Quote className="h-3.5 w-3.5 inline -mt-1 text-secondary mr-1" />
              {r.comment}
            </p>
          )}

          {(r.pros || r.cons) && (
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              {r.pros && (
                <div className="rounded-lg border border-success/30 bg-success/5 p-2.5">
                  <div className="text-[10px] uppercase tracking-wider text-success font-semibold">Pros</div>
                  <p className="mt-1 text-foreground/90 line-clamp-3 whitespace-pre-line">{r.pros}</p>
                </div>
              )}
              {r.cons && (
                <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-2.5">
                  <div className="text-[10px] uppercase tracking-wider text-destructive font-semibold">Cons</div>
                  <p className="mt-1 text-foreground/90 line-clamp-3 whitespace-pre-line">{r.cons}</p>
                </div>
              )}
            </div>
          )}

          <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              {r.would_work_again ? (
                <><ThumbsUp className="h-3 w-3 text-success" /> Would work again</>
              ) : (
                <><ThumbsDown className="h-3 w-3 text-destructive" /> Would not</>
              )}
            </span>
            <span>{r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
