"use client";

import type { LucideIcon } from "lucide-react";

import { getApiErrorMessage } from "@/lib/api-error";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type User } from "@/lib/auth-context";
import { reviewsApi, api } from "@/lib/api";
import { MyAppeals } from "@/components/my-appeals";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import PageLayout from "@/components/page-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  GraduationCap, Star, Trash2, MapPin, ShieldCheck, Loader2,
  AlertTriangle, Mail, BookOpen, Clock, Home, BarChart2,
  CheckCircle, XCircle, Activity, Building2, Flag,
} from "lucide-react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Review {
  id: number;
  accommodation_id: number;
  accommodation_title: string;
  rating: number;
  body: string;
  status: string;
  created_at: string;
  removal_reason?: string | null;
  removed_at?: string | null;
}

interface LandlordProfile {
  id: number;
  display_name: string;
  contact_phone: string | null;
  bio: string | null;
  website: string | null;
  verification_status: string;
  rejection_reason: string | null;
  id_copy_uploaded: boolean;
  proof_of_address_uploaded: boolean;
  id_number_verified: boolean;
  verified_at: string | null;
}

interface LandlordListing {
  id: number;
  title: string;
  address: string;
  status: string;
  total_reviews: number;
  average_rating: number | null;
}

interface ModeratorStats {
  actions_count: number;
  recent_actions: {
    id: number;
    action: string;
    resource_type: string;
    resource_id: number;
    reason: string | null;
    created_at: string;
  }[];
}

// ─── Role badge config ────────────────────────────────────────────────────────

const ROLE_CONFIG: Record<string, { label: string; color: string; icon: LucideIcon }> = {
  student:   { label: "Student",   color: "bg-slate-100 text-slate-700",        icon: GraduationCap },
  landlord:  { label: "Landlord",  color: "bg-blue-50 text-blue-700",            icon: Home },
  moderator: { label: "Moderator", color: "bg-violet-50 text-violet-700",        icon: ShieldCheck },
  admin:     { label: "Admin",     color: "bg-slate-900 text-white",             icon: ShieldCheck },
};

const VERIFICATION_COLORS: Record<string, string> = {
  verified:   "bg-emerald-50 text-emerald-700",
  pending:    "bg-amber-50 text-amber-700",
  unverified: "bg-slate-100 text-slate-600",
  rejected:   "bg-red-50 text-red-700",
};

// ─── Student profile ──────────────────────────────────────────────────────────

function StudentProfile() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // ── Appeal state ──
  const [appealTarget, setAppealTarget] = useState<Review | null>(null);
  const [appealReason, setAppealReason] = useState("");
  const [appealing, setAppealing] = useState(false);

  useEffect(() => {
    reviewsApi.getMyReviews()
      .then((res) => setReviews(res.data))
      .catch(() => toast.error("Failed to load reviews"))
      .finally(() => setReviewsLoading(false));
  }, []);

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

  const handleAppeal = async () => {
    if (!appealTarget) return;
    if (appealReason.trim().length < 20) {
      toast.error("Please provide at least 20 characters explaining your appeal.");
      return;
    }
    setAppealing(true);
    try {
      await api.post("/api/v1/appeals", {
        resource_type: "review",
        resource_id: appealTarget.id,
        reason: appealReason.trim(),
      });
      queryClient.invalidateQueries({ queryKey: ["my-appeals"] });
      toast.success("Appeal submitted. An administrator will review it shortly.");
      setAppealTarget(null);
      setAppealReason("");
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "Failed to submit appeal.");
      toast.error(msg);
    } finally {
      setAppealing(false);
    }
  };

  const averageRating = reviews.length > 0
    ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(1)
    : null;

  return (
    <>
      {/* Stats */}
      {reviews.length > 0 && (
        <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t border-slate-100">
          <div className="text-center">
            <div className="text-2xl font-bold text-slate-900">{reviews.length}</div>
            <div className="text-xs text-slate-500 mt-0.5">Reviews submitted</div>
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

      {/* Reviews section */}
      <div className="mt-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">My Reviews</h2>
          <span className="text-sm text-slate-400">{reviews.length} review{reviews.length !== 1 ? "s" : ""}</span>
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
              Find accommodation near your campus and share your experience.
            </p>
            <Button onClick={() => router.push("/search")} className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl">
              Find accommodation
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {reviews.map((review) => (
              <div key={review.id} className="bg-white rounded-2xl border border-slate-200 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <button
                      onClick={() => router.push(`/listings/${review.accommodation_id}`)}
                      className="text-sm font-semibold text-slate-900 hover:text-slate-600 transition-colors mb-2 text-left line-clamp-1"
                    >
                      {review.accommodation_title}
                    </button>
                    <div className="flex items-center gap-1 mb-2">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Star key={i} className={`h-3.5 w-3.5 ${i < review.rating ? "fill-amber-400 text-amber-400" : "text-slate-200 fill-slate-200"}`} />
                      ))}
                      <span className="text-xs text-slate-400 ml-1">{review.rating}/5</span>
                    </div>
                    <p className="text-sm text-slate-600 leading-relaxed line-clamp-2 mb-3">{review.body}</p>
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="text-xs text-slate-400">
                        {new Date(review.created_at).toLocaleDateString("en-ZA", { year: "numeric", month: "long", day: "numeric" })}
                      </span>
                      <Badge className={`text-xs border-0 rounded-full ${
                        review.status === "analysed" || review.status === "released" ? "bg-emerald-50 text-emerald-700" :
                        review.status === "quarantined" || review.status === "removed" ? "bg-red-50 text-red-700" :
                        "bg-amber-50 text-amber-700"
                      }`}>
                        {review.status === "analysed" || review.status === "released" ? "✓ Published" :
                         review.status === "removed" ? "Removed by moderator" :
                         review.status === "quarantined" ? "⚠️ Under review" : "⏳ Pending analysis"}
                      </Badge>
                    </div>
                    {review.status === "removed" && (
                      <div className="mt-3 rounded-xl border border-red-100 bg-red-50 p-3 text-sm text-red-900">
                        <p>This review is no longer public. It remains in your private history so you can appeal the decision.</p>
                        <p className="mt-1"><strong>Reason:</strong> {review.removal_reason || "No removal reason was recorded."}</p>
                      </div>
                    )}
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {/* Both quarantine and moderator removal can be appealed. */}
                    {(review.status === "quarantined" || review.status === "removed") && (
                      <button
                        onClick={() => { setAppealTarget(review); setAppealReason(""); }}
                        className="p-2 rounded-xl text-slate-300 hover:text-amber-500 hover:bg-amber-50 transition-colors"
                        title="Appeal this moderation decision"
                        aria-label="Appeal this moderation decision"
                      >
                        <Flag className="h-4 w-4" />
                      </button>
                    )}
                    {review.status !== "removed" && <button
                      onClick={() => setDeleteTarget(review.id)}
                      aria-label="Delete this review"
                      className="p-2 rounded-xl text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Delete dialog ── */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent className="rounded-2xl max-w-sm bg-white">
          <DialogHeader>
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-red-50 border border-red-100 mx-auto mb-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
            </div>
            <DialogTitle className="text-center">Delete this review?</DialogTitle>
            <DialogDescription className="text-center text-sm">
              You won&apos;t be able to re-review this accommodation for <strong>14 days</strong>.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 mt-2">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button onClick={handleDelete} disabled={deleting} className="flex-1 rounded-xl bg-red-500 hover:bg-red-600 text-white">
              {deleting ? <><Loader2 className="h-4 w-4 animate-spin mr-2" />Deleting...</> : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Appeal dialog ── */}
      <Dialog open={!!appealTarget} onOpenChange={(open) => { if (!open) { setAppealTarget(null); setAppealReason(""); } }}>
        <DialogContent className="rounded-2xl max-w-sm bg-white">
          <DialogHeader>
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-amber-50 border border-amber-100 mx-auto mb-2">
              <Flag className="h-5 w-5 text-amber-500" />
            </div>
            <DialogTitle className="text-center">Appeal moderation decision</DialogTitle>
            <DialogDescription className="text-center text-sm">
              Explain why you believe this moderation decision should be reconsidered. An administrator will review your appeal.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2">
            <textarea
              value={appealReason}
              onChange={(e) => setAppealReason(e.target.value)}
              placeholder="Describe why this review should be reinstated…"
              rows={4}
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 resize-none"
            />
            <p className="text-xs text-slate-400 mt-1 text-right">{appealReason.trim().length} / 20 min</p>
          </div>
          <DialogFooter className="flex gap-2 mt-2">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => { setAppealTarget(null); setAppealReason(""); }}>
              Cancel
            </Button>
            <Button
              onClick={handleAppeal}
              disabled={appealing || appealReason.trim().length < 20}
              className="flex-1 rounded-xl bg-amber-500 hover:bg-amber-600 text-white"
            >
              {appealing ? <><Loader2 className="h-4 w-4 animate-spin mr-2" />Submitting...</> : "Submit appeal"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}


// ─── Landlord profile ─────────────────────────────────────────────────────────

function LandlordProfile() {
  const queryClient = useQueryClient();
  const router = useRouter();

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ["landlord-profile"],
    queryFn: () => api.get("/api/v1/landlords/me").then(r => r.data as LandlordProfile),
  });

  const { data: listings = [], isLoading: listingsLoading } = useQuery({
    queryKey: ["my-listings"],
    queryFn: () => api.get("/api/v1/accommodations/my").then(r => r.data as LandlordListing[]),
  });

  // ── Appeal state ──
  const [appealTarget, setAppealTarget] = useState<LandlordListing | null>(null);
  const [appealReason, setAppealReason] = useState("");
  const [appealing, setAppealing] = useState(false);

  const STATUS_CONFIG: Record<string, { label: string; color: string; icon: LucideIcon }> = {
    approved: { label: "Live",     color: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle },
    pending:  { label: "Pending",  color: "bg-amber-50 text-amber-700 border-amber-200",       icon: Clock },
    rejected: { label: "Rejected", color: "bg-red-50 text-red-700 border-red-200",             icon: XCircle },
  };

  const handleAppeal = async () => {
    if (!appealTarget) return;
    if (appealReason.trim().length < 20) {
      toast.error("Please provide at least 20 characters explaining your appeal.");
      return;
    }
    setAppealing(true);
    try {
      await api.post("/api/v1/appeals", {
        resource_type: "listing",
        resource_id: appealTarget.id,
        reason: appealReason.trim(),
      });
      queryClient.invalidateQueries({ queryKey: ["my-appeals"] });
      toast.success("Appeal submitted. An administrator will review it shortly.");
      setAppealTarget(null);
      setAppealReason("");
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "Failed to submit appeal.");
      toast.error(msg);
    } finally {
      setAppealing(false);
    }
  };

  return (
    <div className="mt-6 space-y-6">
      {/* Verification status */}
      {profileLoading ? (
        <Skeleton className="h-24 rounded-2xl" />
      ) : profile && profile.verification_status !== "verified" && (
        <div className={`rounded-2xl border p-4 ${
          profile.verification_status === "pending" ? "bg-amber-50 border-amber-200" :
          profile.verification_status === "rejected" ? "bg-red-50 border-red-200" :
          "bg-slate-50 border-slate-200"
        }`}>
          <p className="text-sm font-semibold text-slate-800 mb-1">
            {profile.verification_status === "pending" ? "Verification under review" :
             profile.verification_status === "rejected" ? "Verification rejected" :
             "Account not yet verified"}
          </p>
          <p className="text-xs text-slate-600">
            {profile.verification_status === "rejected"
              ? profile.rejection_reason ?? "Please resubmit your documents."
              : profile.verification_status === "pending"
              ? "An admin will review your documents shortly."
              : "Complete your verification to start listing properties."}
          </p>
          {profile.verification_status !== "pending" && (
            <Button
              size="sm"
              className="mt-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
              onClick={() => router.push("/dashboard")}
            >
              Go to dashboard
            </Button>
          )}
        </div>
      )}

      {/* Account details */}
      {profile && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Account details</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-500">Display name</span>
              <span className="text-sm font-medium text-slate-800">{profile.display_name}</span>
            </div>
            {profile.contact_phone && (
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500">Phone</span>
                <span className="text-sm font-medium text-slate-800">{profile.contact_phone}</span>
              </div>
            )}
            {profile.website && (
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500">Website</span>
                <a href={profile.website} target="_blank" rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline font-medium">
                  {profile.website}
                </a>
              </div>
            )}
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-500">Verification</span>
              <Badge className={`text-xs border-0 rounded-full capitalize ${VERIFICATION_COLORS[profile.verification_status]}`}>
                {profile.verification_status}
              </Badge>
            </div>
            {profile.verified_at && (
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500">Verified on</span>
                <span className="text-sm text-slate-600">
                  {new Date(profile.verified_at).toLocaleDateString("en-ZA", { day: "numeric", month: "long", year: "numeric" })}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Listings summary */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900">My listings</h2>
          <Button size="sm" variant="outline" className="rounded-xl" onClick={() => router.push("/dashboard")}>
            Manage listings
          </Button>
        </div>
        {listingsLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
          </div>
        ) : listings.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
            <Building2 className="w-8 h-8 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-500">No listings yet. Go to your dashboard to add one.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {listings.map((listing: LandlordListing) => {
              const cfg = STATUS_CONFIG[listing.status] ?? STATUS_CONFIG.pending;
              const Icon = cfg.icon;
              return (
                <div
                  key={listing.id}
                  className="bg-white rounded-2xl border border-slate-200 p-4 flex items-center gap-3"
                >
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => router.push(`/listings/${listing.id}`)}
                  >
                    <p className="text-sm font-semibold text-slate-800 truncate">{listing.title}</p>
                    <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                      <MapPin className="w-3 h-3" />{listing.address}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {listing.average_rating && (
                      <span className="text-xs text-slate-500 flex items-center gap-1">
                        <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                        {listing.average_rating.toFixed(1)}
                      </span>
                    )}
                    <Badge className={`text-xs border rounded-full px-2 py-0.5 ${cfg.color}`}>
                      <Icon className="w-3 h-3 mr-1" />
                      {cfg.label}
                    </Badge>
                    {/* Appeal button — only on rejected listings */}
                    {["rejected", "suspended", "removed"].includes(listing.status) && (
                      <button
                        onClick={() => { setAppealTarget(listing); setAppealReason(""); }}
                        className="p-1.5 rounded-xl text-slate-300 hover:text-amber-500 hover:bg-amber-50 transition-colors"
                        title="Appeal this moderation decision"
                      >
                        <Flag className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Appeal dialog ── */}
      <Dialog open={!!appealTarget} onOpenChange={(open) => { if (!open) { setAppealTarget(null); setAppealReason(""); } }}>
        <DialogContent className="rounded-2xl max-w-sm bg-white">
          <DialogHeader>
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-amber-50 border border-amber-100 mx-auto mb-2">
              <Flag className="h-5 w-5 text-amber-500" />
            </div>
            <DialogTitle className="text-center">Appeal listing decision</DialogTitle>
            <DialogDescription className="text-center text-sm">
              Explain why you believe your listing was incorrectly rejected, suspended or removed. An administrator will review your appeal.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2">
            <textarea
              value={appealReason}
              onChange={(e) => setAppealReason(e.target.value)}
              placeholder="Describe why this listing should be approved…"
              rows={4}
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 resize-none"
            />
            <p className="text-xs text-slate-400 mt-1 text-right">{appealReason.trim().length} / 20 min</p>
          </div>
          <DialogFooter className="flex gap-2 mt-2">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => { setAppealTarget(null); setAppealReason(""); }}>
              Cancel
            </Button>
            <Button
              onClick={handleAppeal}
              disabled={appealing || appealReason.trim().length < 20}
              className="flex-1 rounded-xl bg-amber-500 hover:bg-amber-600 text-white"
            >
              {appealing ? <><Loader2 className="h-4 w-4 animate-spin mr-2" />Submitting...</> : "Submit appeal"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Moderator/Admin profile ──────────────────────────────────────────────────

function ModeratorProfile({ user }: { user: User }) {
  const router = useRouter();
  const { isAdmin } = useAuth();

  const { data: stats, isLoading, isError } = useQuery({
    queryKey: ["moderator-stats", user.id],
    queryFn: async () => {
      const { data } = await api.get<{ total: number; items: ModeratorStats["recent_actions"] }>(
        "/api/v1/moderation/log", { params: { mine: true, page_size: 10 } });
      return { actions_count: data.total, recent_actions: data.items };
    },
  });

  const ACTION_COLORS: Record<string, string> = {
    approve_listing: "text-emerald-600",
    reject_listing: "text-red-500",
    remove_review: "text-red-500",
    remove_listing: "text-red-500",
    released: "text-blue-600",
    landlord_verified: "text-emerald-600",
    landlord_verification_rejected: "text-red-500",
  };

  return (
    <div className="mt-6 space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-2xl p-5 text-center">
          <div className="text-2xl font-bold text-slate-900">{isLoading ? "…" : isError ? "—" : stats?.actions_count ?? 0}</div>
          <div className="text-xs text-slate-500 mt-1">Total actions logged</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-5 text-center">
          <div className="text-2xl font-bold text-slate-900 capitalize">{user.role}</div>
          <div className="text-xs text-slate-500 mt-1">Account type</div>
        </div>
      </div>

      {/* Quick links */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5">
        <h2 className="font-semibold text-slate-900 mb-4">Quick access</h2>
        <div className="flex flex-col gap-2">
          <Button
            variant="outline"
            className="rounded-xl justify-start gap-2"
            onClick={() => router.push("/moderation")}
          >
            <ShieldCheck className="w-4 h-4" />
            Moderation panel
          </Button>
          {isAdmin && (
            <Button
              variant="outline"
              className="rounded-xl justify-start gap-2"
              onClick={() => router.push("/admin")}
            >
              <BarChart2 className="w-4 h-4" />
              Admin dashboard
            </Button>
          )}
        </div>
      </div>

      {/* Recent activity */}
      <div>
        <h2 className="text-lg font-bold text-slate-900 mb-4">My recent activity</h2>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-2xl" />)}
          </div>
        ) : isError ? (
          <p className="text-sm text-red-600">Could not load your moderation activity. Refresh to retry.</p>
        ) : !stats || stats.recent_actions.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
            <Activity className="w-8 h-8 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-500">No moderation actions yet.</p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-2xl divide-y divide-slate-50">
            {stats.recent_actions.map((log) => (
              <div key={log.id} className="flex items-center gap-3 px-5 py-3">
                <div className="w-2 h-2 rounded-full bg-slate-300 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className={`text-sm font-medium capitalize ${ACTION_COLORS[log.action] ?? "text-slate-700"}`}>
                    {log.action.replace(/_/g, " ")}
                  </span>
                  <span className="text-sm text-slate-400"> · {log.resource_type} #{log.resource_id}</span>
                  {log.reason && (
                    <p className="text-xs text-slate-400 mt-0.5 truncate">{log.reason}</p>
                  )}
                </div>
                <span className="text-xs text-slate-400 flex-shrink-0">
                  {new Date(log.created_at).toLocaleDateString("en-ZA", { day: "numeric", month: "short" })}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const { user, loading, isStudent, isLandlord, isModerator, isAdmin } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/profile");
  }, [user, loading, router]);

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
  const roleCfg = ROLE_CONFIG[user.role] ?? ROLE_CONFIG.student;
  const RoleIcon = roleCfg.icon;

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
                <Badge className={`border-0 gap-1.5 rounded-full text-xs ${roleCfg.color}`}>
                  <RoleIcon className="h-3.5 w-3.5" />
                  {roleCfg.label}
                </Badge>
                {user.is_active ? (
                  <Badge className="bg-emerald-50 text-emerald-700 border-0 gap-1.5 rounded-full text-xs">
                    <CheckCircle className="h-3.5 w-3.5" />
                    Active
                  </Badge>
                ) : (
                  <Badge className="bg-amber-50 text-amber-700 border-0 gap-1.5 rounded-full text-xs">
                    <Clock className="h-3.5 w-3.5" />
                    Inactive
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* Role-specific content */}
          {isStudent && <StudentProfile />}
          {isLandlord && <LandlordProfile />}
          {(isModerator || isAdmin) && <ModeratorProfile user={user} />}
          {(isStudent || isLandlord) && <MyAppeals />}
        </div>
      </div>
    </PageLayout>
  );
}
