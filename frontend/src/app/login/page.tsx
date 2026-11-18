"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { AlertIcon, PulseLogo, SearchIcon, SpinnerIcon, UploadIcon, ZapIcon } from "@/components/icons";

const highlights = [
  { icon: UploadIcon, text: "Upload PDFs and text files, processed live in the background" },
  { icon: SearchIcon, text: "Keyword, semantic, and hybrid search out of the box" },
  { icon: ZapIcon, text: "Real-time status over Server-Sent Events, not polling" },
];

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login, register } = useAuth();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, fullName || undefined);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-slate-900 p-10 text-white lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(99,102,241,0.5), transparent 55%), radial-gradient(circle at 80% 80%, rgba(16,185,129,0.35), transparent 55%)",
          }}
        />
        <Link href="/" className="relative flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-500">
            <PulseLogo className="h-4 w-4" />
          </span>
          <span className="text-lg font-semibold tracking-tight">PulseSearch</span>
        </Link>

        <div className="relative">
          <h2 className="text-3xl font-semibold leading-tight">
            A real-time search engine for your documents.
          </h2>
          <ul className="mt-8 space-y-4">
            {highlights.map((h) => (
              <li key={h.text} className="flex items-start gap-3 text-sm text-slate-300">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/10">
                  <h.icon className="h-3.5 w-3.5" />
                </span>
                {h.text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-slate-500">
          Keyword + semantic search, real async processing, and Docker-based deployment.
        </p>
      </div>

      <div className="flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-600 text-white">
              <PulseLogo className="h-4 w-4" />
            </span>
            <span className="text-base font-semibold tracking-tight text-slate-900">PulseSearch</span>
          </div>

          <h1 className="text-2xl font-semibold text-slate-900">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>
          <p className="mb-6 mt-1 text-sm text-slate-500">
            {mode === "login"
              ? "Sign in to search and manage your documents."
              : "Start uploading and searching documents in minutes."}
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Full name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between">
                <label className="block text-sm font-medium text-slate-700">Password</label>
                {mode === "login" && (
                  <Link href="/forgot-password" className="text-xs text-indigo-600 hover:text-indigo-700">
                    Forgot password?
                  </Link>
                )}
              </div>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
              {mode === "register" && (
                <p className="mt-1 text-xs text-slate-400">At least 8 characters.</p>
              )}
            </div>

            {error && (
              <p className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:opacity-60"
            >
              {submitting && <SpinnerIcon className="h-4 w-4 animate-spin" />}
              {submitting ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <button
            onClick={() => {
              setError(null);
              setMode(mode === "login" ? "register" : "login");
            }}
            className="mt-5 w-full text-center text-sm text-slate-500 hover:text-slate-700"
          >
            {mode === "login" ? "Need an account? " : "Have an account? "}
            <span className="font-medium text-indigo-600">
              {mode === "login" ? "Register" : "Sign in"}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
