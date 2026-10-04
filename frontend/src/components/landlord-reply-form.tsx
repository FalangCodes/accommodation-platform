"use client";

import { useRef, useState } from "react";
import { isAxiosError } from "axios";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

export function LandlordReplyForm({ reviewId, listingId }: { reviewId: number; listingId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const inFlight = useRef(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current || body.trim().length < 10) return;
    inFlight.current = true;
    setSending(true);
    try {
      await api.post(`/api/v1/reviews/${reviewId}/reply`, { body: body.trim() });
      await queryClient.invalidateQueries({ queryKey: ["reviews", listingId] });
      toast.success("Your response is now public.");
      setOpen(false);
      setBody("");
    } catch (error: unknown) {
      toast.error(isAxiosError(error) && typeof error.response?.data?.detail === "string"
        ? error.response.data.detail : "Could not submit your response.");
      if (isAxiosError(error) && error.response?.status === 409)
        await queryClient.invalidateQueries({ queryKey: ["reviews", listingId] });
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  if (!open) return <Button variant="outline" size="sm" onClick={() => setOpen(true)}>Reply as landlord</Button>;
  return (
    <form onSubmit={submit} className="space-y-2 border-t border-slate-100 pt-3">
      <label htmlFor={`reply-${reviewId}`} className="block text-sm font-medium">Your public response</label>
      <Textarea id={`reply-${reviewId}`} value={body} onChange={event => setBody(event.target.value)}
        minLength={10} maxLength={3000} rows={3} required disabled={sending} />
      <p className="text-xs text-slate-500">One response per review. Your response will be visible to readers.</p>
      <div className="flex gap-2">
        <Button size="sm" type="submit" disabled={sending || body.trim().length < 10}>
          {sending ? "Posting…" : "Post response"}
        </Button>
        <Button size="sm" type="button" variant="outline" disabled={sending} onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}
