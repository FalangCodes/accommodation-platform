"use client";

import { FlaggedReviewQueue } from "@/components/flagged-review-queue";
import { ProtectedDocumentLink } from "@/components/protected-document-link";

import { isAxiosError } from "axios";
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
  ShieldCheck, Loader2, MapPin, Clock, CheckCircle,
  XCircle, Trash2, Eye, AlertTriangle, FileText, MessageSquare, Scale, Flag
} from "lucide-react";
import { toast } from "sonner";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PendingAppeal {
  id: number;
  resource_type: string;
  resource_id: number;
  original_action_id: number;
  appellant_email: string | null;
  original_action: { action: string; reason: string | null; created_at: string } | null;
  reason: string;
  status: string;
}

interface PendingListing {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  created_at: string;
  ownership_doc_url: string | null;
  landlord: {
    display_name: string;
    contact_phone: string | null;
    id_number: string | null;
    verification_status: string;
  } | null;
}


interface PendingLandlord {
  id: number;
  display_name: string;
  email: string;
  contact_phone: string | null;
  id_number: string;
  id_number_verified: boolean;
  id_copy_url: string | null;
  proof_of_address_url: string | null;
  verification_status: string;
  address: string | null;
}

interface SuspendedListing {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  created_at: string;
  landlord: {
    display_name: string | null;
    contact_phone: string | null;
  } | null;
}

// ─── Fetch helpers ────────────────────────────────────────────────────────────

async function fetchPendingAppeals(): Promise<PendingAppeal[]> {
  const { data } = await api.get("/api/v1/moderation/appeals?status=pending");
  return data;
}

async function fetchPendingListings(): Promise<PendingListing[]> {
  const { data } = await api.get("/api/v1/moderation/listings/pending");
  return data;
}

async function fetchSuspendedListings(): Promise<SuspendedListing[]> {
  const { data } = await api.get("/api/v1/moderation/listings/suspended");
  return data;
}


async function fetchPendingLandlords(): Promise<PendingLandlord[]> {
  const { data } = await api.get("/api/v1/landlords/pending-verification");
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

function LandlordVerificationTab({
  onApprove,
  onReject,
}: {
  onApprove: (id: number, name: string) => void;
  onReject: (landlord: PendingLandlord) => void;
}) {
  const { data: landlords = [], isLoading } = useQuery({
    queryKey: ["pending-landlords"],
    queryFn: fetchPendingLandlords,
  });

  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  if (landlords.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-7 h-7 text-emerald-500" />
        </div>
        <h3 className="font-semibold text-slate-900 mb-1">No pending verifications</h3>
        <p className="text-sm text-slate-500">All landlord verifications are up to date.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {landlords.map((landlord) => (
        <div key={landlord.id} className="bg-white border border-slate-200 rounded-2xl p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold text-slate-900">{landlord.display_name}</h3>
                <Badge className="bg-amber-50 text-amber-700 border-amber-200 border rounded-full text-xs px-2 py-0.5">
                  <Clock className="w-3 h-3 mr-1" />
                  Pending
                </Badge>
              </div>
              <p className="text-sm text-slate-500 mb-1">{landlord.email}</p>
              {landlord.contact_phone && (
                <p className="text-xs text-slate-400 mb-2">{landlord.contact_phone}</p>
              )}

              {landlord.address && (
                <p className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  {landlord.address}
                </p>
              )}

              {/* ID Number */}
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">ID Number:</span>
                <code className="text-xs bg-slate-100 px-2 py-0.5 rounded font-mono text-slate-700">
                  {landlord.id_number}
                </code>
                {landlord.id_number_verified && (
                  <Badge className="bg-emerald-50 text-emerald-700 border-0 text-xs">Verified</Badge>
                )}
              </div>

              {/* Document links */}
              <div className="flex items-center gap-3">
                {landlord.id_copy_url ? (
                  <ProtectedDocumentLink href={landlord.id_copy_url}
                    className="flex items-center gap-1.5 text-xs text-blue-600 hover:underline font-medium"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Download ID copy
                  </ProtectedDocumentLink>
                ) : (
                  <span className="text-xs text-red-500">⚠ ID copy not uploaded</span>
                )}
                {landlord.proof_of_address_url ? (
                  <ProtectedDocumentLink href={landlord.proof_of_address_url}
                    className="flex items-center gap-1.5 text-xs text-blue-600 hover:underline font-medium"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Download proof of address
                  </ProtectedDocumentLink>
                ) : (
                  <span className="text-xs text-red-500">⚠ Proof of address not uploaded</span>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                size="sm"
                className="rounded-xl gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={() => onApprove(landlord.id, landlord.display_name)}
              >
                <CheckCircle className="w-3.5 h-3.5" />
                Verify
              </Button>
              <Button
                size="sm"
                className="rounded-xl gap-1.5 text-xs bg-red-500 hover:bg-red-600 text-white"
                onClick={() => onReject(landlord)}
              >
                <XCircle className="w-3.5 h-3.5" />
                Reject
              </Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function RejectLandlordModal({
  open,
  landlord,
  onClose,
  onConfirm,
  loading,
}: {
  open: boolean;
  landlord: PendingLandlord | null;
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
            <XCircle className="w-5 h-5 text-red-500" />
          </div>
          <DialogTitle className="text-center">Reject verification</DialogTitle>
          <DialogDescription className="text-center text-sm">
            {landlord?.display_name}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              Reason for rejection
            </label>
            <Textarea
              className="rounded-xl resize-none h-28 text-sm"
              placeholder="e.g. ID document is blurry, proof of address is expired..."
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
              {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Rejecting...</> : "Reject verification"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Suspended Listings Tab ───────────────────────────────────────────────────

function SuspendedListingsTab({
  onReinstate,
  onRemove,
}: {
  onReinstate: (listing: SuspendedListing) => void;
  onRemove: (listing: SuspendedListing) => void;
}) {
  const { data: listings = [], isLoading } = useQuery({
    queryKey: ["suspended-listings"],
    queryFn: fetchSuspendedListings,
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

  if (listings.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-7 h-7 text-emerald-500" />
        </div>
        <h3 className="font-semibold text-slate-900 mb-1">No suspended listings</h3>
        <p className="text-sm text-slate-500">All live listings are currently active.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {listings.map((listing) => (
        <div key={listing.id} className="bg-white border border-amber-200 rounded-2xl p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold text-slate-900 truncate">{listing.title}</h3>
                <span className="bg-amber-100 text-amber-700 border border-amber-200 rounded-full text-xs px-2 py-0.5 flex-shrink-0 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Suspended
                </span>
              </div>
              <p className="text-sm text-slate-500 flex items-center gap-1 mb-1">
                <MapPin className="w-3.5 h-3.5" />{listing.address}
              </p>
              {listing.landlord?.display_name && (
                <p className="text-xs text-slate-400">
                  Landlord: <span className="font-medium text-slate-600">{listing.landlord.display_name}</span>
                  {listing.landlord.contact_phone && ` · ${listing.landlord.contact_phone}`}
                </p>
              )}
              <p className="text-xs text-slate-400 mt-1">
                R{listing.price_min.toLocaleString()}
                {listing.price_max > listing.price_min && ` – R${listing.price_max.toLocaleString()}`} / month
              </p>
            </div>
            <div className="flex flex-col gap-2 flex-shrink-0">
              <Button
                size="sm"
                className="rounded-xl gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white w-full"
                onClick={() => onReinstate(listing)}
              >
                <CheckCircle className="w-3.5 h-3.5" />
                Reinstate
              </Button>
              <Button
                size="sm"
                className="rounded-xl gap-1.5 text-xs bg-red-500 hover:bg-red-600 text-white w-full"
                onClick={() => onRemove(listing)}
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

// ─── Appeals Tab ────────────────────────────────────────────────────────────────

function AppealsTab({
  onResolve,
}: {
  onResolve: (appeal: PendingAppeal, decision: "upheld" | "dismissed") => void;
}) {
  const { data: appeals = [], isLoading, isError } = useQuery({
    queryKey: ["pending-appeals"],
    queryFn: fetchPendingAppeals,
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

  if (isError) return <p className="text-sm text-red-600">Could not load appeals. Refresh to retry.</p>;

  if (appeals.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
          <Scale className="w-7 h-7 text-emerald-500" />
        </div>
        <h3 className="font-semibold text-slate-900 mb-1">No pending appeals</h3>
        <p className="text-sm text-slate-500">All student and landlord appeals have been resolved.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {appeals.map((appeal) => (
        <div key={appeal.id} className="bg-white border border-slate-200 rounded-2xl p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Badge className="bg-blue-50 text-blue-700 border-blue-200 border rounded-full text-xs px-2 py-0.5">
                  <Scale className="w-3 h-3 mr-1" />
                  Appeal
                </Badge>
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                  {appeal.resource_type} #{appeal.resource_id}
                </span>
              </div>
              {appeal.original_action && (
                <div className="mb-3 text-sm text-slate-600">
                  <p>Original action: {appeal.original_action.action.replaceAll("_", " ")}</p>
                  <p>{appeal.original_action.reason ?? "No reason recorded."}</p>
                </div>
              )}
              <div className="mb-3">
                <p className="text-xs font-semibold text-slate-600 mb-1">Reason provided:</p>
                <p className="text-sm text-slate-700 leading-relaxed italic bg-slate-50 p-3 rounded-xl border border-slate-100">
                  "{appeal.reason}"
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <span>Appeal #{appeal.id} · {appeal.appellant_email}</span>
              </div>
            </div>

            <div className="flex flex-col gap-2 flex-shrink-0">
              <Button
                size="sm"
                className="rounded-xl gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white w-full"
                onClick={() => onResolve(appeal, "upheld")}
              >
                <CheckCircle className="w-3.5 h-3.5" />
                Uphold (Restore)
              </Button>
              <Button
                size="sm"
                className="rounded-xl gap-1.5 text-xs bg-red-500 hover:bg-red-600 text-white w-full"
                onClick={() => onResolve(appeal, "dismissed")}
              >
                <XCircle className="w-3.5 h-3.5" />
                Dismiss appeal
              </Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ResolveAppealModal({
  open,
  appeal,
  decision,
  onClose,
  onConfirm,
  loading,
}: {
  open: boolean;
  appeal: PendingAppeal | null;
  decision: "upheld" | "dismissed" | null;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  loading: boolean;
}) {
  const [reason, setReason] = useState("");
  const isUpheld = decision === "upheld";

  return (
    <Dialog open={open} onOpenChange={() => { if (!loading) { onClose(); setReason(""); } }}>
      <DialogContent className="rounded-2xl max-w-md bg-white">
        <DialogHeader>
          <div className={`flex items-center justify-center w-12 h-12 rounded-2xl border mx-auto mb-2 ${
            isUpheld ? "bg-emerald-50 border-emerald-100" : "bg-red-50 border-red-100"
          }`}>
            {isUpheld ? <CheckCircle className="w-5 h-5 text-emerald-500" /> : <XCircle className="w-5 h-5 text-red-500" />}
          </div>
          <DialogTitle className="text-center">
            {isUpheld ? "Uphold appeal?" : "Dismiss appeal?"}
          </DialogTitle>
          <DialogDescription className="text-center text-sm">
            {isUpheld 
              ? `This will overturn the moderation action and restore the ${appeal?.resource_type}.`
              : `This will reject the appeal and the ${appeal?.resource_type} will keep its current status.`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              Reason (Optional, for internal log)
            </label>
            <Textarea
              className="rounded-xl resize-none h-20 text-sm"
              placeholder="Add an internal note about this decision..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => { onClose(); setReason(""); }} disabled={loading}>
              Cancel
            </Button>
            <Button
              className={`flex-1 rounded-xl text-white ${
                isUpheld ? "bg-emerald-600 hover:bg-emerald-700" : "bg-red-500 hover:bg-red-600"
              }`}
              onClick={() => onConfirm(reason)}
              disabled={loading}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : isUpheld ? "Uphold" : "Dismiss"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}


export default function AdminPage() {
  const { user, loading, isStudent, isLandlord, isAdmin } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"listings" | "reviews" | "landlords" | "suspended" | "appeals">("listings");
  const [rejectTarget, setRejectTarget] = useState<PendingListing | null>(null);
  const [rejectLandlordTarget, setRejectLandlordTarget] = useState<PendingLandlord | null>(null);
  const [resolveAppealTarget, setResolveAppealTarget] = useState<{ appeal: PendingAppeal, decision: "upheld" | "dismissed" } | null>(null);
  const [reinstateTarget, setReinstateTarget] = useState<SuspendedListing | null>(null);
  const [removeListingTarget, setRemoveListingTarget] = useState<SuspendedListing | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/moderation");
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

  const { data: pendingLandlords = [] } = useQuery({
    queryKey: ["pending-landlords"],
    queryFn: fetchPendingLandlords,
    enabled: !!user && !isStudent && !isLandlord,
  });

  const { data: pendingAppeals = [] } = useQuery({
    queryKey: ["pending-appeals"],
    queryFn: fetchPendingAppeals,
    enabled: !!user && isAdmin,
  });

  const { data: suspendedListings = [] } = useQuery({
    queryKey: ["suspended-listings"],
    queryFn: fetchSuspendedListings,
    enabled: !!user && !isStudent && !isLandlord,
  });

  const handleVerifyLandlord = async (id: number, name: string) => {
    try {
      await api.patch(`/api/v1/landlords/${id}/verify`);
      queryClient.invalidateQueries({ queryKey: ["pending-landlords"] });
      toast.success(`${name} has been verified.`);
    } catch {
      toast.error("Failed to verify landlord");
    }
  };

  const handleRejectLandlord = async (reason: string) => {
    if (!rejectLandlordTarget) return;
    setActionLoading(true);
    try {
      await api.patch(`/api/v1/landlords/${rejectLandlordTarget.id}/reject-verification`, { reason });
      queryClient.invalidateQueries({ queryKey: ["pending-landlords"] });
      toast.success(`${rejectLandlordTarget.display_name}'s verification rejected.`);
      setRejectLandlordTarget(null);
    } catch {
      toast.error("Failed to reject verification");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolveAppeal = async (reason: string) => {
    if (!isAdmin || !resolveAppealTarget) return;
    setActionLoading(true);
    try {
      await api.patch(`/api/v1/moderation/appeals/${resolveAppealTarget.appeal.id}/resolve`, { 
        decision: resolveAppealTarget.decision, 
        reason 
      });
      await queryClient.invalidateQueries();
      toast.success(`Appeal ${resolveAppealTarget.decision}.`);
      setResolveAppealTarget(null);
    } catch (error: unknown) {
      toast.error(isAxiosError(error) && typeof error.response?.data?.detail === "string"
        ? error.response.data.detail : "Failed to resolve appeal");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReinstate = async () => {
    if (!reinstateTarget) return;
    setActionLoading(true);
    try {
      await api.patch(`/api/v1/moderation/listings/${reinstateTarget.id}/reinstate`);
      queryClient.invalidateQueries({ queryKey: ["suspended-listings"] });
      toast.success(`"${reinstateTarget.title}" reinstated and is now live.`);
      setReinstateTarget(null);
    } catch {
      toast.error("Failed to reinstate listing");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveListing = async (reason: string) => {
    if (!removeListingTarget) return;
    setActionLoading(true);
    try {
      await api.delete(`/api/v1/moderation/listings/${removeListingTarget.id}/remove`, { data: { reason } });
      queryClient.invalidateQueries({ queryKey: ["suspended-listings"] });
      toast.success(`"${removeListingTarget.title}" has been permanently removed.`);
      setRemoveListingTarget(null);
    } catch {
      toast.error("Failed to remove listing");
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

          <button
            onClick={() => setActiveTab("landlords")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "landlords" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            Landlord verification
            {pendingLandlords.length > 0 && (
              <span className="bg-amber-100 text-amber-700 text-xs px-1.5 py-0.5 rounded-full font-semibold">
                {pendingLandlords.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("suspended")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "suspended" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <AlertTriangle className="w-4 h-4" />
            Suspended
            {suspendedListings.length > 0 && (
              <span className="bg-red-100 text-red-700 text-xs px-1.5 py-0.5 rounded-full font-semibold">
                {suspendedListings.length}
              </span>
            )}
          </button>

          {isAdmin && (
          <button
            onClick={() => setActiveTab("appeals")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "appeals" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Scale className="w-4 h-4" />
            Appeals
            {pendingAppeals.length > 0 && (
              <span className="bg-amber-100 text-amber-700 text-xs px-1.5 py-0.5 rounded-full font-semibold">
                {pendingAppeals.length}
              </span>
            )}
          </button>
          )}
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

                        {/* Landlord info */}
                        {listing.landlord && (
                          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-1.5">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Landlord</p>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-slate-800">{listing.landlord.display_name}</span>
                              <Badge className={`text-xs border rounded-full capitalize ${
                                listing.landlord.verification_status === "verified"
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : "bg-amber-50 text-amber-700 border-amber-200"
                              }`}>
                                {listing.landlord.verification_status}
                              </Badge>
                            </div>
                            {listing.landlord.id_number && (
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-slate-400">ID:</span>
                                <code className="text-xs bg-white border border-slate-200 px-2 py-0.5 rounded font-mono text-slate-700">
                                  {listing.landlord.id_number}
                                </code>
                              </div>
                            )}
                            {listing.landlord.contact_phone && (
                              <p className="text-xs text-slate-500">{listing.landlord.contact_phone}</p>
                            )}
                          </div>
                        )}

                        {/* Ownership document */}
                        <div className="mt-3">
                          {listing.ownership_doc_url ? (
                            <ProtectedDocumentLink href={listing.ownership_doc_url}
                              className="flex items-center gap-1.5 text-xs text-blue-600 hover:underline font-medium"
                            >
                              <FileText className="w-3.5 h-3.5" />
                              Download ownership document
                            </ProtectedDocumentLink>
                          ) : (
                            <span className="text-xs text-red-500 flex items-center gap-1.5">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              No ownership document
                            </span>
                          )}
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
          <FlaggedReviewQueue />
        )}

        {activeTab === "landlords" && (
          <LandlordVerificationTab
            onApprove={handleVerifyLandlord}
            onReject={(landlord) => setRejectLandlordTarget(landlord)}
          />
        )}
        {isAdmin && activeTab === "appeals" && (
          <AppealsTab
            onResolve={(appeal, decision) => setResolveAppealTarget({ appeal, decision })}
          />
        )}
        {activeTab === "suspended" && (
          <SuspendedListingsTab
            onReinstate={(listing) => setReinstateTarget(listing)}
            onRemove={(listing) => setRemoveListingTarget(listing)}
          />
        )}
      </div>
      

      <RejectModal
        open={!!rejectTarget}
        title={rejectTarget?.title ?? ""}
        onClose={() => setRejectTarget(null)}
        onConfirm={handleReject}
        loading={actionLoading}
      />


      <RejectLandlordModal
        open={!!rejectLandlordTarget}
        landlord={rejectLandlordTarget}
        onClose={() => setRejectLandlordTarget(null)}
        onConfirm={handleRejectLandlord}
        loading={actionLoading}
      />

      <ResolveAppealModal
        open={!!resolveAppealTarget}
        appeal={resolveAppealTarget?.appeal ?? null}
        decision={resolveAppealTarget?.decision ?? null}
        onClose={() => setResolveAppealTarget(null)}
        onConfirm={handleResolveAppeal}
        loading={actionLoading}
      />

      <RejectModal
        open={!!removeListingTarget}
        title={`permanently remove ${removeListingTarget?.title ?? ""}`}
        onClose={() => setRemoveListingTarget(null)}
        onConfirm={handleRemoveListing}
        loading={actionLoading}
      />

      <Dialog open={!!reinstateTarget} onOpenChange={(o) => !o && setReinstateTarget(null)}>
        <DialogContent className="max-w-sm rounded-2xl">
          <DialogHeader>
            <DialogTitle>Reinstate listing</DialogTitle>
            <DialogDescription>
              Are you sure you want to restore "{reinstateTarget?.title}"? It will become publicly visible again immediately.
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-3 mt-2">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setReinstateTarget(null)} disabled={actionLoading}>
              Cancel
            </Button>
            <Button
              className="flex-1 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={handleReinstate}
              disabled={actionLoading}
            >
              {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Yes, reinstate"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}
