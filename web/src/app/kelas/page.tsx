"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

export interface SubjectRow {
  id: number;
  nama: string;
  deskripsi: string | null;
  dibuat_oleh: number;
  is_archived: boolean;
  jumlah_pertemuan: number;
  jumlah_siswa: number;
}

export default function KelasPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [subjects, setSubjects] = useState<SubjectRow[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ nama: "", deskripsi: "" });
  const [showArchived, setShowArchived] = useState(false);

  const load = useCallback(async () => {
    try {
      setSubjects(
        await apiFetch<SubjectRow[]>(`/api/v1/subjects${showArchived ? "?termasuk_arsip=true" : ""}`),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat kelas.");
    }
  }, [showArchived]);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else {
        setUser(u);
        load();
      }
    });
  }, [router, load]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;
  const staff = user.role === "guru" || user.role === "admin";

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await apiFetch("/api/v1/subjects", { method: "POST", body: form });
      setForm({ nama: "", deskripsi: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat kelas.");
    }
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>
        {user.role === "siswa" ? "Kelas yang Saya Ikuti" : "Kelas Saya"}
      </h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        {user.role === "siswa"
          ? "Mata pelajaran tempat Anda terdaftar."
          : "Mata pelajaran yang Anda buat dan kelola."}
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      {staff && (
        <form className="card" onSubmit={onCreate} style={{ marginBottom: 16 }}>
          <h3>➕ Buat Mata Pelajaran</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
            <div>
              <label className="label">Nama mata pelajaran</label>
              <input className="input" value={form.nama} onChange={(e) => setForm({ ...form, nama: e.target.value })} required />
            </div>
            <div>
              <label className="label">Deskripsi (opsional)</label>
              <input className="input" value={form.deskripsi} onChange={(e) => setForm({ ...form, deskripsi: e.target.value })} />
            </div>
          </div>
          <button className="btn btn-primary" type="submit" style={{ marginTop: 14 }}>Buat Kelas</button>
        </form>
      )}

      {staff && (
        <label style={{ display: "block", marginBottom: 14 }}>
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />{" "}
          Tampilkan kelas arsip
        </label>
      )}

      <div className="grid-cards">
        {subjects.map((s) => (
          <Link key={s.id} href={`/kelas/${s.id}`} className="card">
            <h3>{s.nama} {s.is_archived && <span className="badge badge-off">arsip</span>}</h3>
            <p className="muted">{s.deskripsi ?? "Tanpa deskripsi"}</p>
            <p className="muted" style={{ marginTop: 8 }}>
              📅 {s.jumlah_pertemuan} pertemuan · 👩‍🎓 {s.jumlah_siswa} siswa
            </p>
          </Link>
        ))}
        {subjects.length === 0 && (
          <p className="muted">
            {user.role === "siswa" ? "Anda belum terdaftar di kelas mana pun." : "Belum ada kelas. Buat lewat formulir di atas."}
          </p>
        )}
      </div>
    </main>
  );
}
