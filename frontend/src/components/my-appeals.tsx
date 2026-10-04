"use client";

import { useState } from "react";
import { isAxiosError } from "axios";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Appeal {
  id: number;
  resource_type: string;
  resource_id: number;
  status: string;
  reason: string;
  resolved_at: string | null;
}

export function MyAppeals() {
  const { user, isLandlord } = useAuth();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const { data: appeals = [], isPending, isError } = useQuery<Appeal[]>({
    queryKey: ["my-appeals", user?.id],
    queryFn: () => api.get("/api/v1/appeals/my").then(response => response.data),
    enabled: !!user,
  });
  const { data: landlord } = useQuery<{ id: number; verification_status: string }>({
    queryKey: ["appeal-landlord-profile", user?.id],
    queryFn: () => api.get("/api/v1/landlords/me").then(response => response.data),
    enabled: !!user && isLandlord,
  });
  const verificationPending = appeals.some(appeal => appeal.resource_type === "landlord"
    && appeal.resource_id === landlord?.id && appeal.status === "pending");

  async function submitVerificationAppeal() {
    if (!landlord || reason.trim().length < 20 || sending) return;
    setSending(true);
    try {
      await api.post("/api/v1/appeals", { resource_type: "landlord", resource_id: landlord.id, reason: reason.trim() });
      await queryClient.invalidateQueries({ queryKey: ["my-appeals"] });
      setShowForm(false);
      setReason("");
      toast.success("Verification appeal submitted for administrator review.");
    } catch (error: unknown) {
      toast.error(isAxiosError(error) && typeof error.response?.data?.detail === "string"
        ? error.response.data.detail : "Failed to submit appeal.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="mt-6 space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="font-semibold text-slate-900">My appeals</h2>
      {landlord?.verification_status === "rejected" && (
        <div className="space-y-3">
          <Button variant="outline" disabled={verificationPending || isPending || isError}
            onClick={() => setShowForm(!showForm)}>
            {verificationPending ? "Verification appeal pending" : "Appeal verification rejection"}
          </Button>
          {showForm && !verificationPending && (
            <div className="space-y-2">
              <label htmlFor="verification-appeal-reason" className="block text-sm text-slate-600">
                Explain why your verification should be restored (at least 20 characters).
              </label>
              <textarea id="verification-appeal-reason" value={reason} onChange={event => setReason(event.target.value)}
                rows={4} className="w-full rounded-xl border border-slate-200 p-3 text-sm" />
              <Button disabled={sending || reason.trim().length < 20} onClick={submitVerificationAppeal}>
                {sending ? "Submitting…" : "Submit appeal"}
              </Button>
            </div>
          )}
        </div>
      )}
      {isPending ? <p className="text-sm text-slate-500">Loading appeals…</p>
        : isError ? <p className="text-sm text-red-600">Could not load your appeals. Refresh to retry.</p>
        : appeals.length === 0 ? <p className="text-sm text-slate-500">You have no appeals yet.</p>
        : appeals.map(appeal => (
          <div key={appeal.id} className="border-t border-slate-100 pt-3 text-sm">
            <p className="font-medium capitalize">{appeal.resource_type} #{appeal.resource_id} · {appeal.status}</p>
            <p className="mt-1 text-slate-600">{appeal.reason}</p>
            {appeal.resolved_at && <p className="mt-1 text-xs text-slate-400">
              Resolved {new Date(appeal.resolved_at).toLocaleString()}
            </p>}
          </div>
        ))}
    </section>
  );
}
