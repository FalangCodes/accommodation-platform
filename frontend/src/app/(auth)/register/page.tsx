"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Building2, Eye, EyeOff, Loader2, GraduationCap, Home,
} from "lucide-react";
import { toast } from "sonner";

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const [role, setRole] = useState<"student" | "landlord">(
    searchParams.get("role") === "landlord" ? "landlord" : "student"
  );

  // Shared
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Student
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [studentNumber, setStudentNumber] = useState("");

  // Landlord
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [bio, setBio] = useState("");
  const [website, setWebsite] = useState("");
  const [idNumber, setIdNumber] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (role === "student") {
        await authApi.registerStudent({
          email,
          password,
          first_name: firstName,
          last_name: lastName,
          student_number: studentNumber,
        });
      } else {
        await authApi.registerLandlord({
          email,
          password,
          display_name: displayName,
          contact_phone: phone || undefined,
          bio: bio || undefined,
          website: website || undefined,
          id_number: idNumber,
        });
      }

      await login(email, password);
      toast.success("Account created successfully!");
      router.push(role === "landlord" ? "/dashboard" : "/");
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail[0]?.msg ?? "Registration failed");
      } else {
        setError(detail ?? "Registration failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "rounded-xl border-gray-200";

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Create an account</h1>
        <p className="text-gray-500 text-sm mt-1">
          Join thousands of students finding great accommodation
        </p>
      </div>

      {/* Role Toggle */}
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

      {/* Info banners */}
      {role === "student" && (
        <div className="mb-4 px-4 py-3 bg-[#E6F1FB] border border-[#B5D4F4] rounded-xl text-sm text-[#1F4E79]">
          A valid <strong>.ac.za</strong> institutional email is required for student accounts.
        </div>
      )}
      {role === "landlord" && (
        <div className="mb-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-700">
          Your ID number is required for identity verification. It is encrypted and never shared publicly.
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-100 rounded-xl text-sm text-red-600">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">

        {/* ── Student fields ── */}
        {role === "student" && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label>First name</Label>
                <Input
                  className={inputClass}
                  placeholder="e.g. Thabo"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Last name</Label>
                <Input
                  className={inputClass}
                  placeholder="e.g. Nkosi"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Student number</Label>
              <Input
                className={inputClass}
                placeholder="e.g. 21301234"
                value={studentNumber}
                onChange={(e) => setStudentNumber(e.target.value)}
                required
              />
            </div>
          </>
        )}

        {/* ── Landlord fields ── */}
        {role === "landlord" && (
          <>
            <div className="flex flex-col gap-1.5">
              <Label>Display name</Label>
              <Input
                className={inputClass}
                placeholder="e.g. John Properties"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>
                Contact phone <span className="text-gray-400">(optional)</span>
              </Label>
              <Input
                className={inputClass}
                placeholder="e.g. 082 123 4567"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>
                Website <span className="text-gray-400">(optional)</span>
              </Label>
              <Input
                className={inputClass}
                placeholder="e.g. https://johnproperties.co.za"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                type="url"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>
                Bio <span className="text-gray-400">(optional)</span>
              </Label>
              <Input
                className={inputClass}
                placeholder="Brief description of your property business"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>South African ID number</Label>
              <Input
                className={inputClass}
                placeholder="13-digit SA ID number"
                value={idNumber}
                onChange={(e) => setIdNumber(e.target.value.replace(/\D/g, ""))}
                maxLength={13}
                required
              />
              <p className="text-xs text-gray-400">
                {idNumber.length}/13 digits — used for identity verification only
              </p>
            </div>
          </>
        )}

        {/* ── Shared fields ── */}
        <div className="flex flex-col gap-1.5">
          <Label>Email address</Label>
          <Input
            className={inputClass}
            type="email"
            placeholder={role === "student" ? "you@spu.ac.za" : "you@gmail.com"}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Password</Label>
          <div className="relative">
            <Input
              className={`${inputClass} pr-10`}
              type={showPassword ? "text" : "password"}
              placeholder="Minimum 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
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
            <><Loader2 className="h-4 w-4 animate-spin mr-2" />Creating account...</>
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
  );
}

export default function RegisterPage() {
  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#1F4E79]">
              <Building2 className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-bold text-[#1F4E79]">AccomFind</span>
          </Link>
        </div>
        <Suspense fallback={
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-[#1F4E79]" />
          </div>
        }>
          <RegisterForm />
        </Suspense>
      </div>
    </div>
  );
}