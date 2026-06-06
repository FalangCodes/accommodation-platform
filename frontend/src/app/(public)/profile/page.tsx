"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { reviewsApi } from "@/lib/api";
import PageLayout from "@/components/page-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  GraduationCap,
  Star,
  Trash2,
  MapPin,
  ShieldCheck,
  Loader2,
  AlertTriangle,
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
  rating: number;
  body: string;
  status: string;
  created_at: string;
  deleted_at: string | null;
}

export default function ProfilePage() {
  const { user, loading, isStudent } = useAuth();
  const router = useRouter();

  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Redirect if not logged in or not a student
  useEffect(() => {
    if (!loading && !user) {
      router.push("/login?redirect=/profile");
    }
  }, [user, loading]);

  // Load student's reviews
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

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-[#1F4E79]" />
        </div>
      </PageLayout>
    );
  }

  if (!user) return null;

  return (
    <PageLayout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">

        {/* ── Profile header ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-8">
          <div className="flex items-start gap-4">
            <div className="h-16 w-16 rounded-2xl bg-[#1F4E79] flex items-center justify-center text-white text-2xl font-bold shrink-0">
              {user.email[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-bold text-gray-900 truncate">
                {user.email.split("@")[0]}
              </h1>
              <p className="text-sm text-gray-500 truncate mt-0.5">{user.email}</p>
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                <Badge className="bg-[#E6F1FB] text-[#1F4E79] border-0 gap-1.5">
                  <GraduationCap className="h-3.5 w-3.5" />
                  Student
                </Badge>
                <Badge className="bg-green-50 text-green-700 border-0 gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Verified
                </Badge>
              </div>
            </div>
          </div>
        </div>

        {/* ── My Reviews ── */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-900">My Reviews</h2>
            <span className="text-sm text-gray-400">
              {reviews.length} review{reviews.length !== 1 ? "s" : ""}
            </span>
          </div>

          {reviewsLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-[#1F4E79]" />
            </div>
          ) : reviews.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center">
              <div className="h-14 w-14 rounded-2xl bg-gray-50 border border-gray-100 flex items-center justify-center mx-auto mb-4">
                <Star className="h-6 w-6 text-gray-300" />
              </div>
              <p className="font-semibold text-gray-900 mb-1">No reviews yet</p>
              <p className="text-sm text-gray-500 mb-5">
                Find accommodation and share your experience with other students.
              </p>
              <Button
                onClick={() => router.push("/search")}
                className="bg-[#1F4E79] hover:bg-[#163a5e] text-white rounded-xl"
              >
                Find accommodation
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {reviews.map((review) => (
                <Card
                  key={review.id}
                  className="p-5 border border-gray-100 shadow-sm rounded-2xl"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">

                      {/* Rating */}
                      <div className="flex items-center gap-1 mb-2">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <Star
                            key={i}
                            className={`h-4 w-4 ${
                              i < review.rating
                                ? "fill-amber-400 text-amber-400"
                                : "text-gray-200"
                            }`}
                          />
                        ))}
                        <span className="text-sm text-gray-500 ml-1.5">
                          {review.rating}/5
                        </span>
                      </div>

                      {/* Body */}
                      <p className="text-sm text-gray-700 leading-relaxed line-clamp-3 mb-3">
                        {review.body}
                      </p>

                      {/* Meta */}
                      <div className="flex items-center gap-3 flex-wrap">
                        <button
                          onClick={() =>
                            router.push(`/listings/${review.accommodation_id}`)
                          }
                          className="flex items-center gap-1.5 text-xs text-[#1F4E79] hover:underline"
                        >
                          <MapPin className="h-3 w-3" />
                          View listing
                        </button>
                        <span className="text-xs text-gray-400">
                          {new Date(review.created_at).toLocaleDateString("en-ZA", {
                            year: "numeric",
                            month: "long",
                            day: "numeric",
                          })}
                        </span>
                        <Badge
                          className={`text-xs border-0 ${
                            review.status === "analysed"
                              ? "bg-green-50 text-green-700"
                              : "bg-amber-50 text-amber-700"
                          }`}
                        >
                          {review.status === "analysed" ? "Analysed" : "Pending analysis"}
                        </Badge>
                      </div>
                    </div>

                    {/* Delete */}
                    <button
                      onClick={() => setDeleteTarget(review.id)}
                      className="shrink-0 p-2 rounded-xl text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="Delete review"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </Card>
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
              You won't be able to re-review this accommodation for <strong>14 days</strong> after deletion.
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