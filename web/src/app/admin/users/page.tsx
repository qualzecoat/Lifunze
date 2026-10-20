"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface UserRow {
  id: number;
  username: string;
  nama_lengkap: string | null;
  role: string;
  is_active: boolean;
  dibuat_oleh: { id: number; username: string; role: string } | null;
}

export default function AdminUsersPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [rows, setRows] = useState<UserRow[]>([]);
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [form, setForm] = useState({ username: "", nama_lengkap: "", password: "" });

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (roleFilter) params.set("role", roleFilter);
    if (search) params.set("search", search);
    try {
      setRows(await apiFetch<UserRow[]>(`/api/v1/admin/users?${params.toString()}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat user.");
    }
  }, [roleFilter, search]);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else if (u.role !== "admin") router.push("/dashboard");
      else setUser(u);
    });
  }, [router]);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  async function onCreateTeacher(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      await apiFetch("/api/v1/admin/teachers", { method: "POST", body: form });
      setOk(`Akun guru ${form.username} dibuat (password sementara).`);
      setForm({ username: "", nama_lengkap: "", password: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat guru.");
    }
  }

  async function resetPassword(r: UserRow) {
    const pw = window.prompt(`Password baru untuk ${r.username} (min. 8 karakter, bersifat sementara):`);
    if (!pw) return;
    try {
      await apiFetch(`/api/v1/admin/users/${r.id}`, { method: "PATCH", body: { new_password: pw } });
      setOk(`Password ${r.username} direset.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal reset password.");
    }
  }

  async function toggleActive(r: UserRow) {
    try {
      await apiFetch(`/api/v1/admin/users/${r.id}`, { method: "PATCH", body: { is_active: !r.is_active } });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengubah status.");
    }
  }

  async function remove(r: UserRow) {
    if (!window.confirm(`Hapus akun ${r.username}? Ini soft-delete: data tersimpan, akun tidak bisa login.`)) return;
    try {
      await apiFetch(`/api/v1/admin/users/${r.id}`, { method: "DELETE" });
      setOk(`Akun ${r.username} dihapus.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus.");
    }
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 16 }}>Kelola User</h1>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <form className="card" onSubmit={onCreateTeacher} style={{ marginBottom: 16 }}>
        <h3>➕ Tambah Guru</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
          <div>
            <label className="label">Username</label>
            <input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          </div>
          <div>
            <label className="label">Nama lengkap</label>
            <input className="input" value={form.nama_lengkap} onChange={(e) => setForm({ ...form, nama_lengkap: e.target.value })} />
          </div>
          <div>
            <label className="label">Password awal (sementara)</label>
            <input className="input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} minLength={8} required />
          </div>
        </div>
        <button className="btn btn-primary" type="submit" style={{ marginTop: 14 }}>Buat Akun Guru</button>
        <p className="muted" style={{ marginTop: 8 }}>Akun admin tidak dibuat dari sini — hanya lewat seed server.</p>
      </form>

      <div className="card">
        <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          <select className="select" style={{ width: 160 }} value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">Semua role</option>
            <option value="admin">Admin</option>
            <option value="guru">Guru</option>
            <option value="siswa">Siswa</option>
          </select>
          <input className="input" style={{ maxWidth: 260 }} placeholder="Cari username/nama..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <table className="table">
          <thead>
            <tr><th>Username</th><th>Nama</th><th>Role</th><th>Status</th><th>Dibuat Oleh</th><th>Aksi</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><strong>{r.username}</strong></td>
                <td>{r.nama_lengkap ?? "-"}</td>
                <td><span className="badge">{r.role}</span></td>
                <td>{r.is_active ? "aktif" : "nonaktif"}</td>
                <td>{r.dibuat_oleh ? `${r.dibuat_oleh.username} (${r.dibuat_oleh.role})` : "— seed —"}</td>
                <td>
                  <div className="row-actions">
                    <button className="btn btn-sm" onClick={() => resetPassword(r)}>Reset PW</button>
                    <button className="btn btn-sm" onClick={() => toggleActive(r)}>{r.is_active ? "Nonaktifkan" : "Aktifkan"}</button>
                    {r.role !== "admin" && r.id !== user.id && (
                      <button className="btn btn-sm btn-danger" onClick={() => remove(r)}>Hapus</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={6} className="muted">Tidak ada user.</td></tr>}
          </tbody>
        </table>
      </div>
    </main>
  );
}
