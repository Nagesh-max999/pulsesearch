"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import {
  AlertIcon,
  CheckCircleIcon,
  ChevronLeftIcon,
  PulseLogo,
  SpinnerIcon,
} from "@/components/icons";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.forgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <Link
          href="/login"
          className="mb-6 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-indigo-600"
        >
          <ChevronLeftIcon className="h-4 w-4" />
          Back to sign in
        </Link>

        <div className="mb-6 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-600 text-white">
            <PulseLogo className="h-4 w-4" />
          </span>
          <span className="text-base font-semibold tracking-tight text-slate-900">
            PulseSearch
          </span>
        </div>

        {sent ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
            <div className="flex items-center gap-2 text-emerald-800">
              <CheckCircleIcon className="h-5 w-5 shrink-0" />
              <p className="text-sm font-medium">Check your email</p>
            </div>
            <p className="mt-1.5 text-sm text-emerald-700">
              If an account exists for <strong>{email}</strong>, a password reset link is on
              its way.
            </p>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-semibold text-slate-900">Reset your password</h1>
            <p className="mb-6 mt-1 text-sm text-slate-500">
              Enter your email and we&apos;ll send you a link to reset your password.
            </p>

            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
                <input
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
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
                {submitting ? "Sending..." : "Send reset link"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
