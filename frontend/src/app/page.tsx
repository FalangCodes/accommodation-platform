"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import ActivityToast from "@/components/activity-toast";
import Navbar from "@/components/navbar";
import {
  GraduationCap,
  MapPin,
  Star,
  Shield,
  Search,
  ChevronDown,
  ArrowRight,
  ShieldCheck,
  BadgePercent,
  UserRoundCheck,
  LockKeyhole,
  MessageSquareText,
  TrendingUp,
  Building2,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PlatformStats {
  listings: number;
  reviews: number;
  students: number;
}

interface FeaturedListing {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  avg_rating: number;
  review_count: number;
  view_count: number;
  first_image_url: string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatStat(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k+`;
  return n > 0 ? `${n}+` : "0";
}

function StarRow({ rating }: { rating: number }) {
  const full = Math.round(rating);
  return (
    <div className="flex gap-0.5 items-center">
      {Array.from({ length: 5 }).map((_, i) => (
        <Star
          key={i}
          className={`w-3.5 h-3.5 ${i < full ? "text-amber-400 fill-amber-400" : "text-gray-200 fill-gray-200"}`}
        />
      ))}
    </div>
  );
}

// ─── Landing Page ─────────────────────────────────────────────────────────────

export default function Home() {
  const router = useRouter();
  const [heroTab, setHeroTab] = useState<"find" | "list">("find");
  const [selectedUniversity] = useState("1"); // Sol Plaatje — only university for now

  const { data: stats } = useQuery<PlatformStats>({
    queryKey: ["platform-stats"],
    queryFn: () => api.get("/api/v1/accommodations/platform-stats").then(r => r.data),
    staleTime: 1000 * 60 * 60 * 24, // 24h — matches backend cache
  });

  const { data: featured = [] } = useQuery<FeaturedListing[]>({
    queryKey: ["featured-listings"],
    queryFn: () => api.get("/api/v1/accommodations/featured").then(r => r.data),
    staleTime: 1000 * 60 * 60 * 24,
  });

  const handleSearch = () => {
    router.push(`/search?university_id=${selectedUniversity}`);
  };

  return (
    <div className="bg-white flex flex-col items-start w-full min-h-dvh">

      <Navbar />

      {/* ── Hero ── */}
      <section className="relative flex items-center w-full min-h-[680px] px-5 lg:px-20 py-16 lg:py-0">
        {/* Background photo with dark blue overlay */}
        <div aria-hidden className="absolute inset-0 pointer-events-none">
          <img
            src="/hero-campus.jpg"
            alt=""
            className="absolute inset-0 w-full h-full object-cover object-center"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[rgba(13,33,55,0.88)] via-[rgba(31,78,121,0.70)] to-[rgba(31,78,121,0.30)]" />
        </div>

        {/* Search card */}
        <div className="bg-white/95 backdrop-blur-sm flex flex-col gap-6 items-start p-9 relative rounded-2xl shadow-2xl w-full max-w-[540px]">
          {/* Tabs */}
          <div className="flex gap-2 items-start w-full">
            <button
              onClick={() => setHeroTab("find")}
              className={`flex flex-1 items-center justify-center py-3 rounded-xl font-bold text-sm transition-colors ${
                heroTab === "find" ? "bg-[#1f4e79] text-white" : "bg-[#1f4e79]/10 text-[#1f4e79]"
              }`}
            >
              Find a Room
            </button>
            <button
              onClick={() => router.push("/register?role=landlord")}
              className={`flex flex-1 items-center justify-center py-3 rounded-xl font-bold text-sm transition-colors ${
                heroTab === "list" ? "bg-[#1f4e79] text-white" : "bg-[#1f4e79]/10 text-[#1f4e79]"
              }`}
            >
              List a Property
            </button>
          </div>

          {/* Hero text */}
          <div className="flex flex-col gap-3 w-full">
            <h1
              className="font-extrabold leading-tight text-[#112a46] text-4xl"
              style={{ fontFamily: "var(--font-outfit)" }}
            >
              Find trusted student accommodation near your campus
            </h1>
            <p className="text-gray-500 text-base leading-relaxed">
              Verified listings. Real student reviews. Make the right decision before you sign a lease.
            </p>
          </div>

          {/* University dropdown + CTA */}
          <div className="flex flex-col gap-4 w-full">
            <div className="bg-white border border-gray-200 flex items-center justify-between px-4 py-3.5 rounded-xl w-full hover:border-[#1f4e79] transition-colors">
              <div className="flex gap-3 items-center">
                <MapPin className="w-4 h-4 text-gray-400" />
                <span className="text-gray-500 text-sm">Sol Plaatje University, Northern Cape</span>
              </div>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </div>
            <button
              onClick={handleSearch}
              className="bg-[#1f4e79] flex items-center justify-center gap-2 py-4 rounded-xl w-full hover:bg-[#163a5b] transition-colors font-bold text-white text-base active:scale-[0.98]"
            >
              <Search className="w-4 h-4" />
              Search Accommodation
            </button>
          </div>
        </div>
      </section>

      {/* ── Trust / Stats Bar ── */}
      <section id="trust-safety" className="bg-white border-y border-gray-100 w-full shrink-0">
        <div className="max-w-7xl mx-auto px-5 lg:px-20 py-6">
          <div className="flex flex-wrap items-center justify-between gap-y-4 gap-x-6">
            {[
              {
                icon: <ShieldCheck className="w-4 h-4 text-emerald-600" />,
                label: stats ? `${formatStat(stats.reviews)} Verified Reviews` : "Verified Student Reviews",
              },
              {
                icon: <BadgePercent className="w-4 h-4 text-emerald-600" />,
                label: "Free for Students",
              },
              {
                icon: <UserRoundCheck className="w-4 h-4 text-emerald-600" />,
                label: stats ? `${formatStat(stats.students)} .ac.za Accounts` : ".ac.za Verified Accounts",
              },
              {
                icon: <LockKeyhole className="w-4 h-4 text-emerald-600" />,
                label: "AI-Powered Safety Moderation",
              },
            ].map((item) => (
              <div key={item.label} className="flex gap-3 items-center shrink-0">
                <div className="bg-emerald-50 flex items-center justify-center p-2 rounded-lg shrink-0">
                  {item.icon}
                </div>
                <span className="font-bold text-[#112a46] text-sm">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section id="how-it-works" className="bg-white w-full shrink-0">
        <div className="max-w-7xl mx-auto px-5 lg:px-20 py-24">
          <div className="flex flex-col gap-3 items-center text-center mb-14">
            <h2
              className="font-extrabold text-[#112a46] text-4xl"
              style={{ fontFamily: "var(--font-outfit)" }}
            >
              Finding your perfect digs has never been easier
            </h2>
            <p className="text-gray-500 text-base max-w-xl">
              AccomFind takes the stress out of student living with a seamless, structured process.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: <Search className="w-5 h-5 text-[#1f4e79]" />,
                title: "Search near campus",
                desc: "Select your university and filter by budget, distance, gender policy, and amenities.",
              },
              {
                icon: <MessageSquareText className="w-5 h-5 text-[#1f4e79]" />,
                title: "Read real reviews",
                desc: "Every review comes from a verified student with a valid institutional email. No fake reviews.",
              },
              {
                icon: <Shield className="w-5 h-5 text-[#1f4e79]" />,
                title: "Move in with confidence",
                desc: "Our AI analyses reviews for safety, cleanliness, and landlord responsiveness so you know what to expect.",
              },
            ].map((card) => (
              <div
                key={card.title}
                className="relative bg-gray-50 border border-gray-200 flex flex-col gap-5 items-start p-8 rounded-2xl"
              >
                <div className="bg-[#1f4e79]/10 flex items-center justify-center rounded-xl w-12 h-12 shrink-0">
                  {card.icon}
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="font-bold text-[#112a46] text-lg" style={{ fontFamily: "var(--font-outfit)" }}>
                    {card.title}
                  </h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{card.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Featured Listings ── */}
      {featured.length > 0 && (
        <section className="bg-gray-50 w-full shrink-0">
          <div className="max-w-7xl mx-auto px-5 lg:px-20 py-24">
            <div className="flex items-center justify-between mb-12">
              <div className="flex flex-col gap-2">
                <h2
                  className="font-extrabold text-[#112a46] text-3xl"
                  style={{ fontFamily: "var(--font-outfit)" }}
                >
                  Popular listings near Sol Plaatje University
                </h2>
                <p className="text-gray-500 text-base">
                  Highest-rated, most-viewed residences verified by our team.
                </p>
              </div>
              <button
                onClick={handleSearch}
                className="hidden md:flex items-center gap-2 font-bold text-[#1f4e79] text-sm hover:underline shrink-0"
              >
                View all listings <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {featured.map((listing) => (
                <Link
                  key={listing.id}
                  href={`/listings/${listing.id}`}
                  className="bg-white border border-gray-200 flex flex-col items-start rounded-2xl overflow-hidden hover:shadow-lg transition-shadow cursor-pointer"
                >
                  {/* Image or gradient placeholder */}
                  <div className="relative h-52 w-full shrink-0 overflow-hidden">
                    {listing.first_image_url ? (
                      <img
                        src={listing.first_image_url}
                        alt={listing.title}
                        className="absolute inset-0 w-full h-full object-cover"
                      />
                    ) : (
                      <div className="absolute inset-0 bg-gradient-to-br from-[#1f4e79] to-[#2e75b6]" />
                    )}
                    <div className="absolute inset-0 flex items-start justify-between p-4">
                      <div className="bg-emerald-50 flex gap-1 items-center px-2.5 py-1 rounded-full shrink-0">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        <span className="font-bold text-emerald-700 text-xs">Verified Landlord</span>
                      </div>
                      <div className="bg-[#112a46]/80 px-3 py-1.5 rounded-lg shrink-0">
                        <span className="font-bold text-white text-xs">
                          R{listing.price_min.toLocaleString()}/mo
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Info */}
                  <div className="flex flex-col gap-4 p-6 w-full">
                    <div className="flex flex-col gap-2">
                      <div className="bg-gray-50 border border-gray-200 inline-flex px-2 py-1 rounded-md w-fit">
                        <span className="font-semibold text-[#1f4e79] text-xs">Sol Plaatje University</span>
                      </div>
                      <h3
                        className="font-bold text-[#112a46] text-lg truncate"
                        style={{ fontFamily: "var(--font-outfit)" }}
                      >
                        {listing.title}
                      </h3>
                    </div>
                    <div className="flex items-center justify-between w-full">
                      <div className="flex gap-1 items-center">
                        <MapPin className="w-3.5 h-3.5 text-gray-400" />
                        <span className="text-gray-500 text-xs truncate max-w-[150px]">{listing.address}</span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <StarRow rating={listing.avg_rating} />
                        <span className="font-semibold text-gray-800 text-xs">{listing.avg_rating}</span>
                        <span className="text-gray-400 text-xs">({listing.review_count})</span>
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Landlord Section ── */}
      <section id="landlord-insights" className="bg-[#f0f4f8] w-full shrink-0">
        <div className="max-w-7xl mx-auto px-5 lg:px-20 py-24">
          <div className="flex flex-col gap-3 items-center text-center mb-14">
            <h2
              className="font-extrabold text-[#112a46] text-4xl"
              style={{ fontFamily: "var(--font-outfit)" }}
            >
              Reach thousands of verified student tenants
            </h2>
            <p className="text-gray-500 text-base max-w-xl">
              Simplify your landlord operations with smart automation and AI-powered review insights.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            {[
              {
                icon: <TrendingUp className="w-5 h-5 text-[#2e75b6]" />,
                title: "AI-Powered Insights",
                desc: "Get real sentiment analysis from verified student reviews — understand exactly how to improve your property.",
              },
              {
                icon: <ShieldCheck className="w-5 h-5 text-[#2e75b6]" />,
                title: "Verified Tenants Only",
                desc: "Every student is verified via their .ac.za institutional email. No fake profiles, no scammers.",
              },
              {
                icon: <Building2 className="w-5 h-5 text-[#2e75b6]" />,
                title: "Strict Review Moderation",
                desc: "Our AI and moderation team quarantine toxic or fake reviews, so your rating stays fair and trustworthy.",
              },
            ].map((card) => (
              <div
                key={card.title}
                className="bg-white border border-gray-200 flex flex-col gap-4 items-start p-8 rounded-2xl"
              >
                <div className="bg-[#2e75b6]/12 flex items-center justify-center rounded-xl w-11 h-11 shrink-0">
                  {card.icon}
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="font-bold text-[#112a46] text-lg" style={{ fontFamily: "var(--font-outfit)" }}>
                    {card.title}
                  </h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{card.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-center">
            <button
              onClick={() => router.push("/register?role=landlord")}
              className="bg-[#1f4e79] px-8 py-4 rounded-xl font-bold text-white text-base hover:bg-[#163a5b] transition-colors active:scale-[0.98]"
            >
              {`List Your Property — It's Free`}
            </button>
          </div>
        </div>
      </section>

      {/* ── Platform Stats Banner ── */}
      <section className="bg-[#1f4e79] w-full shrink-0">
        <div className="max-w-7xl mx-auto px-5 lg:px-20 py-16">
          <div className="flex flex-col md:flex-row items-center justify-around gap-10 text-center">
            {[
              {
                value: stats ? formatStat(stats.students) : "—",
                label: "Verified Students",
              },
              {
                value: stats ? formatStat(stats.listings) : "—",
                label: "Approved Listings",
              },
              {
                value: stats ? formatStat(stats.reviews) : "—",
                label: "Verified Reviews",
              },
              {
                value: "Free",
                label: "Always Free for Students",
              },
            ].map((stat) => (
              <div key={stat.label} className="flex flex-col gap-1 items-center">
                <span
                  className="font-extrabold text-white text-4xl"
                  style={{ fontFamily: "var(--font-outfit)" }}
                >
                  {stat.value}
                </span>
                <span className="text-white/70 text-sm">{stat.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-[#112a46] w-full shrink-0">
        <div className="max-w-7xl mx-auto px-5 lg:px-20 pt-20 pb-10">
          <div className="flex flex-col lg:flex-row items-start justify-between gap-12 mb-16">
            {/* Brand */}
            <div className="flex flex-col gap-5 items-start shrink-0 w-full lg:w-72">
              <div className="flex gap-2 items-center">
                <GraduationCap className="w-7 h-7 text-white" />
                <span
                  className="font-extrabold text-white text-xl"
                  style={{ fontFamily: "var(--font-outfit)" }}
                >
                  AccomFind
                </span>
              </div>
              <p className="text-white/70 text-sm leading-relaxed max-w-[240px]">
                Simplifying and securing student housing near major South African campuses.
              </p>

            </div>

            {/* Link columns */}
            <div className="grid grid-cols-2 gap-10 text-sm">
              {[
                {
                  heading: "For Students",
                  links: [
                    { label: "Find a Room", href: "/search" },
                    { label: "How It Works", href: "#how-it-works" },
                    { label: "Trust & Safety", href: "#trust-safety" },
                    { label: "My Account", href: "/profile" },
                  ],
                },
                {
                  heading: "For Landlords",
                  links: [
                    { label: "List a Property", href: "/dashboard" },
                    { label: "AI Insights", href: "#landlord-insights" },
                    { label: "Verification Portal", href: "/dashboard" },
                    { label: "Account Help", href: "/forgot-password" },
                  ],
                },
              ].map((col) => (
                <div key={col.heading} className="flex flex-col gap-4">
                  <span
                    className="font-bold text-white uppercase text-xs tracking-widest"
                    style={{ fontFamily: "var(--font-outfit)" }}
                  >
                    {col.heading}
                  </span>
                  <div className="flex flex-col gap-3">
                    {col.links.map((link) => (
                      <Link key={link.label} href={link.href}
                        className="text-white/60 hover:text-white transition-colors">
                        {link.label}
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="h-px w-full bg-white/10 mb-8" />

          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-white/40">
            <span>© 2026 AccomFind. All rights reserved.</span>
            <span>Built for South African students.</span>
          </div>
        </div>
      </footer>

      {/* ── Global activity toast — fixed bottom-right, cycles across whole page ── */}
      <ActivityToast />

    </div>
  );
}