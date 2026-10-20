"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface Category {
  id: number;
  nama: string;
}
interface SavedMaterial {
  id: number;
  judul: string;
  kategori_id: number | null;
}
interface SavedQuiz {
  id: number;
  judul: string;
  tipe: string;
  kategori_id: number | null;
  jumlah_soal: number;
}

export default function BankPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [materials, setMaterials] = useState<SavedMaterial[]>([]);
  const [quizzes, setQuizzes] = useState<SavedQuiz[]>([]);
  const [newCat, setNewCat] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const load = useCallback(async () => {
    try {
      setCategories(await apiFetch<Category[]>("/api/v1/bank/categories"));
      setMaterials(await apiFetch<SavedMaterial[]>("/api/v1/bank/materials"));
      setQuizzes(await apiFetch<SavedQuiz[]>("/api/v1/bank/quizzes"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat bank.");
    }
  }, []);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else if (u.role === "siswa") router.push("/dashboard");
      else {
        setUser(u);
        load();
      }
    });
  }, [router, load]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  const catName = (id: number | null) => categories.find((c) => c.id === id)?.nama ?? "-";

  async function addCategory(e: React.FormEvent) {
    e.preventDefault();
    await apiFetch("/api/v1/bank/categories", { method: "POST", body: { nama: newCat } });
    setNewCat("");
    load();
  }

  async function deleteCategory(c: Category) {
    if (!window.confirm(`Hapus kategori "${c.nama}"? Isi bank tidak ikut terhapus (kategorinya dikosongkan).`)) return;
    await apiFetch(`/api/v1/bank/categories/${c.id}`, { method: "DELETE" });
    load();
  }

  async function deleteMaterial(m: SavedMaterial) {
    if (!window.confirm(`Hapus materi bank "${m.judul}"?`)) return;
    await apiFetch(`/api/v1/bank/materials/${m.id}`, { method: "DELETE" });
    load();
  }

  async function deleteQuiz(q: SavedQuiz) {
    if (!window.confirm(`Hapus kuis bank "${q.judul}"?`)) return;
    await apiFetch(`/api/v1/bank/quizzes/${q.id}`, { method: "DELETE" });
    setOk("Kuis bank dihapus.");
    load();
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>📚 Bank Materi & Kuis</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Koleksi pribadi Anda — pakai ulang ke kelas & pertemuan mana pun dari halaman kelas.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <div className="card" style={{ marginBottom: 14 }}>
        <h3>Kategori</h3>
        <form onSubmit={addCategory} style={{ display: "flex", gap: 8, margin: "10px 0", flexWrap: "wrap" }}>
          <input className="input" style={{ maxWidth: 280 }} placeholder="Nama kategori baru" value={newCat} onChange={(e) => setNewCat(e.target.value)} required />
          <button className="btn" type="submit">➕ Tambah</button>
        </form>
        <div className="row-actions">
          {categories.map((c) => (
            <span key={c.id} className="badge" style={{ fontSize: ".82rem", padding: "4px 10px" }}>
              {c.nama}{" "}
              <button onClick={() => deleteCategory(c)} style={{ background: "none", border: "none", cursor: "pointer", color: "inherit" }} title="Hapus kategori">✕</button>
            </span>
          ))}
          {categories.length === 0 && <span className="muted">Belum ada kategori.</span>}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap" }}>
          <h3>Materi Tersimpan ({materials.length})</h3>
          <Link className="btn btn-sm btn-primary" href="/editor/materi?mode=bank">➕ Materi Bank Baru</Link>
        </div>
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>Judul</th><th>Kategori</th><th>Aksi</th></tr></thead>
          <tbody>
            {materials.map((m) => (
              <tr key={m.id}>
                <td><strong>{m.judul}</strong></td>
                <td>{catName(m.kategori_id)}</td>
                <td>
                  <div className="row-actions">
                    <Link className="btn btn-sm" href={`/editor/materi?bank=${m.id}`}>✏️ Edit</Link>
                    <button className="btn btn-sm btn-danger" onClick={() => deleteMaterial(m)}>Hapus</button>
                  </div>
                </td>
              </tr>
            ))}
            {materials.length === 0 && <tr><td colSpan={3} className="muted">Belum ada materi di bank. Simpan dari editor materi atau buat baru.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Kuis Tersimpan ({quizzes.length})</h3>
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>Judul</th><th>Tipe</th><th>Soal</th><th>Kategori</th><th>Aksi</th></tr></thead>
          <tbody>
            {quizzes.map((q) => (
              <tr key={q.id}>
                <td><strong>{q.judul}</strong></td>
                <td>{q.tipe === "pilihan_ganda" ? "Pilihan Ganda" : "Esai/Teks"}</td>
                <td>{q.jumlah_soal}</td>
                <td>{catName(q.kategori_id)}</td>
                <td><button className="btn btn-sm btn-danger" onClick={() => deleteQuiz(q)}>Hapus</button></td>
              </tr>
            ))}
            {quizzes.length === 0 && <tr><td colSpan={5} className="muted">Belum ada kuis di bank. Kuis dibuat dari pertemuan (modul kuis) lalu bisa disimpan ke bank.</td></tr>}
          </tbody>
        </table>
      </div>
    </main>
  );
}
