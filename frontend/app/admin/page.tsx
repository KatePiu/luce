"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  getToken,
  guessTechnique,
  TECHNIQUE_OPTIONS,
  type CurrentUser,
  type EscalationOut,
  type SourceOut,
} from "@/lib/api";

type QueueStatus = "pending" | "uploading" | "done" | "error";

interface QueueItem {
  key: string;
  file: File;
  technique: string;
  status: QueueStatus;
  message?: string;
}

export default function AdminPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [denied, setDenied] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [sources, setSources] = useState<SourceOut[]>([]);
  const [escalations, setEscalations] = useState<EscalationOut[]>([]);

  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploadingAll, setUploadingAll] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  function addFiles(files: FileList | File[]) {
    const items: QueueItem[] = Array.from(files).map((file) => ({
      key: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
      file,
      technique: guessTechnique(file.name),
      status: "pending",
    }));
    setQueue((prev) => [...prev, ...items]);
  }

  function updateItem(key: string, patch: Partial<QueueItem>) {
    setQueue((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));
  }

  function removeItem(key: string) {
    setQueue((prev) => prev.filter((it) => it.key !== key));
  }

  async function uploadAll() {
    setUploadingAll(true);
    // Caricamento sequenziale, un file alla volta: più lento ma non sovraccarica
    // il backend (ogni file calcola embedding per ciascun "pezzo" del testo).
    for (const item of queue) {
      if (item.status === "done") continue;
      updateItem(item.key, { status: "uploading", message: undefined });
      try {
        const source = await api.uploadSource(item.file, item.technique, {});
        updateItem(item.key, { status: "done", message: `Indicizzato come "${source.title}" (v${source.version})` });
      } catch (err) {
        updateItem(item.key, { status: "error", message: err instanceof Error ? err.message : "Caricamento non riuscito" });
      }
    }
    setUploadingAll(false);
    refresh();
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
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
          <h2>Carica nuovi materiali</h2>
          <p style={{ color: "var(--ink-muted)", fontSize: "0.85rem", marginTop: "-0.4rem" }}>
            Trascina anche più file insieme (CSV, .docx, .md, .txt). La categoria viene indovinata dal nome
            del file — controllala prima di confermare, puoi cambiarla dal menu su ogni riga.
          </p>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${dragOver ? "var(--accent-1)" : "var(--border)"}`,
              borderRadius: 16,
              padding: "1.5rem 1rem",
              textAlign: "center",
              cursor: "pointer",
              color: "var(--ink-muted)",
              background: dragOver ? "color-mix(in srgb, var(--accent-1) 8%, transparent)" : "transparent",
              transition: "border-color 0.15s ease, background 0.15s ease",
            }}
          >
            Trascina qui i file, oppure clicca per sceglierli
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.docx,.md,.txt"
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files?.length) addFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </div>

          {queue.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.9rem" }}>
              {queue.map((item) => (
                <div
                  key={item.key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    padding: "0.5rem 0",
                    borderBottom: "1px solid var(--border)",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.file.name}</div>
                    {item.message && (
                      <div style={{ color: item.status === "error" ? "var(--danger)" : "var(--ink-muted)" }}>{item.message}</div>
                    )}
                  </div>
                  <select
                    value={item.technique}
                    onChange={(e) => updateItem(item.key, { technique: e.target.value })}
                    disabled={item.status === "uploading" || item.status === "done"}
                    style={{ fontSize: "0.8rem", padding: "0.4rem 0.5rem" }}
                  >
                    {TECHNIQUE_OPTIONS.map((t) => (
                      <option key={t.slug} value={t.slug}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  <span style={{ width: "1.3rem", textAlign: "center" }}>
                    {item.status === "uploading" && "…"}
                    {item.status === "done" && "✓"}
                    {item.status === "error" && "✕"}
                  </span>
                  {item.status !== "uploading" && (
                    <button className="icon-btn" onClick={() => removeItem(item.key)} aria-label="Rimuovi">
                      ×
                    </button>
                  )}
                </div>
              ))}

              <button className="primary-btn" onClick={uploadAll} disabled={uploadingAll || queue.every((q) => q.status === "done")}>
                {uploadingAll ? "Caricamento in corso…" : `Carica e indicizza (${queue.filter((q) => q.status !== "done").length})`}
              </button>
            </div>
          )}
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
