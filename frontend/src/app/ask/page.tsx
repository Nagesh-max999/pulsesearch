"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { ProtectedRoute } from "@/components/protected-route";
import {
  AlertIcon,
  DocumentsIcon,
  SendIcon,
  SparklesIcon,
  SpinnerIcon,
} from "@/components/icons";
import { api, ApiError } from "@/lib/api";
import type { AskResponse } from "@/lib/types";

function AskContent() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  const askMutation = useMutation({
    mutationFn: () => api.ask(question),
    onSuccess: (data) => {
      setResult(data);
      setNotConfigured(false);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 503) {
        setNotConfigured(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong");
      }
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotConfigured(false);
    if (question.trim()) askMutation.mutate();
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-6 flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
          <SparklesIcon className="h-4 w-4" />
        </span>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Ask AI</h1>
          <p className="text-sm text-slate-500">
            Ask a question in plain English — answered from your documents, with sources.
          </p>
        </div>
      </div>

      <form onSubmit={onSubmit} className="mb-6 flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. How does hybrid search work?"
          autoFocus
          className="flex-1 rounded-md border border-slate-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
        />
        <button
          type="submit"
          disabled={askMutation.isPending || !question.trim()}
          className="flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
        >
          {askMutation.isPending ? (
            <SpinnerIcon className="h-4 w-4 animate-spin" />
          ) : (
            <SendIcon className="h-4 w-4" />
          )}
          Ask
        </button>
      </form>

      {notConfigured && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
          <p className="font-medium">AI answers aren&apos;t set up on this deployment yet.</p>
          <p className="mt-1 text-amber-700">
            Set{" "}
            <code className="rounded bg-amber-100 px-1 py-0.5 text-xs">
              AI_ANSWERS_ENABLED=true
            </code>{" "}
            and{" "}
            <code className="rounded bg-amber-100 px-1 py-0.5 text-xs">ANTHROPIC_API_KEY</code>{" "}
            in the backend environment, then try again.
          </p>
        </div>
      )}

      {error && (
        <p className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertIcon className="h-4 w-4 shrink-0" />
          {error}
        </p>
      )}

      {askMutation.isPending && !result && (
        <div className="flex flex-col items-center gap-3 py-12 text-slate-400">
          <SpinnerIcon className="h-6 w-6 animate-spin text-indigo-500" />
          <p className="text-sm">Reading your documents...</p>
        </div>
      )}

      {result && (
        <div className="animate-fade-in space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-indigo-600">
              <SparklesIcon className="h-3.5 w-3.5" />
              Answer
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
              {result.answer}
            </p>
          </div>

          {result.citations.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                Sources ({result.citations.length})
              </p>
              <ul className="space-y-2">
                {result.citations.map((citation, idx) => (
                  <li
                    key={`${citation.document_id}-${idx}`}
                    className="rounded-lg border border-slate-200 bg-white p-3"
                  >
                    <Link
                      href={`/documents/${citation.document_id}`}
                      className="flex items-center gap-1.5 text-sm font-medium text-slate-900 hover:text-indigo-600"
                    >
                      <DocumentsIcon className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                      {citation.title}
                    </Link>
                    <p className="mt-1.5 line-clamp-2 text-xs text-slate-500">
                      {citation.snippet}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-xs text-slate-400">Answered in {result.latency_ms.toFixed(0)} ms</p>
        </div>
      )}
    </div>
  );
}

export default function AskPage() {
  return (
    <ProtectedRoute>
      <AskContent />
    </ProtectedRoute>
  );
}
