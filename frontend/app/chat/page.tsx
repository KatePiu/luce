"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { StopIcon } from "@/components/ActionIcons";
import LuceMark from "@/components/LuceMark";
import { FEEDBACK_OPTIONS, api, clearToken, getToken, type CitedSource, type MessageOut, type SuggestedVideo } from "@/lib/api";

// Luce genera occasionalmente markdown leggero (**grassetto**) e link diretti ai video nelle
// risposte (WhatsApp li interpreta nativamente). Nella chat web li rendiamo come <strong> e
// <a> invece di mostrare asterischi/URL grezzi non cliccabili. Nessun'altra sintassi markdown
// è gestita di proposito — sono le uniche che compaiono nei materiali/risposte reali.
function renderAssistantText(text: string) {
  return text.split(/(\*\*.+?\*\*|https?:\/\/\S+)/g).map((part, i) => {
    const boldMatch = part.match(/^\*\*(.+)\*\*$/);
    if (boldMatch) return <strong key={i}>{boldMatch[1]}</strong>;
    if (/^https?:\/\/\S+$/.test(part)) {
      return (
        <a key={i} href={part} target="_blank" rel="noreferrer">
          {part}
        </a>
      );
    }
    return part;
  });
}

// Card video — usata sia per le fonti citate (con timestamp, se disponibile) sia per i video
// suggeriti per titolo (mai un timestamp: non esiste per quei video). Anteprima e link
// testuale sono lo stesso elemento <a>, quindi aprono sempre esattamente lo stesso video —
// Luce_Anteprime_Video_Cowork_Specifica, criteri di accettazione. Se l'immagine manca o non
// si carica, la card degrada a solo titolo + link, senza mai bloccare la risposta.
function VideoCard({
  title,
  previewUrl,
  openUrl,
  timestampLabel,
}: {
  title: string;
  previewUrl?: string | null;
  openUrl: string;
  timestampLabel?: string | null;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <a href={openUrl} target="_blank" rel="noreferrer" className="video-card">
      {previewUrl && !imgFailed && (
        <span className="video-card-thumb">
          <img src={previewUrl} alt="" onError={() => setImgFailed(true)} />
        </span>
      )}
      <span className="video-card-info">
        <span className="video-card-title">{title}</span>
        <span className="video-card-link">{timestampLabel ? `Vai al video da ${timestampLabel}` : "Guarda il video"}</span>
      </span>
    </a>
  );
}

// Domande di esempio per la schermata iniziale: aiutano il primo utilizzo (un tap invece di
// dover capire cosa scrivere) e mostrano il tipo di domande a cui Luce sa rispondere bene.
const EXAMPLE_QUESTIONS = [
  "Tempo di posa dell'henné rosso su base 7",
  "Come correggere un riflesso troppo arancione",
  "Procedura del Taglio Mariam",
];

interface DisplayMessage {
  id: string;
  direction: "inbound" | "outbound";
  text: string;
  sources?: CitedSource[];
  suggestedVideos?: SuggestedVideo[];
  escalated?: boolean;
  messageId?: string;
  feedbackTipo?: string;
  feedbackExpanded?: boolean;
}

export default function ChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatPageInner />
    </Suspense>
  );
}

function ChatPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialConversationId = searchParams.get("c") || undefined;

  const [conversationId, setConversationId] = useState<string | undefined>(initialConversationId);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [escalated, setEscalated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const listEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api
      .me()
      .then((u) => setIsAdmin(u.role === "admin"))
      .catch(() => {});
  }, [router]);

  useEffect(() => {
    if (!initialConversationId) return;
    api
      .listMessages(initialConversationId)
      .then((history: MessageOut[]) => {
        setMessages(
          history.map((m) => ({
            id: m.id,
            direction: m.direction,
            text: m.body || m.voice_transcript || "",
            sources: m.sources_cited || undefined,
            messageId: m.direction === "outbound" ? m.id : undefined,
          }))
        );
      })
      .catch(() => setError("Non sono riuscito a caricare la conversazione."));
  }, [initialConversationId]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Il campo di scrittura cresce con il testo (fino al max-height definito in CSS, poi
  // scrolla): senza questo, una domanda più lunga di una riga nasconde alla vista quanto
  // già digitato, con il rischio di non accorgersi di un errore di battitura.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  function pushMessage(msg: DisplayMessage) {
    setMessages((prev) => [...prev, msg]);
  }

  async function handleSend(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text || sending) return;
    setInput("");
    setError(null);
    pushMessage({ id: `local-${Date.now()}`, direction: "inbound", text });
    setSending(true);
    try {
      const res = await api.sendMessage(text, conversationId);
      setConversationId(res.conversation_id);
      setEscalated(res.escalated);
      pushMessage({
        id: `${res.conversation_id}-${Date.now()}`,
        direction: "outbound",
        text: res.text,
        sources: res.cited_sources,
        suggestedVideos: res.suggested_videos,
        escalated: res.escalated,
        messageId: res.message_id || undefined,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invio non riuscito, riprova.");
    } finally {
      setSending(false);
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      recorder.onstop = () => stream.getTracks().forEach((t) => t.stop());
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch {
      setError("Impossibile accedere al microfono. Controlla i permessi del browser.");
    }
  }

  async function stopRecordingAndSend() {
    const recorder = mediaRecorderRef.current;
    if (!recorder) return;
    setRecording(false);

    const audioBlob: Blob = await new Promise((resolve) => {
      recorder.onstop = () => resolve(new Blob(audioChunksRef.current, { type: "audio/webm" }));
      recorder.stop();
    });

    const placeholderId = `local-voice-${Date.now()}`;
    pushMessage({ id: placeholderId, direction: "inbound", text: "🎤 Trascrizione in corso…" });
    setSending(true);
    setError(null);
    try {
      const res = await api.sendVoice(audioBlob, conversationId);
      setConversationId(res.conversation_id);
      setEscalated(res.escalated);
      if (res.transcript) {
        setMessages((prev) => prev.map((m) => (m.id === placeholderId ? { ...m, text: res.transcript as string } : m)));
      }
      pushMessage({
        id: `${res.conversation_id}-${Date.now()}`,
        direction: "outbound",
        text: res.text,
        sources: res.cited_sources,
        suggestedVideos: res.suggested_videos,
        escalated: res.escalated,
        messageId: res.message_id || undefined,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invio del vocale non riuscito, riprova.");
    } finally {
      setSending(false);
    }
  }

  async function handleFeedback(messageId: string, tipo: string) {
    try {
      const res = await api.sendFeedback(messageId, tipo);
      setMessages((prev) => prev.map((m) => (m.messageId === messageId ? { ...m, feedbackTipo: tipo } : m)));
      if (res.escalated) {
        setEscalated(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invio del feedback non riuscito, riprova.");
    }
  }

  async function handleTalkToTutor() {
    if (!conversationId) {
      setError("Scrivi prima almeno un messaggio, poi potrai chiedere un tutor umano.");
      return;
    }
    const res = await api.requestHumanTutor(conversationId);
    setEscalated(true);
    pushMessage({ id: `escalate-${Date.now()}`, direction: "outbound", text: res.text, escalated: true });
  }

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <div className="page">
      <div className="top-bar">
        <h1>
          <LuceMark size={20} />
          LUCE
        </h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <Link href="/history" className="icon-btn">
            Cronologia
          </Link>
          {isAdmin && (
            <Link href="/admin" className="icon-btn">
              Admin
            </Link>
          )}
          <button className="icon-btn" onClick={handleLogout}>
            Esci
          </button>
        </div>
      </div>

      <div className="message-list">
        {messages.length === 0 && (
          <>
            <div className="empty-state">
              Ciao, sono Luce, il tutor virtuale dell&apos;Accademia Coppola. Posso aiutarti a
              ritrovare procedure e video oppure guidarti passo passo se hai un dubbio tecnico.
              Dimmi cosa stai facendo o quale problema hai davanti.
            </div>
            <div className="example-chips">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button key={q} className="example-chip" onClick={() => handleSend(q)} disabled={sending}>
                  {q}
                </button>
              ))}
            </div>
          </>
        )}
        {messages.map((m) =>
          m.direction === "inbound" ? (
            <div key={m.id} className="bubble inbound">
              {m.text}
            </div>
          ) : (
            <div key={m.id} className={`assistant-row${m.escalated ? " escalated" : ""}`}>
              <div className="assistant-avatar">
                <LuceMark size={14} />
              </div>
              <div className="assistant-content">
                {renderAssistantText(m.text)}
                {m.sources && m.sources.length > 0 && (
                  <div className="sources-box">
                    {m.sources.map((s) => (
                      <div key={s.source_id}>
                        Fonte: {s.title}
                        {!s.video_title && s.document_url && (
                          <>
                            {" · "}
                            <a href={s.document_url} target="_blank" rel="noreferrer">
                              Apri
                            </a>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {m.sources && m.sources.some((s) => s.video_title && (s.video_open_url || s.video_url)) && (
                  <div className="video-cards">
                    {m.sources
                      .filter((s) => s.video_title && (s.video_open_url || s.video_url))
                      .map((s) => (
                        <VideoCard
                          key={s.source_id}
                          title={s.video_title as string}
                          previewUrl={s.video_preview_url}
                          openUrl={(s.video_open_url || s.video_url) as string}
                          timestampLabel={s.start_timestamp}
                        />
                      ))}
                  </div>
                )}
                {m.suggestedVideos && m.suggestedVideos.length > 0 && (
                  <div className="video-cards">
                    {m.suggestedVideos.map((v) => (
                      <VideoCard key={v.video_id} title={v.title} previewUrl={v.preview_url} openUrl={v.url} />
                    ))}
                  </div>
                )}
                {m.messageId &&
                  (m.feedbackTipo ? (
                    <div className="feedback-box feedback-given">
                      Grazie per il feedback: {FEEDBACK_OPTIONS.find((o) => o.tipo === m.feedbackTipo)?.label || m.feedbackTipo}
                    </div>
                  ) : (
                    <div className="feedback-box">
                      <div className="feedback-row">
                        <button
                          className="feedback-btn feedback-btn-primary"
                          onClick={() => handleFeedback(m.messageId!, FEEDBACK_OPTIONS[0].tipo)}
                        >
                          {FEEDBACK_OPTIONS[0].label}
                        </button>
                        <button
                          className="feedback-btn"
                          onClick={() =>
                            setMessages((prev) =>
                              prev.map((msg) => (msg.id === m.id ? { ...msg, feedbackExpanded: !msg.feedbackExpanded } : msg))
                            )
                          }
                        >
                          Altro feedback
                        </button>
                      </div>
                      {m.feedbackExpanded && (
                        <div className="feedback-row feedback-row-secondary">
                          {FEEDBACK_OPTIONS.slice(1).map((opt) => (
                            <button key={opt.tipo} className="feedback-btn" onClick={() => handleFeedback(m.messageId!, opt.tipo)}>
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            </div>
          )
        )}
        {sending && (
          <div className="assistant-row">
            <div className="thinking-orb" />
            <div className="thinking-label">Sto cercando nei materiali dell&apos;Accademia…</div>
          </div>
        )}
        <div ref={listEndRef} />
      </div>

      {error && <p className="error-text" style={{ padding: "0 1rem" }}>{error}</p>}

      {!escalated && (
        <button className="tutor-btn" onClick={handleTalkToTutor}>
          Parla con un tutor
        </button>
      )}
      {escalated && (
        <p className="empty-state" style={{ padding: "0 1rem 0.5rem" }}>
          Un tutor umano è stato avvisato e prenderà in carico questa conversazione.
        </p>
      )}

      <div className="composer">
        <textarea
          ref={textareaRef}
          rows={1}
          placeholder="Scrivi la tua domanda…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={sending || escalated}
        />
        <button
          className="icon-round-btn"
          onClick={recording ? stopRecordingAndSend : startRecording}
          disabled={sending || escalated}
          aria-label={recording ? "Ferma registrazione e invia" : "Registra messaggio vocale"}
          title={recording ? "Ferma e invia" : "Registra vocale"}
        >
          {recording ? (
            <StopIcon size={44} />
          ) : (
            <img src="/icons/mic.png" alt="" width={44} height={44} className="icon-img" />
          )}
        </button>
        <button
          className="icon-round-btn"
          onClick={() => handleSend()}
          disabled={sending || escalated || !input.trim()}
          aria-label="Invia"
        >
          <img src="/icons/send.png" alt="" width={44} height={44} className="icon-img" />
        </button>
      </div>
    </div>
  );
}
