import type { DocumentStatus } from "@/lib/types";
import { AlertIcon, CheckCircleIcon, ClockIcon, SpinnerIcon } from "./icons";

const STYLES: Record<DocumentStatus, string> = {
  UPLOADED: "bg-slate-100 text-slate-700",
  PROCESSING: "bg-amber-100 text-amber-800",
  TEXT_EXTRACTED: "bg-amber-100 text-amber-800",
  INDEXING: "bg-amber-100 text-amber-800",
  GENERATING_EMBEDDING: "bg-amber-100 text-amber-800",
  COMPLETED: "bg-emerald-100 text-emerald-800",
  FAILED: "bg-red-100 text-red-800",
};

const IN_PROGRESS: DocumentStatus[] = ["PROCESSING", "TEXT_EXTRACTED", "INDEXING", "GENERATING_EMBEDDING"];

function StatusIcon({ status }: { status: DocumentStatus }) {
  const className = "h-3 w-3";
  if (status === "COMPLETED") return <CheckCircleIcon className={className} />;
  if (status === "FAILED") return <AlertIcon className={className} />;
  if (IN_PROGRESS.includes(status)) return <SpinnerIcon className={`${className} animate-spin`} />;
  return <ClockIcon className={className} />;
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      <StatusIcon status={status} />
      {status.replaceAll("_", " ")}
    </span>
  );
}
