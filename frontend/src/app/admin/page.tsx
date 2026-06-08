"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import PageLayout from "@/components/page-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  ShieldCheck, Loader2, MapPin, Star, Clock, CheckCircle,
  XCircle, Trash2, Eye, AlertTriangle, FileText, MessageSquare,
} from "lucide-react";
import { toast } from "sonner";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PendingListing {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  created_at: string;
}

interface FlaggedReview {
  id: number;
  accommodation_id: number;
  student_id: number;
  rating: number;
  body: string;
  created_at: string;
  nlp?: {
    sentiment: string;
    spam_flag: boolean;
  };
}

// ─── Fetch helpers ────────────────────────────────────────────────────────────

async function fetchPendingListings(): Promise<PendingListing[]> {
  const { data } = await api.get("/api/v1/moderation/listings/pending");
  return data;
}

async function fetchFlaggedReviews(): Promise<FlaggedReview[]> {
  // Fetch all reviews from all accommodations that are spam-flagged
  const { data } = await api.get("/api/v1/moderation/reviews/flagged");
  return data;
}

// ─── Reject Modal ─────────────────────────────────────────────────────────────

function RejectModal({
  open,
  title,
  onClose,
  onConfirm,
  loading,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  loading: boolean;
}) {
  const [reason, setReason] = useState("");

  const handleConfirm = () => {
    if (!reason.trim()) { toast.error("Please provide a reason"); return; }
    onConfirm(reason);
  };

  return (
    <Dialog open={open} onOpenChange={() => { if (!loading) { onClose(); setReason(""); } }}>
      <DialogContent className="rounded-2xl max-w-md bg-white">
        <DialogHeader>
          <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-red-50 border border-red-100 mx-auto mb-2">
            <XCircle className="w-5 h-5 text-red-500" />
          </div>
          <DialogTitle className="text-center">Reject listing</DialogTitle>
          <DialogDescription className="text-center text-sm line-clamp-1">{title}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              Reason for rejection
            </label>
            <Textarea
              className="rounded-xl resize-none h-28 text-sm"
              placeholder="e.g. Listing contains inaccurate information, missing required details..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => { onClose(); setReason(""); }} disabled={loading}>
              Cancel
            </Button>
            <Button
              className="flex-1 rounded-xl bg-red-500 hover:bg-red-600 text-white"
              onClick={handleConfirm}
              disabled={loading || !reason.trim()}
            >
              {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Rejecting...</> : "Reject listing"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FlaggedReviewsTab({ onRemove }: { onRemove: (review: FlaggedReview) => void }) {
  const router = useRouter();

  const { data: flaggedReviews = [], isLoading } = useQuery({
    queryKey: ["flagged-reviews"],
    queryFn: fetchFlaggedReviews,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-28 w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  if (flaggedReviews.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-7 h-7 text-emerald-500" />
        </div>
        <h3 className="font-semibold text-slate-900 mb-1">No flagged reviews</h3>
        <p className="text-sm text-slate-500">The NLP pipeline hasn't flagged any reviews as spam.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {flaggedReviews.map((review) => (
        <div key={review.id} className="bg-white border border-slate-200 rounded-2xl p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Badge className="bg-red-50 text-red-700 border-red-200 border rounded-full text-xs px-2 py-0.5">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Spam flagged
                </Badge>
                <div className="flex items-center gap-1">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star
                      key={i}
                      className={`w-3 h-3 ${i < review.rating ? "fill-amber-400 text-amber-400" : "text-slate-200 fill-slate-200"}`}
                    />
                  ))}
                </div>
                {review.nlp?.sentiment && (
                  <span className="text-xs text-slate-500 capitalize">{review.nlp.sentiment}</span>
                )}
              </div>
              <p className="text-sm text-slate-600 leading-relaxed mb-3 line-clamp-3">
                {review.body}
              </p>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <span>Review #{review.id}</span>
                <span>·</span>
                <span>Listing #{review.accommodation_id}</span>
                <span>·</span>
                <span>{new Date(review.created_at).toLocaleDateString("en-ZA", {
                  day: "numeric", month: "short", year: "numeric"
                })}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                variant="outline"
                size="sm"
                className="rounded-xl gap-1.5 text-xs"
                onClick={() => router.push(`/listings/${review.accommodation_id}`)}
              >
                <Eye className="w-3.5 h-3.5" />
                View listing
              </Button>
              <Button
                size="sm"
                className="rounded-xl gap-1.5 text-xs bg-red-500 hover:bg-red-600 text-white"
                onClick={() => onRemove(review)}
              >
                <Trash2 className="w-3.5 h-3.5" />
                Remove
              </Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Remove Review Modal ──────────────────────────────────────────────────────

function RemoveReviewModal({
  open,
  onClose,
  onConfirm,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  loading: boolean;
}) {
  const [reason, setReason] = useState("");

  return (
    <Dialog open={open} onOpenChange={() => { if (!loading) { onClose(); setReason(""); } }}>
      <DialogContent className="rounded-2xl max-w-md bg-white">
        <DialogHeader>
          <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-red-50 border border-red-100 mx-auto mb-2">
            <Trash2 className="w-5 h-5 text-red-500" />
          </div>
          <DialogTitle className="text-center">Remove review</DialogTitle>
          <DialogDescription className="text-center text-sm">
            This will soft-delete the review and log the moderation action.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              Reason for removal
            </label>
            <Textarea
              className="rounded-xl resize-none h-28 text-sm"
              placeholder="e.g. Review violates community guidelines, contains spam..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => { onClose(); setReason(""); }} disabled={loading}>
              Cancel
            </Button>
            <Button
              className="flex-1 rounded-xl bg-red-500 hover:bg-red-600 text-white"
              onClick={() => { if (!reason.trim()) { toast.error("Please provide a reason"); return; } onConfirm(reason); }}
              disabled={loading || !reason.trim()}
            >
              {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Removing...</> : "Remove review"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { user, loading, isStudent, isLandlord } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"listings" | "reviews">("listings");
  const [rejectTarget, setRejectTarget] = useState<PendingListing | null>(null);
  const [removeTarget, setRemoveTarget] = useState<FlaggedReview | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/admin");
    if (!loading && user && (isStudent || isLandlord)) router.push("/");
  }, [user, loading]);

  const { data: pendingListings = [], isLoading: listingsLoading } = useQuery({
    queryKey: ["pending-listings"],
    queryFn: fetchPendingListings,
    enabled: !!user && !isStudent && !isLandlord,
  });

  // ── Approve ──
  const handleApprove = async (id: number, title: string) => {
    try {
      await api.patch(`/api/v1/moderation/listings/${id}/approve`);
      queryClient.invalidateQueries({ queryKey: ["pending-listings"] });
      toast.success(`"${title}" approved and is now live.`);
    } catch {
      toast.error("Failed to approve listing");
    }
  };

  // ── Reject ──
  const handleReject = async (reason: string) => {
    if (!rejectTarget) return;
    setActionLoading(true);
    try {
      await api.patch(`/api/v1/moderation/listings/${rejectTarget.id}/reject`, { reason });
      queryClient.invalidateQueries({ queryKey: ["pending-listings"] });
      toast.success(`"${rejectTarget.title}" rejected.`);
      setRejectTarget(null);
    } catch {
      toast.error("Failed to reject listing");
    } finally {
      setActionLoading(false);
    }
  };

  // ── Remove review ──
  const handleRemoveReview = async (reason: string) => {
    if (!removeTarget) return;
    setActionLoading(true);
    try {
      await api.delete(`/api/v1/moderation/reviews/${removeTarget.id}`, { data: { reason } });
      queryClient.invalidateQueries({ queryKey: ["flagged-reviews"] });
      toast.success("Review removed.");
      setRemoveTarget(null);
    } catch {
      toast.error("Failed to remove review");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      </PageLayout>
    );
  }

  if (!user || isStudent || isLandlord) return null;

  return (
    <PageLayout>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Moderation Panel</h1>
            <p className="text-sm text-slate-500">Review pending listings and flagged content</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit mb-6">
          <button
            onClick={() => setActiveTab("listings")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "listings" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <FileText className="w-4 h-4" />
            Pending listings
            {pendingListings.length > 0 && (
              <span className="bg-amber-100 text-amber-700 text-xs px-1.5 py-0.5 rounded-full font-semibold">
                {pendingListings.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("reviews")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "reviews" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            Flagged reviews
          </button>
        </div>

        {/* ── Pending listings tab ── */}
        {activeTab === "listings" && (
          <>
            {listingsLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-28 w-full rounded-2xl" />
                ))}
              </div>
            ) : pendingListings.length === 0 ? (
              <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center">
                <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-7 h-7 text-emerald-500" />
                </div>
                <h3 className="font-semibold text-slate-900 mb-1">All caught up</h3>
                <p className="text-sm text-slate-500">No listings pending review right now.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {pendingListings.map((listing) => (
                  <div key={listing.id} className="bg-white border border-slate-200 rounded-2xl p-5">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-slate-900">{listing.title}</h3>
                          <Badge className="bg-amber-50 text-amber-700 border-amber-200 border rounded-full text-xs px-2 py-0.5">
                            <Clock className="w-3 h-3 mr-1" />
                            Pending
                          </Badge>
                        </div>
                        <p className="text-sm text-slate-500 flex items-center gap-1.5 mb-2">
                          <MapPin className="w-3.5 h-3.5" />{listing.address}
                        </p>
                        <div className="flex items-center gap-4">
                          <span className="text-sm font-medium text-slate-700">
                            R{listing.price_min.toLocaleString()} – R{listing.price_max.toLocaleString()}/mo
                          </span>
                          <span className="text-xs text-slate-400 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            Submitted {new Date(listing.created_at).toLocaleDateString("en-ZA", {
                              day: "numeric", month: "short", year: "numeric"
                            })}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-xl gap-1.5 text-xs"
                          onClick={() => router.push(`/listings/${listing.id}`)}
                        >
                          <Eye className="w-3.5 h-3.5" />
                          Preview
                        </Button>
                        <Button
                          size="sm"
                          className="rounded-xl gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                          onClick={() => handleApprove(listing.id, listing.title)}
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          className="rounded-xl gap-1.5 text-xs bg-red-500 hover:bg-red-600 text-white"
                          onClick={() => setRejectTarget(listing)}
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          Reject
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ── Flagged reviews tab ── */}
        {activeTab === "reviews" && (
          <FlaggedReviewsTab onRemove={(review) => setRemoveTarget(review)} />
        )}
      </div>

      <RejectModal
        open={!!rejectTarget}
        title={rejectTarget?.title ?? ""}
        onClose={() => setRejectTarget(null)}
        onConfirm={handleReject}
        loading={actionLoading}
      />

      <RemoveReviewModal
        open={!!removeTarget}
        onClose={() => setRemoveTarget(null)}
        onConfirm={handleRemoveReview}
        loading={actionLoading}
      />
    </PageLayout>
  );
}