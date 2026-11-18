import type { DocumentStatus } from "@/lib/types";
import { CheckCircleIcon, SpinnerIcon } from "./icons";

const STAGES: { status: DocumentStatus; label: string }[] = [
  { status: "UPLOADED", label: "Uploaded" },
  { status: "PROCESSING", label: "Processing" },
  { status: "TEXT_EXTRACTED", label: "Text extracted" },
  { status: "INDEXING", label: "Indexing" },
  { status: "GENERATING_EMBEDDING", label: "Embedding" },
  { status: "COMPLETED", label: "Completed" },
];

export function PipelineStepper({ status }: { status: DocumentStatus }) {
  if (status === "FAILED") {
    return null;
  }

  const currentIndex = STAGES.findIndex((s) => s.status === status);

  return (
    <div className="flex items-center">
      {STAGES.map((stage, idx) => {
        const done = idx < currentIndex || status === "COMPLETED";
        const active = idx === currentIndex && status !== "COMPLETED";
        return (
          <div key={stage.status} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1.5">
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  done
                    ? "bg-emerald-500 text-white"
                    : active
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-100 text-slate-400"
                }`}
              >
                {done ? (
                  <CheckCircleIcon className="h-4 w-4" />
                ) : active ? (
                  <SpinnerIcon className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  idx + 1
                )}
              </span>
              <span
                className={`w-20 text-center text-[11px] leading-tight ${
                  done || active ? "font-medium text-slate-700" : "text-slate-400"
                }`}
              >
                {stage.label}
              </span>
            </div>
            {idx < STAGES.length - 1 && (
              <div className={`mx-1 h-0.5 flex-1 rounded ${done ? "bg-emerald-500" : "bg-slate-100"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
