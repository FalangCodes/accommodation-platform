"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Building2, Eye, EyeOff, Loader2, GraduationCap, Home } from "lucide-react";
import { toast } from "sonner";

export default function RegisterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const [role, setRole] = useState<"student" | "landlord">(
    searchParams.get("role") === "landlord" ? "landlord" : "student"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (role === "student") {
        await authApi.registerStudent({ email, password });
      } else {
        await authApi.registerLandlord({
          email,
          password,
          display_name: displayName,
          contact_phone: phone,
        });
      }
      await login(email, password);
      toast.success("Account created successfully!");
      router.push(role === "landlord" ? "/dashboard" : "/");
    } catch (err: any) {
      setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#1F4E79]">
              <Building2 className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-bold text-[#1F4E79]">AccomFind</span>
          </Link>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900">Create an account</h1>
            <p className="text-gray-500 text-sm mt-1">
              Join thousands of students finding great accommodation
            </p>
          </div>

          {/* Role toggle */}
          <div className="grid grid-cols-2 gap-2 mb-6 p-1 bg-gray-100 rounded-xl">
            <button
              type="button"
              onClick={() => setRole("student")}
              className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
                role === "student"
                  ? "bg-white text-[#1F4E79] shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <GraduationCap className="h-4 w-4" />
              Student
            </button>
            <button
              type="button"
              onClick={() => setRole("landlord")}
              className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
                role === "landlord"
                  ? "bg-white text-[#1F4E79] shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Home className="h-4 w-4" />
              Landlord
            </button>
          </div>

          {/* Student email hint */}
          {role === "student" && (
            <div className="mb-4 px-4 py-3 bg-[#E6F1FB] border border-[#B5D4F4] rounded-xl text-sm text-[#1F4E79]">
              A valid <strong>.ac.za</strong> institutional email is required for student accounts.
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-4 px-4 py-3 bg-red-50 border border-red-100 rounded-xl text-sm text-red-600">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">

            {role === "landlord" && (
              <>
                <div className="flex flex-col gap-1.5">
                  <Label className="text-sm font-medium text-gray-700">
                    Display name
                  </Label>
                  <Input
                    placeholder="e.g. John Properties"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    required
                    className="rounded-xl border-gray-200"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label className="text-sm font-medium text-gray-700">
                    Contact phone <span className="text-gray-400">(optional)</span>
                  </Label>
                  <Input
                    placeholder="e.g. 082 123 4567"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="rounded-xl border-gray-200"
                  />
                </div>
              </>
            )}

            <div className="flex flex-col gap-1.5">
              <Label className="text-sm font-medium text-gray-700">
                Email address
              </Label>
              <Input
                type="email"
                placeholder={role === "student" ? "you@spu.ac.za" : "you@gmail.com"}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="rounded-xl border-gray-200"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label className="text-sm font-medium text-gray-700">
                Password
              </Label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Minimum 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="rounded-xl border-gray-200 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-[#1F4E79] hover:bg-[#163a5e] text-white rounded-xl py-5 font-semibold mt-2"
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Creating account...</>
              ) : (
                `Create ${role} account`
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-[#1F4E79] font-semibold hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}