"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, getToken, type ConversationSummary } from "@/lib/api";

export default function HistoryPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api.listConversations().then(setConversations).catch(() => setError("Non sono riuscito a caricare la cronologia."));
  }, [router]);

  const statusLabel: Record<string, string> = {
    bot: "In corso",
    escalated: "Passata a un tutor",
    human_active: "Gestita da un tutor",
    closed: "Chiusa",
  };

  return (
    <div className="page">
      <div className="top-bar">
        <h1>Cronologia</h1>
        <Link href="/chat" className="icon-btn">
          Nuova chat
        </Link>
      </div>

      {error && <p className="error-text" style={{ padding: "0 1rem" }}>{error}</p>}

      {conversations.length === 0 && !error && (
        <div className="empty-state">Nessuna conversazione ancora. Torna alla chat per iniziare.</div>
      )}

      <ul className="history-list">
        {conversations.map((c) => (
          <li key={c.id}>
            <Link href={`/chat?c=${c.id}`}>
              <div>{c.channel === "web" ? "Chat web" : "WhatsApp"}</div>
              <div className="status">
                {statusLabel[c.status] || c.status} · {new Date(c.updated_at).toLocaleString("it-IT")}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
