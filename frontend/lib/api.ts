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
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface CitedSource {
  source_id: string;
  title: string;
  video_title?: string | null;
  video_url?: string | null;
  video_platform?: string | null;
  document_url?: string | null;
  start_timestamp?: string | null;
}

export interface ChatMessageResponse {
  conversation_id: string;
  message_id?: string | null;
  text: string;
  escalated: boolean;
  cited_sources: CitedSource[];
  retrieval_score?: number | null;
  transcript?: string | null;
}

// I 7 tipi di feedback della Specifica_Definitiva_Tutor_AI, punto 11, letterali — l'ordine
// qui determina l'ordine dei bottoni in chat.
export const FEEDBACK_OPTIONS: { tipo: string; label: string }[] = [
  { tipo: "mi_e_stata_utile", label: "Mi è stata utile" },
  { tipo: "non_ha_risolto_il_problema", label: "Non ha risolto il problema" },
  { tipo: "problema_risolto", label: "Problema risolto" },
  { tipo: "problema_parzialmente_risolto", label: "Problema parzialmente risolto" },
  { tipo: "problema_non_risolto", label: "Problema non risolto" },
  { tipo: "risposta_non_corretta", label: "Risposta non corretta" },
  { tipo: "ho_dovuto_contattare_il_tutor", label: "Ho dovuto contattare il tutor" },
];

export interface FeedbackResponse {
  id: string;
  tipo: string;
  case_stato: string | null;
  escalated: boolean;
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
  video_title: string | null;
  video_id: string | null;
  document_url: string | null;
  updated_at: string;
}

export interface VideoOut {
  id: string;
  title: string;
  platform: "drive" | "vimeo" | "youtube" | "other";
  url: string;
  technique: string | null;
  description: string | null;
  updated_at: string;
}

export interface CaseOut {
  id: string;
  conversation_id: string;
  area: string | null;
  tecnica: string | null;
  base_partenza: string | null;
  capelli_bianchi: string | null;
  storico_tecnico: string | null;
  porosita: string | null;
  servizio_eseguito: string | null;
  formula_prodotti: string | null;
  tempi_condizioni: string | null;
  problema_osservato: string | null;
  zona_coinvolta: string | null;
  risultato_desiderato: string | null;
  risultato_reale: string | null;
  fonti_trovate: string[] | null;
  livello_confidenza: string | null;
  esito: string | null;
  stato: string;
  promoted_source_id: string | null;
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

// Tassonomia a 5 categorie: Shatush e Infusion rientrano in "tecnico" (sono
// tecniche di colorazione), non categorie a parte. La categoria "fonti_esterne"
// (principi professionali generali esterni) è stata disattivata per aderire
// strettamente alla gerarchia fonti a 6 livelli della "Specifica definitiva" —
// vedi backend/app/rag/prompt.py. I documenti già caricati restano disattivati
// in produzione, non cancellati.
export const TECHNIQUE_OPTIONS = [
  { slug: "taglio", label: "Taglio" },
  { slug: "piega", label: "Piega (phon e pieghe)" },
  { slug: "tecnico", label: "Tecnico — Colorazione (incl. Shatush, Infusion)" },
  { slug: "altri_prodotti", label: "Altri prodotti" },
  { slug: "casi_particolari", label: "Casi particolari" },
];

const ALTRI_PRODOTTI_NAMES = [
  "AMO",
  "COPPOLINO",
  "MINERAL RELAX",
  "MEDITERRANEAN",
  "MR COPPOLA",
  "MR. COPPOLA",
  "NATURA_MAGICA",
  "NATURA MAGICA",
];

/** Indovina la categoria dal nome file, seguendo gli stessi pattern osservati
 * nei materiali reali dell'Accademia (es. "TAGLIO_MARIAM.csv",
 * "Piega_Rita_guida_tecnica.docx", "04 - HENNE SHATUSH - CASTANO.csv").
 * È solo un suggerimento pre-selezionato: resta sempre modificabile prima
 * di confermare il caricamento. */
export function guessTechnique(filename: string): string {
  const name = filename.toUpperCase();
  if (name.includes("CASO") || name.includes("CASI")) return "casi_particolari";
  if (name.startsWith("TAGLIO") || name.includes("TAGLIO_")) return "taglio";
  if (name.startsWith("PHON") || name.includes("PIEGA_")) return "piega";
  if (
    name.startsWith("TECNICO") ||
    name.includes("TECNICO_") ||
    name.includes("HENNE") ||
    name.includes("SHATUSH") ||
    name.includes("COLOR_OIL") ||
    name.includes("INFUSION")
  )
    return "tecnico";
  if (name.includes("SCHEDA_PRODOTTO") || name.includes("GUIDA_PRODOTTI") || ALTRI_PRODOTTI_NAMES.some((p) => name.includes(p)))
    return "altri_prodotti";
  return TECHNIQUE_OPTIONS[0].slug;
}

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

  sendFeedback: (messageId: string, tipo: string, nota?: string) =>
    request<FeedbackResponse>(`/chat/messages/${messageId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ tipo, nota: nota ?? null }),
    }),

  // --- Amministrazione ---

  uploadSource: (file: File, techniqueSlug: string, extra: { title?: string; video_id?: string; document_url?: string }) => {
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

  deleteSource: (sourceId: string) => request<void>(`/admin/sources/${sourceId}`, { method: "DELETE" }),

  listEscalations: (status?: string) =>
    request<EscalationOut[]>(`/admin/escalations${status ? `?status=${status}` : ""}`),

  resolveEscalation: (escalationId: string, notes: string) =>
    request<EscalationOut>(`/admin/escalations/${escalationId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    }),

  testResponse: (question: string) =>
    request<ChatMessageResponse>(`/admin/test-response?question=${encodeURIComponent(question)}`, { method: "POST" }),

  listCases: (stato?: string) => request<CaseOut[]>(`/admin/cases${stato ? `?stato=${stato}` : ""}`),

  validateCase: (caseId: string) =>
    request<{ case: CaseOut; promoted_source_id: string }>(`/admin/cases/${caseId}/validate`, { method: "POST" }),

  declassifyCase: (caseId: string) => request<CaseOut>(`/admin/cases/${caseId}/declassify`, { method: "POST" }),

  // --- Gestione video (svincolata dalla piattaforma: oggi Drive, in futuro Vimeo o altro) ---

  listVideos: () => request<VideoOut[]>("/admin/videos"),

  createVideo: (data: { title: string; url: string; platform: string; technique_slug?: string; description?: string }) =>
    request<VideoOut>("/admin/videos", { method: "POST", body: JSON.stringify(data) }),

  updateVideo: (
    videoId: string,
    data: Partial<{ title: string; url: string; platform: string; technique_slug: string; description: string }>
  ) => request<VideoOut>(`/admin/videos/${videoId}`, { method: "PATCH", body: JSON.stringify(data) }),

  deleteVideo: (videoId: string) => request<void>(`/admin/videos/${videoId}`, { method: "DELETE" }),
};
