"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import PageLayout from "@/components/page-layout";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  MapPin,
  List,
  Map,
  Star,
  Wifi,
  ShieldCheck,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
  Lock,
  TrendingUp,
  Eye,
  Loader2,
} from "lucide-react";
import dynamic from "next/dynamic";


// Leaflet must be dynamically imported (no SSR)
const SearchMap = dynamic(() => import("@/components/search-map"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[600px] rounded-2xl bg-slate-100 animate-pulse flex items-center justify-center">
      <MapPin className="w-8 h-8 text-slate-300" />
    </div>
  ),
});

// ─── Types ────────────────────────────────────────────────────────────────────

interface University {
  id: number;
  name: string;
  domain: string;
  province: string;
}

interface Accommodation {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  status: string;
  average_rating?: number;
  review_count?: number;
  sentiment_summary?: "positive" | "neutral" | "negative";
  cover_image?: string | null; 
  distance_km?: number;
  lat?: number;   // ← add
  lng?: number;   // ← add
}

interface SearchResponse {
  items: Accommodation[];
  total: number;
  page: number;
  page_size: number;
}

interface MapItem {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  average_rating?: number;
  lat?: number;   // ← add
  lng?: number;   // ← add
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 10;
const BLUR_LAST_N = 3; // last N cards on page 1 are blurred for guests

const SENTIMENT_CONFIG = {
  positive: { label: "Highly Rated", color: "bg-emerald-100 text-emerald-700 border-emerald-200" },
  neutral:  { label: "Mixed Reviews", color: "bg-amber-100 text-amber-700 border-amber-200" },
  negative: { label: "Poor Reviews", color: "bg-red-100 text-red-700 border-red-200" },
};

// ─── Fetch helpers ────────────────────────────────────────────────────────────

async function fetchUniversities(): Promise<University[]> {
  const { data } = await api.get("/api/v1/universities/");
  return data;
}

async function fetchAccommodations(params: {
  university_id?: number;
  radius_km?: number;
  price_min?: number;
  price_max?: number;
  min_rating?: number;
  gender_policy?: string;
  funding_type?: string;
  page: number;
}): Promise<SearchResponse> {
  const query = new URLSearchParams();
  if (params.university_id) query.set("university_id", String(params.university_id));
  if (params.radius_km)    query.set("radius_km", String(params.radius_km));
  if (params.price_min)    query.set("price_min", String(params.price_min));
  if (params.price_max)    query.set("price_max", String(params.price_max));
  if (params.min_rating)   query.set("min_rating", String(params.min_rating));
  if (params.gender_policy) query.set("gender_policy", params.gender_policy);  // ← add
  if (params.funding_type)  query.set("funding_type", params.funding_type);    // ← add
  query.set("page", String(params.page));
  query.set("page_size", String(PAGE_SIZE));

  const { data } = await api.get(`/api/v1/accommodations/search?${query.toString()}`);
  return data;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ListingCardSkeleton() {
  return (
    <div className="rounded-2xl overflow-hidden border border-slate-200 bg-white">
      <Skeleton className="w-full h-52" />
      <div className="p-4 space-y-3">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
        <Skeleton className="h-4 w-1/3" />
      </div>
    </div>
  );
}

function StarRating({ rating, count }: { rating?: number; count?: number }) {
  const r = rating ?? 0;
  return (
    <div className="flex items-center gap-1.5">
      <Star
        className={`w-4 h-4 ${r > 0 ? "fill-amber-400 text-amber-400" : "text-slate-300"}`}
      />
      <span className="text-sm font-semibold text-slate-700">
        {r > 0 ? r.toFixed(1) : "No ratings"}
      </span>
      {count !== undefined && count > 0 && (
        <span className="text-sm text-slate-400">({count})</span>
      )}
    </div>
  );
}

function ListingCard({
  item,
  blurred,
  index,
}: {
  item: Accommodation;
  blurred: boolean;
  index: number;
}) {
  const router = useRouter();
  const sentiment = item.sentiment_summary
    ? SENTIMENT_CONFIG[item.sentiment_summary]
    : null;

  const imageUrl = item.cover_image ?? null;

  const handleClick = () => {
    if (!blurred) router.push(`/listings/${item.id}`);
  };

  return (
    <div
      className={`group rounded-2xl overflow-hidden border border-slate-200 bg-white transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 ${
        blurred ? "cursor-default" : "cursor-pointer"
      }`}
      onClick={handleClick}
    >
      {/* Image */}
      <div className="relative w-full h-52 overflow-hidden bg-slate-100">
        {item.cover_image ? (
          <img
            src={imageUrl!}
            alt={item.title}
            className={`w-full h-full object-cover transition-transform duration-500 group-hover:scale-105 ${
              blurred ? "blur-sm scale-105" : ""
            }`}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
            <MapPin className="w-10 h-10 text-slate-300" />
          </div>
        )}

        {/* Distance badge */}
        {item.distance_km !== undefined && item.distance_km !== null && Number(item.distance_km) > 0 && (
          <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-sm text-xs font-medium text-slate-700 px-2.5 py-1 rounded-full border border-white/60 shadow-sm">
            {Number(item.distance_km) < 1
              ? `${Math.round(Number(item.distance_km) * 1000)}m away`
              : `${Number(item.distance_km).toFixed(1)}km away`}
          </div>
        )}

        {/* Sentiment badge */}
        {sentiment && !blurred && (
          <div
            className={`absolute top-3 right-3 text-xs font-medium px-2.5 py-1 rounded-full border ${sentiment.color}`}
          >
            {sentiment.label}
          </div>
        )}

        {/* Blur overlay */}
        {blurred && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/40 backdrop-blur-md">
            <Lock className="w-7 h-7 text-white mb-2" />
            <p className="text-white text-sm font-semibold">Sign in to view</p>
          </div>
        )}
      </div>

      {/* Content */}
      <div className={`p-4 space-y-2 ${blurred ? "blur-[2px] select-none" : ""}`}>
        <h3 className="font-semibold text-slate-900 text-base leading-snug line-clamp-1 group-hover:text-slate-700 transition-colors">
          {blurred ? "••••••••••••••" : item.title}
        </h3>
        <div className="flex items-center gap-1.5 text-slate-500 text-sm">
          <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="line-clamp-1">
            {blurred ? "•••••••••••••••••" : item.address}
          </span>
        </div>

        <div className="flex items-center justify-between pt-1">
          <StarRating rating={item.average_rating} count={item.review_count} />
          <div className="text-right">
            <span className="text-sm font-bold text-slate-900">
              {blurred ? "R••••" : `R${item.price_min.toLocaleString()}`}
            </span>
            {item.price_max > item.price_min && !blurred && (
              <span className="text-xs text-slate-400">
                {" "}– R{item.price_max.toLocaleString()}
              </span>
            )}
            <div className="text-xs text-slate-400">per month</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function GuestGateBanner({ returnUrl }: { returnUrl: string }) {
  return (
    <div className="col-span-full mt-4">
      <div className="relative rounded-2xl overflow-hidden border border-slate-200 bg-gradient-to-br from-slate-900 to-slate-800 p-8 text-center shadow-xl">
        {/* Decorative background */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 left-1/4 w-64 h-64 bg-blue-400 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-violet-400 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-white/10 border border-white/20 mb-4">
            <Lock className="w-6 h-6 text-white" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">
            Sign in to see more listings
          </h3>
          <p className="text-slate-300 text-sm mb-6 max-w-md mx-auto">
            You're viewing a preview. Create a free account to unlock all listings,
            detailed NLP insights, and reviews.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button asChild size="lg" className="bg-white text-slate-900 hover:bg-slate-100 font-semibold rounded-xl">
              <Link href={`/register?redirect=${encodeURIComponent(returnUrl)}`}>
                Create free account
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="border-white/30 text-white hover:bg-white/10 rounded-xl">
              <Link href={`/login?redirect=${encodeURIComponent(returnUrl)}`}>
                Sign in
              </Link>
            </Button>
          </div>

          <div className="mt-6 flex items-center justify-center gap-6 text-xs text-slate-400">
            <span className="flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5" /> Free to join</span>
            <span className="flex items-center gap-1.5"><TrendingUp className="w-3.5 h-3.5" /> NLP insights</span>
            <span className="flex items-center gap-1.5"><Eye className="w-3.5 h-3.5" /> Full listings</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterBar({
  universities,
  filters,
  onChange,
  onApply,
}: {
  universities: University[];
  filters: Filters;
  onChange: (f: Partial<Filters>) => void;
  onApply: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm">
      {/* Always-visible top bar */}
      <div className="flex items-center gap-3 p-3 flex-wrap">
        {/* University */}
        <Select
          value={filters.university_id ? String(filters.university_id) : "all"}
          onValueChange={(v) =>
            onChange({ university_id: v === "all" ? undefined : Number(v) })
          }
        >
          <SelectTrigger className="w-52 rounded-xl border-slate-200 h-10 text-sm">
            <SelectValue placeholder="All universities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All universities</SelectItem>
            {universities.map((u) => (
              <SelectItem key={u.id} value={String(u.id)}>
                {u.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Radius */}
        <Select
          value={String(filters.radius_km)}
          onValueChange={(v) => onChange({ radius_km: Number(v) })}
        >
          <SelectTrigger className="w-36 rounded-xl border-slate-200 h-10 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[1, 2, 3, 5, 10, 20].map((r) => (
              <SelectItem key={r} value={String(r)}>
                Within {r}km
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* More filters toggle */}
        <Button
          variant="outline"
          size="sm"
          className="rounded-xl h-10 gap-2 ml-auto border-slate-200"
          onClick={() => setOpen((o) => !o)}
        >
          <SlidersHorizontal className="w-4 h-4" />
          More filters
          {(filters.price_min > 0 || filters.price_max < 15000 || filters.min_rating > 0 || 
            filters.gender_policy !== undefined || filters.funding_type !== undefined) && (
            <span className="w-2 h-2 rounded-full bg-blue-500" />
          )}
        </Button>

        <Button
          size="sm"
          className="rounded-xl h-10 bg-slate-900 hover:bg-slate-800 text-white"
          onClick={onApply}
        >
          Search
        </Button>
      </div>

      {/* Expandable filters */}
      {open && (
        <div className="border-t border-slate-100 p-4 grid grid-cols-1 sm:grid-cols-2 gap-6">

          {/* Price range */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 block">
              Price range (per month)
            </label>
            <div className="px-1">
              <Slider
                min={0}
                max={15000}
                step={500}
                value={[filters.price_min, filters.price_max]}
                onValueChange={([min, max]) =>
                  onChange({ price_min: min, price_max: max })
                }
                className="mb-2"
              />
              <div className="flex justify-between text-sm text-slate-600 font-medium">
                <span>R{filters.price_min.toLocaleString()}</span>
                <span>
                  {filters.price_max >= 15000
                    ? "R15,000+"
                    : `R${filters.price_max.toLocaleString()}`}
                </span>
              </div>
            </div>
          </div>

          {/* Min rating */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 block">
              Minimum rating
            </label>
            <div className="flex gap-2 flex-wrap">
              {[0, 3, 3.5, 4, 4.5].map((r) => (
                <button
                  key={r}
                  onClick={() => onChange({ min_rating: r })}
                  className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                    filters.min_rating === r
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
                  }`}
                >
                  {r === 0 ? (
                    "Any"
                  ) : (
                    <>
                      <Star className="w-3 h-3 fill-current" />
                      {r}+
                    </>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Gender policy */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 block">
              Gender policy
            </label>
            <div className="flex gap-2 flex-wrap">
              {[
                { value: undefined, label: "Any" },
                { value: "male", label: "Male only" },
                { value: "female", label: "Female only" },
              ].map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => onChange({ gender_policy: opt.value as any })}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                    filters.gender_policy === opt.value
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Funding type */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 block">
              Funding type
            </label>
            <div className="flex gap-2 flex-wrap">
              {[
                { value: undefined, label: "Any" },
                { value: "self_funded", label: "Self-funded" },
                { value: "bursary", label: "Bursary/NSFAS" },
              ].map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => onChange({ funding_type: opt.value as any })}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                    filters.funding_type === opt.value
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}

// ─── Filters state type ───────────────────────────────────────────────────────

interface Filters {
  university_id?: number;
  radius_km: number;
  price_min: number;
  price_max: number;
  min_rating: number;
  gender_policy?: "male" | "female";   // ← add
  funding_type?: "self_funded" | "bursary";  // ← add
}

// ─── Main Page ─────────────────────────────────────────────────────────────────
function SearchPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isStudent, isLandlord } = useAuth();
  const isGuest = !user;


  // Initialise filters from URL query params
  const [filters, setFilters] = useState<Filters>({
    university_id: searchParams.get("university_id")
      ? Number(searchParams.get("university_id"))
      : undefined,
    radius_km: Number(searchParams.get("radius_km") ?? 5),
    price_min: Number(searchParams.get("price_min") ?? 0),
    price_max: Number(searchParams.get("price_max") ?? 15000),
    min_rating: Number(searchParams.get("min_rating") ?? 0),
    gender_policy: (searchParams.get("gender_policy") as "male" | "female") ?? undefined,
    funding_type: (searchParams.get("funding_type") as "self_funded" | "bursary") ?? undefined,
  });

  // Applied filters — only update when user clicks Search
  const [appliedFilters, setAppliedFilters] = useState<Filters>({
    university_id: searchParams.get("university_id")
      ? Number(searchParams.get("university_id"))
      : undefined,
    radius_km: Number(searchParams.get("radius_km") ?? 5),
    price_min: Number(searchParams.get("price_min") ?? 0),
    price_max: Number(searchParams.get("price_max") ?? 15000),
    min_rating: Number(searchParams.get("min_rating") ?? 0),
    gender_policy: (searchParams.get("gender_policy") as "male" | "female") ?? undefined,
    funding_type: (searchParams.get("funding_type") as "self_funded" | "bursary") ?? undefined,
  });
  const [page, setPage] = useState(
    Number(searchParams.get("page") ?? 1)
  );
  const [viewMode, setViewMode] = useState<"grid" | "map">("grid");

  const currentUrl =
    typeof window !== "undefined" ? window.location.pathname + window.location.search : "/search";

  // ── Universities ──
  const { data: universities = [] } = useQuery<University[]>({
    queryKey: ["universities"],
    queryFn: fetchUniversities,
    staleTime: Infinity,
  });

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    const params = new URLSearchParams(window.location.search);
    params.set("page", String(newPage));
    router.replace(`/search?${params.toString()}`, { scroll: false });
  };

  // ── Accommodations ──
  const {
  data: results,
  isLoading,
  isError,
  isFetching,
} = useQuery<SearchResponse>({
  queryKey: ["accommodations-search", appliedFilters, page],
  queryFn: () => fetchAccommodations({ ...appliedFilters, page }),
  placeholderData: (previousData) => previousData,
});

  // Redirect guests to login if they try to access page 2+
  useEffect(() => {
    if (isGuest && page > 1) {
      router.push(`/login?redirect=${encodeURIComponent(currentUrl)}`);
    }
  }, [isGuest, page]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [page]);

  const items = results?.items ?? [];
  const total = results?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Which cards on page 1 are blurred for guests
  const getCardBlurred = (index: number) => {
    if (!isGuest) return false;
    if (page > 1) return true; // shouldn't reach here due to redirect
    return index >= PAGE_SIZE - BLUR_LAST_N;
  };

  const handleApplyFilters = () => {
    setAppliedFilters(filters);
    setPage(1);

    const params = new URLSearchParams();
    if (filters.university_id) params.set("university_id", String(filters.university_id));
    if (filters.radius_km !== 5) params.set("radius_km", String(filters.radius_km));
    if (filters.price_min > 0) params.set("price_min", String(filters.price_min));
    if (filters.price_max < 15000) params.set("price_max", String(filters.price_max));
    if (filters.min_rating > 0) params.set("min_rating", String(filters.min_rating));
    if (filters.gender_policy) params.set("gender_policy", filters.gender_policy);
    if (filters.funding_type) params.set("funding_type", filters.funding_type);
    params.set("page", "1");

    router.replace(`/search?${params.toString()}`, { scroll: false });
  };

  return (
    <PageLayout>
    <div className="min-h-screen bg-slate-50">
      {/* ── Header strip ── */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <FilterBar
            universities={universities}
            filters={filters}
            onChange={(partial) => setFilters((f) => ({ ...f, ...partial }))}
            onApply={handleApplyFilters}
          />
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ── Results header ── */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              {isLoading ? (
                <Skeleton className="h-7 w-48 inline-block" />
              ) : (
                <>
                  {total.toLocaleString()} listing{total !== 1 ? "s" : ""} found
                </>
              )}
            </h1>
            {appliedFilters.university_id && universities.length > 0 && (
              <p className="text-sm text-slate-500 mt-0.5">
                Near{" "}
                {
                  universities.find((u) => u.id === appliedFilters.university_id)
                    ?.name
                }
                {" "}· within {appliedFilters.radius_km}km
              </p>
            )}
          </div>

          {/* View toggle */}
          <div className="flex items-center bg-slate-100 rounded-xl p-1 gap-1">
            <button
              onClick={() => setViewMode("grid")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                viewMode === "grid"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <List className="w-4 h-4" />
              List
            </button>
            <button
              onClick={() => setViewMode("map")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                viewMode === "map"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <Map className="w-4 h-4" />
              Map
            </button>
          </div>
        </div>

        {/* ── Error state ── */}
        {isError && (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-red-50 border border-red-100 mb-4">
              <MapPin className="w-7 h-7 text-red-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 mb-2">
              Something went wrong
            </h3>
            <p className="text-slate-500 mb-4">
              We couldn't load listings right now. Please try again.
            </p>
            <Button onClick={handleApplyFilters} variant="outline" className="rounded-xl">
              Retry
            </Button>
          </div>
        )}

        {/* ── Map view ── */}
        {viewMode === "map" && !isError && (
          <SearchMap
            items={items}
            isLoading={isLoading}
            onMarkerClick={(id) => router.push(`/listings/${id}`)}
          />
        )}

        {/* ── Grid view ── */}
        {viewMode === "grid" && !isError && (
          <>
            {isLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {Array.from({ length: 6 }).map((_, i) => (
                  <ListingCardSkeleton key={i} />
                ))}
              </div>
            ) : items.length === 0 ? (
              <div className="text-center py-24">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-slate-100 border border-slate-200 mb-4">
                  <MapPin className="w-7 h-7 text-slate-400" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">
                  No listings found
                </h3>
                <p className="text-slate-500 mb-4">
                  Try increasing the search radius or adjusting your filters.
                </p>
                <Button
                  onClick={() =>
                    setFilters((f) => ({ ...f, radius_km: 20 }))
                  }
                  variant="outline"
                  className="rounded-xl"
                >
                  Expand to 20km
                </Button>
              </div>
            ) : (
              <>
                <div
                  className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 transition-opacity duration-200 ${
                    isFetching ? "opacity-60" : "opacity-100"
                  }`}
                >
                  {items.map((item, index) => (
                    <ListingCard
                      key={item.id}
                      item={item}
                      blurred={getCardBlurred(index)}
                      index={index}
                    />
                  ))}

                  {/* Guest gate banner after blurred cards */}
                  {isGuest && page === 1 && items.length >= PAGE_SIZE - BLUR_LAST_N && (
                    <GuestGateBanner returnUrl={currentUrl} />
                  )}
                </div>

                {/* ── Pagination ── */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-10">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(Math.max(1, page - 1))}
                      disabled={page === 1}
                      className="rounded-xl gap-1.5"
                    >
                      <ChevronLeft className="w-4 h-4" />
                      Previous
                    </Button>

                    <div className="flex items-center gap-1">
                      {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                        const pageNum = i + 1;
                        return (
                          <button
                            key={pageNum}
                            onClick={() => {
                              if (isGuest && pageNum > 1) {
                                router.push(
                                  `/login?redirect=${encodeURIComponent(currentUrl)}`
                                );
                                return;
                              }
                              handlePageChange(pageNum);
                            }}
                            className={`w-9 h-9 rounded-lg text-sm font-medium transition-all ${
                              page === pageNum
                                ? "bg-slate-900 text-white"
                                : isGuest && pageNum > 1
                                ? "text-slate-300 cursor-not-allowed"
                                : "text-slate-600 hover:bg-slate-100"
                            }`}
                          >
                            {isGuest && pageNum > 1 ? (
                              <Lock className="w-3 h-3 mx-auto" />
                            ) : (
                              pageNum
                            )}
                          </button>
                        );
                      })}
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (isGuest) {
                          router.push(
                            `/login?redirect=${encodeURIComponent(currentUrl)}`
                          );
                          return;
                        }
                        handlePageChange(Math.min(totalPages, page + 1));
                      }}
                      disabled={page === totalPages}
                      className="rounded-xl gap-1.5"
                    >
                      Next
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
    </PageLayout>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    }>
      <SearchPageInner />
    </Suspense>
  );
}