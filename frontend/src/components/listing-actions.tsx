"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { EnquiryButton } from "@/components/enquiry-button";

export function listingWebsiteUrl(value?: string | null): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

export function ListingActions({ listingId, listingTitle, website, dark = false }: {
  listingId: number; listingTitle: string; website?: string | null; dark?: boolean;
}) {
  const { user, loading } = useAuth();
  const url = listingWebsiteUrl(website);
  const primary = `w-full min-h-11 rounded-xl font-semibold ${dark ? "bg-white text-slate-900 hover:bg-slate-100" : "bg-[#1f4e79] text-white hover:bg-[#173752]"}`;
  const secondary = `w-full min-h-11 rounded-xl text-sm font-medium underline underline-offset-4 ${dark ? "bg-transparent text-white hover:bg-white/10" : "bg-transparent text-[#1f4e79] hover:bg-slate-100"}`;
  const enquiryStyle = url ? secondary : primary;
  const label = url ? "Ask a question" : "Enquire";
  return <div>
    {url && <Button asChild className={primary}>
      <a href={url} target="_blank" rel="noopener noreferrer">
        Visit official website <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      </a>
    </Button>}
    {loading ? <Button disabled className={enquiryStyle}>Loading…</Button>
      : user ? <EnquiryButton listingId={listingId} listingTitle={listingTitle} label={label} className={enquiryStyle} />
        : <Button asChild className={enquiryStyle}>
          <Link href={`/login?redirect=/listings/${listingId}`}>{url ? label : "Sign in to enquire"}</Link>
        </Button>}
  </div>;
}
