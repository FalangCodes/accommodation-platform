import Link from "next/link";

export interface AppealReview {
  id: number;
  body: string;
  rating: number;
  created_at: string | null;
  status: string;
  accommodation_id: number;
  accommodation_title: string | null;
}

const STATUS: Record<string, string> = {
  removed: "Removed",
  quarantined: "Awaiting moderation",
  pending_analysis: "Pending analysis",
  analysed: "Published",
  released: "Released by moderator",
};

export function AppealReviewContext({ review }: { review?: AppealReview | null }) {
  const date = review?.created_at ? new Date(review.created_at) : null;
  return (
    <section aria-label="Original review" className="mb-3 min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <h4 className="mb-2 text-xs font-semibold text-slate-700">Original review</h4>
      {review ? <>
        <Link href={`/listings/${review.accommodation_id}`} className="text-sm font-medium text-blue-700 underline break-words">
          {review.accommodation_title || `Listing #${review.accommodation_id}`}
        </Link>
        <div className="my-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
          <span>Review #{review.id}</span>
          <span>Rating: {review.rating}/5</span>
          {date && !Number.isNaN(date.getTime()) && <span>{date.toLocaleDateString("en-ZA", { year: "numeric", month: "short", day: "numeric", timeZone: "Africa/Johannesburg" })}</span>}
          <span>Current status: {STATUS[review.status] || review.status.replaceAll("_", " ")}</span>
        </div>
        <blockquote className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-800">
          {review.body}
        </blockquote>
      </> : <p className="text-sm text-slate-500">The original review is unavailable.</p>}
    </section>
  );
}
