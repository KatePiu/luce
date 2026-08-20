"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import LuceMark from "@/components/LuceMark";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { access_token } = await api.login(email, password);
      setToken(access_token);
      router.replace("/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Accesso non riuscito");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="form-page" onSubmit={handleSubmit}>
      <h1>
        <LuceMark size={30} />
        LUCE
      </h1>
      <p style={{ color: "var(--ink-muted)", marginTop: 0 }}>
        Accedi con l&apos;account fornito dall&apos;Accademia Coppola.
      </p>

      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      {error && <p className="error-text">{error}</p>}

      <button className="primary-btn" type="submit" disabled={loading}>
        {loading ? "Accesso in corso…" : "Accedi"}
      </button>
    </form>
  );
}
