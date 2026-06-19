"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";
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
  ArrowLeft, MapPin, Star, Eye, Home, User, Phone, Globe,
  Calendar, CheckCircle, XCircle, Clock, FileText, Loader2,
  Wifi, ShieldCheck, Zap, Wrench, Volume2, DollarSign, AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AccommodationDetail {
  id: number;
  title: string;
  description: string;
  address: string;
  price_min: number;
  price_max: number;
  status: string;
  created_at: string;
  lat: number;
  lng: number;
  gender_policy: string | null;
  funding_type: string | null;
  property_type: string | null;
  website: string | null;
  amenities: string[] | null;
  ownership_doc_url: string | null;
  total_reviews: number;
  average_rating: number | null;
  dominant_sentiment: string | null;
  landlord_id: number;
  landlord_name: string | null;
  images: { id: number; url: string; order: number }[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  approved: { label: "Live", color: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle },
  pending:  { label: "Pending review", color: "bg-amber-50 text-amber-700 border-amber-200", icon: Clock },
  rejected: { label: "Rejected", color: "bg-red-50 text-red-700 border-red-200", icon: XCircle },
};

const AMENITY_LABELS: Record<string, string> = {
  wifi: "WiFi", parking: "Parking", laundry: "Laundry",
  furnished: "Furnished", security: "Security", generator: "Generator",
  solar: "Solar", cctv: "CCTV", study_room: "Study Room",
  kitchen: "Kitchen", garden: "Garden",
};

const VERIFICATION_COLORS: Record<string, string> = {
  verified: "bg-emerald-50 text-emerald-700 border-emerald-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  unverified: "bg-slate-100 text-slate-600 border-slate-200",
  rejected: "bg-red-50 text-red-700 border-red-200",
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminAccommodationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading, isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/admin");
    if (!loading && user && !isAdmin) router.push("/");
  }, [user, loading]);

  // Fetch accommodation detail
  const { data: listing, isLoading: listingLoading, isError } = useQuery({
    queryKey: ["admin-accommodation", id],
    queryFn: async () => {
      const { data } = await api.get(`/api/v1/accommodations/${id}`);
      return data as AccommodationDetail;
    },
    enabled: !!id,
  });

  

  // Fetch landlord from admin endpoint
  const { data: landlordData, isLoading: landlordDataLoading } = useQuery({
    queryKey: ["admin-landlord-detail", listing?.landlord_id],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/admin/users/landlords");
      return data.find((l: any) => l.landlord_id === listing?.landlord_id);
    },
    enabled: !!listing?.landlord_id,
  });

  // Fetch today's views from analytics
  const { data: viewsData } = useQuery({
    queryKey: ["admin-accommodation-views", id],
    queryFn: async () => {
      const { data } = await api.get(`/api/v1/admin/accommodations/${id}/views`);
      return data;
    },
    enabled: !!id,
  });

  const handleApprove = async () => {
    setActionLoading(true);
    try {
      await api.patch(`/api/v1/moderation/listings/${id}/approve`);
      toast.success("Listing approved and is now live.");
      queryClient.invalidateQueries({ queryKey: ["admin-accommodation", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-universities-tree"] });
    } catch {
      toast.error("Failed to approve listing");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) { toast.error("Please provide a reason"); return; }
    setActionLoading(true);
    try {
      await api.patch(`/api/v1/moderation/listings/${id}/reject`, { reason: rejectReason });
      toast.success("Listing rejected.");
      queryClient.invalidateQueries({ queryKey: ["admin-accommodation", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-universities-tree"] });
      setRejectOpen(false);
      setRejectReason("");
    } catch {
      toast.error("Failed to reject listing");
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

  if (!user || !isAdmin) return null;

  if (isError) {
    return (
      <PageLayout>
        <div className="max-w-5xl mx-auto px-4 py-10 text-center">
          <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-slate-900 mb-2">Accommodation not found</h2>
          <Button onClick={() => router.push("/admin")} variant="outline" className="rounded-xl">
            Back to admin
          </Button>
        </div>
      </PageLayout>
    );
  }

  const statusCfg = listing ? (STATUS_CONFIG[listing.status] ?? STATUS_CONFIG.pending) : null;
  const StatusIcon = statusCfg?.icon;

  return (
    <PageLayout>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

        {/* Back */}
        <button
          onClick={() => router.push("/admin")}
          className="flex items-center gap-2 text-slate-500 hover:text-slate-800 text-sm font-medium mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to admin
        </button>

        {listingLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="h-5 w-1/3" />
            <Skeleton className="h-64 w-full rounded-2xl" />
          </div>
        ) : listing && (
          <>
            {/* Header */}
            <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-2xl font-bold text-slate-900">{listing.title}</h1>
                  {statusCfg && StatusIcon && (
                    <Badge className={`text-xs border rounded-full px-2 py-0.5 ${statusCfg.color}`}>
                      <StatusIcon className="w-3 h-3 mr-1" />
                      {statusCfg.label}
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-slate-500 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5" />{listing.address}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-xl gap-1.5"
                  onClick={() => router.push(`/listings/${id}`)}
                >
                  <Eye className="w-3.5 h-3.5" />
                  View listing
                </Button>
                {listing.status === "pending" && (
                  <>
                    <Button
                      size="sm"
                      className="rounded-xl gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={handleApprove}
                      disabled={actionLoading}
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      className="rounded-xl gap-1.5 bg-red-500 hover:bg-red-600 text-white"
                      onClick={() => setRejectOpen(true)}
                      disabled={actionLoading}
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      Reject
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

              {/* Left column */}
              <div className="lg:col-span-2 space-y-6">

                {/* Cover image */}
                {listing.images.length > 0 && (
                  <div className="w-full h-64 rounded-2xl overflow-hidden">
                    <img
                      src={listing.images[0].url}
                      alt={listing.title}
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}

                {/* Description */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5">
                  <h2 className="font-semibold text-slate-900 mb-3">Description</h2>
                  <p className="text-sm text-slate-600 leading-relaxed">{listing.description}</p>
                </div>

                {/* Property details */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5">
                  <h2 className="font-semibold text-slate-900 mb-4">Property details</h2>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Type</p>
                      <p className="text-sm font-medium text-slate-700 capitalize">
                        {listing.property_type?.replace("_", " ") ?? "Not specified"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Suitable for</p>
                      <p className="text-sm font-medium text-slate-700 capitalize">
                        {listing.gender_policy === "mixed" ? "Everyone"
                          : listing.gender_policy ? `${listing.gender_policy} only`
                          : "Not specified"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Funding</p>
                      <p className="text-sm font-medium text-slate-700">
                        {listing.funding_type === "self_funded" ? "Self funded"
                          : listing.funding_type === "bursary" ? "Bursary / NSFAS"
                          : listing.funding_type === "both" ? "Self funded & Bursary"
                          : "Not specified"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Price</p>
                      <p className="text-sm font-medium text-slate-700">
                        R{listing.price_min.toLocaleString()} – R{listing.price_max.toLocaleString()}/mo
                      </p>
                    </div>
                    {listing.website && (
                      <div className="col-span-2">
                        <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Website</p>
                        <a
                          href={listing.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:underline font-medium"
                        >
                          {listing.website}
                        </a>
                      </div>
                    )}
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Listed</p>
                      <p className="text-sm font-medium text-slate-700">
                        {new Date(listing.created_at).toLocaleDateString("en-ZA", {
                          day: "numeric", month: "long", year: "numeric"
                        })}
                      </p>
                    </div>
                  </div>

                  {/* Amenities */}
                  {listing.amenities && listing.amenities.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Amenities</p>
                      <div className="flex flex-wrap gap-2">
                        {listing.amenities.map(a => (
                          <span key={a} className="text-xs px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 font-medium capitalize">
                            {AMENITY_LABELS[a] ?? a.replace("_", " ")}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Ownership document */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5">
                  <h2 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-400" />
                    Ownership document
                  </h2>
                  {listing.ownership_doc_url ? (
                    <a
                      href={listing.ownership_doc_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-blue-600 hover:underline font-medium"
                    >
                      <Eye className="w-4 h-4" />
                      View ownership document
                    </a>
                  ) : (
                    <p className="text-sm text-amber-600 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" />
                      No ownership document uploaded yet
                    </p>
                  )}
                </div>
              </div>

              {/* Right column */}
              <div className="space-y-4">

                {/* Stats */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5">
                  <h3 className="font-semibold text-slate-900 text-sm mb-4">Performance</h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-500 flex items-center gap-2">
                        <Eye className="w-4 h-4" /> Total views
                      </span>
                      <span className="text-sm font-bold text-slate-900">
                        {viewsData?.total_views ?? 0}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-500 flex items-center gap-2">
                        <Star className="w-4 h-4" /> Reviews
                      </span>
                      <span className="text-sm font-bold text-slate-900">
                        {listing.total_reviews}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-500 flex items-center gap-2">
                        <Star className="w-4 h-4 fill-amber-400 text-amber-400" /> Avg rating
                      </span>
                      <span className="text-sm font-bold text-slate-900">
                        {listing.average_rating?.toFixed(1) ?? "—"}
                      </span>
                    </div>
                    {listing.dominant_sentiment && (
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-slate-500">Sentiment</span>
                        <Badge className={`text-xs border rounded-full capitalize ${
                          listing.dominant_sentiment === "positive" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                          listing.dominant_sentiment === "negative" ? "bg-red-50 text-red-700 border-red-200" :
                          "bg-amber-50 text-amber-700 border-amber-200"
                        }`}>
                          {listing.dominant_sentiment}
                        </Badge>
                      </div>
                    )}
                  </div>
                </div>

                {/* Landlord details */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5">
                  <h3 className="font-semibold text-slate-900 text-sm mb-4 flex items-center gap-2">
                    <User className="w-4 h-4 text-slate-400" /> Landlord
                  </h3>
                  {landlordDataLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-4 w-1/2" />
                    </div>
                  ) : landlordData ? (
                    <div className="space-y-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-800">{landlordData.display_name}</p>
                        <p className="text-xs text-slate-400">{landlordData.email}</p>
                      </div>

                      {landlordData.contact_phone && (
                        <div className="flex items-center gap-2 text-sm text-slate-600">
                          <Phone className="w-3.5 h-3.5 text-slate-400" />
                          {landlordData.contact_phone}
                        </div>
                      )}

                      {landlordData.website && (
                        <div className="flex items-center gap-2">
                          <Globe className="w-3.5 h-3.5 text-slate-400" />
                          <a
                            href={landlordData.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:underline"
                          >
                            {landlordData.website}
                          </a>
                        </div>
                      )}

                      <div className="pt-2 border-t border-slate-100">
                        <p className="text-xs text-slate-400 mb-1">Verification status</p>
                        <Badge className={`text-xs border rounded-full capitalize ${
                          VERIFICATION_COLORS[landlordData.verification_status] ?? ""
                        }`}>
                          {landlordData.verification_status}
                        </Badge>
                      </div>

                      {landlordData.id_number && (
                        <div>
                          <p className="text-xs text-slate-400 mb-1">ID Number</p>
                          <code className="text-xs bg-slate-100 px-2 py-1 rounded font-mono text-slate-700">
                            {landlordData.id_number}
                          </code>
                        </div>
                      )}

                      <div className="flex gap-2">
                        {landlordData.id_copy_url && (
                          <a
                            href={landlordData.id_copy_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                          >
                            <Eye className="w-3 h-3" /> ID copy
                          </a>
                        )}
                        {landlordData.proof_of_address_url && (
                          <a
                            href={landlordData.proof_of_address_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                          >
                            <Eye className="w-3 h-3" /> Proof of address
                          </a>
                        )}
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full rounded-xl text-xs mt-2"
                        onClick={() => router.push("/admin?tab=users")}
                      >
                        View in user management
                      </Button>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">Landlord details not available</p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Reject modal */}
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent className="rounded-2xl max-w-md bg-white">
          <DialogHeader>
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-red-50 border border-red-100 mx-auto mb-2">
              <XCircle className="w-5 h-5 text-red-500" />
            </div>
            <DialogTitle className="text-center">Reject listing</DialogTitle>
            <DialogDescription className="text-center text-sm line-clamp-1">
              {listing?.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Reason</label>
              <Textarea
                className="rounded-xl resize-none h-28 text-sm"
                placeholder="e.g. Missing property details, inaccurate information..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
              />
            </div>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setRejectOpen(false)} disabled={actionLoading}>
                Cancel
              </Button>
              <Button
                className="flex-1 rounded-xl bg-red-500 hover:bg-red-600 text-white"
                onClick={handleReject}
                disabled={actionLoading || !rejectReason.trim()}
              >
                {actionLoading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Rejecting...</> : "Reject"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}