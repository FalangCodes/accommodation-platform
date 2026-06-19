"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "@/lib/api";
import PageLayout from "@/components/page-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  ShieldCheck, Loader2, Users, Home, Star, Eye, TrendingUp,
  Building2, ChevronDown, ChevronRight, MapPin, Globe,
  CheckCircle, XCircle, Clock, AlertTriangle, Plus,
  GraduationCap, UserCheck, UserX, BarChart2, Activity,
} from "lucide-react";
import { toast } from "sonner";

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

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({ label, value, icon: Icon, sub }: { label: string; value: string | number; icon: any; sub?: string }) {
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
  const { data: stats, isLoading } = useQuery({
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
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Failed to add university");
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
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Failed to create moderator");
    } finally {
      setSubmitting(false);
    }
  };

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
          <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 text-sm">All students</h3>
            <span className="text-xs text-slate-400">{students.length} total</span>
          </div>
          {studentsLoading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-xl" />)}
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {students.map((s: Student) => (
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
          <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 text-sm">All landlords</h3>
            <span className="text-xs text-slate-400">{landlords.length} total</span>
          </div>
          {landlordsLoading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-xl" />)}
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {landlords.map((l: Landlord) => (
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
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-sm">All moderators</h3>
              <span className="text-xs text-slate-400">{moderators.length} total</span>
            </div>
            {moderatorsLoading ? (
              <div className="p-4 space-y-3">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-xl" />)}
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {moderators.map((m: Moderator) => (
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

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { user, loading, isAdmin } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"overview" | "universities" | "users" | "moderation">("overview");

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

  const TABS = [
    { id: "overview", label: "Overview", icon: BarChart2 },
    { id: "universities", label: "Universities", icon: Building2 },
    { id: "users", label: "User management", icon: Users },
    { id: "moderation", label: "Moderation", icon: ShieldCheck },
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
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "overview" && <OverviewTab />}
        {activeTab === "universities" && <UniversitiesTab />}
        {activeTab === "users" && <UserManagementTab />}
        {activeTab === "moderation" && (
          <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center">
            <ShieldCheck className="w-8 h-8 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm mb-4">Full moderation panel is available at the dedicated moderation page.</p>
            <Button
              onClick={() => router.push("/moderation")}
              className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl"
            >
              Go to moderation panel
            </Button>
          </div>
        )}
      </div>
    </PageLayout>
  );
}