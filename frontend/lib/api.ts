const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("luce_token");
}

export function setToken(token: string) {
  localStorage.setItem("luce_token", token);
}

export function clearToken() {
  localStorage.removeItem("luce_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || "Errore di comunicazione con il server");
  }
  return res.json();
}

export interface CitedSource {
  source_id: string;
  title: string;
  video_title?: string | null;
  video_url?: string | null;
  document_url?: string | null;
  start_timestamp?: string | null;
}

export interface ChatMessageResponse {
  conversation_id: string;
  text: string;
  escalated: boolean;
  cited_sources: CitedSource[];
  retrieval_score?: number | null;
}

export interface ConversationSummary {
  id: string;
  channel: string;
  status: string;
  updated_at: string;
}

export interface MessageOut {
  id: string;
  direction: "inbound" | "outbound";
  kind: "text" | "voice";
  body: string | null;
  voice_transcript: string | null;
  sources_cited: CitedSource[] | null;
  created_at: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
}

export interface SourceOut {
  id: string;
  title: string;
  technique: string | null;
  origin_filename: string;
  origin_kind: string;
  version: number;
  status: "active" | "disabled";
  video_url: string | null;
  document_url: string | null;
  updated_at: string;
}

export interface EscalationOut {
  id: string;
  conversation_id: string;
  reason: string;
  summary: string | null;
  status: string;
  created_at: string;
}

export const TECHNIQUE_OPTIONS = [
  { slug: "tagli", label: "Tagli" },
  { slug: "pieghe", label: "Pieghe" },
  { slug: "tecnico", label: "Tecnico / colorazione" },
  { slug: "shatush", label: "Shatush / Henné" },
  { slug: "infusion", label: "Infusion" },
  { slug: "altri_prodotti", label: "Altri prodotti" },
  { slug: "casi_particolari", label: "Casi particolari" },
];

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<CurrentUser>("/auth/me"),

  sendMessage: (text: string, conversationId?: string) =>
    request<ChatMessageResponse>("/chat/message", {
      method: "POST",
      body: JSON.stringify({ text, conversation_id: conversationId ?? null }),
    }),

  sendVoice: (audioBlob: Blob, conversationId?: string) => {
    const form = new FormData();
    form.append("audio", audioBlob, "voice.webm");
    const qs = conversationId ? `?conversation_id=${conversationId}` : "";
    return request<ChatMessageResponse>(`/chat/voice${qs}`, { method: "POST", body: form });
  },

  requestHumanTutor: (conversationId: string) =>
    request<ChatMessageResponse>(`/chat/conversations/${conversationId}/escalate`, { method: "POST" }),

  listConversations: () => request<ConversationSummary[]>("/chat/conversations"),

  listMessages: (conversationId: string) => request<MessageOut[]>(`/chat/conversations/${conversationId}/messages`),

  // --- Amministrazione ---

  uploadSource: (file: File, techniqueSlug: string, extra: { title?: string; video_title?: string; video_url?: string; document_url?: string }) => {
    const form = new FormData();
    form.append("file", file);
    form.append("technique_slug", techniqueSlug);
    Object.entries(extra).forEach(([k, v]) => {
      if (v) form.append(k, v);
    });
    return request<SourceOut>("/admin/sources/upload", { method: "POST", body: form });
  },

  listSources: () => request<SourceOut[]>("/admin/sources"),

  setSourceStatus: (sourceId: string, status: "active" | "disabled") =>
    request<SourceOut>(`/admin/sources/${sourceId}/status?status=${status}`, { method: "PATCH" }),

  listEscalations: (status?: string) =>
    request<EscalationOut[]>(`/admin/escalations${status ? `?status=${status}` : ""}`),

  resolveEscalation: (escalationId: string, notes: string) =>
    request<EscalationOut>(`/admin/escalations/${escalationId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    }),

  testResponse: (question: string) =>
    request<ChatMessageResponse>(`/admin/test-response?question=${encodeURIComponent(question)}`, { method: "POST" }),
};
