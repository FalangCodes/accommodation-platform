"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Star, ShieldCheck } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ActivityItem {
  type: "review" | "listing";
  rating?: number;
  title: string;
}

// ─── Animation phases ─────────────────────────────────────────────────────────
// visible (5 000ms) → sliding-out (500ms) → hidden gap (1 000ms) → sliding-in (500ms) → visible …

type Phase = "sliding-in" | "visible" | "sliding-out" | "hidden";

const DISPLAY_MS   = 5_000;
const ANIMATE_MS   =   500;
const GAP_MS       = 1_000;

// ─── Component ────────────────────────────────────────────────────────────────

export default function ActivityToast() {
  const [index, setIndex]   = useState(0);
  const [phase, setPhase]   = useState<Phase>("sliding-in");

  const { data: items = [] } = useQuery<ActivityItem[]>({
    queryKey: ["activity-feed"],
    queryFn: () => api.get("/api/v1/accommodations/activity").then(r => r.data),
    staleTime: 1000 * 60 * 60, // 1 hour — matches backend cache
  });

  useEffect(() => {
    if (items.length === 0) return;

    let timer: ReturnType<typeof setTimeout>;

    switch (phase) {
      case "sliding-in":
        // Wait for slide-in animation to finish, then hold visible
        timer = setTimeout(() => setPhase("visible"), ANIMATE_MS);
        break;
      case "visible":
        // Hold the card, then start exit
        timer = setTimeout(() => setPhase("sliding-out"), DISPLAY_MS);
        break;
      case "sliding-out":
        // Wait for slide-out animation to finish, then gap
        timer = setTimeout(() => setPhase("hidden"), ANIMATE_MS);
        break;
      case "hidden":
        // Cool-off gap, then advance to next card
        timer = setTimeout(() => {
          setIndex(i => (i + 1) % items.length);
          setPhase("sliding-in");
        }, GAP_MS);
        break;
    }

    return () => clearTimeout(timer);
  }, [phase, items.length]);

  if (items.length === 0) return null;

  const item      = items[index];
  const isShowing = phase === "sliding-in" || phase === "visible";

  return (
    <div
      aria-live="polite"
      className="fixed bottom-6 right-4 z-50 max-w-[260px] w-full"
      style={{
        transition: `opacity ${ANIMATE_MS}ms ease, transform ${ANIMATE_MS}ms ease`,
        opacity:   isShowing ? 1 : 0,
        transform: isShowing ? "translateY(0px)" : "translateY(14px)",
        pointerEvents: isShowing ? "none" : "none", // decorative only
      }}
    >
      {item.type === "review" ? (
        <ReviewCard rating={item.rating ?? 5} title={item.title} />
      ) : (
        <ListingCard title={item.title} />
      )}
    </div>
  );
}

// ─── Sub-cards ────────────────────────────────────────────────────────────────

function ReviewCard({ rating, title }: { rating: number; title: string }) {
  const filled = Math.min(5, Math.max(1, rating));
  return (
    <div className="bg-white rounded-2xl shadow-lg border border-gray-100 px-4 py-3 flex items-center gap-3">
      <div className="bg-amber-50 rounded-xl p-2 shrink-0">
        <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
      </div>
      <div className="flex flex-col gap-0.5 min-w-0">
        {/* Star row */}
        <div className="flex items-center gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star
              key={i}
              className={`w-3 h-3 ${
                i < filled ? "text-amber-400 fill-amber-400" : "text-gray-200 fill-gray-200"
              }`}
            />
          ))}
        </div>
        <span className="text-sm font-semibold text-[#112a46] truncate">{title}</span>
        <span className="text-xs text-gray-400">Verified student review</span>
      </div>
    </div>
  );
}

function ListingCard({ title }: { title: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-lg border border-gray-100 px-4 py-3 flex items-center gap-3">
      <div className="bg-emerald-50 rounded-xl p-2 shrink-0">
        <ShieldCheck className="w-4 h-4 text-emerald-600" />
      </div>
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-semibold text-[#112a46] truncate">{title}</span>
        <span className="text-xs text-gray-400">Listing verified · SPU</span>
      </div>
    </div>
  );
}
