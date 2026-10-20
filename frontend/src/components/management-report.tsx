"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import Link from "next/link";
import { reportsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Download, FileText, Loader2 } from "lucide-react";
import { Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { toast } from "sonner";

interface Action {
  priority: string; priority_label?: string; title: string; evidence: string; action: string; owner: string; success_measure: string;
}
export interface ManagementDocument {
  version: number; title: string; audience: string; generated_at: string;
  property_address?: string;
  property_profile?: { label: string; value: string }[];
  period: { label: string; partial?: boolean; cutoff?: string; comparison_label?: string };
  summary: string[];
  kpis: { key: string; label: string; value: number | null; comparison?: { previous: number | null; delta: number | null; percent: number | null; label: string; unit?: string } }[];
  view_history: { month_label: string; views: number; cumulative: number }[];
  sentiment: { counts: Record<string, number>; classified: number; published: number };
  ratings: Record<string, number>;
  topics: { name: string; mentions: number; positive: number; negative: number; neutral: number; unclassified: number; priority: string; priority_label?: string; evidence: string }[];
  actions: Action[]; strengths: string[]; operations: { label: string; value: number | string }[];
  listing_priorities: { id: number; title: string; views: number; reviews: number; negative: number; rating: number | null; status: string; reason: string }[];
  data_quality: string[];
  campus_coverage?: { name: string; approved_listings: number; verified_students: number }[];
}

export function ReportDownloadButton({ reportId }: { reportId: number }) {
  const [busy, setBusy] = useState(false);
  async function download() {
    if (busy) return;
    setBusy(true);
    try {
      const response = await reportsApi.download(reportId);
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      const filename = String(response.headers["content-disposition"] ?? "").match(/filename="([^"]+)"/)?.[1];
      link.download = filename || `accomfind-report-${reportId}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      toast.error("The PDF could not be downloaded. Please try again.");
    } finally { setBusy(false); }
  }
  return <Button size="sm" disabled={busy} onClick={download} className="rounded-xl gap-2">
    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />} Download report PDF
  </Button>;
}

export function ManagementReport({ reportId, report }: { reportId: number; report: ManagementDocument }) {
  const [cumulative, setCumulative] = useState(false);
  return <div className="space-y-6">
    <header className="bg-white border border-slate-200 rounded-2xl p-6 flex flex-wrap justify-between gap-4">
      <div><p className="text-xs font-bold uppercase tracking-wide text-[#1f4e79]">AccomFind management report</p>
        <h2 className="text-2xl font-bold text-slate-900 mt-2">{report.title}</h2>
        {report.property_address && <p className="text-sm text-slate-500 mt-1">{report.property_address}</p>}
        {!!report.property_profile?.length && <p className="text-xs text-slate-500 mt-2">Current profile: {report.property_profile.map(item => `${item.label}: ${item.value}`).join(" · ")}</p>}
        <p className="text-sm text-slate-500 mt-2">{report.period.label}{report.period.partial ? " · Month to date" : " · Calendar month"} · Saved {new Date(report.generated_at).toLocaleDateString("en-ZA")}</p>
        <p className="text-xs text-slate-500 mt-1">Prepared for {report.audience}</p></div>
      <ReportDownloadButton reportId={reportId} />
    </header>
    <section className="bg-blue-50 border border-blue-100 rounded-2xl p-6">
      <h3 className="font-semibold text-slate-900 mb-3">Executive assessment</h3>
      <div className="space-y-3">{report.summary.map((text, index) => <p key={index} className="text-sm text-slate-700 leading-relaxed">{text}</p>)}</div>
    </section>
    <section><h3 className="font-semibold text-slate-900 mb-3">Performance overview</h3>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{report.kpis.map(metric => <div key={metric.key} className="bg-white border border-slate-200 rounded-xl p-4">
        <p className="text-xs text-slate-500">{metric.label}</p><p className="text-2xl font-bold text-slate-900 mt-2">{metric.value === null ? "Not enough data" : metric.value.toLocaleString("en-ZA", { maximumFractionDigits: 2 })}</p>
        {metric.comparison && <p className="text-xs text-slate-500 mt-2">{metric.comparison.delta === null ? "No comparable rating sample" : `${metric.comparison.delta >= 0 ? "+" : ""}${metric.comparison.delta}${metric.comparison.unit ? ` ${metric.comparison.unit}` : metric.comparison.percent === null ? " · no percentage baseline" : ` (${metric.comparison.percent >= 0 ? "+" : ""}${metric.comparison.percent}%)`}`}<br />{metric.comparison.label}</p>}
      </div>)}</div>
    </section>
    {report.view_history.length > 0 && <section className="bg-white border border-slate-200 rounded-2xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4"><h3 className="font-semibold text-slate-900">Recorded visibility over time</h3>
        <Button size="sm" variant="outline" onClick={() => setCumulative(!cumulative)}>{cumulative ? "Show monthly views" : "Show cumulative views"}</Button></div>
      <ResponsiveContainer width="100%" height={230}><LineChart data={report.view_history} margin={{ left: 0, right: 12 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month_label" tick={{ fontSize: 11 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip formatter={value => [value ?? 0, cumulative ? "Cumulative page views" : "Monthly page views"]} />
        <Line type="linear" dataKey={cumulative ? "cumulative" : "views"} stroke="#1f4e79" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart></ResponsiveContainer>
      <p className="text-xs text-slate-500 mt-3">Recorded page views, including repeat visits. Unflushed views are excluded; month assignment uses the database flush date.</p>
    </section>}
    <div className="grid md:grid-cols-2 gap-4">
      <section className="bg-white border border-slate-200 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-4">Overall review sentiment</h3>
        {Object.entries(report.sentiment.counts).map(([label, count]) => <div key={label} className="mb-3"><div className="flex justify-between text-sm capitalize mb-1"><span>{label}</span><span>{count} {count === 1 ? "review" : "reviews"}{report.sentiment.classified ? ` · ${Math.round(count / report.sentiment.classified * 100)}%` : ""}</span></div><div className="bg-slate-100 h-2 rounded-full"><div className="bg-[#1f4e79] h-2 rounded-full" style={{ width: `${report.sentiment.classified ? count / report.sentiment.classified * 100 : 0}%` }} /></div></div>)}
        <p className="text-xs text-slate-500">Published reviews: {report.sentiment.published} · Recognised sentiment results: {report.sentiment.classified}.</p>
      </section>
      <section className="bg-white border border-slate-200 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-4">Rating distribution</h3>
        {Object.entries(report.ratings).map(([rating, count]) => <div key={rating} className="flex items-center gap-3 mb-3 text-sm"><span className="w-12">{rating} {rating === "1" ? "star" : "stars"}</span><div className="flex-1 bg-slate-100 h-2 rounded-full"><div className="bg-amber-500 h-2 rounded-full" style={{ width: `${report.sentiment.published ? count / report.sentiment.published * 100 : 0}%` }} /></div><span>{count}</span></div>)}
      </section>
    </div>
    {report.topics.length > 0 && <section className="bg-white border border-slate-200 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-3">Topics behind the feedback</h3>
      <p className="text-xs text-slate-500 mb-4">Whole-review sentiment among reviews mentioning a topic, rather than an independent score for that topic.</p>
      <div className="grid sm:grid-cols-2 gap-3">{report.topics.map(topic => <div key={topic.name} className="border border-slate-200 rounded-xl p-4"><h4 className="font-medium text-sm">{topic.name}</h4><p className="text-sm text-slate-600 mt-2">{topic.evidence}</p><p className="text-xs text-slate-500 mt-2">{topic.positive} positive · {topic.neutral} neutral{topic.unclassified ? ` · ${topic.unclassified} unclassified` : ""} · {topic.priority_label ?? `${topic.priority} investigation priority`}</p></div>)}</div>
    </section>}
    <section><h3 className="font-semibold text-slate-900 mb-3">Prioritised action plan</h3><div className="space-y-3">{report.actions.map((action, index) => <article key={index} className="bg-white border border-slate-200 rounded-xl p-5">
      <p className="text-xs font-semibold text-[#1f4e79]">{action.priority_label ?? `${action.priority} priority`} · {action.owner}</p><h4 className="font-semibold text-slate-900 mt-2">{action.title}</h4><p className="text-sm text-slate-600 mt-2">{action.evidence}</p><p className="text-sm text-slate-800 mt-3">{action.action}</p><p className="text-xs text-slate-500 mt-3"><strong>Follow-up measure:</strong> {action.success_measure}</p>
    </article>)}</div></section>
    {report.strengths.length > 0 && <section className="bg-emerald-50 border border-emerald-100 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-3">Strengths to preserve</h3>{report.strengths.map((text, index) => <p key={index} className="text-sm text-slate-700 mb-3">{text}</p>)}</section>}
    {report.operations.length > 0 && <section className="bg-white border border-slate-200 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-3">Operational context · Current at generation</h3>{report.operations.map(item => <div key={item.label} className="flex justify-between gap-4 py-2 border-b border-slate-100 text-sm"><span className="text-slate-600">{item.label}</span><strong>{item.value}</strong></div>)}</section>}
    {report.listing_priorities.length > 0 && <section className="bg-white border border-slate-200 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-3">Listings for administrator follow-up</h3>{report.listing_priorities.map(item => <div key={item.id} className="py-3 border-b border-slate-100"><Link href={`/admin/accommodations/${item.id}`} className="font-medium text-sm text-[#1f4e79] hover:underline">{item.title}</Link><p className="text-xs text-slate-500 mt-1">{item.status} · Period views: {item.views} · Published reviews: {item.reviews} · Negative overall sentiment: {item.negative}{item.rating === null ? "" : ` · ${item.rating}/5 rating`}</p><p className="text-sm text-slate-700 mt-2">{item.reason}</p></div>)}</section>}
    {!!report.campus_coverage?.length && <section className="bg-white border border-slate-200 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-3">Campus discovery coverage · Current at generation</h3>{report.campus_coverage.map(item => <div key={item.name} className="py-3 border-b border-slate-100 text-sm"><strong>{item.name}</strong><p className="text-slate-600 mt-1">Approved linked listings: {item.approved_listings} · Active verified students: {item.verified_students}</p></div>)}<p className="text-xs text-slate-500 mt-3">These counts do not measure beds, occupancy or unmet housing demand.</p></section>}
    <section className="bg-slate-50 border border-slate-200 rounded-2xl p-6"><h3 className="font-semibold text-slate-900 mb-3">Methodology and interpretation limits</h3><ul className="list-disc pl-5 space-y-2">{report.data_quality.map((text, index) => <li key={index} className="text-xs text-slate-600 leading-relaxed">{text}</li>)}</ul></section>
  </div>;
}

export function LandlordReports({ accommodationId }: { accommodationId: number }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const { data: reports = [] } = useQuery<{ id: number; period_year: number; period_month: number; status: string }[]>({
    queryKey: ["landlord-reports", accommodationId], queryFn: () => reportsApi.list({ report_type: "accommodation", entity_id: accommodationId }).then(r => r.data),
  });
  const { data: detail, isLoading, isError } = useQuery<{ document: ManagementDocument | null }>({
    queryKey: ["landlord-report-detail", selected], queryFn: () => reportsApi.get(selected!).then(r => r.data), enabled: selected !== null,
  });
  async function generate() {
    if (busy) return;
    setBusy(true);
    const [year, periodMonth] = month.split("-").map(Number);
    try {
      const response = await reportsApi.generate({ report_type: "accommodation", entity_id: accommodationId, year, month: periodMonth });
      setSelected(response.data.report_id);
      await queryClient.invalidateQueries({ queryKey: ["landlord-reports", accommodationId] });
      toast.success("Management report generated");
    } catch (error) { toast.error(isAxiosError(error) && typeof error.response?.data?.detail === "string" ? error.response.data.detail : "The report could not be generated."); }
    finally { setBusy(false); }
  }
  return <section className="space-y-4">
    <div className="bg-white border border-slate-200 rounded-2xl p-5"><h3 className="font-semibold text-slate-900">Property management reports</h3><p className="text-sm text-slate-500 mt-2">Generate a saved report with visibility trends, published feedback and an action plan.</p>
      <div className="flex flex-wrap gap-3 mt-4 items-center"><label className="text-sm text-slate-600">Reporting month <input type="month" value={month} max={new Date().toISOString().slice(0,7)} onChange={event => setMonth(event.target.value)} className="ml-2 border rounded-lg p-2" /></label><Button disabled={busy || !month} onClick={generate} className="gap-2 rounded-xl">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} Generate report</Button></div>
      {reports.some(report => report.status === "complete") && <label className="block text-sm text-slate-600 mt-4">Saved reports <select value={selected ?? ""} onChange={event => setSelected(event.target.value ? Number(event.target.value) : null)} className="ml-2 border rounded-lg p-2"><option value="">Choose a saved report</option>{reports.filter(report => report.status === "complete").map(report => <option key={report.id} value={report.id}>{report.period_year}-{String(report.period_month).padStart(2,"0")} · #{report.id}</option>)}</select></label>}
    </div>
    {selected !== null && isLoading && <p className="text-sm text-slate-500">Loading saved report...</p>}
    {isError && <p role="alert" className="text-sm text-red-600">The saved report could not be loaded.</p>}
    {selected !== null && detail?.document && <ManagementReport reportId={selected} report={detail.document} />}
    {selected !== null && detail && !detail.document && <div className="bg-white border rounded-xl p-4 text-sm text-slate-600">This is a legacy statistics report. Generate a new report for the management analysis.<div className="mt-3"><ReportDownloadButton reportId={selected} /></div></div>}
  </section>;
}
