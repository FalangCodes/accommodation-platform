"use client";

import { useState, type ReactNode } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export function ProtectedDocumentLink({ href, className, children }: {
  href: string; className?: string; children: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      // Never send a bearer token to arbitrary storage or external URLs.
      if (!/^\/api\/v1\/(?:landlords\/\d+\/documents\/(?:id-copy|proof-of-address)|accommodations\/\d+\/documents\/ownership)$/.test(href)) {
        throw new Error("Invalid document endpoint");
      }
      const response = await api.get<Blob>(href, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = /filename="([^"]+)"/.exec(response.headers["content-disposition"] ?? "")?.[1] ?? "verification-document";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast.error("Unable to download this document. Check your access and try again.");
    } finally {
      setBusy(false);
    }
  };
  return <button type="button" className={className} disabled={busy} onClick={download} aria-busy={busy}>
    {busy ? "Downloading…" : children}
  </button>;
}
