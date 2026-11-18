"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  DashboardIcon,
  DocumentsIcon,
  LogOutIcon,
  PulseLogo,
  SearchIcon,
  SparklesIcon,
} from "./icons";

const links = [
  { href: "/dashboard", label: "Dashboard", icon: DashboardIcon },
  { href: "/documents", label: "Documents", icon: DocumentsIcon },
  { href: "/search", label: "Search", icon: SearchIcon },
  { href: "/ask", label: "Ask AI", icon: SparklesIcon },
];

function initials(name: string | null, email: string) {
  const source = name?.trim() || email;
  const parts = source.split(/[\s@]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "").concat(parts[1]?.[0] ?? "").toUpperCase() || "U";
}

export function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  return (
    <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-8">
          <Link href="/dashboard" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-600 text-white">
              <PulseLogo className="h-4 w-4" />
            </span>
            <span className="text-base font-semibold tracking-tight text-slate-900">PulseSearch</span>
          </Link>
          <div className="flex gap-1">
            {links.map((link) => {
              const active = pathname.startsWith(link.href);
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-xs font-medium text-white">
              {initials(user.full_name, user.email)}
            </span>
            <span className="hidden text-sm text-slate-500 sm:inline">{user.email}</span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            <LogOutIcon className="h-3.5 w-3.5" />
            Log out
          </button>
        </div>
      </div>
    </nav>
  );
}
