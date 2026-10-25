"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";

interface FlaggedReview {
  id: number;
  accommodation_id: number;
  rating: number;
  body: string;
  created_at: string;
}

function useFlaggedReviews() {
  const { user } = useAuth();
  const allowed = user?.role === "admin" || user?.role === "moderator";
  return useQuery({
    queryKey: ["flagged-reviews", user?.id],
    queryFn: async () => (await api.get<FlaggedReview[]>("/api/v1/reviews/flagged")).data,
    enabled: allowed,
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: 30_000,
  });
}

export function FlaggedReviewCount() {
  const { data, isError } = useFlaggedReviews();
  if (isError) return <span title="Flagged review count unavailable" aria-label="Flagged review count unavailable">!</span>;
  if (!data?.length) return null;
  return <span aria-label={`${data.length} flagged reviews`} title="Flagged reviews awaiting moderation" className="rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-700">{data.length}</span>;
}

export function FlaggedReviewQueue() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [removeTarget, setRemoveTarget] = useState<FlaggedReview | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const allowed = user?.role === "admin" || user?.role === "moderator";
  const { data: reviews = [], isPending, isError, isFetching, refetch } = useFlaggedReviews();

  async function decide(id: number, action: "release" | "remove") {
    if (busy || (action === "remove" && !reason.trim())) return;
    setBusy(true);
    try {
      if (action === "release") await api.patch(`/api/v1/moderation/reviews/${id}/release`);
      else await api.delete(`/api/v1/moderation/reviews/${id}`, { data: { reason: reason.trim() } });
      setRemoveTarget(null);
      setReason("");
      // Refresh both the queue and the admin audit/counts after a decision.
      await queryClient.invalidateQueries();
      toast.success(action === "release" ? "Review released and is now publicly visible." : "Review removed.");
    } catch {
      toast.error("Could not update the review. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!allowed) return null;

  return (
    <section aria-labelledby="flagged-review-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="flagged-review-heading" className="font-semibold text-slate-900">Flagged reviews</h2>
          <p className="text-sm text-slate-500">Hidden from students until a moderator releases them. Updates every 30 seconds.</p>
        </div>
        <Button variant="outline" size="sm" disabled={isFetching || busy} onClick={() => void refetch()}>
          {isFetching ? "Refreshing…" : "Refresh reviews"}
        </Button>
      </div>
      {isPending ? <p role="status" className="text-sm text-slate-500">Loading flagged reviews…</p>
        : isError ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Could not load flagged reviews. Refresh reviews to try again.
        </div>
        : reviews.length === 0 ? <p className="rounded-xl border bg-white p-6 text-sm text-slate-600">No reviews are currently awaiting moderation.</p>
        : reviews.map(review => (
          <article key={review.id} aria-label={`Review ${review.id}`} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <span className="rounded-full bg-amber-50 px-3 py-1 font-medium text-amber-800">Flagged for moderation</span>
              <span>Review #{review.id} · Listing #{review.accommodation_id}</span>
              <span>Rating: {review.rating}/5</span>
              <span>{new Date(review.created_at).toLocaleDateString("en-ZA")}</span>
            </div>
            <p className="whitespace-pre-wrap break-words text-sm text-slate-700">{review.body}</p>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm"><Link href={`/listings/${review.accommodation_id}`}>View listing</Link></Button>
              <Button size="sm" disabled={busy} onClick={() => void decide(review.id, "release")}>Release</Button>
              <Button size="sm" variant="destructive" disabled={busy} onClick={() => { setReason(""); setRemoveTarget(review); }}>Remove</Button>
            </div>
          </article>
        ))}
      <Dialog open={!!removeTarget} onOpenChange={open => { if (!open && !busy) setRemoveTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove review</DialogTitle>
            <DialogDescription>Provide a reason for removing review #{removeTarget?.id}. The moderation action will be recorded.</DialogDescription>
          </DialogHeader>
          <label htmlFor="review-removal-reason" className="text-sm font-medium">Reason for removal</label>
          <Textarea id="review-removal-reason" value={reason} onChange={event => setReason(event.target.value)} disabled={busy} />
          <div className="flex justify-end gap-2">
            <Button variant="outline" disabled={busy} onClick={() => setRemoveTarget(null)}>Cancel</Button>
            <Button variant="destructive" disabled={busy || !reason.trim()} onClick={() => removeTarget && void decide(removeTarget.id, "remove")}>
              {busy ? "Removing…" : "Remove review"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
