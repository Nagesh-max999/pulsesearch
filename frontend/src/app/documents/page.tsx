"use client";

import { useRef, useState, type DragEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ProtectedRoute } from "@/components/protected-route";
import { DocumentRow } from "@/components/document-row";
import { AlertIcon, ChevronLeftIcon, ChevronRightIcon, InboxIcon, SpinnerIcon, UploadIcon } from "@/components/icons";
import { api, ApiError } from "@/lib/api";

function UploadZone({
  onFile,
  isPending,
}: {
  onFile: (file: File) => void;
  isPending: boolean;
}) {
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onFile(file);
  }

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
        dragging
          ? "border-indigo-400 bg-indigo-50"
          : "border-slate-300 bg-white hover:border-indigo-300 hover:bg-slate-50"
      }`}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
        {isPending ? <SpinnerIcon className="h-5 w-5 animate-spin" /> : <UploadIcon className="h-5 w-5" />}
      </span>
      <p className="mt-3 text-sm font-medium text-slate-700">
        {isPending ? "Uploading..." : "Drop a file here or click to upload"}
      </p>
      <p className="mt-1 text-xs text-slate-400">PDF, TXT, or Markdown</p>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.md"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
        disabled={isPending}
      />
    </label>
  );
}

function DocumentsContent() {
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const pageSize = 10;

  const { data, isLoading } = useQuery({
    queryKey: ["documents", page],
    queryFn: () => api.listDocuments(page, pageSize),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadDocument(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["document-analytics"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Upload failed"),
  });

  function onFile(file: File) {
    setError(null);
    uploadMutation.mutate(file);
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload PDFs or text files — they&apos;re processed and indexed automatically.
        </p>
      </div>

      <div className="mb-6">
        <UploadZone onFile={onFile} isPending={uploadMutation.isPending} />
        {error && (
          <p className="mt-3 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertIcon className="h-4 w-4 shrink-0" />
            {error}
          </p>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white">
        {isLoading ? (
          <p className="px-5 py-6 text-center text-sm text-slate-400">Loading...</p>
        ) : data?.items.length ? (
          <ul className="divide-y divide-slate-100">
            {data.items.map((doc) => (
              <DocumentRow key={doc.id} document={doc} />
            ))}
          </ul>
        ) : (
          <div className="flex flex-col items-center px-5 py-14 text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-400">
              <InboxIcon className="h-5 w-5" />
            </span>
            <p className="mt-3 text-sm text-slate-500">No documents yet</p>
            <p className="mt-1 text-xs text-slate-400">Upload a PDF or text file to get started.</p>
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2 text-sm">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            <ChevronLeftIcon className="h-4 w-4" />
            Previous
          </button>
          <span className="px-2 py-1 text-slate-500">
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            Next
            <ChevronRightIcon className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <DocumentsContent />
    </ProtectedRoute>
  );
}
