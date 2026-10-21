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

interface ClassTemplateRow {
  id: number;
  nama: string;
  deskripsi: string | null;
  jumlah_pertemuan: number;
  jumlah_materi: number;
  jumlah_kuis: number;
}

export default function KelasPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [subjects, setSubjects] = useState<SubjectRow[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ nama: "", deskripsi: "" });
  const [showArchived, setShowArchived] = useState(false);
  const [templates, setTemplates] = useState<ClassTemplateRow[]>([]);
  const [tplForm, setTplForm] = useState({ template_id: "", nama: "" });
  const [ok, setOk] = useState("");

  const loadTemplates = useCallback(async () => {
    try {
      setTemplates(await apiFetch<ClassTemplateRow[]>("/api/v1/class-templates"));
    } catch {
      /* template opsional; abaikan bila gagal */
    }
  }, []);

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
        if (u.role === "guru" || u.role === "admin") loadTemplates();
      }
    });
  }, [router, load, loadTemplates]);

  function bisaKelola(s: SubjectRow) {
    return user?.role === "admin" || s.dibuat_oleh === user?.id;
  }

  async function renameSubject(s: SubjectRow) {
    const nama = window.prompt("Nama baru kelas:", s.nama);
    if (!nama || nama === s.nama) return;
    await apiFetch(`/api/v1/subjects/${s.id}`, { method: "PATCH", body: { nama } });
    load();
  }

  async function toggleArchiveRow(s: SubjectRow) {
    await apiFetch(`/api/v1/subjects/${s.id}`, {
      method: "PATCH",
      body: { is_archived: !s.is_archived },
    });
    load();
  }

  async function deleteSubjectRow(s: SubjectRow) {
    if (!window.confirm(`Hapus kelas "${s.nama}" beserta seluruh isinya? Tindakan ini tidak bisa dibatalkan.`)) return;
    await apiFetch(`/api/v1/subjects/${s.id}`, { method: "DELETE" });
    load();
  }

  async function saveTemplateRow(s: SubjectRow) {
    const nama = window.prompt("Nama template:", s.nama);
    if (!nama) return;
    setError("");
    setOk("");
    try {
      await apiFetch(`/api/v1/subjects/${s.id}/save-template`, { method: "POST", body: { nama } });
      setOk(`Kelas "${s.nama}" tersimpan sebagai template "${nama}".`);
      loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan template.");
    }
  }

  async function instantiateFromTemplate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!tplForm.template_id || !tplForm.nama) return;
    try {
      const r = await apiFetch<{ id: number; peringatan?: string[] }>(
        `/api/v1/class-templates/${tplForm.template_id}/instantiate`,
        { method: "POST", body: { nama: tplForm.nama } },
      );
      // Audit #36: peringatan (mis. lampiran hilang) ditampilkan, tidak ditelan.
      if (r.peringatan && r.peringatan.length > 0) {
        window.alert(`Kelas dibuat, dengan catatan:\n\n${r.peringatan.join("\n")}`);
      }
      router.push(`/kelas/${r.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat kelas dari template.");
    }
  }

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
      {ok && <div className="alert alert-ok">{ok}</div>}

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

      {staff && templates.length > 0 && (
        <form className="card" onSubmit={instantiateFromTemplate} style={{ marginBottom: 16 }}>
          <h3>📋 Buat Kelas dari Template</h3>
          <p className="muted" style={{ marginBottom: 10 }}>
            Kelas baru berisi salinan pertemuan, materi, dan kuis dari template — tanpa siswa,
            tanpa jadwal/tanggal, dan tanpa jendela kuis.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
            <div>
              <label className="label">Template</label>
              <select
                className="input"
                value={tplForm.template_id}
                onChange={(e) => setTplForm({ ...tplForm, template_id: e.target.value })}
                required
              >
                <option value="">— pilih template —</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nama} ({t.jumlah_pertemuan} pertemuan, {t.jumlah_materi} materi, {t.jumlah_kuis} kuis)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Nama kelas baru</label>
              <input
                className="input"
                value={tplForm.nama}
                onChange={(e) => setTplForm({ ...tplForm, nama: e.target.value })}
                required
              />
            </div>
          </div>
          <button className="btn btn-primary" type="submit" style={{ marginTop: 14 }}>Buat dari Template</button>
        </form>
      )}

      {staff && (
        <label style={{ display: "block", marginBottom: 14 }}>
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />{" "}
          Tampilkan kelas arsip
        </label>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {subjects.map((s) => (
          <div key={s.id} className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 0 }}>
            <div style={{ minWidth: 220, flex: 1 }}>
              <h3 style={{ margin: 0 }}>
                {s.nama} {s.is_archived && <span className="badge badge-off">arsip</span>}
              </h3>
              <p className="muted" style={{ margin: "4px 0 0" }}>{s.deskripsi ?? "Tanpa deskripsi"}</p>
              <p className="muted" style={{ margin: "4px 0 0" }}>
                📅 {s.jumlah_pertemuan} pertemuan · 👩‍🎓 {s.jumlah_siswa} siswa
              </p>
            </div>
            <span className="row-actions">
              <Link className="btn btn-sm btn-primary" href={`/kelas/${s.id}`}>Buka</Link>
              {staff && bisaKelola(s) && (
                <>
                  <button className="btn btn-sm" onClick={() => renameSubject(s)}>✏️ Ubah Nama</button>
                  <button className="btn btn-sm" onClick={() => saveTemplateRow(s)}>💾 Simpan Template</button>
                  <button className="btn btn-sm" onClick={() => toggleArchiveRow(s)}>
                    {s.is_archived ? "Keluarkan dari Arsip" : "Arsipkan"}
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => deleteSubjectRow(s)}>Hapus</button>
                </>
              )}
            </span>
          </div>
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
