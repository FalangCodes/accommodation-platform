export function SummaryUpdated({ generatedAt, reviewCount }: {
  generatedAt?: string | null;
  reviewCount?: number;
}) {
  if (!generatedAt) return null;
  const date = new Date(generatedAt);
  if (Number.isNaN(date.getTime())) return null;
  return (
    <p className="mb-2 text-xs text-slate-500">
      Summary updated {date.toLocaleDateString("en-ZA", { year: "numeric", month: "short", day: "numeric", timeZone: "Africa/Johannesburg" })}
      {typeof reviewCount === "number" && <> · based on {reviewCount} review{reviewCount === 1 ? "" : "s"}</>}
    </p>
  );
}
