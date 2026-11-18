"use client";

import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { StatusBadge } from "./status-badge";
import { DocumentsIcon, TrashIcon } from "./icons";
import { useDocumentStatus } from "@/lib/use-document-status";
import { api } from "@/lib/api";
import type { DocumentItem } from "@/lib/types";

export function DocumentRow({ document }: { document: DocumentItem }) {
  const status = useDocumentStatus(document.id, document.status);
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteDocument(document.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  function onDelete() {
    if (window.confirm(`Delete "${document.title}"? This can't be undone.`)) {
      deleteMutation.mutate();
    }
  }

  return (
    <li className="group flex items-center justify-between gap-4 px-5 py-3 transition-colors hover:bg-slate-50">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
          <DocumentsIcon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <Link
            href={`/documents/${document.id}`}
            className="block truncate text-sm font-medium text-slate-800 hover:text-indigo-600"
          >
            {document.title}
          </Link>
          <p className="truncate text-xs text-slate-400">
            {(document.file_size_bytes / 1024).toFixed(1)} KB &middot;{" "}
            {new Date(document.created_at).toLocaleString()}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <StatusBadge status={status} />
        <button
          onClick={onDelete}
          disabled={deleteMutation.isPending}
          aria-label={`Delete ${document.title}`}
          className="rounded-md p-1.5 text-slate-300 opacity-0 transition-opacity hover:bg-red-50 hover:text-red-600 focus-visible:opacity-100 group-hover:opacity-100 disabled:opacity-50"
        >
          <TrashIcon className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}
