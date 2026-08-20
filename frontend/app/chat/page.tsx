"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MicIcon, SendIcon, StopIcon } from "@/components/ActionIcons";
import LuceMark from "@/components/LuceMark";
import { api, clearToken, getToken, type CitedSource, type MessageOut } from "@/lib/api";

interface DisplayMessage {
  id: string;
  direction: "inbound" | "outbound";
  text: string;
  sources?: CitedSource[];
  escalated?: boolean;
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
          }))
        );
      })
      .catch(() => setError("Non sono riuscito a caricare la conversazione."));
  }, [initialConversationId]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function pushMessage(msg: DisplayMessage) {
    setMessages((prev) => [...prev, msg]);
  }

  async function handleSend() {
    const text = input.trim();
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
        escalated: res.escalated,
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

    pushMessage({ id: `local-voice-${Date.now()}`, direction: "inbound", text: "🎤 Messaggio vocale…" });
    setSending(true);
    setError(null);
    try {
      const res = await api.sendVoice(audioBlob, conversationId);
      setConversationId(res.conversation_id);
      setEscalated(res.escalated);
      pushMessage({
        id: `${res.conversation_id}-${Date.now()}`,
        direction: "outbound",
        text: res.text,
        sources: res.cited_sources,
        escalated: res.escalated,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invio del vocale non riuscito, riprova.");
    } finally {
      setSending(false);
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
          <div className="empty-state">
            Scrivi una domanda tecnica, oppure tieni premuto il microfono per un messaggio vocale.
          </div>
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
                {m.text}
                {m.sources && m.sources.length > 0 && (
                  <div className="sources-box">
                    {m.sources.map((s) => (
                      <div key={s.source_id}>
                        Fonte: {s.title}
                        {s.video_title && ` — ${s.video_title}`}
                        {s.start_timestamp && ` (dal minuto ${s.start_timestamp})`}
                        {(s.video_url || s.document_url) && (
                          <>
                            {" · "}
                            <a href={s.video_url || s.document_url || "#"} target="_blank" rel="noreferrer">
                              Apri
                            </a>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}
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
          {recording ? <StopIcon size={44} /> : <MicIcon size={44} />}
        </button>
        <button
          className="icon-round-btn"
          onClick={handleSend}
          disabled={sending || escalated || !input.trim()}
          aria-label="Invia"
        >
          <SendIcon size={44} />
        </button>
      </div>
    </div>
  );
}
