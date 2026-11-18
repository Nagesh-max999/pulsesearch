"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { ProtectedRoute } from "@/components/protected-route";
import { AlertIcon, DocumentsIcon, SearchIcon, SpinnerIcon, ZapIcon, type IconComponent } from "@/components/icons";
import { api, ApiError } from "@/lib/api";
import { sanitizeSnippet } from "@/lib/sanitize";
import type { SearchMode, SearchResponse } from "@/lib/types";

const MODES: { value: SearchMode; label: string; icon: IconComponent }[] = [
  { value: "HYBRID", label: "Hybrid", icon: ZapIcon },
  { value: "KEYWORD", label: "Keyword", icon: DocumentsIcon },
  { value: "SEMANTIC", label: "Semantic", icon: SearchIcon },
];

function SearchContent() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("HYBRID");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const searchMutation = useMutation({
    mutationFn: () => api.search(query, mode),
    onSuccess: setResult,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Search failed"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (query.trim()) searchMutation.mutate();
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="mb-1 text-2xl font-semibold text-slate-900">Search</h1>
      <p className="mb-6 text-sm text-slate-500">Search across all of your uploaded documents.</p>

      <form onSubmit={onSubmit} className="mb-2 space-y-3">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your documents..."
            autoFocus
            className="w-full rounded-md border border-slate-300 py-2.5 pl-9 pr-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className="inline-flex rounded-md border border-slate-200 bg-slate-100 p-0.5">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => setMode(m.value)}
                className={`flex items-center gap-1.5 rounded-[5px] px-3 py-1.5 text-xs font-medium transition-colors ${
                  mode === m.value
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <m.icon className="h-3.5 w-3.5" />
                {m.label}
              </button>
            ))}
          </div>
          <button
            type="submit"
            disabled={searchMutation.isPending || !query.trim()}
            className="flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
          >
            {searchMutation.isPending && <SpinnerIcon className="h-4 w-4 animate-spin" />}
            Search
          </button>
        </div>
      </form>

      {error && (
        <p className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertIcon className="h-4 w-4 shrink-0" />
          {error}
        </p>
      )}

      {result && (
        <div className="mt-6">
          <p className="mb-4 text-sm text-slate-500">
            {result.total} result{result.total !== 1 && "s"} for &ldquo;{result.query}&rdquo; in{" "}
            {result.latency_ms.toFixed(1)} ms ({result.mode.toLowerCase()})
          </p>

          {result.results.length === 0 && (
            <div className="flex flex-col items-center rounded-lg border border-slate-200 bg-white px-4 py-12 text-center">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <SearchIcon className="h-5 w-5" />
              </span>
              <p className="mt-3 text-sm text-slate-500">No results found</p>
              <p className="mt-1 text-xs text-slate-400">Try a different query or search mode.</p>
            </div>
          )}

          <ul className="space-y-3">
            {result.results.map((item, idx) => (
              <li
                key={`${item.document_id}-${idx}`}
                className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-4">
                  <Link
                    href={`/documents/${item.document_id}`}
                    className="flex items-center gap-1.5 text-sm font-medium text-slate-900 hover:text-indigo-600"
                  >
                    <DocumentsIcon className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                    {item.title}
                  </Link>
                  <div className="flex shrink-0 items-center gap-2">
                    <div className="h-1.5 w-14 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-indigo-500"
                        style={{ width: `${Math.min(100, Math.round(item.score * 100))}%` }}
                      />
                    </div>
                    <span className="whitespace-nowrap text-xs text-slate-400">{item.score.toFixed(3)}</span>
                  </div>
                </div>
                <p
                  className="mt-2 text-sm text-slate-600"
                  dangerouslySetInnerHTML={{ __html: sanitizeSnippet(item.snippet) }}
                />
                {item.matched_terms.length > 0 && (
                  <p className="mt-2 text-xs text-slate-400">
                    Matched: {item.matched_terms.join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <ProtectedRoute>
      <SearchContent />
    </ProtectedRoute>
  );
}
