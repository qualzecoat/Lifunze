"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface StudentRow {
  id: number;
  username: string;
  nama_lengkap: string | null;
  is_active: boolean;
  must_change_password: boolean;
  dibuat_oleh: { id: number; username: string; role: string } | null;
}

export default function SiswaPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [form, setForm] = useState({ username: "", nama_lengkap: "", password: "" });
  const [importResult, setImportResult] = useState<{ berhasil: number; gagal: { baris: number; username: string; pesan: string }[] } | null>(null);
  const [subjects, setSubjects] = useState<{ id: number; nama: string }[]>([]);
  const [importKelas, setImportKelas] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setStudents(await apiFetch<StudentRow[]>("/api/v1/users/students"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat siswa.");
    }
  }, []);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else if (u.role === "siswa") router.push("/dashboard");
      else {
        setUser(u);
        load();
        apiFetch<{ id: number; nama: string }[]>("/api/v1/subjects").then(setSubjects).catch(() => {});
      }
    });
  }, [router, load]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      await apiFetch("/api/v1/users/students", { method: "POST", body: form });
      setOk(`Akun siswa ${form.username} dibuat. Password awal bersifat sementara — siswa wajib menggantinya saat login pertama.`);
      setForm({ username: "", nama_lengkap: "", password: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat siswa.");
    }
  }

  async function onImport() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setError("");
    setImportResult(null);
    const fd = new FormData();
    fd.append("file", file);
    if (importKelas) fd.append("subject_id", importKelas);
    try {
      const res = await apiFetch<{ berhasil: number; gagal: { baris: number; username: string; pesan: string }[] }>(
        "/api/v1/users/students/import",
        { method: "POST", formData: fd },
      );
      setImportResult(res);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import gagal.");
    }
  }

  async function resetPassword(s: StudentRow) {
    const pw = window.prompt(`Password baru untuk ${s.username} (min. 8 karakter, bersifat sementara):`);
    if (!pw) return;
    try {
      await apiFetch(`/api/v1/users/students/${s.id}`, { method: "PATCH", body: { new_password: pw } });
      setOk(`Password ${s.username} direset.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal reset password.");
    }
  }

  async function toggleActive(s: StudentRow) {
    try {
      await apiFetch(`/api/v1/users/students/${s.id}`, { method: "PATCH", body: { is_active: !s.is_active } });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengubah status.");
    }
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>Kelola Siswa</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        {user.role === "guru"
          ? "Anda hanya melihat & mengelola siswa yang Anda buat."
          : "Sebagai admin, Anda melihat semua siswa."}
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 14, marginBottom: 16 }}>
        <form className="card" onSubmit={onCreate}>
          <h3>➕ Tambah Siswa</h3>
          <label className="label">Username</label>
          <input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          <label className="label">Nama lengkap</label>
          <input className="input" value={form.nama_lengkap} onChange={(e) => setForm({ ...form, nama_lengkap: e.target.value })} />
          <label className="label">Password awal (sementara)</label>
          <input className="input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} minLength={8} required />
          <button className="btn btn-primary" type="submit" style={{ marginTop: 16 }}>Buat Akun</button>
        </form>

        <div className="card">
          <h3>📥 Import CSV</h3>
          <p className="muted">
            Format: header <code>username,nama_lengkap,password</code>. Baris yang gagal tidak membatalkan baris lain.
          </p>
          <input ref={fileRef} type="file" accept=".csv,text/csv" style={{ margin: "12px 0" }} />
          <label className="label">Langsung daftarkan ke kelas (opsional)</label>
          <select className="select" value={importKelas} onChange={(e) => setImportKelas(e.target.value)}>
            <option value="">— tidak didaftarkan —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>{s.nama}</option>
            ))}
          </select>
          <br />
          <button className="btn" onClick={onImport}>Import</button>
          {importResult && (
            <div style={{ marginTop: 12 }}>
              <p>✅ Berhasil: <strong>{importResult.berhasil}</strong></p>
              {importResult.gagal.map((g) => (
                <p key={g.baris} className="muted">❌ Baris {g.baris} ({g.username}): {g.pesan}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr><th>Username</th><th>Nama</th><th>Status</th><th>Dibuat Oleh</th><th>Aksi</th></tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr key={s.id}>
                <td><strong>{s.username}</strong></td>
                <td>{s.nama_lengkap ?? "-"}</td>
                <td>{s.is_active ? <span className="badge">aktif</span> : <span className="badge badge-off">nonaktif</span>}</td>
                <td>{s.dibuat_oleh?.username ?? "-"}</td>
                <td>
                  <div className="row-actions">
                    <button className="btn btn-sm" onClick={() => resetPassword(s)}>Reset PW</button>
                    <button className="btn btn-sm" onClick={() => toggleActive(s)}>{s.is_active ? "Nonaktifkan" : "Aktifkan"}</button>
                  </div>
                </td>
              </tr>
            ))}
            {students.length === 0 && (
              <tr><td colSpan={5} className="muted">Belum ada siswa.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
