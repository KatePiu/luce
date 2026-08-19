"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  getToken,
  TECHNIQUE_OPTIONS,
  type CurrentUser,
  type EscalationOut,
  type SourceOut,
} from "@/lib/api";

export default function AdminPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [denied, setDenied] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [sources, setSources] = useState<SourceOut[]>([]);
  const [escalations, setEscalations] = useState<EscalationOut[]>([]);

  const [file, setFile] = useState<File | null>(null);
  const [technique, setTechnique] = useState(TECHNIQUE_OPTIONS[0].slug);
  const [videoUrl, setVideoUrl] = useState("");
  const [documentUrl, setDocumentUrl] = useState("");
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const [testQuestion, setTestQuestion] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        if (u.role !== "admin") {
          setDenied(true);
          return;
        }
        refresh();
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  function refresh() {
    api.listSources().then(setSources).catch((e) => setLoadError(e.message));
    api.listEscalations("open").then(setEscalations).catch((e) => setLoadError(e.message));
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const source = await api.uploadSource(file, technique, {
        video_url: videoUrl || undefined,
        document_url: documentUrl || undefined,
      });
      setUploadMsg(`Caricato: ${source.title} (versione ${source.version})`);
      setFile(null);
      setVideoUrl("");
      setDocumentUrl("");
      refresh();
    } catch (err) {
      setUploadMsg(err instanceof Error ? err.message : "Caricamento non riuscito");
    } finally {
      setUploading(false);
    }
  }

  async function toggleSource(source: SourceOut) {
    const next = source.status === "active" ? "disabled" : "active";
    await api.setSourceStatus(source.id, next);
    refresh();
  }

  async function handleResolve(escalationId: string) {
    const notes = window.prompt("Note sulla risoluzione (facoltative):") || "";
    await api.resolveEscalation(escalationId, notes);
    refresh();
  }

  async function handleTest(e: React.FormEvent) {
    e.preventDefault();
    if (!testQuestion.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testResponse(testQuestion);
      setTestResult(res.text + (res.escalated ? "\n\n[Verrebbe inoltrata a un tutor umano]" : ""));
    } catch (err) {
      setTestResult(err instanceof Error ? err.message : "Test non riuscito");
    } finally {
      setTesting(false);
    }
  }

  if (denied) {
    return (
      <div className="page" style={{ padding: "1.5rem" }}>
        <h1>Accesso riservato</h1>
        <p>Questa sezione è visibile solo agli amministratori.</p>
        <Link href="/chat">Torna alla chat</Link>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <div className="top-bar">
        <h1>Amministrazione LUCE</h1>
        <Link href="/chat" className="icon-btn">
          Torna alla chat
        </Link>
      </div>

      <div style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "2rem" }}>
        <section>
          <h2>Carica un nuovo materiale</h2>
          <form onSubmit={handleUpload} style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            <input type="file" accept=".csv,.docx,.md,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
            <select value={technique} onChange={(e) => setTechnique(e.target.value)}>
              {TECHNIQUE_OPTIONS.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.label}
                </option>
              ))}
            </select>
            <input placeholder="Link al video (facoltativo)" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} />
            <input
              placeholder="Link al documento originale (facoltativo)"
              value={documentUrl}
              onChange={(e) => setDocumentUrl(e.target.value)}
            />
            <button className="primary-btn" type="submit" disabled={uploading || !file}>
              {uploading ? "Caricamento…" : "Carica e indicizza"}
            </button>
            {uploadMsg && <p>{uploadMsg}</p>}
          </form>
        </section>

        <section>
          <h2>Fonti indicizzate ({sources.length})</h2>
          {loadError && <p className="error-text">{loadError}</p>}
          <table style={{ width: "100%", fontSize: "0.85rem", borderCollapse: "collapse" }}>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "0.4rem 0" }}>
                    <div>{s.title}</div>
                    <div style={{ color: "var(--ink-muted)" }}>
                      {s.technique} · v{s.version} · {s.origin_filename}
                    </div>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="icon-btn" onClick={() => toggleSource(s)}>
                      {s.status === "active" ? "Disattiva" : "Attiva"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h2>Escalation aperte ({escalations.length})</h2>
          {escalations.length === 0 && <p style={{ color: "var(--ink-muted)" }}>Nessuna al momento.</p>}
          {escalations.map((e) => (
            <div key={e.id} style={{ padding: "0.6rem 0", borderBottom: "1px solid var(--border)" }}>
              <div>
                <b>{e.reason}</b> — {new Date(e.created_at).toLocaleString("it-IT")}
              </div>
              <div style={{ color: "var(--ink-muted)" }}>{e.summary}</div>
              <button className="icon-btn" onClick={() => handleResolve(e.id)}>
                Segna come risolta
              </button>
            </div>
          ))}
        </section>

        <section>
          <h2>Testa una risposta</h2>
          <form onSubmit={handleTest} style={{ display: "flex", gap: "0.5rem" }}>
            <input
              style={{ flex: 1, padding: "0.6rem", border: "1px solid var(--border)", borderRadius: 8 }}
              placeholder="Fai una domanda di prova…"
              value={testQuestion}
              onChange={(e) => setTestQuestion(e.target.value)}
            />
            <button className="primary-btn" type="submit" disabled={testing}>
              Testa
            </button>
          </form>
          {testResult && (
            <pre style={{ whiteSpace: "pre-wrap", background: "var(--bg)", padding: "0.8rem", borderRadius: 8, marginTop: "0.6rem" }}>
              {testResult}
            </pre>
          )}
        </section>
      </div>
    </div>
  );
}
