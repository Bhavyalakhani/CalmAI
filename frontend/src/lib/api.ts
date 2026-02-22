// typed api client for calmai backend
// handles auth headers, token refresh, and all api endpoints

import type {
  Patient,
  Therapist,
  JournalEntry,
  PatientAnalytics,
  DashboardStats,
  TrendDataPoint,
  RAGResponse,
  Conversation,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// token storage keys

const ACCESS_TOKEN_KEY = "calmai_access_token";
const REFRESH_TOKEN_KEY = "calmai_refresh_token";

// token helpers

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// base fetch with auth

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // try token refresh on 401
  if (res.status === 401 && token) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${getAccessToken()}`;
      const retryRes = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
      });
      if (!retryRes.ok) {
        throw new ApiError(retryRes.status, await retryRes.text());
      }
      return retryRes.json();
    }
    // refresh failed - clear tokens
    clearTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }

  return res.json();
}

async function tryRefreshToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: refresh }),
    });

    if (!res.ok) return false;

    const data = await res.json();
    setTokens(data.accessToken || data.access_token, data.refreshToken || data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// error class

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

// auth api

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  token_type: string;
}

export interface SignupPayload {
  email: string;
  password: string;
  name: string;
  role: "therapist" | "patient";
  specialization?: string;
  licenseNumber?: string;
  practiceName?: string;
  therapistId?: string;
  dateOfBirth?: string;
}

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setTokens(data.accessToken || (data as any).access_token, data.refreshToken || (data as any).refresh_token);
  return data;
}

export async function signup(payload: SignupPayload): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setTokens(data.accessToken || (data as any).access_token, data.refreshToken || (data as any).refresh_token);
  return data;
}

export async function getMe(): Promise<Therapist | Patient> {
  return apiFetch("/auth/me");
}

export function logout() {
  clearTokens();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

// patients api

export async function fetchPatients(): Promise<Patient[]> {
  return apiFetch("/patients");
}

export async function fetchPatient(id: string): Promise<Patient> {
  return apiFetch(`/patients/${id}`);
}

// invite codes api

export interface InviteCodeResult {
  code: string;
  expiresAt: string;
  message: string;
}

export interface InviteCode {
  code: string;
  therapistId: string;
  therapistName: string;
  createdAt: string;
  expiresAt: string;
  isUsed: boolean;
  usedBy?: string;
}

export async function generateInviteCode(): Promise<InviteCodeResult> {
  return apiFetch("/patients/invite", {
    method: "POST",
  });
}

export async function fetchInviteCodes(): Promise<InviteCode[]> {
  return apiFetch("/patients/invites");
}

// journals api

export async function fetchJournals(params?: {
  patientId?: string;
  limit?: number;
  skip?: number;
}): Promise<JournalEntry[]> {
  const searchParams = new URLSearchParams();
  if (params?.patientId) searchParams.set("patientId", params.patientId);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.skip) searchParams.set("skip", String(params.skip));
  const qs = searchParams.toString();
  return apiFetch(`/journals${qs ? `?${qs}` : ""}`);
}

export async function submitJournal(
  content: string,
  mood?: number
): Promise<{ journalId: string; message: string }> {
  return apiFetch("/journals", {
    method: "POST",
    body: JSON.stringify({ content, mood }),
  });
}

// conversations api

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
  page: number;
  pageSize: number;
}

export async function fetchConversations(params?: {
  topic?: string;
  severity?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<ConversationListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.topic) searchParams.set("topic", params.topic);
  if (params?.severity) searchParams.set("severity", params.severity);
  if (params?.search) searchParams.set("search", params.search);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.pageSize) searchParams.set("pageSize", String(params.pageSize));
  const qs = searchParams.toString();
  return apiFetch(`/conversations${qs ? `?${qs}` : ""}`);
}

// analytics api

export async function fetchAnalytics(
  patientId: string
): Promise<PatientAnalytics> {
  return apiFetch(`/analytics/${patientId}`);
}

// dashboard api

export async function fetchDashboardStats(): Promise<DashboardStats> {
  return apiFetch("/dashboard/stats");
}

export async function fetchMoodTrend(
  patientId: string,
  days?: number
): Promise<TrendDataPoint[]> {
  const qs = days ? `?days=${days}` : "";
  return apiFetch(`/dashboard/mood-trend/${patientId}${qs}`);
}

// rag assistant api

export async function ragSearch(params: {
  query: string;
  patientId?: string;
  topK?: number;
  sourceType?: string;
  conversationHistory?: { role: string; content: string }[];
}): Promise<RAGResponse> {
  return apiFetch("/search/rag", {
    method: "POST",
    body: JSON.stringify({
      query: params.query,
      patientId: params.patientId,
      topK: params.topK || 5,
      sourceType: params.sourceType,
      conversationHistory: params.conversationHistory,
    }),
  });
}
