import { SpinnerIcon } from "./icons";

export function Loading({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-slate-400">
      <SpinnerIcon className="h-6 w-6 animate-spin text-indigo-500" />
      <p className="text-sm">{label}</p>
    </div>
  );
}
