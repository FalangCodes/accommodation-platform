"use client";

import { useEffect, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

export function EnquiryButton({ listingId, listingTitle }: { listingId: number; listingTitle: string }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [retrySeconds, setRetrySeconds] = useState(0);
  const requestId = useRef<string | null>(null);
  const inFlight = useRef(false);

  useEffect(() => {
    if (retrySeconds <= 0) return;
    const timer = setTimeout(() => setRetrySeconds(seconds => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [retrySeconds]);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!consent || inFlight.current || message.trim().length < 20 || retrySeconds > 0) return;
    inFlight.current = true;
    setSending(true);
    setError("");
    requestId.current ??= crypto.randomUUID();
    try {
      const response = await api.post(`/api/v1/accommodations/${listingId}/enquiries`,
        { message: message.trim(), consent }, { headers: { "Idempotency-Key": requestId.current } });
      toast.success(response.data.detail);
      setOpen(false);
      setMessage("");
      setConsent(false);
      requestId.current = null;
    } catch (failure: unknown) {
      setError(isAxiosError(failure) && typeof failure.response?.data?.detail === "string"
        ? failure.response.data.detail : "The result could not be confirmed. Retry with this form to check before starting a new enquiry.");
      if (isAxiosError(failure) && failure.response?.status === 429) {
        setRetrySeconds(Number(failure.response.headers["retry-after"]) || 60);
      }
      if (isAxiosError(failure) && failure.response?.status === 503) {
        setRetrySeconds(60);
        requestId.current = null;
      }
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  return (
    <>
      <Button disabled={user?.role !== "student"} onClick={() => setOpen(true)}
        className="w-full bg-white text-slate-900 hover:bg-slate-100 rounded-xl font-semibold">
        {user?.role === "student" ? "Contact landlord" : "Student enquiries only"}
      </Button>
      <Dialog open={open} onOpenChange={value => { if (!sending) setOpen(value); }}>
        <DialogContent className="bg-white text-slate-900 rounded-2xl">
          <DialogHeader>
            <DialogTitle>Enquire about {listingTitle}</DialogTitle>
            <DialogDescription>AccomFind will email your enquiry to the landlord. They can reply directly to you.</DialogDescription>
          </DialogHeader>
          <form onSubmit={send} className="space-y-4">
            <div>
              <label htmlFor="listing-enquiry" className="block text-sm font-medium mb-2">Your enquiry</label>
              <Textarea id="listing-enquiry" value={message} disabled={sending}
                onChange={event => { setMessage(event.target.value); requestId.current = null; }}
                rows={5} minLength={20} maxLength={3000} required placeholder="Ask about availability, costs or the property…" />
              <p className="mt-1 text-xs text-slate-500">{message.trim().length}/3000 characters · minimum 20</p>
            </div>
            <label className="flex items-start gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={consent} disabled={sending} required className="mt-1"
                onChange={event => setConsent(event.target.checked)} />
              <span>I agree to share my name and verified email ({user?.email}) with this landlord so they can reply.</span>
            </label>
            <p className="text-xs text-slate-500">The landlord’s contact details stay private. Enquiries are not saved as an in-app conversation.</p>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            <Button type="submit" disabled={sending || !consent || message.trim().length < 20 || retrySeconds > 0}
              className="w-full">
              {sending ? "Sending…" : retrySeconds > 0 ? `Try again in ${retrySeconds}s` : "Send enquiry"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
