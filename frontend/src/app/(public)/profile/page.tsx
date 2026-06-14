"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { reviewsApi } from "@/lib/api";
import PageLayout from "@/components/page-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  GraduationCap,
  Star,
  Trash2,
  MapPin,
  ShieldCheck,
  Loader2,
  AlertTriangle,
  User,
  Mail,
  BookOpen,
  Clock,
} from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Review {
  id: number;
  accommodation_id: number;
  accommodation_title: string;
  rating: number;
  body: string;
  status: string;
  created_at: string;
}

export default function ProfilePage() {
  const { user, loading, isStudent } = useAuth();
  const router = useRouter();

  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/profile");
  }, [user, loading]);

  useEffect(() => {
    if (!user || !isStudent) return;
    reviewsApi
      .getMyReviews()
      .then((res) => setReviews(res.data))
      .catch(() => toast.error("Failed to load reviews"))
      .finally(() => setReviewsLoading(false));
  }, [user]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await reviewsApi.delete(deleteTarget);
      setReviews((prev) => prev.filter((r) => r.id !== deleteTarget));
      toast.success("Review deleted. You can re-review after 14 days.");
      setDeleteTarget(null);
    } catch {
      toast.error("Failed to delete review");
    } finally {
      setDeleting(false);
    }
  };

  const averageRating = reviews.length > 0
    ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(1)
    : null;

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      </PageLayout>
    );
  }

  if (!user) return null;

  const username = user.email.split("@")[0];

  return (
    <PageLayout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-6">

        {/* ── Profile header ── */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-start gap-4">
            <div className="h-16 w-16 rounded-2xl bg-slate-900 flex items-center justify-center text-white text-2xl font-bold shrink-0">
              {username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-bold text-slate-900 truncate capitalize">
                {username}
              </h1>
              <p className="text-sm text-slate-500 truncate mt-0.5 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5" />
                {user.email}
              </p>
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                <Badge className="bg-slate-100 text-slate-700 border-0 gap-1.5 rounded-full">
                  <GraduationCap className="h-3.5 w-3.5" />
                  Student
                </Badge>
                {user.is_active ? (
                  <Badge className="bg-emerald-50 text-emerald-700 border-0 gap-1.5 rounded-full">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Active
                  </Badge>
                ) : (
                  <Badge className="bg-amber-50 text-amber-700 border-0 gap-1.5 rounded-full">
                    <Clock className="h-3.5 w-3.5" />
                    Pending verification
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* Stats row */}
          {reviews.length > 0 && (
            <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t border-slate-100">
              <div className="text-center">
                <div className="text-2xl font-bold text-slate-900">{reviews.length}</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Review{reviews.length !== 1 ? "s" : ""} submitted
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-slate-900 flex items-center justify-center gap-1.5">
                  <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
                  {averageRating}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">Average rating given</div>
              </div>
            </div>
          )}
        </div>

        {/* ── My Reviews ── */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-slate-900">My Reviews</h2>
            <span className="text-sm text-slate-400">
              {reviews.length} review{reviews.length !== 1 ? "s" : ""}
            </span>
          </div>

          {reviewsLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : reviews.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
                <BookOpen className="h-7 w-7 text-slate-300" />
              </div>
              <p className="font-semibold text-slate-900 mb-1">No reviews yet</p>
              <p className="text-sm text-slate-500 mb-6 max-w-xs mx-auto">
                Find accommodation near your campus and share your experience with other students.
              </p>
              <Button
                onClick={() => router.push("/search")}
                className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl"
              >
                Find accommodation
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {reviews.map((review) => (
                <div
                  key={review.id}
                  className="bg-white rounded-2xl border border-slate-200 p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">

                      {/* Accommodation name */}
                      <button
                        onClick={() => router.push(`/listings/${review.accommodation_id}`)}
                        className="text-sm font-semibold text-slate-900 hover:text-slate-600 transition-colors mb-2 text-left line-clamp-1"
                      >
                        {review.accommodation_title}
                      </button>

                      {/* Rating */}
                      <div className="flex items-center gap-1 mb-2">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <Star
                            key={i}
                            className={`h-3.5 w-3.5 ${
                              i < review.rating
                                ? "fill-amber-400 text-amber-400"
                                : "text-slate-200 fill-slate-200"
                            }`}
                          />
                        ))}
                        <span className="text-xs text-slate-400 ml-1">{review.rating}/5</span>
                      </div>

                      {/* Body */}
                      <p className="text-sm text-slate-600 leading-relaxed line-clamp-2 mb-3">
                        {review.body}
                      </p>

                      {/* Meta */}
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className="text-xs text-slate-400">
                          {new Date(review.created_at).toLocaleDateString("en-ZA", {
                            year: "numeric",
                            month: "long",
                            day: "numeric",
                          })}
                        </span>
                        <Badge
                          className={`text-xs border-0 rounded-full ${
                            review.status === "analysed" || review.status === "released"
                              ? "bg-emerald-50 text-emerald-700"
                              : review.status === "quarantined"
                              ? "bg-red-50 text-red-700"
                              : "bg-amber-50 text-amber-700"
                          }`}
                        >
                          {review.status === "analysed" || review.status === "released"
                            ? "✓ Published"
                            : review.status === "quarantined"
                            ? "⚠️ Under review"
                            : "⏳ Pending analysis"}
                        </Badge>
                      </div>
                    </div>

                    {/* Delete button */}
                    <button
                      onClick={() => setDeleteTarget(review.id)}
                      className="shrink-0 p-2 rounded-xl text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="Delete review"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Delete confirmation dialog ── */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent className="rounded-2xl max-w-sm">
          <DialogHeader>
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-red-50 border border-red-100 mx-auto mb-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
            </div>
            <DialogTitle className="text-center">Delete this review?</DialogTitle>
            <DialogDescription className="text-center text-sm">
              You won't be able to re-review this accommodation for{" "}
              <strong>14 days</strong> after deletion.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 mt-2">
            <Button
              variant="outline"
              className="flex-1 rounded-xl"
              onClick={() => setDeleteTarget(null)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              disabled={deleting}
              className="flex-1 rounded-xl bg-red-500 hover:bg-red-600 text-white"
            >
              {deleting ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" />Deleting...</>
              ) : (
                "Delete"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}