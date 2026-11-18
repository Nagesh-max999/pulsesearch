"use client";

import { use, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ProtectedRoute } from "@/components/protected-route";
import { StatusBadge } from "@/components/status-badge";
import { PipelineStepper } from "@/components/pipeline-stepper";
import { Loading } from "@/components/loading";
import { AlertIcon, ChevronLeftIcon, LayersIcon } from "@/components/icons";
import { useDocumentStatus } from "@/lib/use-document-status";
import { api } from "@/lib/api";

function DocumentDetailContent({ id }: { id: string }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["document", id],
    queryFn: () => api.getDocument(id),
  });

  const status = useDocumentStatus(id, data?.status ?? "UPLOADED");

  useEffect(() => {
    if (data && status !== data.status && (status === "COMPLETED" || status === "FAILED")) {
      refetch();
    }
  }, [status, data, refetch]);

  if (isLoading || !data) return <Loading />;

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <Link
        href="/documents"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-indigo-600"
      >
        <ChevronLeftIcon className="h-4 w-4" />
        Documents
      </Link>

      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold text-slate-900">{data.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {data.original_filename} &middot; {(data.file_size_bytes / 1024).toFixed(1)} KB &middot;{" "}
            {new Date(data.created_at).toLocaleString()}
          </p>
        </div>
        <StatusBadge status={status} />
      </div>

      {data.error_message ? (
        <div className="mb-6 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
          {data.error_message}
        </div>
      ) : (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-5">
          <PipelineStepper status={status} />
        </div>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-3 flex items-center gap-2 font-medium text-slate-900">
          <LayersIcon className="h-4 w-4 text-slate-400" />
          Searchable chunks {data.chunk_count > 0 && `(${data.chunk_count} total)`}
        </h2>
        {data.chunk_previews.length ? (
          <ul className="space-y-3">
            {data.chunk_previews.map((chunk) => (
              <li key={chunk.chunk_index} className="rounded-md bg-slate-50 p-3 text-sm text-slate-700">
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                  Chunk {chunk.chunk_index + 1}
                </p>
                {chunk.content.slice(0, 400)}
                {chunk.content.length > 400 && "..."}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">
            {status === "COMPLETED" ? "No chunks were generated." : "Processing in progress..."}
          </p>
        )}
      </div>
    </div>
  );
}

export default function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <ProtectedRoute>
      <DocumentDetailContent id={id} />
    </ProtectedRoute>
  );
}
