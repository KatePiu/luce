"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  getToken,
  guessTechnique,
  TECHNIQUE_OPTIONS,
  type CaseOut,
  type CurrentUser,
  type EscalationOut,
  type SourceOut,
  type VideoOut,
} from "@/lib/api";

const CASE_FILTERS: { stato: string; label: string }[] = [
  { stato: "DA_VALIDARE", label: "Da validare" },
  { stato: "VALIDATO_PER_KNOWLEDGE", label: "Validati (Knowledge)" },
  { stato: "NON_RISOLTO", label: "Casi negativi" },
];

type QueueStatus = "pending" | "uploading" | "done" | "error";

interface QueueItem {
  key: string;
  file: File;
  technique: string;
  videoId: string;
  status: QueueStatus;
  message?: string;
}

const PLATFORM_OPTIONS = [
  { slug: "drive", label: "Google Drive" },
  { slug: "vimeo", label: "Vimeo" },
  { slug: "youtube", label: "YouTube" },
  { slug: "other", label: "Altro" },
];

export default function AdminPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [denied, setDenied] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [sources, setSources] = useState<SourceOut[]>([]);
  const [videos, setVideos] = useState<VideoOut[]>([]);
  const [escalations, setEscalations] = useState<EscalationOut[]>([]);

  const [cases, setCases] = useState<CaseOut[]>([]);
  const [casesFilter, setCasesFilter] = useState(CASE_FILTERS[0].stato);
  const [casesBusy, setCasesBusy] = useState<string | null>(null);

  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploadingAll, setUploadingAll] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [newVideoTitle, setNewVideoTitle] = useState("");
  const [newVideoUrl, setNewVideoUrl] = useState("");
  const [newVideoPlatform, setNewVideoPlatform] = useState("drive");
  const [newVideoTechnique, setNewVideoTechnique] = useState(TECHNIQUE_OPTIONS[0].slug);
  const [savingVideo, setSavingVideo] = useState(false);

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
    api.listVideos().then(setVideos).catch((e) => setLoadError(e.message));
    api.listEscalations("open").then(setEscalations).catch((e) => setLoadError(e.message));
    api.listCases(casesFilter).then(setCases).catch((e) => setLoadError(e.message));
  }

  useEffect(() => {
    if (user?.role === "admin") {
      api.listCases(casesFilter).then(setCases).catch((e) => setLoadError(e.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [casesFilter]);

  function addFiles(files: FileList | File[]) {
    const items: QueueItem[] = Array.from(files).map((file) => ({
      key: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
      file,
      technique: guessTechnique(file.name),
      videoId: "",
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
        const source = await api.uploadSource(item.file, item.technique, {
          video_id: item.videoId || undefined,
        });
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

  async function handleDeleteSource(source: SourceOut) {
    if (!window.confirm(`Eliminare definitivamente "${source.title}"? Il file originale su Drive non viene toccato, ma va ricaricato da qui per riaverlo indicizzato.`)) return;
    await api.deleteSource(source.id);
    refresh();
  }

  async function handleAddVideo(e: React.FormEvent) {
    e.preventDefault();
    if (!newVideoTitle.trim() || !newVideoUrl.trim()) return;
    setSavingVideo(true);
    try {
      await api.createVideo({
        title: newVideoTitle.trim(),
        url: newVideoUrl.trim(),
        platform: newVideoPlatform,
        technique_slug: newVideoTechnique,
      });
      setNewVideoTitle("");
      setNewVideoUrl("");
      refresh();
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Impossibile salvare il video");
    } finally {
      setSavingVideo(false);
    }
  }

  async function handleVideoUrlEdit(video: VideoOut) {
    const url = window.prompt(`Nuovo link per "${video.title}"`, video.url);
    if (!url || url === video.url) return;
    await api.updateVideo(video.id, { url });
    refresh();
  }

  async function handleVideoPlatformChange(video: VideoOut, platform: string) {
    await api.updateVideo(video.id, { platform });
    refresh();
  }

  async function handleDeleteVideo(video: VideoOut) {
    if (!window.confirm(`Eliminare il video "${video.title}"? Le trascrizioni/guide collegate restano, solo il link viene rimosso.`)) return;
    await api.deleteVideo(video.id);
    refresh();
  }

  async function handleResolve(escalationId: string) {
    const notes = window.prompt("Note sulla risoluzione (facoltative):") || "";
    await api.resolveEscalation(escalationId, notes);
    refresh();
  }

  async function handleValidateCase(caseId: string) {
    setCasesBusy(caseId);
    try {
      await api.validateCase(caseId);
      setCases((prev) => prev.filter((c) => c.id !== caseId));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Validazione non riuscita");
    } finally {
      setCasesBusy(null);
    }
  }

  async function handleDeclassifyCase(caseId: string) {
    if (!window.confirm("Declassare questo caso? La fonte eventualmente promossa verrà disattivata.")) return;
    setCasesBusy(caseId);
    try {
      await api.declassifyCase(caseId);
      setCases((prev) => prev.filter((c) => c.id !== caseId));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Operazione non riuscita");
    } finally {
      setCasesBusy(null);
    }
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
          <h2>Video guida</h2>
          <p style={{ color: "var(--ink-muted)", fontSize: "0.85rem", marginTop: "-0.4rem" }}>
            Un video può esistere anche solo con il titolo, senza trascrizione: il tutor lo propone comunque
            se pertinente. La piattaforma è scelta qui, non nel codice — si può cambiare in ogni momento.
          </p>

          <form onSubmit={handleAddVideo} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <input placeholder="Titolo del video" value={newVideoTitle} onChange={(e) => setNewVideoTitle(e.target.value)} />
            <input placeholder="Link (Drive, Vimeo, ...)" value={newVideoUrl} onChange={(e) => setNewVideoUrl(e.target.value)} />
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <select value={newVideoPlatform} onChange={(e) => setNewVideoPlatform(e.target.value)} style={{ flex: 1, minWidth: 0 }}>
                {PLATFORM_OPTIONS.map((p) => (
                  <option key={p.slug} value={p.slug}>
                    {p.label}
                  </option>
                ))}
              </select>
              <select
                value={newVideoTechnique}
                onChange={(e) => setNewVideoTechnique(e.target.value)}
                style={{ flex: 1, minWidth: 0 }}
              >
                {TECHNIQUE_OPTIONS.map((t) => (
                  <option key={t.slug} value={t.slug}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <button className="primary-btn" type="submit" disabled={savingVideo || !newVideoTitle.trim() || !newVideoUrl.trim()}>
              {savingVideo ? "Salvataggio…" : "Aggiungi video"}
            </button>
          </form>

          {videos.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginTop: "1rem" }}>
              {videos.map((v) => (
                <div
                  key={v.id}
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
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v.title}</div>
                    <div style={{ color: "var(--ink-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {v.technique} · {v.url}
                    </div>
                  </div>
                  <select
                    value={v.platform}
                    onChange={(e) => handleVideoPlatformChange(v, e.target.value)}
                    style={{ fontSize: "0.8rem", padding: "0.3rem 0.4rem" }}
                  >
                    {PLATFORM_OPTIONS.map((p) => (
                      <option key={p.slug} value={p.slug}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                  <button className="icon-btn" onClick={() => handleVideoUrlEdit(v)}>
                    Link
                  </button>
                  <button className="icon-btn" onClick={() => handleDeleteVideo(v)} style={{ color: "var(--danger)" }}>
                    Elimina
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2>Carica nuovi materiali</h2>
          <p style={{ color: "var(--ink-muted)", fontSize: "0.85rem", marginTop: "-0.4rem" }}>
            Trascina anche più file insieme (CSV, .docx, .md, .txt). La categoria viene indovinata dal nome
            del file — controllala prima di confermare. Collega ogni file al video corrispondente (facoltativo:
            se il file è una trascrizione o una guida discorsiva dello stesso video, collegali entrambi allo
            stesso video così il tutor può combinarli e citare il timestamp giusto).
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
                    flexWrap: "wrap",
                    alignItems: "center",
                    gap: "0.5rem",
                    padding: "0.5rem 0",
                    borderBottom: "1px solid var(--border)",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ flex: "1 1 100%", minWidth: 0 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.file.name}</div>
                    {item.message && (
                      <div style={{ color: item.status === "error" ? "var(--danger)" : "var(--ink-muted)" }}>{item.message}</div>
                    )}
                  </div>
                  <select
                    value={item.technique}
                    onChange={(e) => updateItem(item.key, { technique: e.target.value })}
                    disabled={item.status === "uploading" || item.status === "done"}
                    style={{ fontSize: "0.8rem", padding: "0.4rem 0.5rem", minWidth: 0 }}
                  >
                    {TECHNIQUE_OPTIONS.map((t) => (
                      <option key={t.slug} value={t.slug}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={item.videoId}
                    onChange={(e) => updateItem(item.key, { videoId: e.target.value })}
                    disabled={item.status === "uploading" || item.status === "done"}
                    style={{ fontSize: "0.8rem", padding: "0.4rem 0.5rem", flex: 1, minWidth: "8rem" }}
                  >
                    <option value="">Nessun video collegato</option>
                    {videos.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.title}
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
                      {s.video_title && ` · video: ${s.video_title}`}
                    </div>
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="icon-btn" onClick={() => toggleSource(s)}>
                      {s.status === "active" ? "Disattiva" : "Attiva"}
                    </button>
                    <button className="icon-btn" onClick={() => handleDeleteSource(s)} style={{ color: "var(--danger)" }}>
                      Elimina
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
          <h2>Casi</h2>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.7rem" }}>
            {CASE_FILTERS.map((f) => (
              <button
                key={f.stato}
                className="icon-btn"
                style={casesFilter === f.stato ? { borderColor: "var(--accent-1)", color: "var(--accent-ink)" } : undefined}
                onClick={() => setCasesFilter(f.stato)}
              >
                {f.label}
              </button>
            ))}
          </div>
          {cases.length === 0 && <p style={{ color: "var(--ink-muted)" }}>Nessun caso in questo stato.</p>}
          {cases.map((c) => (
            <div key={c.id} style={{ padding: "0.6rem 0", borderBottom: "1px solid var(--border)" }}>
              <div>
                <b>{c.problema_osservato || c.area || "Caso senza descrizione"}</b>
                {c.tecnica && <> — {c.tecnica}</>}
              </div>
              <div style={{ color: "var(--ink-muted)", fontSize: "0.85rem" }}>
                {[
                  c.base_partenza && `Base: ${c.base_partenza}`,
                  c.capelli_bianchi && `Bianchi: ${c.capelli_bianchi}`,
                  c.porosita && `Porosità: ${c.porosita}`,
                  c.zona_coinvolta && `Zona: ${c.zona_coinvolta}`,
                  c.risultato_reale && `Risultato: ${c.risultato_reale}`,
                ]
                  .filter(Boolean)
                  .join(" · ") || "Scheda diagnostica incompleta"}
              </div>
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.4rem" }}>
                {c.stato === "DA_VALIDARE" && (
                  <>
                    <button className="icon-btn" disabled={casesBusy === c.id} onClick={() => handleValidateCase(c.id)}>
                      Valida → Knowledge
                    </button>
                    <button className="icon-btn" disabled={casesBusy === c.id} onClick={() => handleDeclassifyCase(c.id)}>
                      Rifiuta
                    </button>
                  </>
                )}
                {c.stato === "VALIDATO_PER_KNOWLEDGE" && (
                  <button className="icon-btn" disabled={casesBusy === c.id} onClick={() => handleDeclassifyCase(c.id)}>
                    Declassa/ritira
                  </button>
                )}
              </div>
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
