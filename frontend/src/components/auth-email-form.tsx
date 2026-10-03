"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AxiosError } from "axios";
import { authApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Mode = "verify" | "forgot" | "reset";

function EmailForm({ mode }: { mode: Mode }) {
  const { clearSession } = useAuth();
  const search = useSearchParams();
  const [email, setEmail] = useState(search.get("email") || "");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);

  async function perform(action: "verify" | "resend" | "forgot" | "reset") {
    setError("");
    setMessage("");
    if (action === "reset" && password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if ((action === "verify" || action === "reset") && !token) {
      setError("Open the link in your email first, or request a new link below.");
      return;
    }
    setLoading(true);
    try {
      const response = action === "verify" ? await authApi.verifyEmail(token!)
        : action === "reset" ? await authApi.resetPassword(token!, password)
        : action === "resend" ? await authApi.resendVerification(email)
        : await authApi.requestPasswordReset(email);
      setMessage(response.data.message);
      if (action === "verify" || action === "reset") {
        setComplete(true);
        window.history.replaceState(null, "", window.location.pathname);
      }
      if (action === "reset") {
        clearSession();
      }
    } catch (caught: unknown) {
      const detail = caught instanceof AxiosError ? caught.response?.data?.detail : undefined;
      setError(typeof detail === "string" ? detail : "We could not complete this request. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const title = mode === "verify" ? "Verify your email" : mode === "forgot" ? "Forgot your password?" : "Reset your password";
  return (
    <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center px-4 py-10">
      <main className="w-full max-w-md rounded-2xl bg-white border border-gray-100 shadow-sm p-8">
        <Link href="/" className="font-bold text-[#1F4E79]">AccomFind</Link>
        <h1 className="text-2xl font-bold mt-6 mb-3">{title}</h1>
        <p className="text-sm text-gray-600 mb-5">
          {mode === "verify" ? "Check your institutional inbox. Open the verification link, then select Verify email. The link expires in 24 hours."
            : mode === "forgot" ? "Enter your account email to request a password reset link."
            : "Choose a new password. The email link expires in 30 minutes. You will need to sign in again on all devices."}
        </p>
        {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="mb-4 rounded-xl bg-green-50 p-3 text-sm text-green-800">{message}</p>}
        {!complete && mode === "verify" && (
          <Button disabled={loading} onClick={() => perform("verify")} className="w-full mb-6 bg-[#1F4E79] text-white">{loading ? "Please wait..." : "Verify email"}</Button>
        )}
        {!complete && mode === "reset" && (
          <form onSubmit={(event) => { event.preventDefault(); void perform("reset"); }} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">New password</Label>
              <Input id="new-password" type="password" autoComplete="new-password" required minLength={8} maxLength={64} value={password} onChange={(event) => setPassword(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm new password</Label>
              <Input id="confirm-password" type="password" autoComplete="new-password" required minLength={8} maxLength={64} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
            </div>
            <Button disabled={loading} type="submit" className="w-full bg-[#1F4E79] text-white">{loading ? "Please wait..." : "Reset password"}</Button>
          </form>
        )}
        {!complete && mode !== "reset" && (
          <form onSubmit={(event) => { event.preventDefault(); void perform(mode === "verify" ? "resend" : "forgot"); }} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="recovery-email">{mode === "verify" ? "Institutional email" : "Email address"}</Label>
              <Input id="recovery-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
            </div>
            <Button disabled={loading} type="submit" variant="outline" className="w-full">{loading ? "Please wait..." : mode === "verify" ? "Resend verification email" : "Send reset link"}</Button>
          </form>
        )}
        {mode === "reset" && !complete && <Link href="/forgot-password" className="block mt-4 text-sm text-[#1F4E79] hover:underline">Request a new reset link</Link>}
        <Link href="/login" className="block mt-6 text-sm text-center text-[#1F4E79] hover:underline">Back to sign in</Link>
      </main>
    </div>
  );
}

export function AuthEmailForm({ mode }: { mode: Mode }) {
  return <Suspense fallback={<p role="status" className="p-8">Loading...</p>}><EmailForm mode={mode} /></Suspense>;
}
