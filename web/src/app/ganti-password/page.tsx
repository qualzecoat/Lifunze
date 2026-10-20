"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

export default function GantiPasswordPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else setUser(u);
    });
  }, [router]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  const firstLogin = user.must_change_password;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOk("");
    if (newPw !== confirmPw) {
      setError("Konfirmasi password baru tidak sama.");
      return;
    }
    setLoading(true);
    try {
      if (firstLogin) {
        await apiFetch("/api/v1/auth/first-login-password", {
          method: "POST",
          body: { new_password: newPw },
        });
      } else {
        await apiFetch("/api/v1/auth/change-password", {
          method: "POST",
          body: { old_password: oldPw, new_password: newPw },
        });
      }
      setOk("Password berhasil diganti. Mengalihkan ke dashboard...");
      setTimeout(() => router.push("/dashboard"), 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengganti password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <form className="card" onSubmit={onSubmit} style={{ maxWidth: 460 }}>
        <h2 style={{ marginBottom: 6 }}>{firstLogin ? "Buat Password Baru" : "Ganti Password"}</h2>
        {firstLogin && (
          <p className="muted">
            Ini login pertama Anda dengan password sementara. Buat password baru (minimal 8 karakter) untuk melanjutkan.
          </p>
        )}
        {error && <div className="alert alert-error">{error}</div>}
        {ok && <div className="alert alert-ok">{ok}</div>}
        {!firstLogin && (
          <>
            <label className="label" htmlFor="old">Password lama</label>
            <input id="old" className="input" type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} required />
          </>
        )}
        <label className="label" htmlFor="new">Password baru</label>
        <input id="new" className="input" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} minLength={8} required />
        <label className="label" htmlFor="confirm">Konfirmasi password baru</label>
        <input id="confirm" className="input" type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} minLength={8} required />
        <button className="btn btn-primary" type="submit" disabled={loading} style={{ marginTop: 18 }}>
          {loading ? "Menyimpan..." : "Simpan Password"}
        </button>
      </form>
    </main>
  );
}
