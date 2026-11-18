"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import {
  AlertIcon,
  CheckCircleIcon,
  ChevronLeftIcon,
  PulseLogo,
  SpinnerIcon,
} from "@/components/icons";
import { Loading } from "@/components/loading";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    if (!token) {
      setError("This reset link is missing its token. Request a new one.");
      return;
    }

    setSubmitting(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
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
        <span className="text-base font-semibold tracking-tight text-slate-900">PulseSearch</span>
      </div>

      {done ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
          <div className="flex items-center gap-2 text-emerald-800">
            <CheckCircleIcon className="h-5 w-5 shrink-0" />
            <p className="text-sm font-medium">Password updated</p>
          </div>
          <p className="mt-1.5 text-sm text-emerald-700">Taking you to sign in...</p>
        </div>
      ) : (
        <>
          <h1 className="text-2xl font-semibold text-slate-900">Set a new password</h1>
          <p className="mb-6 mt-1 text-sm text-slate-500">
            Choose a new password for your account.
          </p>

          {!token && (
            <p className="mb-4 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
              This link is missing its reset token — open it directly from the email, or{" "}
              <Link href="/forgot-password" className="underline">
                request a new one
              </Link>
              .
            </p>
          )}

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                New password
              </label>
              <input
                type="password"
                required
                minLength={8}
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
              <p className="mt-1 text-xs text-slate-400">At least 8 characters.</p>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Confirm new password
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
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
              disabled={submitting || !token}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:opacity-60"
            >
              {submitting && <SpinnerIcon className="h-4 w-4 animate-spin" />}
              {submitting ? "Updating..." : "Update password"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Suspense fallback={<Loading />}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
