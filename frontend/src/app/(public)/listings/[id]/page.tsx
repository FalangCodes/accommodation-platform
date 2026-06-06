"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import PageLayout from "@/components/page-layout";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MapPin, Star, Wifi, ShieldCheck, Zap, Wrench, Volume2,
  DollarSign, User, ChevronLeft, Lock, MessageSquare,
  TrendingUp, Home, Calendar
} from "lucide-react";
import dynamic from "next/dynamic";

const DetailMap = dynamic(() => import("@/components/detail-map"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-64 rounded-2xl bg-slate-100 animate-pulse" />
  ),
});

// ─── Types ────────────────────────────────────────────────────────────────────

interface ListingDetail {
  id: number;
  landlord_id: number;
  landlord_name: string;
  title: string;
  description: string;
  address: string;
  price_min: number;
  price_max: number;
  status: string;
  created_at: string;
  lat: number;
  lng: number;
  images: { id: number; url: string; order: number }[];
  total_reviews: number;
  average_rating: number | null;
  dominant_sentiment: "positive" | "neutral" | "negative" | null;
  sentiment_distribution: { positive: number; neutral: number; negative: number };
  top_aspects: Record<string, number>;
}

interface Review {
  id: number;
  rating: number;
  body: string;
  created_at: string;
  student_id: number;
  nlp?: {
    sentiment: string;
    sentiment_score: number;
    aspects: Record<string, number>;
    spam_flag: boolean;
  };
  reply?: {
    id: number;
    body: string;
    created_at: string;
  };
}

// ─── Constants ────────────────────────────────────────────────────────────────

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

const SENTIMENT_STYLES = {
  positive: "bg-emerald-100 text-emerald-700 border-emerald-200",
  neutral:  "bg-amber-100 text-amber-700 border-amber-200",
  negative: "bg-red-100 text-red-700 border-red-200",
};

const SENTIMENT_LABELS = {
  positive: "Positive",
  neutral: "Mixed",
  negative: "Negative",
};

// ─── Fetch helpers ────────────────────────────────────────────────────────────

async function fetchListing(id: string): Promise<ListingDetail> {
  const { data } = await api.get(`/api/v1/accommodations/${id}`);
  return data;
}

async function fetchReviews(id: string): Promise<Review[]> {
  const { data } = await api.get(`/api/v1/reviews/accommodation/${id}`);
  return data;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StarRating({ rating, size = "md" }: { rating: number; size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "w-3 h-3", md: "w-4 h-4", lg: "w-5 h-5" };
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={`${sizes[size]} ${i <= Math.round(rating) ? "fill-amber-400 text-amber-400" : "text-slate-200 fill-slate-200"}`}
        />
      ))}
    </div>
  );
}

function AspectBar({ label, score, icon: Icon }: { label: string; score: number; icon: any }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5 w-28 flex-shrink-0">
        <Icon className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-xs text-slate-600 font-medium">{label}</span>
      </div>
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-semibold text-slate-700 w-8 text-right">{pct}%</span>
    </div>
  );
}

function ReviewCard({ review, blurred }: { review: Review; blurred: boolean }) {
  const sentiment = review.nlp?.sentiment?.toLowerCase() as keyof typeof SENTIMENT_STYLES | undefined;

  return (
    <div className={`bg-white border border-slate-200 rounded-2xl p-5 space-y-3 ${blurred ? "blur-sm select-none pointer-events-none" : ""}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center">
            <User className="w-4 h-4 text-slate-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">
              {blurred ? "••••••••" : "Student"}
            </p>
            <p className="text-xs text-slate-400">
              {blurred ? "••••••" : new Date(review.created_at).toLocaleDateString("en-ZA", { month: "short", year: "numeric" })}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StarRating rating={review.rating} size="sm" />
          {sentiment && !blurred && (
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${SENTIMENT_STYLES[sentiment]}`}>
              {SENTIMENT_LABELS[sentiment]}
            </span>
          )}
        </div>
      </div>

      <p className="text-sm text-slate-600 leading-relaxed">
        {blurred ? "•".repeat(120) : review.body}
      </p>

      {/* Aspect tags */}
      {!blurred && review.nlp?.aspects && Object.keys(review.nlp.aspects).length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {Object.entries(review.nlp.aspects)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 4)
            .map(([aspect, score]) => (
              <span
                key={aspect}
                className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200"
              >
                {ASPECT_LABELS[aspect] ?? aspect}
              </span>
            ))}
        </div>
      )}

      {/* Landlord reply */}
      {!blurred && review.reply && (
        <div className="mt-3 pl-4 border-l-2 border-slate-200 bg-slate-50 rounded-r-xl p-3">
          <p className="text-xs font-semibold text-slate-500 mb-1">Landlord response</p>
          <p className="text-sm text-slate-600">{review.reply.body}</p>
        </div>
      )}
    </div>
  );
}

function PhotoGrid({ images }: { images: { url: string }[] }) {
  const [lightbox, setLightbox] = useState<number | null>(null);

  // Placeholder grid when no images
  const slots = images.length > 0 ? images : Array(5).fill(null);

  return (
    <>
      <div className="grid grid-cols-4 grid-rows-2 gap-2 h-[420px] rounded-2xl overflow-hidden">
        {/* Main large image */}
        <div
          className="col-span-2 row-span-2 relative cursor-pointer group bg-slate-100"
          onClick={() => images.length > 0 && setLightbox(0)}
        >
          {images[0] ? (
            <img src={images[0].url} alt="Main" className="w-full h-full object-cover group-hover:brightness-95 transition" />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
              <Home className="w-16 h-16 text-slate-300" />
            </div>
          )}
        </div>

        {/* 4 smaller images */}
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="relative cursor-pointer group bg-slate-100"
            onClick={() => images[i] && setLightbox(i)}
          >
            {images[i] ? (
              <>
                <img src={images[i].url} alt={`Photo ${i + 1}`} className="w-full h-full object-cover group-hover:brightness-95 transition" />
                {i === 3 && images.length > 5 && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <span className="text-white font-semibold text-sm">+{images.length - 5} more</span>
                  </div>
                )}
              </>
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
                <Home className="w-8 h-8 text-slate-200" />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Lightbox */}
      {lightbox !== null && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={() => setLightbox(null)}
        >
          <img
            src={images[lightbox].url}
            alt="Full size"
            className="max-w-full max-h-full rounded-xl object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          <button className="absolute top-4 right-4 text-white text-2xl font-bold" onClick={() => setLightbox(null)}>✕</button>
        </div>
      )}
    </>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const isGuest = !user;
  const [activeTab, setActiveTab] = useState<"details" | "reviews" | "location">("details");

  const { data: listing, isLoading: listingLoading, isError } = useQuery({
    queryKey: ["listing", id],
    queryFn: () => fetchListing(id),
  });

  const { data: reviews = [], isLoading: reviewsLoading } = useQuery({
    queryKey: ["reviews", id],
    queryFn: () => fetchReviews(id),
    enabled: activeTab === "reviews",
  });

  if (isError) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Listing not found</h2>
          <Button onClick={() => router.push("/search")} variant="outline" className="rounded-xl">
            Back to search
          </Button>
        </div>
      </div>
    );
  }

  return (
    <PageLayout>
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        {/* Back button */}
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-slate-500 hover:text-slate-800 text-sm font-medium mb-6 transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
          Back to results
        </button>

        {/* Title row */}
        {listingLoading ? (
          <div className="space-y-2 mb-6">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-5 w-1/3" />
          </div>
        ) : (
          <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">{listing!.title}</h1>
              <div className="flex items-center gap-2 mt-1 text-slate-500 text-sm">
                <MapPin className="w-4 h-4" />
                <span>{listing!.address}</span>
                {listing!.average_rating && (
                  <>
                    <span className="text-slate-300">·</span>
                    <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                    <span className="font-semibold text-slate-700">{listing!.average_rating.toFixed(1)}</span>
                    <span className="text-slate-400">({listing!.total_reviews} reviews)</span>
                  </>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-slate-900">
                R{listing!.price_min.toLocaleString()}
                {listing!.price_max > listing!.price_min && (
                  <span className="text-lg font-normal text-slate-400"> – R{listing!.price_max.toLocaleString()}</span>
                )}
              </div>
              <div className="text-sm text-slate-400">per month</div>
            </div>
          </div>
        )}

        {/* Photo grid */}
        {listingLoading ? (
          <Skeleton className="w-full h-[420px] rounded-2xl mb-8" />
        ) : (
          <div className="mb-8">
            <PhotoGrid images={listing!.images} />
          </div>
        )}

        {/* Main content grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

          {/* Left — tabs */}
          <div className="lg:col-span-2 space-y-6">

            {/* Tab bar */}
            <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
              {(["details", "reviews", "location"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
                    activeTab === tab
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {tab}
                  {tab === "reviews" && listing && (
                    <span className="ml-1.5 text-xs bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">
                      {listing.total_reviews}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Details tab */}
            {activeTab === "details" && (
              <div className="space-y-6">
                {listingLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                    <Skeleton className="h-4 w-4/6" />
                  </div>
                ) : (
                  <>
                    <div className="bg-white border border-slate-200 rounded-2xl p-6">
                      <h2 className="font-semibold text-slate-900 mb-3">About this place</h2>
                      <p className="text-slate-600 leading-relaxed whitespace-pre-line">
                        {listing!.description}
                      </p>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-6">
                      <h2 className="font-semibold text-slate-900 mb-4">Listed by</h2>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                          <User className="w-5 h-5 text-slate-400" />
                        </div>
                        <div>
                          <p className="font-medium text-slate-800">{listing!.landlord_name ?? "Landlord"}</p>
                          <p className="text-xs text-slate-400 flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            Listed {new Date(listing!.created_at).toLocaleDateString("en-ZA", { month: "long", year: "numeric" })}
                          </p>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Reviews tab */}
            {activeTab === "reviews" && (
              <div className="space-y-4">
                {/* Write review CTA */}
                {isGuest ? (
                  <div className="bg-slate-900 rounded-2xl p-5 flex items-center justify-between">
                    <p className="text-white text-sm font-medium">Sign in to leave a review</p>
                    <Button asChild size="sm" className="bg-white text-slate-900 hover:bg-slate-100 rounded-xl">
                      <Link href={`/login?redirect=/listings/${id}`}>Sign in</Link>
                    </Button>
                  </div>
                ) : user?.role === "student" ? (
                  <div className="bg-slate-900 rounded-2xl p-5 flex items-center justify-between">
                    <p className="text-white text-sm font-medium">Share your experience</p>
                    <Button size="sm" className="bg-white text-slate-900 hover:bg-slate-100 rounded-xl">
                      Write a review
                    </Button>
                  </div>
                ) : null}

                {reviewsLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-36 w-full rounded-2xl" />
                  ))
                ) : reviews.length === 0 ? (
                  <div className="text-center py-12 bg-white border border-slate-200 rounded-2xl">
                    <MessageSquare className="w-8 h-8 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500 text-sm">No reviews yet. Be the first!</p>
                  </div>
                ) : (
                  reviews.map((review, index) => (
                    <ReviewCard
                      key={review.id}
                      review={review}
                      blurred={isGuest && index >= 2}
                    />
                  ))
                )}

                {/* Guest gate after 2 reviews */}
                {isGuest && reviews.length > 2 && (
                  <div className="bg-slate-900 rounded-2xl p-6 text-center">
                    <Lock className="w-6 h-6 text-white mx-auto mb-2" />
                    <p className="text-white font-semibold mb-1">
                      {reviews.length - 2} more review{reviews.length - 2 !== 1 ? "s" : ""}
                    </p>
                    <p className="text-slate-300 text-sm mb-4">Sign in to read all reviews</p>
                    <Button asChild className="bg-white text-slate-900 hover:bg-slate-100 rounded-xl">
                      <Link href={`/login?redirect=/listings/${id}`}>Sign in to read more</Link>
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Location tab */}
            {activeTab === "location" && listing && (
              <div className="space-y-4">
                <div className="bg-white border border-slate-200 rounded-2xl p-6">
                  <h2 className="font-semibold text-slate-900 mb-1">Location</h2>
                  <p className="text-sm text-slate-500 mb-4">{listing.address}</p>
                  <DetailMap lat={listing.lat} lng={listing.lng} title={listing.title} />
                </div>
              </div>
            )}
          </div>

          {/* Right — NLP sidebar */}
          <div className="space-y-4">
            {listingLoading ? (
              <Skeleton className="h-64 w-full rounded-2xl" />
            ) : listing && (
              <>
                {/* Sentiment summary */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-4 h-4 text-slate-500" />
                    <h3 className="font-semibold text-slate-900 text-sm">Get A.I Summary</h3>
                  </div>

                  {listing.total_reviews === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-4">No reviews to analyse yet</p>
                  ) : (
                    <>
                      {/* Dominant sentiment badge */}
                      {listing.dominant_sentiment && (
                        <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium mb-4 ${SENTIMENT_STYLES[listing.dominant_sentiment]}`}>
                          <Star className="w-3.5 h-3.5" />
                          Overall {SENTIMENT_LABELS[listing.dominant_sentiment]}
                        </div>
                      )}

                      {/* Sentiment distribution */}
                      <div className="space-y-2 mb-4">
                        {(["positive", "neutral", "negative"] as const).map((s) => {
                          const count = listing.sentiment_distribution[s];
                          const pct = listing.total_reviews > 0
                            ? Math.round((count / listing.total_reviews) * 100)
                            : 0;
                          const colors = {
                            positive: "bg-emerald-500",
                            neutral: "bg-amber-400",
                            negative: "bg-red-400"
                          };
                          return (
                            <div key={s} className="flex items-center gap-2">
                              <span className="text-xs text-slate-500 capitalize w-16">{s}</span>
                              <div className="flex-1 h-1.5 bg-slate-100 rounded-full">
                                <div className={`h-full rounded-full ${colors[s]}`} style={{ width: `${pct}%` }} />
                              </div>
                              <span className="text-xs text-slate-500 w-8 text-right">{pct}%</span>
                            </div>
                          );
                        })}
                      </div>

                      {/* Aspect breakdown — blurred for guests */}
                      <div className="relative">
                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                          Common Aspects In Reviews
                        </h4>
                        <div className={`space-y-2.5 ${isGuest ? "blur-sm select-none" : ""}`}>
                          {Object.entries(listing.top_aspects).map(([aspect, score]) => {
                            const Icon = ASPECT_ICONS[aspect] ?? ShieldCheck;
                            return (
                              <AspectBar
                                key={aspect}
                                label={ASPECT_LABELS[aspect] ?? aspect}
                                score={score}
                                icon={Icon}
                              />
                            );
                          })}
                        </div>
                        {isGuest && (
                          <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <Lock className="w-5 h-5 text-slate-400 mb-1.5" />
                            <p className="text-xs text-slate-500 font-medium text-center">
                              Sign in to see full breakdown
                            </p>
                            <Link
                              href={`/login?redirect=/listings/${id}`}
                              className="text-xs text-blue-600 hover:underline mt-1"
                            >
                              Sign in free
                            </Link>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>

                {/* Price card */}
                <div className="bg-slate-900 rounded-2xl p-5 text-white">
                  <div className="text-2xl font-bold mb-1">
                    R{listing.price_min.toLocaleString()}
                    {listing.price_max > listing.price_min && (
                      <span className="text-lg font-normal text-slate-300">
                        {" "}– R{listing.price_max.toLocaleString()}
                      </span>
                    )}
                  </div>
                  <div className="text-slate-400 text-sm mb-4">per month</div>
                  {isGuest ? (
                    <Button asChild className="w-full bg-white text-slate-900 hover:bg-slate-100 rounded-xl font-semibold">
                      <Link href={`/login?redirect=/listings/${id}`}>Sign in to enquire</Link>
                    </Button>
                  ) : (
                    <Button className="w-full bg-white text-slate-900 hover:bg-slate-100 rounded-xl font-semibold">
                      Contact landlord
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
    </PageLayout>
  );
}