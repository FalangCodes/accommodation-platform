"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api, accommodationsApi } from "@/lib/api";
import PageLayout from "@/components/page-layout";
import { LandlordReports } from "@/components/management-report";
import { SummaryUpdated } from "@/components/summary-updated";
import ImageUploader from "@/components/image-uploader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  Plus, MapPin, Star, TrendingUp, Eye, ChevronRight,
  Loader2, Home, CheckCircle, Clock, XCircle,
  Wifi, ShieldCheck, Zap, Wrench, Volume2, DollarSign, User,
  BarChart2, ArrowLeft,
} 
from "lucide-react";
import { toast } from "sonner";
import { ImagePlus, FileText } from "lucide-react";


// ─── Types ────────────────────────────────────────────────────────────────────

interface Listing {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  status: "incomplete" | "pending" | "approved" | "rejected";
  created_at: string;
  total_reviews: number;
  average_rating: number | null;
  ownership_doc_url?: string | null;
}

interface Analytics {
  accommodation_id: number;
  total_views: number;
  total_reviews: number;
  average_rating: number;
  sentiment_distribution: { positive: number; neutral: number; negative: number };
  top_aspects: Record<string, number>;
}

interface LandlordProfile {
  id: number;
  display_name: string;
  verification_status: "unverified" | "pending" | "verified" | "rejected";
  rejection_reason: string | null;
  id_copy_uploaded: boolean;
  proof_of_address_uploaded: boolean;
  id_number_verified: boolean;
  verified_at: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, any> = {
  incomplete: { label: "Missing Document", color: "bg-slate-50 text-slate-700 border-slate-200", icon: FileText },
  pending:  { label: "Pending review",  color: "bg-amber-50 text-amber-700 border-amber-200",   icon: Clock },
  approved: { label: "Live",            color: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle },
  rejected: { label: "Rejected",        color: "bg-red-50 text-red-700 border-red-200",          icon: XCircle },
};

const ASPECT_ICONS: Record<string, any> = {
  "cleanliness": ShieldCheck,
  "safety": ShieldCheck,
  "noise levels": Volume2,
  "landlord responsiveness": User,
  "wifi and internet": Wifi,
  "water and electricity": Zap,
  "maintenance and repairs": Wrench,
  "value for money": DollarSign,
};

const ASPECT_LABELS: Record<string, string> = {
  "cleanliness": "Cleanliness",
  "safety": "Safety",
  "noise levels": "Noise Levels",
  "landlord responsiveness": "Landlord",
  "wifi and internet": "WiFi",
  "water and electricity": "Utilities",
  "maintenance and repairs": "Maintenance",
  "value for money": "Value",
};

// ─── Fetch helpers ────────────────────────────────────────────────────────────

async function fetchMyProfile(): Promise<LandlordProfile> {
  const { data } = await api.get("/api/v1/landlords/me");
  return data;
}

async function fetchMyListings(): Promise<Listing[]> {
  const { data } = await api.get("/api/v1/accommodations/my");
  return data;
}

async function fetchAnalytics(id: number): Promise<Analytics> {
  const { data } = await api.get(`/api/v1/accommodations/${id}/analytics`);
  return data;
}

// ─── Create Listing Modal ─────────────────────────────────────────────────────

function CreateListingModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [newListingId, setNewListingId] = useState<number | null>(null); // ← add this
  const [form, setForm] = useState({
    title: "",
    description: "",
    address: "",
    latitude: "",
    longitude: "",
    price_min: "",
    price_max: "",
    property_type: "",
    gender_policy: "",
    funding_type: "",
    website: "",
    amenities: [] as string[],
  });

  const update = (field: string, value: string | string[]) =>
  setForm((f) => ({ ...f, [field]: value }));

  const [ownershipUploaded, setOwnershipUploaded] = useState(false);
  const [uploadingOwnership, setUploadingOwnership] = useState(false);
  const ownershipRef = useRef<HTMLInputElement>(null);

  const handleClose = () => {
    setOwnershipUploaded(false);
    setUploadingOwnership(false);
    if (submitting) return;
    onClose();
    setTimeout(() => {
      setStep(1);
      setNewListingId(null);
      setForm({
        title: "", description: "", address: "",
        latitude: "", longitude: "",
        price_min: "", price_max: "",
        property_type: "", gender_policy: "",
        funding_type: "", website: "",
        amenities: [],
      });
    }, 300);
  };

  const handleSubmit = async () => {
    if (!form.title || !form.description || !form.address || !form.latitude || !form.longitude || !form.price_min || !form.price_max) {
      toast.error("Please fill in all fields");
      return;
    }
    if (Number(form.price_min) > Number(form.price_max)) {
      toast.error("Minimum price cannot exceed maximum price");
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.post("/api/v1/accommodations", {
        title: form.title,
        description: form.description,
        address: form.address,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        price_min: Number(form.price_min),
        price_max: Number(form.price_max),
        gender_policy: form.gender_policy || undefined,
        funding_type: form.funding_type || undefined,
        property_type: form.property_type || undefined,
        website: form.website || undefined,
        amenities: form.amenities.length > 0 ? form.amenities : undefined,
      });
      setNewListingId(res.data.id); // ← capture ID
      onSuccess();
      setStep(4); // ← proceed to photo upload step
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Failed to create listing");
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass = "w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white";

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="rounded-2xl max-w-lg bg-white">
        <DialogHeader>
          <DialogTitle>
          {step === 1 ? "Listing details"
            : step === 2 ? "Location"
            : step === 3 ? "Pricing & details"
            : step === 4 ? "Ownership document"
            : "Add photos"}
        </DialogTitle>
        <DialogDescription>
          {step === 1 ? "Step 1 of 4 — Basic information"
            : step === 2 ? "Step 2 of 4 — Where is the property?"
            : step === 3 ? "Step 3 of 4 — Pricing and property details"
            : step === 4 ? "Step 4 of 4 — Proof of ownership"
            : "Optional — Add photos to attract more students"}
        </DialogDescription>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex gap-1.5 mb-2">
          {[1, 2, 3, 4].map((s) => (
            <div
              key={s}
              className={`h-1 flex-1 rounded-full transition-all ${s <= Math.min(step, 3) ? "bg-slate-900" : "bg-slate-200"}`}
            />
          ))}
        </div>

        <div className="space-y-4">
          {/* Step 1 — Info */}
          {step === 1 && (
            <>
              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Title</label>
                <input
                  className={inputClass}
                  placeholder="e.g. Modern Student Flat near SPU"
                  value={form.title}
                  onChange={(e) => update("title", e.target.value)}
                  maxLength={200}
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Description</label>
                <Textarea
                  className="rounded-xl resize-none h-32 text-sm"
                  placeholder="Describe the property — rooms, amenities, rules, proximity to campus..."
                  value={form.description}
                  onChange={(e) => update("description", e.target.value)}
                />
                <p className="text-xs text-slate-400 mt-1">{form.description.length} / 2000</p>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Property type</label>
                <select
                  className={inputClass}
                  value={form.property_type}
                  onChange={(e) => update("property_type", e.target.value)}
                >
                  <option value="">Select type</option>
                  <option value="bachelor">Bachelor</option>
                  <option value="single_room">Single Room</option>
                  <option value="shared_room">Shared Room</option>
                  <option value="shared_room">Mixed</option>
                  <option value="flat">Flat</option>
                  <option value="house">House</option>
                </select>
              </div>
            </>
          )}

          {/* Step 2 — Location */}
          {step === 2 && (
            <>
              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Street address</label>
                <input
                  className={inputClass}
                  placeholder="e.g. 12 Warren Street, Kimberley"
                  value={form.address}
                  onChange={(e) => update("address", e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Latitude</label>
                  <input
                    className={inputClass}
                    placeholder="-28.7282"
                    value={form.latitude}
                    onChange={(e) => update("latitude", e.target.value)}
                    type="number"
                    step="any"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Longitude</label>
                  <input
                    className={inputClass}
                    placeholder="24.7435"
                    value={form.longitude}
                    onChange={(e) => update("longitude", e.target.value)}
                    type="number"
                    step="any"
                  />
                </div>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
                <p className="text-xs text-amber-700">
                  💡 Use <a href="https://maps.google.com" target="_blank" className="underline font-medium">Google Maps</a> to find exact coordinates — right-click on your property and copy the coordinates shown. 
                </p>
              </div>
            </>
          )}

          {/* Step 3 — Pricing */}
          {step === 3 && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Minimum rent (R/month)</label>
                  <input
                    className={inputClass}
                    placeholder="3500"
                    value={form.price_min}
                    onChange={(e) => update("price_min", e.target.value)}
                    type="number"
                    min="0"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Maximum rent (R/month)</label>
                  <input
                    className={inputClass}
                    placeholder="5000"
                    value={form.price_max}
                    onChange={(e) => update("price_max", e.target.value)}
                    type="number"
                    min="0"
                  />
                </div>
              </div>
              {/* Gender policy */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Accommodation for</label>
                  <select
                    className={inputClass}
                    value={form.gender_policy}
                    onChange={(e) => update("gender_policy", e.target.value)}
                  >
                    <option value="">Select</option>
                    <option value="male">Male only</option>
                    <option value="female">Female only</option>
                    <option value="mixed">Mixed</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Funding type</label>
                  <select
                    className={inputClass}
                    value={form.funding_type}
                    onChange={(e) => update("funding_type", e.target.value)}
                  >
                    <option value="">Select</option>
                    <option value="self_funded">Self funded</option>
                    <option value="bursary">Bursary / NSFAS</option>
                    <option value="both">Both</option>
                  </select>
                </div>
              </div>

              {/* Website */}
              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
                  Website <span className="text-slate-400">(optional)</span>
                </label>
                <input
                  className={inputClass}
                  placeholder="e.g. https://myresidence.co.za"
                  value={form.website}
                  onChange={(e) => update("website", e.target.value)}
                  type="url"
                />
              </div>

              {/* Amenities */}
              <div>
                <label className="text-xs font-semibold text-slate-600 mb-2 block">Amenities</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { value: "wifi", label: "WiFi" },
                    { value: "parking", label: "Parking" },
                    { value: "laundry", label: "Laundry" },
                    { value: "furnished", label: "Furnished" },
                    { value: "security", label: "Security" },
                    { value: "generator", label: "Generator" },
                    { value: "solar", label: "Solar" },
                    { value: "cctv", label: "CCTV" },
                    { value: "study_room", label: "Study room" },
                    { value: "kitchen", label: "Kitchen" },
                    { value: "garden", label: "Garden" },
                  ].map((amenity) => (
                    <button
                      key={amenity.value}
                      type="button"
                      onClick={() => {
                        const current = form.amenities ?? [];
                        const updated = current.includes(amenity.value)
                          ? current.filter((a) => a !== amenity.value)
                          : [...current, amenity.value];
                        update("amenities", updated as any);
                      }}
                      className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        (form.amenities ?? []).includes(amenity.value)
                          ? "bg-slate-900 text-white border-slate-900"
                          : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
                      }`}
                    >
                      {amenity.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                <p className="text-xs text-slate-500">
                  Your listing will be submitted for moderator review before going live. This usually takes 24–48 hours.
                </p>
              </div>
            </>
          )}

          {/* Step 4 — Ownership document */}
          {step === 4 && newListingId && (
            <div className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
                <p className="text-xs text-amber-700 font-medium mb-1">Required before moderator review</p>
                <p className="text-xs text-amber-600">
                  Your listing will only appear in the moderation queue once you upload proof of ownership — a title deed, lease agreement, or signed mandate letter.
                </p>
              </div>

              <div
                onClick={() => !uploadingOwnership && ownershipRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
                  ownershipUploaded
                    ? "border-emerald-300 bg-emerald-50"
                    : uploadingOwnership
                    ? "border-slate-200 bg-slate-50 cursor-not-allowed"
                    : "border-slate-300 hover:border-slate-400 hover:bg-slate-50"
                }`}
              >
                <input
                  ref={ownershipRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file || !newListingId) return;
                    setUploadingOwnership(true);
                    try {
                      await accommodationsApi.uploadOwnershipDoc(newListingId, file);
                      setOwnershipUploaded(true);
                      toast.success("Ownership document uploaded");
                    } catch (err: any) {
                      toast.error(err?.response?.data?.detail ?? "Upload failed");
                    } finally {
                      setUploadingOwnership(false);
                    }
                  }}
                  disabled={uploadingOwnership}
                />
                {uploadingOwnership ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                    <p className="text-sm text-slate-500">Uploading...</p>
                  </div>
                ) : ownershipUploaded ? (
                  <div className="flex flex-col items-center gap-2">
                    <CheckCircle className="h-10 w-10 text-emerald-500" />
                    <p className="text-sm font-semibold text-emerald-700">Document uploaded</p>
                    <p className="text-xs text-emerald-600">Click to replace</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-12 w-12 rounded-xl bg-slate-100 flex items-center justify-center">
                      <FileText className="h-6 w-6 text-slate-400" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-700">Click to upload ownership document</p>
                      <p className="text-xs text-slate-400 mt-0.5">Title deed, lease agreement or mandate · PDF, JPEG, PNG · Max 10MB</p>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex gap-3">
                {!ownershipUploaded && (
                  <Button
                    variant="outline"
                    className="flex-1 rounded-xl text-slate-500"
                    onClick={() => setStep(5)}
                  >
                    Save as incomplete (Skip doc)
                  </Button>
                )}
                <Button
                  className="flex-1 rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
                  onClick={() => setStep(5)}
                >
                  {ownershipUploaded ? "Submit for review & add photos" : "Skip to photos"}
                </Button>
              </div>
            </div>
          )}

          {/* Step 5 — Photos */}
          {step === 5 && newListingId && (
            <ImageUploader
              accommodationId={newListingId}
              onDone={handleClose}
              showDoneButton={true}
            />
          )}

          {/* Navigation — hide on step 4 */}
          {step < 4 && (
            <div className="flex gap-3 pt-2">
              {step > 1 && (
                <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setStep(s => s - 1)} disabled={submitting}>
                  Back
                </Button>
              )}
              {step < 3 ? (
                <Button
                  className="flex-1 rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
                  onClick={() => {
                    if (step === 1 && (!form.title || !form.description)) { toast.error("Please fill in title and description"); return; }
                    if (step === 2 && (!form.address || !form.latitude || !form.longitude)) { toast.error("Please fill in all location fields"); return; }
                    setStep(s => s + 1);
                  }}
                >
                  Continue
                </Button>
              ) : (
                <Button
                  className="flex-1 rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
                  onClick={handleSubmit}
                  disabled={submitting}
                >
                  {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Saving...</> : "Save & Continue"}
                </Button>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Analytics Panel ──────────────────────────────────────────────────────────

function AnalyticsPanel({ listing, onBack }: { listing: Listing; onBack: () => void }) {
  const [showReports, setShowReports] = useState(false);
  const { data: analytics, isLoading } = useQuery({
    queryKey: ["analytics", listing.id],
    queryFn: () => fetchAnalytics(listing.id),
  });

  const { data: insights } = useQuery({
  queryKey: ["listing-insights", listing.id],
  queryFn: () => api.get(`/api/v1/accommodations/${listing.id}/insights`).then(r => r.data),
});

  if (showReports) return <div className="space-y-4">
    <button onClick={() => setShowReports(false)} className="text-sm text-slate-500 hover:text-slate-800">Back to property insights</button>
    <LandlordReports accommodationId={listing.id} />
  </div>;

  return (
    <div className="space-y-6">
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-slate-500 hover:text-slate-800 text-sm font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to listings
      </button>

      <div>
        <h2 className="text-xl font-bold text-slate-900">{listing.title}</h2>
        <p className="text-sm text-slate-500 mt-0.5 flex items-center gap-1.5">
          <MapPin className="w-3.5 h-3.5" />{listing.address}
        </p>
      </div>

      <Button variant="outline" onClick={() => setShowReports(true)} className="rounded-xl">Generate / view management reports</Button>

      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
      ) : analytics && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Total views", value: analytics.total_views, icon: Eye },
              { label: "Total reviews", value: analytics.total_reviews, icon: Star },
              { label: "Average rating", value: analytics.average_rating > 0 ? analytics.average_rating.toFixed(1) : "—", icon: TrendingUp },
              { label: "Positive sentiment", value: `${analytics.total_reviews > 0 ? Math.round((analytics.sentiment_distribution.positive / analytics.total_reviews) * 100) : 0}%`, icon: BarChart2 },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="bg-white border border-slate-200 rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="w-4 h-4 text-slate-400" />
                  <span className="text-xs text-slate-500">{label}</span>
                </div>
                <div className="text-2xl font-bold text-slate-900">{value}</div>
              </div>
            ))}
          </div>

          {/* Sentiment distribution */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5">
            <h3 className="font-semibold text-slate-900 text-sm mb-4">Sentiment breakdown</h3>
            <div className="space-y-3">
              {(["positive", "neutral", "negative"] as const).map((s) => {
                const count = analytics.sentiment_distribution[s];
                const pct = analytics.total_reviews > 0
                  ? Math.round((count / analytics.total_reviews) * 100) : 0;
                const colors = { positive: "bg-emerald-500", neutral: "bg-amber-400", negative: "bg-red-400" };
                const labels = { positive: "Positive", neutral: "Neutral", negative: "Negative" };
                return (
                  <div key={s} className="flex items-center gap-3">
                    <span className="text-sm text-slate-600 w-20">{labels[s]}</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${colors[s]}`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-sm font-semibold text-slate-700 w-12 text-right">{pct}% ({count})</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Insight Engine Panel */}
          {insights && insights.insights && Object.keys(insights.insights).length > 0 && (
  <div className="bg-white border border-slate-200 rounded-2xl p-5">
    <div className="flex items-center gap-2 mb-4">
      <TrendingUp className="w-4 h-4 text-slate-400" />
      <h3 className="font-semibold text-slate-900 text-sm">Accommodation Insight Engine</h3>
      <span className="text-xs text-slate-400 ml-auto">
        Based on {insights.review_count ?? 0} review{(insights.review_count ?? 0) !== 1 ? "s" : ""}
      </span>
    </div>

    <p className="mb-4 text-xs text-slate-500">Figures reflect current published reviews. Written summaries refresh every two weeks.</p>
    {/* Aspect breakdown */}
    <div className="space-y-3 mb-6">
      {Object.entries(insights.insights).map(([aspect, data]: [string, any]) => {
        const Icon = ASPECT_ICONS[aspect] ?? ShieldCheck;
        const isPositive = (data.overall_sentiment ?? "").includes("positive");
        const isNegative = (data.overall_sentiment ?? "").includes("negative");

        return (
          <div key={aspect} className="border border-slate-100 rounded-xl p-3">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <Icon className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-xs font-semibold text-slate-700">{data.display_name}</span>
                {!data.show_to_students && (
                  <span className="text-xs bg-slate-100 text-slate-400 px-1.5 py-0.5 rounded-full">
                    Hidden from students
                  </span>
                )}
              </div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                isPositive ? "bg-emerald-50 text-emerald-700" :
                isNegative ? "bg-red-50 text-red-700" :
                "bg-amber-50 text-amber-700"
              }`}>
                {data.sentiment_label ?? "Mixed"}
              </span>
            </div>

            {/* Stars + positive rate */}
            <div className="flex items-center gap-2 mb-2">
              <div className="flex items-center gap-0.5">
                {[1,2,3,4,5].map((i) => (
                  <Star key={i} className={`w-3 h-3 ${i <= Math.round(data.star_rating ?? 0) ? "fill-amber-400 text-amber-400" : "text-slate-200 fill-slate-200"}`} />
                ))}
              </div>
              <span className="text-xs text-slate-500">
                {data.positive_rate ?? 0}% positive · {data.mention_count ?? 0} mentions
              </span>
            </div>

            {/* Opinion */}
            {data.overall_opinion && (
              <p className="text-xs text-slate-500 italic mb-2">"{data.overall_opinion}"</p>
            )}
            <SummaryUpdated generatedAt={data.summary_generated_at} reviewCount={data.summary_review_count} />

            {/* Progress bar */}
            <div className="flex items-center gap-2 mb-2">
              <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${isPositive ? "bg-emerald-500" : isNegative ? "bg-red-400" : "bg-amber-400"}`}
                  style={{ width: `${data.positive_rate ?? 0}%` }}
                />
              </div>
            </div>

            {/* Evidence */}
            {(data.strengths ?? []).length > 0 && (
              <div className="space-y-1 mb-1">
                {(data.strengths ?? []).slice(0, 2).map((s: string, i: number) => (
                  <div key={i} className="flex items-start gap-1.5">
                    <span className="text-emerald-500 text-xs flex-shrink-0 mt-0.5">✓</span>
                    <span className="text-xs text-slate-600">{s}</span>
                  </div>
                ))}
              </div>
            )}
            {(data.concerns ?? []).length > 0 && (
              <div className="space-y-1">
                {(data.concerns ?? []).slice(0, 2).map((c: string, i: number) => (
                  <div key={i} className="flex items-start gap-1.5">
                    <span className="text-red-400 text-xs flex-shrink-0 mt-0.5">✗</span>
                    <span className="text-xs text-slate-600">{c}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>

    {/* Recommendations */}
    {(insights.recommendations ?? []).length > 0 && (
      <div>
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Recommendations
        </h4>
        <div className="space-y-3">
          {(insights.recommendations ?? []).map((rec: any, i: number) => (
            <div
              key={i}
              className={`rounded-xl p-3 border ${
                rec.priority === "high"
                  ? "bg-red-50 border-red-200"
                  : "bg-amber-50 border-amber-200"
              }`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`text-xs font-semibold ${
                  rec.priority === "high" ? "text-red-700" : "text-amber-700"
                }`}>
                  {rec.priority === "high" ? "⚠️ High priority" : "⚡ Medium priority"} · {rec.display_name}
                </span>
                <span className="text-xs text-slate-400 ml-auto">
                  {rec.positive_rate}% positive · {rec.mention_count} mentions
                </span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed">{rec.recommendation}</p>
              <SummaryUpdated generatedAt={rec.summary_generated_at} reviewCount={rec.summary_review_count} />
            </div>
          ))}
        </div>
      </div>
    )}

    {(insights.recommendations ?? []).length === 0 && (
      <div className="mt-2 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
        <p className="text-xs text-emerald-700 font-medium">
          ✓ No critical issues identified. Students are generally satisfied with this property.
        </p>
      </div>
    )}
  </div>
)}
        </>
      )}
    </div>
  );
}

function VerificationBanner({
  profile,
  onUploadSuccess,
}: {
  profile: LandlordProfile;
  onUploadSuccess: () => void;
}) {
  const [uploadingId, setUploadingId] = useState(false);
  const [uploadingPoa, setUploadingPoa] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const idRef = useRef<HTMLInputElement>(null);
  const poaRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (
    file: File,
    type: "id-copy" | "proof-of-address",
    setLoading: (v: boolean) => void
  ) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post(`/api/v1/landlords/me/documents/${type}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${type === "id-copy" ? "ID copy" : "Proof of address"} uploaded successfully`);
      onUploadSuccess();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitVerification = async () => {
    setSubmitting(true);
    try {
      await api.post("/api/v1/landlords/me/verification/submit");
      toast.success("Verification submitted! An admin will review your documents shortly.");
      onUploadSuccess();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (profile.verification_status === "verified") return null;

  const bannerConfig = {
    unverified: {
      bg: "bg-amber-50 border-amber-200",
      icon: <ShieldCheck className="w-5 h-5 text-amber-600" />,
      title: "Complete your verification",
      message: "Upload your ID copy and proof of address to get verified and start listing properties.",
    },
    pending: {
      bg: "bg-blue-50 border-blue-200",
      icon: <Clock className="w-5 h-5 text-blue-600" />,
      title: "Verification under review",
      message: "Your documents have been submitted. An admin will review them shortly.",
    },
    rejected: {
      bg: "bg-red-50 border-red-200",
      icon: <XCircle className="w-5 h-5 text-red-600" />,
      title: "Verification rejected",
      message: profile.rejection_reason ?? "Your verification was rejected. Please resubmit your documents.",
    },
  };

  const config = bannerConfig[profile.verification_status];

  return (
    <div className={`border rounded-2xl p-5 mb-6 ${config.bg}`}>
      <div className="flex items-start gap-3 mb-4">
        {config.icon}
        <div>
          <h3 className="font-semibold text-slate-900 text-sm">{config.title}</h3>
          <p className="text-sm text-slate-600 mt-0.5">{config.message}</p>
        </div>
      </div>

      {(profile.verification_status === "unverified" || profile.verification_status === "rejected") && (
        <div className="space-y-3">
          {/* Document uploads */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* ID Copy */}
            <div
              onClick={() => !uploadingId && idRef.current?.click()}
              className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                profile.id_copy_uploaded
                  ? "bg-emerald-50 border-emerald-200"
                  : "bg-white border-slate-200 hover:border-slate-300"
              }`}
            >
              <input
                ref={idRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload(file, "id-copy", setUploadingId);
                }}
              />
              {uploadingId ? (
                <Loader2 className="w-4 h-4 animate-spin text-slate-400 flex-shrink-0" />
              ) : profile.id_copy_uploaded ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              ) : (
                <ShieldCheck className="w-4 h-4 text-slate-400 flex-shrink-0" />
              )}
              <div>
                <p className="text-xs font-semibold text-slate-700">ID Copy</p>
                <p className="text-xs text-slate-400">
                  {profile.id_copy_uploaded ? "Uploaded ✓" : "Click to upload"}
                </p>
              </div>
            </div>

            {/* Proof of Address */}
            <div
              onClick={() => !uploadingPoa && poaRef.current?.click()}
              className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                profile.proof_of_address_uploaded
                  ? "bg-emerald-50 border-emerald-200"
                  : "bg-white border-slate-200 hover:border-slate-300"
              }`}
            >
              <input
                ref={poaRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload(file, "proof-of-address", setUploadingPoa);
                }}
              />
              {uploadingPoa ? (
                <Loader2 className="w-4 h-4 animate-spin text-slate-400 flex-shrink-0" />
              ) : profile.proof_of_address_uploaded ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              ) : (
                <ShieldCheck className="w-4 h-4 text-slate-400 flex-shrink-0" />
              )}
              <div>
                <p className="text-xs font-semibold text-slate-700">Proof of Address</p>
                <p className="text-xs text-slate-400">
                  {profile.proof_of_address_uploaded ? "Uploaded ✓" : "Click to upload"}
                </p>
              </div>
            </div>
          </div>

          {/* Submit button */}
          <Button
            className="w-full rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
            onClick={handleSubmitVerification}
            disabled={
              submitting ||
              !profile.id_copy_uploaded ||
              !profile.proof_of_address_uploaded
            }
          >
            {submitting ? (
              <><Loader2 className="w-4 h-4 animate-spin mr-2" />Submitting...</>
            ) : (
              "Submit for verification"
            )}
          </Button>

          {(!profile.id_copy_uploaded || !profile.proof_of_address_uploaded) && (
            <p className="text-xs text-slate-400 text-center">
              Upload both documents to submit for verification
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function OwnershipDocUploader({ accommodationId, onSuccess }: { accommodationId: number; onSuccess: () => void }) {
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await accommodationsApi.uploadOwnershipDoc(accommodationId, file);
      setUploaded(true);
      setTimeout(onSuccess, 1000);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      onClick={() => !uploading && fileRef.current?.click()}
      className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
        uploaded ? "border-emerald-300 bg-emerald-50" :
        uploading ? "border-slate-200 bg-slate-50 cursor-not-allowed" :
        "border-slate-300 hover:border-slate-400 hover:bg-slate-50"
      }`}
    >
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
        disabled={uploading}
      />
      {uploading ? (
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500">Uploading...</p>
        </div>
      ) : uploaded ? (
        <div className="flex flex-col items-center gap-2">
          <CheckCircle className="h-10 w-10 text-emerald-500" />
          <p className="text-sm font-semibold text-emerald-700">Uploaded successfully</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <div className="h-12 w-12 rounded-xl bg-slate-100 flex items-center justify-center">
            <FileText className="h-6 w-6 text-slate-400" />
          </div>
          <p className="text-sm font-semibold text-slate-700">Click to upload</p>
          <p className="text-xs text-slate-400">Title deed, lease or mandate · PDF, JPEG, PNG · Max 10MB</p>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user, loading, isLandlord } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [managingImages, setManagingImages] = useState<Listing | null>(null);
  const [uploadingOwnershipFor, setUploadingOwnershipFor] = useState<Listing | null>(null);
  

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/dashboard");
    if (!loading && user && !isLandlord) router.push("/");
  }, [user, loading]);

  const { data: listings = [], isLoading } = useQuery({
    queryKey: ["my-listings"],
    queryFn: fetchMyListings,
    enabled: !!user && isLandlord,
  });

  const handleCreateSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["my-listings"] });
    toast.success("Listing submitted for review! It will go live once approved by a moderator.");
  };

  const { data: profile, refetch: refetchProfile } = useQuery({
  queryKey: ["landlord-profile"],
  queryFn: fetchMyProfile,
  enabled: !!user && isLandlord,
});

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      </PageLayout>
    );
  }

  if (!user || !isLandlord) return null;

  return (
    <PageLayout>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

        {selectedListing ? (
          <AnalyticsPanel listing={selectedListing} onBack={() => setSelectedListing(null)} />
        ) : (
          <>
            {/* Verification banner */}
            {profile && profile.verification_status !== "verified" && (
              <VerificationBanner
                profile={profile}
                onUploadSuccess={refetchProfile}
              />
            )}
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">My Listings</h1>
                <p className="text-sm text-slate-500 mt-0.5">
                  Manage your properties and view performance analytics
                </p>
              </div>
              <Button
                onClick={() => {
                  if (profile && profile.verification_status !== "verified") {
                    toast.error("Complete your verification before adding listings.");
                    return;
                  }
                  setCreateOpen(true);
                }}
                className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl gap-2"
              >
                <Plus className="w-4 h-4" />
                Add listing
              </Button>
            </div>

            {/* Listings */}
            {isLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-28 w-full rounded-2xl" />
                ))}
              </div>
            ) : listings.length === 0 ? (
              <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
                  <Home className="w-7 h-7 text-slate-300" />
                </div>
                <h3 className="font-semibold text-slate-900 mb-1">No listings yet</h3>
                <p className="text-sm text-slate-500 mb-6 max-w-xs mx-auto">
                  Add your first property to start reaching students near campus.
                </p>
                <Button
                
                  onClick={() => {
                  if (profile && profile.verification_status !== "verified") {
                    toast.error("Complete your verification before adding listings.");
                    return;
                  }
                  setCreateOpen(true);
                  }}
                  className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Add your first listing
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                {listings.map((listing) => {
                  const statusCfg = STATUS_CONFIG[listing.status] ?? STATUS_CONFIG.pending;
                  const StatusIcon = statusCfg.icon;
                  return (
                    <div
                      key={listing.id}
                      className="bg-white border border-slate-200 rounded-2xl p-5 flex items-center gap-4 hover:shadow-sm transition-shadow"
                    >
                      {/* Icon */}
                      <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0">
                        <Home className="w-5 h-5 text-slate-400" />
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-slate-900 text-sm">{listing.title}</h3>
                          <Badge className={`text-xs border rounded-full px-2 py-0.5 ${statusCfg.color}`}>
                            <StatusIcon className="w-3 h-3 mr-1" />
                            {statusCfg.label}
                          </Badge>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                          <MapPin className="w-3 h-3" />{listing.address}
                        </p>
                        <div className="flex items-center gap-4 mt-2">
                          <span className="text-xs text-slate-600 font-medium">
                            R{listing.price_min.toLocaleString()} – R{listing.price_max.toLocaleString()}/mo
                          </span>
                          {listing.average_rating && (
                            <span className="text-xs text-slate-500 flex items-center gap-1">
                              <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                              {listing.average_rating.toFixed(1)} ({listing.total_reviews})
                            </span>
                          )}
                          <span className="text-xs text-slate-400">
                            {new Date(listing.created_at).toLocaleDateString("en-ZA", { month: "short", year: "numeric" })}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-xl text-xs gap-1.5"
                          onClick={() => router.push(`/listings/${listing.id}`)}
                        >
                          <Eye className="w-3.5 h-3.5" />
                          View
                        </Button>

                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-xl text-xs gap-1.5"
                          onClick={() => setManagingImages(listing)}
                        >
                          <ImagePlus className="w-3.5 h-3.5" />
                          Photos
                        </Button>
                        {!listing.ownership_doc_url && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="rounded-xl text-xs gap-1.5 border-amber-200 text-amber-700 hover:bg-amber-50"
                            onClick={() => setUploadingOwnershipFor(listing)}
                          >
                            <FileText className="w-3.5 h-3.5" />
                            Add ownership doc
                          </Button>
                        )}
                        {listing.status === "approved" && (
                          <Button
                            size="sm"
                            className="rounded-xl text-xs gap-1.5 bg-slate-900 hover:bg-slate-800 text-white"
                            onClick={() => setSelectedListing(listing)}
                          >
                            <BarChart2 className="w-3.5 h-3.5" />
                            Analytics
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      <CreateListingModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={handleCreateSuccess}
      />

      {/* Manage images dialog */}
      <Dialog open={!!managingImages} onOpenChange={() => setManagingImages(null)}>
        <DialogContent className="rounded-2xl max-w-lg bg-white">
          <DialogHeader>
            <DialogTitle>Manage photos</DialogTitle>
            <DialogDescription>
              {managingImages?.title}
            </DialogDescription>
          </DialogHeader>
          {managingImages && (
            <ImageUploader
              accommodationId={managingImages.id}
              showDoneButton={false}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Ownership doc dialog */}
      <Dialog open={!!uploadingOwnershipFor} onOpenChange={() => setUploadingOwnershipFor(null)}>
        <DialogContent className="rounded-2xl max-w-md bg-white">
          <DialogHeader>
            <DialogTitle>Upload ownership document</DialogTitle>
            <DialogDescription>{uploadingOwnershipFor?.title}</DialogDescription>
          </DialogHeader>
          {uploadingOwnershipFor && (
            <OwnershipDocUploader
              accommodationId={uploadingOwnershipFor.id}
              onSuccess={() => {
                queryClient.invalidateQueries({ queryKey: ["my-listings"] });
                setUploadingOwnershipFor(null);
                toast.success("Ownership document uploaded. Your listing will now appear in the moderation queue.");
              }}
            />
          )}
        </DialogContent>
      </Dialog>

    </PageLayout>
  );
}