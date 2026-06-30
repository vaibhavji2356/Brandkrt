import React, { useState } from "react";
import { toast } from "sonner";
import { Send, Loader2, ThumbsUp, ThumbsDown } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import StarRating from "@/components/StarRating";

export default function ReviewForm({
  targetUserId,
  dealId,
  kind = "brand_to_influencer", // or "influencer_to_brand"
  existing = null,
  onSubmitted,
}) {
  const [rating, setRating] = useState(existing?.rating || 0);
  const [comment, setComment] = useState(existing?.comment || "");
  const [pros, setPros] = useState(existing?.pros || "");
  const [cons, setCons] = useState(existing?.cons || "");
  const [wwa, setWwa] = useState(existing?.would_work_again ?? true);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!rating) return toast.error("Please pick a rating");
    setBusy(true);
    try {
      const { data } = await api.post("/feedback", {
        target_user_id: targetUserId,
        deal_id: dealId,
        rating,
        comment: comment.trim() || null,
        pros: pros.trim() || null,
        cons: cons.trim() || null,
        would_work_again: !!wwa,
        kind,
      });
      toast.success(existing ? "Review updated" : "Review submitted");
      onSubmitted?.(data.review);
    } catch (err) {
      toast.error(formatApiError(err));
    }
    setBusy(false);
  };

  return (
    <form onSubmit={submit} className="rounded-2xl border border-border bg-card p-5 space-y-4" data-testid="review-form">
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Your rating</label>
        <div className="mt-2 flex items-center gap-3">
          <StarRating value={rating} onChange={setRating} readOnly={false} size={26} testId="review-stars" />
          <span className="text-sm font-semibold text-primary dark:text-white">
            {rating ? `${rating}/5` : "Tap a star"}
          </span>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Pros" hint="What worked well?">
          <Textarea rows={3} value={pros} onChange={(e) => setPros(e.target.value)} placeholder="e.g. clear brief, on-time delivery, professional" data-testid="review-pros" />
        </Field>
        <Field label="Cons" hint="Anything to improve?">
          <Textarea rows={3} value={cons} onChange={(e) => setCons(e.target.value)} placeholder="e.g. slow approvals, unclear feedback" data-testid="review-cons" />
        </Field>
      </div>

      <Field label="Overall comment" hint="Optional — visible publicly on the profile">
        <Textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Share more context for future partners" data-testid="review-comment" />
      </Field>

      <label className="flex items-start gap-2 text-sm">
        <Checkbox checked={wwa} onCheckedChange={(v) => setWwa(!!v)} data-testid="review-wwa" />
        <span className="flex items-center gap-2">
          {wwa ? <ThumbsUp className="h-4 w-4 text-success" /> : <ThumbsDown className="h-4 w-4 text-destructive" />}
          I would work with this {kind === "brand_to_influencer" ? "creator" : "brand"} again
        </span>
      </label>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={busy || !rating}
          data-testid="review-submit"
          className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-sm font-semibold disabled:opacity-60"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {existing ? "Update review" : "Submit review"}
        </button>
      </div>
    </form>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      {hint && <span className="text-[10px] text-muted-foreground/70 ml-2">{hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  );
}
