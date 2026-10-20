"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Logo from "@/components/Logo";
import { apiFetch, type User } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await apiFetch<{ user: User }>("/api/v1/auth/login", {
        method: "POST",
        body: { username, password },
      });
      router.push(res.user.must_change_password ? "/ganti-password" : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal login.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
    >
      <form className="card" onSubmit={onSubmit} style={{ width: "100%", maxWidth: 380 }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
          <Logo size={44} />
        </div>
        <p className="muted" style={{ textAlign: "center", marginBottom: 8 }}>
          Serunya Belajar, Mudahnya Mengajar.
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        <label className="label" htmlFor="username">Username</label>
        <input
          id="username"
          className="input"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
        <label className="label" htmlFor="password">Password</label>
        <input
          id="password"
          className="input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        <button
          className="btn btn-primary"
          type="submit"
          disabled={loading}
          style={{ width: "100%", justifyContent: "center", marginTop: 20 }}
        >
          {loading ? "Memproses..." : "Masuk"}
        </button>
        <p className="muted" style={{ marginTop: 14, textAlign: "center" }}>
          Belum punya akun? Akun dibuatkan oleh guru atau admin Anda.
        </p>
      </form>
    </main>
  );
}
