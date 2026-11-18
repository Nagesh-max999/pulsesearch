"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Loading } from "@/components/loading";
import { PulseLogo, SearchIcon, UploadIcon, ZapIcon } from "@/components/icons";

const features = [
  {
    icon: SearchIcon,
    title: "Keyword search",
    description: "Fast, relevance-ranked full-text search powered by PostgreSQL.",
  },
  {
    icon: ZapIcon,
    title: "Semantic search",
    description: "Find documents by meaning using local embeddings and pgvector cosine similarity.",
  },
  {
    icon: UploadIcon,
    title: "Live processing",
    description: "Upload and watch documents move through the pipeline in real time over SSE.",
  },
];

const steps = [
  { title: "Upload", description: "Drop in a PDF or text file — the API responds instantly." },
  { title: "Process", description: "Text extraction, chunking, and embedding run in the background." },
  { title: "Search", description: "Query by keyword, meaning, or a hybrid blend of both." },
];

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  if (loading || user) return <Loading />;

  return (
    <div className="animate-fade-in">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-600 text-white">
            <PulseLogo className="h-4 w-4" />
          </span>
          <span className="text-base font-semibold tracking-tight text-slate-900">PulseSearch</span>
        </div>
        <Link
          href="/login"
          className="rounded-md border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Sign in
        </Link>
      </header>

      <div className="mx-auto max-w-4xl px-6 pb-24 pt-12 text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">
          <ZapIcon className="h-3 w-3" />
          Real-time keyword + semantic search
        </span>
        <h1 className="mt-5 text-5xl font-bold tracking-tight text-slate-900">PulseSearch</h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-slate-600">
          Upload documents, watch them get processed live, and search them by keyword,
          semantic meaning, or a hybrid of both.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link
            href="/login"
            className="rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
          >
            Get started
          </Link>
          <Link
            href="/login"
            className="rounded-md border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Sign in
          </Link>
        </div>

        <div className="mt-20 grid gap-5 text-left sm:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                <feature.icon className="h-4 w-4" />
              </span>
              <h3 className="mt-4 font-semibold text-slate-900">{feature.title}</h3>
              <p className="mt-1.5 text-sm text-slate-500">{feature.description}</p>
            </div>
          ))}
        </div>

        <div className="mt-24 rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">How it works</h2>
          <div className="mt-6 grid gap-8 text-left sm:grid-cols-3">
            {steps.map((step, idx) => (
              <div key={step.title} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
                  {idx + 1}
                </span>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">{step.title}</h3>
                  <p className="mt-1 text-sm text-slate-500">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
