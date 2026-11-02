"use client";

import type { LucideIcon } from "lucide-react";

import { getApiErrorMessage } from "@/lib/api-error";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi, reportsApi, moderationApi } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { FileText, RefreshCw, Calendar } from "lucide-react";
import PageLayout from "@/components/page-layout";
import { ManagementReport, ReportDownloadButton, type ManagementDocument } from "@/components/management-report";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  ShieldCheck, Loader2, Users, Home, Star, Eye, TrendingUp,
  Building2, ChevronDown, ChevronRight, MapPin, XCircle, Clock, Plus,
  GraduationCap, BarChart2, Activity,
  ChevronLeft,
} from "lucide-react";
import { toast } from "sonner";
import { FlaggedReviewQueue, FlaggedReviewCount } from "@/components/flagged-review-queue";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Stats {
  users: { total_students: number; total_landlords: number; total_moderators: number };
  accommodations: { total: number; approved: number; pending: number };
  reviews: { total: number; quarantined: number };
  total_views: number;
  landlord_verification: Record<string, number>;
  top_viewed: { id: number; title: string; address: string; views: number }[];
  top_rated: { id: number; title: string; address: string; avg_rating: number; review_count: number }[];
  recent_activity: { id: number; action: string; resource_type: string; resource_id: number; reason: string | null; created_at: string }[];
}

interface UniversityTree {
  id: number;
  name: string;
  domain: string;
  province: string;
  accommodation_count: number;
  accommodations: {
    id: number;
    title: string;
    address: string;
    status: string;
    created_at: string;
    price_min: number;
    price_max: number;
    gender_policy: string | null;
    funding_type: string | null;
    property_type: string | null;
    website: string | null;
    ownership_doc_url: string | null;
    total_views: number;
    review_count: number;
    avg_rating: number | null;
    landlord: { id: number; display_name: string; verification_status: string } | null;
  }[];
}

interface Student {
  id: number;
  student_id: number;
  email: string;
  first_name: string | null;
  last_name: string | null;
  student_number: string | null;
  university: string;
  verification_tier: number;
  is_active: boolean;
  review_count: number;
  joined: string;
}

interface Landlord {
  id: number;
  landlord_id: number;
  email: string;
  display_name: string;
  contact_phone: string | null;
  verification_status: string;
  id_number: string | null;
  id_copy_url: string | null;
  proof_of_address_url: string | null;
  is_active: boolean;
  listing_count: number;
  joined: string;
}

interface Moderator {
  id: number;
  email: string;
  is_active: boolean;
  actions_count: number;
  joined: string;
}

interface Report {
  id: number;
  report_type: string;
  period_year: number;
  period_month: number;
  generated_at: string;
  status: string;
  entity_id: number | null;
  entity_type: string | null;
  entity_name: string | null;
}

interface ReportDetail {
  document?: ManagementDocument | null;
  id: number;
  report_type: string;
  period_year: number;
  period_month: number;
  generated_at: string;
  status: string;
  entity_id: number | null;
  entity_name?: string | null;
  metrics: Record<string, { key: string; label: string; value: number; breakdown: Record<string, unknown> | null }[]>;
}

interface ModerationLogEntry {
  id: number;
  moderator_email: string;
  action: string;
  resource_type: string;
  resource_id: number;
  reason: string | null;
  created_at: string;
  resource_detail: {
    // accommodation
    title?: string;
    address?: string;
    landlord_name?: string;
    landlord_phone?: string;
    // review
    body?: string;
    rating?: number;
    status?: string;
    student_name?: string;
    // landlord
    display_name?: string;
    verification_status?: string;
  };
}

interface ModerationLogResponse {
  items: ModerationLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({ label, value, icon: Icon, sub }: { label: string; value: string | number; icon: LucideIcon; sub?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-slate-400" />
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab() {
  const { data: stats, isLoading } = useQuery<Stats>({
    queryKey: ["admin-stats"],
    queryFn: () => adminApi.getStats().then(r => r.data),
  });

  if (isLoading) return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
    </div>
  );

  if (!stats) return null;

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Students" value={stats.users.total_students} icon={GraduationCap} />
        <StatCard label="Landlords" value={stats.users.total_landlords} icon={Home}
          sub={`${stats.landlord_verification["verified"] ?? 0} verified`} />
        <StatCard label="Moderators" value={stats.users.total_moderators} icon={ShieldCheck} />
        <StatCard label="Total views" value={stats.total_views.toLocaleString()} icon={Eye} />
        <StatCard label="Accommodations" value={stats.accommodations.total} icon={Building2}
          sub={`${stats.accommodations.approved} live · ${stats.accommodations.pending} pending`} />
        <StatCard label="Reviews" value={stats.reviews.total} icon={Star}
          sub={`${stats.reviews.quarantined} quarantined`} />
        <StatCard label="Pending verification" value={stats.landlord_verification["pending"] ?? 0} icon={Clock} />
        <StatCard label="Rejected landlords" value={stats.landlord_verification["rejected"] ?? 0} icon={XCircle} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top viewed */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5">
          <h3 className="font-semibold text-slate-900 text-sm mb-4 flex items-center gap-2">
            <Eye className="w-4 h-4 text-slate-400" /> Top viewed listings
          </h3>
          <div className="space-y-3">
            {stats.top_viewed.map((item, i) => (
              <div key={item.id} className="flex items-center gap-3">
                <span className="text-xs font-bold text-slate-300 w-4">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{item.title}</p>
                  <p className="text-xs text-slate-400 truncate">{item.address}</p>
                </div>
                <span className="text-sm font-bold text-slate-700">{item.views}</span>
              </div>
            ))}
            {stats.top_viewed.length === 0 && <p className="text-sm text-slate-400">No views recorded yet</p>}
          </div>
        </div>

        {/* Top rated */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5">
          <h3 className="font-semibold text-slate-900 text-sm mb-4 flex items-center gap-2">
            <Star className="w-4 h-4 text-slate-400" /> Top rated listings
          </h3>
          <div className="space-y-3">
            {stats.top_rated.map((item, i) => (
              <div key={item.id} className="flex items-center gap-3">
                <span className="text-xs font-bold text-slate-300 w-4">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{item.title}</p>
                  <p className="text-xs text-slate-400">{item.review_count} reviews</p>
                </div>
                <span className="text-sm font-bold text-amber-600">{item.avg_rating}★</span>
              </div>
            ))}
            {stats.top_rated.length === 0 && <p className="text-sm text-slate-400">No ratings yet</p>}
          </div>
        </div>
      </div>

      {/* Recent activity */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5">
        <h3 className="font-semibold text-slate-900 text-sm mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4 text-slate-400" /> Recent moderation activity
        </h3>
        <div className="space-y-2">
          {stats.recent_activity.map((log) => (
            <div key={log.id} className="flex items-center gap-3 py-2 border-b border-slate-50 last:border-0">
              <div className="w-2 h-2 rounded-full bg-slate-300 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="text-sm text-slate-700 font-medium capitalize">{log.action.replace(/_/g, " ")}</span>
                <span className="text-sm text-slate-400"> · {log.resource_type} #{log.resource_id}</span>
                {log.reason && <span className="text-xs text-slate-400"> · {log.reason}</span>}
              </div>
              <span className="text-xs text-slate-400 flex-shrink-0">
                {new Date(log.created_at).toLocaleDateString("en-ZA", { day: "numeric", month: "short" })}
              </span>
            </div>
          ))}
          {stats.recent_activity.length === 0 && <p className="text-sm text-slate-400">No activity yet</p>}
        </div>
      </div>
    </div>
  );
}

// ─── Universities Tab ─────────────────────────────────────────────────────────

function UniversitiesTab() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<number[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ name: "", domain: "", province: "", lat: "", lng: "" });
  const [submitting, setSubmitting] = useState(false);

  const { data: universities = [], isLoading } = useQuery({
    queryKey: ["admin-universities-tree"],
    queryFn: () => adminApi.getUniversitiesTree().then(r => r.data),
  });

  const toggle = (id: number) => setExpanded(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
  );

  const handleAdd = async () => {
    if (!form.name || !form.domain || !form.province || !form.lat || !form.lng) {
      toast.error("All fields required"); return;
    }
    setSubmitting(true);
    try {
      await adminApi.addUniversity({
        name: form.name,
        domain: form.domain,
        province: form.province,
        lat: Number(form.lat),
        lng: Number(form.lng),
      });
      toast.success(`${form.name} added successfully`);
      queryClient.invalidateQueries({ queryKey: ["admin-universities-tree"] });
      setAddOpen(false);
      setForm({ name: "", domain: "", province: "", lat: "", lng: "" });
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to add university"));
    } finally {
      setSubmitting(false);
    }
  };

  const STATUS_COLORS: Record<string, string> = {
    approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
    pending: "bg-amber-50 text-amber-700 border-amber-200",
    rejected: "bg-red-50 text-red-700 border-red-200",
  };

  const inputClass = "w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white";

  const PROVINCES = [
    "Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal",
    "Limpopo", "Mpumalanga", "Northern Cape", "North West", "Western Cape"
  ];

  if (isLoading) return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          onClick={() => setAddOpen(true)}
          className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl gap-2"
          size="sm"
        >
          <Plus className="w-4 h-4" /> Add university
        </Button>
      </div>

      {universities.map((uni: UniversityTree) => (
        <div key={uni.id} className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          {/* University row */}
          <button
            onClick={() => toggle(uni.id)}
            className="w-full flex items-center gap-3 p-4 hover:bg-slate-50 transition-colors text-left"
          >
            {expanded.includes(uni.id)
              ? <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
              : <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
            }
            <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center flex-shrink-0">
              <Building2 className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-slate-900 text-sm">{uni.name}</p>
              <p className="text-xs text-slate-400">{uni.domain} · {uni.province}</p>
            </div>
            <Badge className="bg-slate-100 text-slate-600 border-0 text-xs rounded-full">
              {uni.accommodation_count} accommodation{uni.accommodation_count !== 1 ? "s" : ""}
            </Badge>
          </button>

          {/* Accommodations list */}
          {expanded.includes(uni.id) && (
            <div className="border-t border-slate-100">
              {uni.accommodations.length === 0 ? (
                <p className="text-sm text-slate-400 px-6 py-4">No accommodations linked to this university yet.</p>
              ) : (
                uni.accommodations.map((acc) => (
                  <div
                    key={acc.id}
                    className="flex items-center gap-4 px-6 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => router.push(`/admin/accommodations/${acc.id}`)}
                  >
                    {/* Title */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-800 truncate">{acc.title}</p>
                      <p className="text-xs text-slate-400 flex items-center gap-1">
                        <MapPin className="w-3 h-3" />{acc.address}
                      </p>
                    </div>

                    {/* Landlord */}
                    <div className="hidden md:block w-40 flex-shrink-0">
                      <p className="text-xs text-slate-500 truncate">
                        {acc.landlord?.display_name ?? "Unknown"}
                      </p>
                      <p className="text-xs text-slate-400 capitalize">
                        {acc.landlord?.verification_status ?? "—"}
                      </p>
                    </div>

                    {/* Stats */}
                    <div className="hidden md:flex items-center gap-4 flex-shrink-0">
                      <span className="text-xs text-slate-500 flex items-center gap-1">
                        <Eye className="w-3 h-3" />{acc.total_views}
                      </span>
                      <span className="text-xs text-slate-500 flex items-center gap-1">
                        <Star className="w-3 h-3" />{acc.avg_rating?.toFixed(1) ?? "—"}
                      </span>
                    </div>

                    {/* Status */}
                    <Badge className={`text-xs border rounded-full px-2 py-0.5 flex-shrink-0 ${STATUS_COLORS[acc.status] ?? ""}`}>
                      {acc.status}
                    </Badge>

                    <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      ))}

      {/* Add university modal */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="rounded-2xl max-w-md bg-white">
          <DialogHeader>
            <DialogTitle>Add university</DialogTitle>
            <DialogDescription>Add a new partner university to the platform.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1.5 block">University name</label>
              <input className={inputClass} placeholder="e.g. University of Cape Town"
                value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Email domain</label>
              <input className={inputClass} placeholder="e.g. uct.ac.za"
                value={form.domain} onChange={e => setForm(f => ({ ...f, domain: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Province</label>
              <select className={`${inputClass} h-10`} value={form.province}
                onChange={e => setForm(f => ({ ...f, province: e.target.value }))}>
                <option value="">Select province</option>
                {PROVINCES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Latitude</label>
                <input className={inputClass} placeholder="-33.9579" type="number" step="any"
                  value={form.lat} onChange={e => setForm(f => ({ ...f, lat: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Longitude</label>
                <input className={inputClass} placeholder="18.4616" type="number" step="any"
                  value={form.lng} onChange={e => setForm(f => ({ ...f, lng: e.target.value }))} />
              </div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
              <p className="text-xs text-amber-700">
                💡 Use <a href="https://maps.google.com" target="_blank" className="underline font-medium">Google Maps</a> to find campus coordinates.
              </p>
            </div>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setAddOpen(false)} disabled={submitting}>
                Cancel
              </Button>
              <Button className="flex-1 rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
                onClick={handleAdd} disabled={submitting}>
                {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Adding...</> : "Add university"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── User Management Tab ──────────────────────────────────────────────────────

function UserManagementTab() {
  const queryClient = useQueryClient();
  const [subTab, setSubTab] = useState<"students" | "landlords" | "moderators">("students");
  const [createModOpen, setCreateModOpen] = useState(false);
  const [modForm, setModForm] = useState({ email: "", password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [studentSearch, setStudentSearch] = useState("");
  const [landlordSearch, setLandlordSearch] = useState("");
  const [moderatorSearch, setModeratorSearch] = useState("");

  const { data: students = [], isLoading: studentsLoading } = useQuery({
    queryKey: ["admin-students"],
    queryFn: () => adminApi.getStudents().then(r => r.data),
    enabled: subTab === "students",
  });

  const { data: landlords = [], isLoading: landlordsLoading } = useQuery({
    queryKey: ["admin-landlords"],
    queryFn: () => adminApi.getLandlords().then(r => r.data),
    enabled: subTab === "landlords",
  });

  const { data: moderators = [], isLoading: moderatorsLoading } = useQuery({
    queryKey: ["admin-moderators"],
    queryFn: () => adminApi.getModerators().then(r => r.data),
    enabled: subTab === "moderators",
  });

  const handleToggleUser = async (userId: number, isActive: boolean, name: string) => {
    setActionLoading(userId);
    try {
      if (isActive) {
        await adminApi.deactivateUser(userId);
        toast.success(`${name} deactivated`);
      } else {
        await adminApi.activateUser(userId);
        toast.success(`${name} activated`);
      }
      queryClient.invalidateQueries({ queryKey: ["admin-students"] });
      queryClient.invalidateQueries({ queryKey: ["admin-landlords"] });
      queryClient.invalidateQueries({ queryKey: ["admin-moderators"] });
    } catch {
      toast.error("Failed to update user status");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateModerator = async () => {
    if (!modForm.email || !modForm.password) { toast.error("Email and password required"); return; }
    setSubmitting(true);
    try {
      await adminApi.createModerator(modForm);
      toast.success(`Moderator ${modForm.email} created`);
      queryClient.invalidateQueries({ queryKey: ["admin-moderators"] });
      setCreateModOpen(false);
      setModForm({ email: "", password: "" });
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to create moderator"));
    } finally {
      setSubmitting(false);
    }
  };

  const filteredStudents = students.filter((s: Student) => {
    if (!studentSearch.trim()) return true;
    const q = studentSearch.toLowerCase().trim();
    return (
      s.email.toLowerCase().includes(q) ||
      s.first_name?.toLowerCase().includes(q) ||
      s.last_name?.toLowerCase().includes(q) ||
      s.student_number?.toLowerCase().includes(q) ||
      `${s.first_name} ${s.last_name}`.toLowerCase().includes(q)
    );
  });

  const filteredLandlords = landlords.filter((l: Landlord) => {
    if (!landlordSearch.trim()) return true;
    const q = landlordSearch.toLowerCase().trim();
    return (
      l.display_name.toLowerCase().includes(q) ||
      l.email.toLowerCase().includes(q)
    );
  });

  const filteredModerators = moderators.filter((m: Moderator) => {
    if (!moderatorSearch.trim()) return true;
    return m.email.toLowerCase().includes(moderatorSearch.toLowerCase().trim());
  });

  const inputClass = "w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white";

  return (
    <div className="space-y-4">
      {/* Sub tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
        {(["students", "landlords", "moderators"] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setSubTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
              subTab === tab ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Students */}
      {subTab === "students" && (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-900 text-sm flex-shrink-0">All students</h3>
            <div className="flex items-center gap-3 flex-1 justify-end">
              <input
                type="text"
                placeholder="Search by name, email, number..."
                value={studentSearch}
                onChange={e => setStudentSearch(e.target.value)}
                className="border border-slate-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white w-56"
              />
              <span className="text-xs text-slate-400 flex-shrink-0">{filteredStudents.length} total</span>
            </div>
          </div>
          {studentsLoading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-xl" />)}
            </div>
          ) : filteredStudents.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm text-slate-400">
                {studentSearch.trim() ? `No students match "${studentSearch}"` : "No students yet."}
              </p>
              {studentSearch.trim() && (
                <button onClick={() => setStudentSearch("")} className="text-xs text-slate-400 hover:text-slate-600 underline mt-1">
                  Clear search
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {filteredStudents.map((s: Student) => (
                <div key={s.id} className="flex items-center gap-4 px-5 py-3">
                  <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
                    <GraduationCap className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800">
                      {s.first_name && s.last_name ? `${s.first_name} ${s.last_name}` : s.email}
                    </p>
                    <p className="text-xs text-slate-400">{s.email} · {s.university}</p>
                  </div>
                  <div className="hidden md:flex items-center gap-4 text-xs text-slate-400">
                    <span>{s.review_count} reviews</span>
                    <span>{s.student_number ?? "No student number"}</span>
                  </div>
                  <Badge className={`text-xs border-0 rounded-full ${s.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                    {s.is_active ? "Active" : "Inactive"}
                  </Badge>
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-xl text-xs flex-shrink-0"
                    disabled={actionLoading === s.id}
                    onClick={() => handleToggleUser(s.id, s.is_active, s.email)}
                  >
                    {actionLoading === s.id ? <Loader2 className="w-3 h-3 animate-spin" /> : s.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Landlords */}
      {subTab === "landlords" && (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-900 text-sm flex-shrink-0">All landlords</h3>
            <div className="flex items-center gap-3 flex-1 justify-end">
              <input
                type="text"
                placeholder="Search by name or email..."
                value={landlordSearch}
                onChange={e => setLandlordSearch(e.target.value)}
                className="border border-slate-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white w-56"
              />
              <span className="text-xs text-slate-400 flex-shrink-0">{filteredLandlords.length} total</span>
            </div>
          </div>
          {landlordsLoading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-xl" />)}
            </div>
          ) : filteredLandlords.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm text-slate-400">
                {landlordSearch.trim() ? `No landlords match "${landlordSearch}"` : "No landlords yet."}
              </p>
              {landlordSearch.trim() && (
                <button onClick={() => setLandlordSearch("")} className="text-xs text-slate-400 hover:text-slate-600 underline mt-1">
                  Clear search
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {filteredLandlords.map((l: Landlord) => (
                <div key={l.id} className="flex items-center gap-4 px-5 py-3">
                  <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
                    <Home className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800">{l.display_name}</p>
                    <p className="text-xs text-slate-400">{l.email} · {l.listing_count} listings</p>
                  </div>
                  <Badge className={`text-xs border rounded-full px-2 py-0.5 flex-shrink-0 ${
                    l.verification_status === "verified" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                    l.verification_status === "pending" ? "bg-amber-50 text-amber-700 border-amber-200" :
                    l.verification_status === "rejected" ? "bg-red-50 text-red-700 border-red-200" :
                    "bg-slate-100 text-slate-600 border-slate-200"
                  }`}>
                    {l.verification_status}
                  </Badge>
                  <Badge className={`text-xs border-0 rounded-full ${l.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                    {l.is_active ? "Active" : "Inactive"}
                  </Badge>
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-xl text-xs flex-shrink-0"
                    disabled={actionLoading === l.id}
                    onClick={() => handleToggleUser(l.id, l.is_active, l.display_name)}
                  >
                    {actionLoading === l.id ? <Loader2 className="w-3 h-3 animate-spin" /> : l.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Moderators */}
      {subTab === "moderators" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button
              onClick={() => setCreateModOpen(true)}
              className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl gap-2"
              size="sm"
            >
              <Plus className="w-4 h-4" /> Create moderator
            </Button>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
              <h3 className="font-semibold text-slate-900 text-sm flex-shrink-0">All moderators</h3>
              <div className="flex items-center gap-3 flex-1 justify-end">
                <input
                  type="text"
                  placeholder="Search by email..."
                  value={moderatorSearch}
                  onChange={e => setModeratorSearch(e.target.value)}
                  className="border border-slate-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white w-56"
                />
                <span className="text-xs text-slate-400 flex-shrink-0">{filteredModerators.length} total</span>
              </div>
            </div>
            {moderatorsLoading ? (
              <div className="p-4 space-y-3">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-xl" />)}
              </div>
            ) : filteredModerators.length === 0 ? (
              <div className="px-5 py-10 text-center">
                <p className="text-sm text-slate-400">
                  {moderatorSearch.trim() ? `No moderators match "${moderatorSearch}"` : "No moderators yet."}
                </p>
                {moderatorSearch.trim() && (
                  <button onClick={() => setModeratorSearch("")} className="text-xs text-slate-400 hover:text-slate-600 underline mt-1">
                    Clear search
                  </button>
                )}
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {filteredModerators.map((m: Moderator) => (
                  <div key={m.id} className="flex items-center gap-4 px-5 py-3">
                    <div className="w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center flex-shrink-0">
                      <ShieldCheck className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-800">{m.email}</p>
                      <p className="text-xs text-slate-400">{m.actions_count} actions logged · Joined {new Date(m.joined).toLocaleDateString("en-ZA", { month: "short", year: "numeric" })}</p>
                    </div>
                    <Badge className={`text-xs border-0 rounded-full ${m.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                      {m.is_active ? "Active" : "Inactive"}
                    </Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      className="rounded-xl text-xs flex-shrink-0"
                      disabled={actionLoading === m.id}
                      onClick={() => handleToggleUser(m.id, m.is_active, m.email)}
                    >
                      {actionLoading === m.id ? <Loader2 className="w-3 h-3 animate-spin" /> : m.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create moderator modal */}
      <Dialog open={createModOpen} onOpenChange={setCreateModOpen}>
        <DialogContent className="rounded-2xl max-w-sm bg-white">
          <DialogHeader>
            <DialogTitle>Create moderator</DialogTitle>
            <DialogDescription>New moderator will be able to review listings and flagged content.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Email</label>
              <input className={inputClass} placeholder="mod@accomfind.co.za" type="email"
                value={modForm.email} onChange={e => setModForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600 mb-1.5 block">Password</label>
              <input className={inputClass} placeholder="Minimum 8 characters" type="password"
                value={modForm.password} onChange={e => setModForm(f => ({ ...f, password: e.target.value }))} />
            </div>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setCreateModOpen(false)} disabled={submitting}>
                Cancel
              </Button>
              <Button className="flex-1 rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
                onClick={handleCreateModerator} disabled={submitting}>
                {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Creating...</> : "Create"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  traffic: Eye,
  users: Users,
  listings: Building2,
  reviews: Star,
  nlp: TrendingUp,
  verification: ShieldCheck,
  moderation: Activity,
};

function MetricCard({ label, value, breakdown }: { label: string; value: number; breakdown?: Record<string, unknown> | null }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-xl font-bold text-slate-900">{typeof value === "number" ? value.toLocaleString() : value}</p>
      {breakdown && Object.keys(breakdown).length > 0 && (
        <div className="mt-2 space-y-1">
          {Object.entries(breakdown).filter(([k]) => !["accommodation_id", "title"].includes(k)).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between">
              <span className="text-xs text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
              <span className="text-xs font-semibold text-slate-700">{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ReportDetailView({ reportId, onBack }: { reportId: number; onBack: () => void }) {
  const { data: report, isLoading } = useQuery<ReportDetail>({
    queryKey: ["admin-report", reportId],
    queryFn: () => reportsApi.get(reportId).then(r => r.data),
  });

   const { data: trendData = [] } = useQuery({
  queryKey: ["accommodation-trend", report?.entity_id],
  queryFn: () => reportsApi.getAccommodationTrend(report!.entity_id!).then(r => r.data),
  enabled: !!report && !report.document && report.report_type === "accommodation" && !!report.entity_id,
});

  if (isLoading) return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48 rounded-xl" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
    </div>
  );

  if (!report) return null;

  if (report.document) return <div className="space-y-4">
    <button onClick={onBack} className="text-sm text-slate-500 hover:text-slate-800">Back to reports</button>
    <ManagementReport reportId={reportId} report={report.document} />
  </div>;

  const periodLabel = `${MONTH_NAMES[report.period_month - 1]} ${report.period_year}`;



  return (
    <>
      <div className="space-y-6">
        {/* Saved report toolbar */}
        <div className="flex items-center justify-between no-print">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ChevronRight className="w-4 h-4 rotate-180" /> Back to reports
          </button>
          <ReportDownloadButton reportId={reportId} />
        </div>

        {/* Legacy report content */}
        <div className="space-y-8">
          {/* Header */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">AccomFind Platform Report</p>
                <h2 className="text-xl font-bold text-slate-900 capitalize">
                  {report.report_type.replace(/_/g, " ")}
                  {report.entity_name && (
                    <span className="text-slate-500 font-normal"> — {report.entity_name}</span>
                  )}
                </h2>
                <p className="text-sm text-slate-500 mt-1 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5" /> {periodLabel}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-400">Generated</p>
                <p className="text-sm font-medium text-slate-700">
                  {new Date(report.generated_at).toLocaleDateString("en-ZA", {
                    day: "numeric", month: "long", year: "numeric"
                  })}
                </p>
                <Badge className="mt-1 text-xs bg-emerald-50 text-emerald-700 border-0 rounded-full">
                  {report.status}
                </Badge>
              </div>
            </div>
          </div>

          {/* Metric categories */}
          {Object.entries(report.metrics).map(([category, metrics]) => {
            const Icon = CATEGORY_ICONS[category] ?? FileText;
            return (
              <div key={category} className="space-y-3">
                <h3 className="font-semibold text-slate-900 text-sm flex items-center gap-2 capitalize">
                  <Icon className="w-4 h-4 text-slate-400" />
                  {category.replace(/_/g, " ")}
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {metrics.map(m => (
                    <MetricCard key={m.key} label={m.label} value={m.value} breakdown={m.breakdown} />
                  ))}
                </div>
              </div>
            );
          })}
          {/* Trend chart — only for accommodation reports */}
          {report.report_type === "accommodation" && report.entity_id && (
            <div className="bg-white border border-slate-200 rounded-2xl p-5">
              <h3 className="font-semibold text-slate-900 text-sm mb-4 flex items-center gap-2">
                <Eye className="w-4 h-4 text-slate-400" /> Views — last 6 months
              </h3>
              {trendData.length === 0 ? (
                <div className="h-36 flex items-center justify-center">
                  <p className="text-xs text-slate-400 text-center">
                    No trend data yet — generate more monthly reports to build history.
                  </p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={144}>
                  <LineChart data={trendData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <XAxis dataKey="month_label" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: "#1e293b", border: "none", borderRadius: "8px", fontSize: "12px", color: "#f8fafc" }}
                      formatter={(value) => [value ?? 0, "Views"]}
                    />
                    <Line type="monotone" dataKey="views" stroke="#1e293b" strokeWidth={2} dot={{ fill: "#1e293b", r: 3 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
function AccommodationReportGenerator({ onGenerate, generating }: { onGenerate: (id: number) => void; generating: boolean }) {
  const [selectedId, setSelectedId] = useState<number | "">("");

  const { data: universities = [] } = useQuery({
    queryKey: ["admin-universities-tree"],
    queryFn: () => adminApi.getUniversitiesTree().then(r => r.data),
  });

  const allAccommodations = (universities as UniversityTree[]).flatMap(u => u.accommodations);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5">
      <h3 className="font-semibold text-slate-900 text-sm mb-1">Accommodation report</h3>
      <p className="text-xs text-slate-400 mb-4">Generate a report for a specific listing this month.</p>
      <div className="flex gap-2">
        <select
          value={selectedId}
          onChange={e => setSelectedId(e.target.value === "" ? "" : Number(e.target.value))}
          className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white min-w-0"
        >
          <option value="">Select accommodation</option>
          {allAccommodations.map(acc => (
            <option key={acc.id} value={acc.id}>{acc.title}</option>
          ))}
        </select>
        <Button
          size="sm"
          className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl gap-2 flex-shrink-0"
          disabled={generating || selectedId === ""}
          onClick={() => selectedId !== "" && onGenerate(Number(selectedId))}
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Generate
        </Button>
      </div>
    </div>
  );
}

function UniversityReportGenerator({ onGenerate, generating }: { onGenerate: (id: number) => void; generating: boolean }) {
  const [selectedId, setSelectedId] = useState<number | "">("");

  const { data: universities = [] } = useQuery({
    queryKey: ["admin-universities-tree"],
    queryFn: () => adminApi.getUniversitiesTree().then(r => r.data),
  });

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5">
      <h3 className="font-semibold text-slate-900 text-sm mb-1">University report</h3>
      <p className="text-xs text-slate-400 mb-4">Generate a report for a specific university this month.</p>
      <div className="flex gap-2">
        <select
          value={selectedId}
          onChange={e => setSelectedId(e.target.value === "" ? "" : Number(e.target.value))}
          className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white min-w-0"
        >
          <option value="">Select university</option>
          {(universities as UniversityTree[]).map(u => (
            <option key={u.id} value={u.id}>{u.name}</option>
          ))}
        </select>
        <Button
          size="sm"
          className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl gap-2 flex-shrink-0"
          disabled={generating || selectedId === ""}
          onClick={() => selectedId !== "" && onGenerate(Number(selectedId))}
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Generate
        </Button>
      </div>
    </div>
  );
}

function ReportsTab() {
  const queryClient = useQueryClient();
  const now = new Date();
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const TYPE_LABELS: Record<string, string> = {
    platform_summary: "Platform Summary",
    accommodation: "Accommodation",
    university: "University",
  };

  const { data: reports = [], isLoading } = useQuery<Report[]>({
    queryKey: ["admin-reports", filterType],
    queryFn: () => reportsApi.list(filterType !== "all" ? { report_type: filterType } : undefined).then(r => r.data),
  });

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await reportsApi.generate({
        report_type: "platform_summary",
        year: now.getFullYear(),
        month: now.getMonth() + 1,
      });
      toast.success("Platform summary report generated");
      queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to generate report"));
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateAccommodation = async (accommodationId: number) => {
  setGenerating(true);
  try {
    await reportsApi.generate({
      report_type: "accommodation",
      year: now.getFullYear(),
      month: now.getMonth() + 1,
      entity_id: accommodationId,
    });
    toast.success("Accommodation report generated");
    queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
  } catch (err: unknown) {
    toast.error(getApiErrorMessage(err, "Failed to generate report"));
  } finally {
    setGenerating(false);
  }
};

  const handleGenerateUniversity = async (universityId: number) => {
    setGenerating(true);
    try {
      await reportsApi.generate({
        report_type: "university",
        year: now.getFullYear(),
        month: now.getMonth() + 1,
        entity_id: universityId,
      });
      toast.success("University report generated");
      queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to generate report"));
    } finally {
      setGenerating(false);
    }
  };

  const filteredReports = reports.filter(r => {
  if (!searchQuery.trim()) return true;
  const q = searchQuery.toLowerCase().trim();
  return (
    r.entity_name?.toLowerCase().includes(q) ||
    MONTH_NAMES[r.period_month - 1].toLowerCase().includes(q) ||
    String(r.period_year).includes(q) ||
    TYPE_LABELS[r.report_type]?.toLowerCase().includes(q)
  );
});

  if (selectedReportId !== null) {
    return <ReportDetailView reportId={selectedReportId} onBack={() => setSelectedReportId(null)} />;
  }

  

  return (
    <div className="space-y-6">
      {/* Actions bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Platform reports</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Current period: {MONTH_NAMES[now.getMonth()]} {now.getFullYear()}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white"
          >
            <option value="all">All types</option>
            <option value="platform_summary">Platform summary</option>
            <option value="accommodation">Accommodation</option>
            <option value="university">University</option>
          </select>

          <Button
            size="sm"
            className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl gap-2"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
              : <><RefreshCw className="w-4 h-4" /> Generate platform report</>
            }
          </Button>
        </div>
        
      </div>

      {/* Entity report generators */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <AccommodationReportGenerator onGenerate={handleGenerateAccommodation} generating={generating} />
        <UniversityReportGenerator onGenerate={handleGenerateUniversity} generating={generating} />
      </div>

      {/* Reports table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
          <h3 className="font-semibold text-slate-900 text-sm flex items-center gap-2 flex-shrink-0">
            <FileText className="w-4 h-4 text-slate-400" /> Report history
          </h3>
          <div className="flex items-center gap-3 flex-1 justify-end">
            <input
              type="text"
              placeholder="Search by name, month, year..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="border border-slate-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white w-56"
            />
            <span className="text-xs text-slate-400 flex-shrink-0">{filteredReports.length} reports</span>
          </div>
        </div>

        {isLoading ? (
        <div className="p-4 space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-xl" />)}
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="px-5 py-12 text-center">
          <FileText className="w-8 h-8 text-slate-200 mx-auto mb-3" />
          {searchQuery.trim() ? (
            <>
              <p className="text-sm text-slate-400">No reports match &quot;{searchQuery}&quot;</p>
              <button
                onClick={() => setSearchQuery("")}
                className="text-xs text-slate-400 hover:text-slate-600 underline mt-2"
              >
                Clear search
              </button>
            </>
          ) : (
            <>
              <p className="text-sm text-slate-400">No reports generated yet.</p>
              <p className="text-xs text-slate-300 mt-1">Click &quot;Generate platform report&quot; to create the first one.</p>
            </>
          )}
        </div>
      ) : (
        <div className="divide-y divide-slate-50">
          {filteredReports.map((r: Report) => (
            <div
              key={r.id}
              className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 cursor-pointer transition-colors"
              onClick={() => setSelectedReportId(r.id)}
            >
              <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                <FileText className="w-4 h-4 text-slate-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800">
                  {TYPE_LABELS[r.report_type] ?? r.report_type}
                  {r.entity_name && ` — ${r.entity_name}`}
                  {" "}· {MONTH_NAMES[r.period_month - 1]} {r.period_year}
                </p>
                <p className="text-xs text-slate-400">
                  Generated {new Date(r.generated_at).toLocaleDateString("en-ZA", {
                    day: "numeric", month: "short", year: "numeric"
                  })}
                </p>
              </div>
              <Badge className={`text-xs border rounded-full px-2 py-0.5 flex-shrink-0 ${
                r.status === "complete"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : r.status === "generating"
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : "bg-red-50 text-red-700 border-red-200"
              }`}>
                {r.status}
              </Badge>
              <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}

const ACTION_CONFIG: Record<string, { label: string; color: string }> = {
  approve_listing:                  { label: "Approved listing",       color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  reject_listing:                   { label: "Rejected listing",       color: "bg-red-50 text-red-700 border-red-200" },
  remove_review:                    { label: "Removed review",         color: "bg-red-50 text-red-700 border-red-200" },
  released:                         { label: "Released review",        color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  landlord_verified:                { label: "Verified landlord",      color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  landlord_verification_rejected:   { label: "Rejected verification",  color: "bg-red-50 text-red-700 border-red-200" },
  quarantined: { label: "Automatic quarantine", color: "bg-amber-50 text-amber-700 border-amber-200" },
  appeal_upheld:                    { label: "Appeal upheld",          color: "bg-blue-50 text-blue-700 border-blue-200" },
  appeal_dismissed:                 { label: "Appeal dismissed",       color: "bg-slate-100 text-slate-600 border-slate-200" },
};

function ModerationLogModal({ entry, onClose }: { entry: ModerationLogEntry; onClose: () => void }) {
  const cfg = ACTION_CONFIG[entry.action] ?? { label: entry.action.replace(/_/g, " "), color: "bg-slate-100 text-slate-600 border-slate-200" };
  const d = entry.resource_detail;

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="rounded-2xl max-w-lg bg-white">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Badge className={`text-xs border rounded-full px-2 py-0.5 capitalize ${cfg.color}`}>
              {cfg.label}
            </Badge>
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            By {entry.moderator_email} · {new Date(entry.created_at).toLocaleDateString("en-ZA", {
              day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit"
            })}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">

          {/* Accommodation detail */}
          {entry.resource_type === "accommodation" && d.title && (
            <div className="bg-slate-50 rounded-xl p-4 space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Listing</p>
              <p className="text-sm font-semibold text-slate-900">{d.title}</p>
              {d.address && <p className="text-xs text-slate-500 flex items-center gap-1"><MapPin className="w-3 h-3" />{d.address}</p>}
              {d.landlord_name && (
                <div className="pt-1 border-t border-slate-200">
                  <p className="text-xs text-slate-400">Landlord</p>
                  <p className="text-sm text-slate-700 font-medium">{d.landlord_name}</p>
                  {d.landlord_phone && <p className="text-xs text-slate-400">{d.landlord_phone}</p>}
                </div>
              )}
            </div>
          )}

          {/* Review detail */}
          {entry.resource_type === "review" && d.body && (
            <div className="bg-slate-50 rounded-xl p-4 space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Review</p>
              {d.student_name && <p className="text-xs text-slate-500">By {d.student_name}</p>}
              {d.rating && (
                <div className="flex items-center gap-1">
                  {[1,2,3,4,5].map(i => (
                    <Star key={i} className={`w-3.5 h-3.5 ${i <= (d.rating ?? 0) ? "fill-amber-400 text-amber-400" : "text-slate-200"}`} />
                  ))}
                </div>
              )}
              <p className="text-sm text-slate-700 leading-relaxed">{d.body}</p>
              {d.status && (
                <Badge className="text-xs bg-slate-100 text-slate-500 border-0 rounded-full capitalize">
                  {d.status}
                </Badge>
              )}
            </div>
          )}

          {/* Landlord detail */}
          {entry.resource_type === "landlord" && d.display_name && (
            <div className="bg-slate-50 rounded-xl p-4 space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Landlord</p>
              <p className="text-sm font-semibold text-slate-900">{d.display_name}</p>
              {d.verification_status && (
                <Badge className={`text-xs border rounded-full capitalize ${
                  d.verification_status === "verified" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                  d.verification_status === "rejected" ? "bg-red-50 text-red-700 border-red-200" :
                  "bg-slate-100 text-slate-600 border-slate-200"
                }`}>
                  {d.verification_status}
                </Badge>
              )}
            </div>
          )}

          {/* Reason */}
          {entry.reason && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Reason / Notes</p>
              <p className="text-sm text-slate-700 bg-amber-50 border border-amber-100 rounded-xl p-3 leading-relaxed">
                {entry.reason}
              </p>
            </div>
          )}

          {/* Resource reference */}
          <div className="flex items-center justify-between text-xs text-slate-400 pt-1 border-t border-slate-100">
            <span className="capitalize">{entry.resource_type} #{entry.resource_id}</span>
            <span>Log entry #{entry.id}</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ModerationTab() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<ModerationLogEntry | null>(null);

  const { data, isLoading } = useQuery<ModerationLogResponse>({
    queryKey: ["moderation-log", page],
    queryFn: () => moderationApi.getModerationLog(page).then(r => r.data),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  const filtered = items.filter(entry => {
    if (!search.trim()) return true;
    const q = search.toLowerCase().trim();
    const d = entry.resource_detail;
    return (
      entry.moderator_email.toLowerCase().includes(q) ||
      entry.action.replace(/_/g, " ").toLowerCase().includes(q) ||
      entry.resource_type.toLowerCase().includes(q) ||
      d.title?.toLowerCase().includes(q) ||
      d.display_name?.toLowerCase().includes(q) ||
      d.student_name?.toLowerCase().includes(q) ||
      d.body?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <FlaggedReviewQueue />

      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Moderation audit log</h2>
          <p className="text-xs text-slate-400 mt-0.5">{total} total actions recorded</p>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="rounded-xl gap-2"
          onClick={() => window.open("/moderation", "_blank")}
        >
          <ShieldCheck className="w-4 h-4" /> Open moderation panel
        </Button>
      </div>

      {/* Log table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
          <h3 className="font-semibold text-slate-900 text-sm flex-shrink-0 flex items-center gap-2">
            <Activity className="w-4 h-4 text-slate-400" /> Activity
          </h3>
          <div className="flex items-center gap-3 flex-1 justify-end">
            <input
              type="text"
              placeholder="Search by moderator, action, listing..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="border border-slate-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white w-64"
            />
            <span className="text-xs text-slate-400 flex-shrink-0">{filtered.length} shown</span>
          </div>
        </div>

        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14 rounded-xl" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Activity className="w-8 h-8 text-slate-200 mx-auto mb-3" />
            <p className="text-sm text-slate-400">
              {search.trim() ? `No entries match "${search}"` : "No moderation activity yet."}
            </p>
            {search.trim() && (
              <button onClick={() => setSearch("")} className="text-xs text-slate-400 hover:text-slate-600 underline mt-1">
                Clear search
              </button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-slate-50">
            {filtered.map(entry => {
              const cfg = ACTION_CONFIG[entry.action] ?? { label: entry.action.replace(/_/g, " "), color: "bg-slate-100 text-slate-600 border-slate-200" };
              const d = entry.resource_detail;
              const resourceName = d.title ?? d.display_name ?? d.student_name ?? `${entry.resource_type} #${entry.resource_id}`;

              return (
                <div
                  key={entry.id}
                  className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => setSelectedEntry(entry)}
                >
                  {/* Moderator avatar */}
                  <div className="w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-white">
                      {entry.moderator_email[0].toUpperCase()}
                    </span>
                  </div>

                  {/* Main info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-slate-800 truncate">
                        {entry.moderator_email}
                      </p>
                      <Badge className={`text-xs border rounded-full px-2 py-0.5 flex-shrink-0 capitalize ${cfg.color}`}>
                        {cfg.label}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-400 truncate mt-0.5">
                      <span className="capitalize">{entry.resource_type}</span>
                      {" · "}{resourceName}
                      {entry.reason && <span className="text-slate-300"> · {entry.reason}</span>}
                    </p>
                  </div>

                  {/* Timestamp */}
                  <span className="text-xs text-slate-400 flex-shrink-0 hidden md:block">
                    {new Date(entry.created_at).toLocaleDateString("en-ZA", {
                      day: "numeric", month: "short", year: "numeric"
                    })}
                  </span>

                  <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && !search.trim() && (
          <div className="flex items-center justify-center gap-2 px-5 py-4 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-xl gap-1.5"
            >
              <ChevronLeft className="w-4 h-4" /> Previous
            </Button>
            <span className="text-sm text-slate-500 px-3">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="rounded-xl gap-1.5"
            >
              Next <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Detail modal */}
      {selectedEntry && (
        <ModerationLogModal
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
        />
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { user, loading, isAdmin } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"overview" | "universities" | "users" | "moderation" | "reports">("overview");

  useEffect(() => {
    if (!loading && !user) router.push("/login?redirect=/admin");
    if (!loading && user && !isAdmin) router.push("/");
  }, [user, loading, isAdmin, router]);

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

  const TABS = [
    { id: "overview", label: "Overview", icon: BarChart2 },
    { id: "universities", label: "Universities", icon: Building2 },
    { id: "users", label: "User management", icon: Users },
    { id: "moderation", label: "Moderation", icon: ShieldCheck },
    { id: "reports", label: "Reports", icon: FileText },
  ] as const;

  return (
    <PageLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
            <p className="text-sm text-slate-500">Platform management and analytics</p>
            <button onClick={() => router.push("/moderation")} className="text-sm text-blue-600 hover:underline">Review moderation and appeals</button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit mb-8 flex-wrap">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
              {id === "moderation" && <FlaggedReviewCount />}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "overview" && <OverviewTab />}
        {activeTab === "universities" && <UniversitiesTab />}
        {activeTab === "users" && <UserManagementTab />}
        {activeTab === "moderation" && <ModerationTab />}
        {activeTab === "reports" && <ReportsTab />}
      </div>
    </PageLayout>
  );
}
