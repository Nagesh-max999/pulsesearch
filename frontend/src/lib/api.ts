import type {
  AnalyticsSummary,
  AskResponse,
  DocumentAnalytics,
  DocumentDetail,
  DocumentListResponse,
  DocumentUploadResponse,
  SearchMode,
  SearchResponse,
  User,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("pulsesearch_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("pulsesearch_token", token);
  else window.localStorage.removeItem("pulsesearch_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData) && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // no JSON body
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string, full_name?: string) =>
    request<{ access_token: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, newPassword: string) =>
    request<{ message: string }>("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  me: () => request<User>("/api/auth/me"),

  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentUploadResponse>("/api/documents", {
      method: "POST",
      body: form,
    });
  },

  listDocuments: (page = 1, pageSize = 20) =>
    request<DocumentListResponse>(`/api/documents?page=${page}&page_size=${pageSize}`),

  getDocument: (id: string) => request<DocumentDetail>(`/api/documents/${id}`),

  deleteDocument: (id: string) =>
    request<void>(`/api/documents/${id}`, { method: "DELETE" }),

  search: (query: string, mode: SearchMode, page = 1, pageSize = 10) =>
    request<SearchResponse>(
      `/api/search?q=${encodeURIComponent(query)}&mode=${mode}&page=${page}&page_size=${pageSize}`
    ),

  ask: (question: string) =>
    request<AskResponse>(`/api/ask?q=${encodeURIComponent(question)}`),

  searchAnalytics: () => request<AnalyticsSummary>("/api/analytics/search"),

  documentAnalytics: () => request<DocumentAnalytics>("/api/analytics/documents"),

  documentEventsUrl: (id: string) => {
    const token = getToken();
    return `${API_URL}/api/documents/${id}/events${token ? `?token=${token}` : ""}`;
  },

  userEventsUrl: () => {
    const token = getToken();
    return `${API_URL}/api/events${token ? `?token=${token}` : ""}`;
  },
};

export { API_URL };
