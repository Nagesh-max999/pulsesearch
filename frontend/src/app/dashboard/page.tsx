"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ProtectedRoute } from "@/components/protected-route";
import { StatusBadge } from "@/components/status-badge";
import {
  CheckCircleIcon,
  ClockIcon,
  DocumentsIcon,
  InboxIcon,
  SearchIcon,
  type IconComponent,
} from "@/components/icons";
import { api } from "@/lib/api";

function StatCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  icon: IconComponent;
  tone: "slate" | "amber" | "emerald" | "indigo";
}) {
  const tones: Record<typeof tone, string> = {
    slate: "bg-slate-100 text-slate-600",
    amber: "bg-amber-100 text-amber-700",
    emerald: "bg-emerald-100 text-emerald-700",
    indigo: "bg-indigo-100 text-indigo-700",
  };
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{label}</p>
        <span className={`flex h-8 w-8 items-center justify-center rounded-md ${tones[tone]}`}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value.toLocaleString()}</p>
    </div>
  );
}

function ModeBar({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="text-slate-400">
          {count} &middot; {pct}%
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function DashboardContent() {
  const { data: docAnalytics } = useQuery({
    queryKey: ["document-analytics"],
    queryFn: api.documentAnalytics,
  });
  const { data: recent } = useQuery({
    queryKey: ["documents", 1],
    queryFn: () => api.listDocuments(1, 5),
  });
  const { data: searchAnalytics } = useQuery({
    queryKey: ["search-analytics"],
    queryFn: api.searchAnalytics,
  });

  const byStatus = docAnalytics?.by_status ?? {};
  const processing =
    (byStatus.PROCESSING ?? 0) +
    (byStatus.TEXT_EXTRACTED ?? 0) +
    (byStatus.INDEXING ?? 0) +
    (byStatus.GENERATING_EMBEDDING ?? 0);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-900">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total documents" value={docAnalytics?.total ?? 0} icon={DocumentsIcon} tone="slate" />
        <StatCard label="Processing" value={processing} icon={ClockIcon} tone="amber" />
        <StatCard label="Completed" value={byStatus.COMPLETED ?? 0} icon={CheckCircleIcon} tone="emerald" />
        <StatCard
          label="Searches (30d)"
          value={searchAnalytics?.total_searches ?? 0}
          icon={SearchIcon}
          tone="indigo"
        />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-5">
        <div className="rounded-lg border border-slate-200 bg-white lg:col-span-3">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
            <h2 className="font-medium text-slate-900">Recent activity</h2>
            <Link href="/documents" className="text-sm text-indigo-600 hover:text-indigo-700">
              View all
            </Link>
          </div>
          {recent?.items.length ? (
            <ul className="divide-y divide-slate-100">
              {recent.items.map((doc) => (
                <li key={doc.id} className="flex items-center justify-between px-5 py-3">
                  <Link
                    href={`/documents/${doc.id}`}
                    className="truncate text-sm text-slate-800 hover:text-indigo-600 hover:underline"
                  >
                    {doc.title}
                  </Link>
                  <StatusBadge status={doc.status} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-col items-center px-5 py-12 text-center">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <InboxIcon className="h-5 w-5" />
              </span>
              <p className="mt-3 text-sm text-slate-400">No documents yet</p>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 lg:col-span-2">
          <h2 className="mb-4 font-medium text-slate-900">Search mode breakdown</h2>
          {searchAnalytics && searchAnalytics.total_searches > 0 ? (
            <div className="space-y-4">
              <ModeBar
                label="Hybrid"
                count={searchAnalytics.hybrid_searches}
                total={searchAnalytics.total_searches}
                color="bg-indigo-500"
              />
              <ModeBar
                label="Keyword"
                count={searchAnalytics.keyword_searches}
                total={searchAnalytics.total_searches}
                color="bg-slate-500"
              />
              <ModeBar
                label="Semantic"
                count={searchAnalytics.semantic_searches}
                total={searchAnalytics.total_searches}
                color="bg-emerald-500"
              />
              <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
                <span>Avg latency</span>
                <span className="font-medium text-slate-700">
                  {searchAnalytics.avg_latency_ms.toFixed(1)} ms
                </span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Zero-result searches</span>
                <span className="font-medium text-slate-700">{searchAnalytics.zero_result_searches}</span>
              </div>

              {searchAnalytics.top_queries.length > 0 && (
                <div className="border-t border-slate-100 pt-3">
                  <p className="mb-2 text-xs font-medium text-slate-500">Top queries</p>
                  <ul className="space-y-1.5">
                    {searchAnalytics.top_queries.slice(0, 5).map((q) => (
                      <li key={q.query} className="flex items-center justify-between text-xs">
                        <span className="truncate text-slate-600">{q.query}</span>
                        <span className="ml-2 shrink-0 text-slate-400">{q.count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center py-8 text-center">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <SearchIcon className="h-5 w-5" />
              </span>
              <p className="mt-3 text-sm text-slate-400">No searches yet</p>
              <Link href="/search" className="mt-1 text-xs text-indigo-600 hover:text-indigo-700">
                Try a search
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
