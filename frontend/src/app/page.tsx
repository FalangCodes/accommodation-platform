"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import PageLayout from "@/components/page-layout";
import { Button } from "@/components/ui/button";
import { Building2, Shield, Star, MapPin, ArrowRight, Search } from "lucide-react";

const UNIVERSITIES = [
  { id: 1, name: "Sol Plaatje University" },
];

export default function Home() {
  const router = useRouter();
  const [selectedUniversity, setSelectedUniversity] = useState("");

  const handleSearch = () => {
    if (!selectedUniversity) return;
    router.push(`/search?university_id=${selectedUniversity}`);
  };

  return (
    <PageLayout>
      {/* ── HERO ── */}
      <section className="relative bg-gradient-to-br from-[#1F4E79] via-[#2E75B6] to-[#1D6A72] text-white">
        <div className="absolute inset-0 bg-black/10" />
        <div className="relative max-w-7xl mx-auto px-6 lg:px-10 py-24 lg:py-32">
          <div className="max-w-2xl">
            <span className="inline-block bg-white/20 backdrop-blur-sm text-white text-sm font-medium px-4 py-1.5 rounded-full mb-6">
              Trusted by students across South Africa
            </span>
            <h1 className="text-4xl lg:text-6xl font-bold leading-tight mb-6">
              Find trusted student accommodation near your campus
            </h1>
            <p className="text-lg text-white/80 mb-10 leading-relaxed">
              Read verified reviews from real students. Make informed decisions before you sign a lease.
            </p>

            {/* Search box */}
            <div className="bg-white rounded-2xl p-3 flex flex-col sm:flex-row gap-3 shadow-2xl max-w-xl">
              <select
                value={selectedUniversity}
                onChange={(e) => setSelectedUniversity(e.target.value)}
                className="flex-1 px-4 py-3 rounded-xl text-gray-800 text-sm font-medium bg-gray-50 border border-gray-200 focus:outline-none focus:ring-2 focus:ring-[#1F4E79]"
              >
                <option value="">Select your university</option>
                {UNIVERSITIES.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </select>
              <Button
                onClick={handleSearch}
                disabled={!selectedUniversity}
                className="bg-[#1F4E79] hover:bg-[#163a5e] text-white px-8 py-3 rounded-xl font-semibold flex items-center gap-2 disabled:opacity-50"
              >
                <Search className="h-4 w-4" />
                Search
              </Button>
            </div>
          </div>
        </div>

        {/* Wave divider */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 60" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0 60L1440 60L1440 20C1200 60 960 0 720 20C480 40 240 0 0 20L0 60Z" fill="#F8F9FA"/>
          </svg>
        </div>
      </section>

      {/* ── STATS BAR ── */}
      <section className="bg-white border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-6">
          <div className="flex flex-wrap justify-center gap-10 text-center">
            {[
              { value: "1", label: "Partner university" },
              { value: "Verified", label: "Student reviews" },
              { value: "Free", label: "Always free for students" },
              { value: "Secure", label: ".ac.za verified accounts" },
            ].map((stat) => (
              <div key={stat.label}>
                <p className="text-2xl font-bold text-[#1F4E79]">{stat.value}</p>
                <p className="text-sm text-gray-500 mt-0.5">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="max-w-7xl mx-auto px-6 lg:px-10 py-20">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold text-gray-900 mb-3">How AccomFind works</h2>
          <p className="text-gray-500 max-w-xl mx-auto">
            Finding safe, affordable student accommodation has never been easier.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            {
              icon: <Search className="h-7 w-7 text-[#1F4E79]" />,
              step: "01",
              title: "Search near your campus",
              description: "Select your university and we'll show you verified listings within your preferred distance.",
            },
            {
              icon: <Star className="h-7 w-7 text-[#1F4E79]" />,
              step: "02",
              title: "Read verified reviews",
              description: "Every review comes from a verified student with a valid institutional email address. No fake reviews.",
            },
            {
              icon: <Shield className="h-7 w-7 text-[#1F4E79]" />,
              step: "03",
              title: "Move in with confidence",
              description: "Our AI analyses reviews for safety, cleanliness, and landlord responsiveness so you know what to expect.",
            },
          ].map((item) => (
            <div
              key={item.step}
              className="relative bg-white rounded-2xl p-8 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
            >
              <span className="absolute top-6 right-6 text-4xl font-black text-gray-100">
                {item.step}
              </span>
              <div className="h-12 w-12 bg-[#E6F1FB] rounded-xl flex items-center justify-center mb-5">
                {item.icon}
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{item.title}</h3>
              <p className="text-gray-500 text-sm leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── FOR LANDLORDS ── */}
      <section className="bg-[#1F4E79] text-white">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-16">
          <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
            <div className="max-w-lg">
              <h2 className="text-3xl font-bold mb-4">Are you a landlord?</h2>
              <p className="text-white/75 leading-relaxed mb-6">
                List your property and reach thousands of verified students actively looking for accommodation near their campus. Get insights from AI-powered review analysis.
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  onClick={() => router.push("/register?role=landlord")}
                  className="bg-white text-[#1F4E79] hover:bg-gray-100 font-semibold px-6 rounded-full"
                >
                  List your property
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 shrink-0">
              {[
                { icon: <Building2 className="h-5 w-5" />, label: "Easy listing management" },
                { icon: <Star className="h-5 w-5" />, label: "Review analytics dashboard" },
                { icon: <Shield className="h-5 w-5" />, label: "Verified student tenants" },
                { icon: <MapPin className="h-5 w-5" />, label: "Campus proximity targeting" },
              ].map((feature) => (
                <div
                  key={feature.label}
                  className="flex items-center gap-3 bg-white/10 rounded-xl px-4 py-3"
                >
                  <span className="text-white/80">{feature.icon}</span>
                  <span className="text-sm font-medium text-white/90">{feature.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="bg-white border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#1F4E79]">
                <Building2 className="h-4 w-4 text-white" />
              </div>
              <span className="text-sm font-semibold text-[#1F4E79]">AccomFind</span>
            </div>
            <p className="text-xs text-gray-400">
              © 2026 AccomFind. Built for South African students.
            </p>
            <div className="flex gap-4">
              <a href="#" className="text-xs text-gray-400 hover:text-gray-600">Privacy</a>
              <a href="#" className="text-xs text-gray-400 hover:text-gray-600">Terms</a>
              <a href="#" className="text-xs text-gray-400 hover:text-gray-600">Contact</a>
            </div>
          </div>
        </div>
      </footer>
    </PageLayout>
  );
}