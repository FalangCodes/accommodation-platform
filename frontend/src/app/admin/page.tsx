"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import PageLayout from "@/components/page-layout";
import { Loader2, ShieldCheck } from "lucide-react";

export default function AdminPage() {
  const { user, loading, isAdmin } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/admin");
    if (!loading && user && !isAdmin) router.push("/");
  }, [user, loading]);

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      </PageLayout>
    );
  }

  if (!user || !isAdmin) return null;

  return (
    <PageLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
            <p className="text-sm text-slate-500">Platform management and analytics</p>
          </div>
        </div>

        <p className="text-slate-500">Building in progress — tabs coming next.</p>
      </div>
    </PageLayout>
  );
}