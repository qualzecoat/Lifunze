"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import TabsBar from "@/components/TabsBar";
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
interface BankQuestion {
  id: number;
  tipe: string;
  pertanyaan: string;
  bobot: number;
  options: { label: string; teks: string; is_correct: boolean }[] | null;
  jawaban_referensi: string | null;
  kategori_id: number | null;
}
interface ExploreMaterial extends SavedMaterial {
  pemilik: { username: string; nama_lengkap: string | null };
}
interface ExploreQuiz extends SavedQuiz {
  pemilik: { username: string; nama_lengkap: string | null };
}
interface TemplateRow {
  id: number;
  nama: string;
  deskripsi: string | null;
  jumlah_pertemuan: number;
  jumlah_materi: number;
  jumlah_kuis: number;
}

export default function BankPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [materials, setMaterials] = useState<SavedMaterial[]>([]);
  const [quizzes, setQuizzes] = useState<SavedQuiz[]>([]);
  const [questions, setQuestions] = useState<BankQuestion[]>([]);
  const [exploreMats, setExploreMats] = useState<ExploreMaterial[]>([]);
  const [exploreQuizzes, setExploreQuizzes] = useState<ExploreQuiz[]>([]);
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [extractFor, setExtractFor] = useState<number | null>(null);
  const [newCat, setNewCat] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  type TabKey = "materi" | "kuis" | "soal" | "template" | "jelajahi";
  const [tab, setTab] = useState<TabKey>("materi");
  const [okJump, setOkJump] = useState<{ label: string; tab: TabKey } | null>(null);
  // form soal baru
  const [qTipe, setQTipe] = useState<"pilihan_ganda" | "teks">("pilihan_ganda");
  const [qPertanyaan, setQPertanyaan] = useState("");
  const [qBobot, setQBobot] = useState("1");
  const [qKategori, setQKategori] = useState("");
  const [qRef, setQRef] = useState("");
  const [qOptions, setQOptions] = useState<{ teks: string; benar: boolean }[]>([
    { teks: "", benar: false },
    { teks: "", benar: true },
  ]);

  const load = useCallback(async () => {
    try {
      setCategories(await apiFetch<Category[]>("/api/v1/bank/categories"));
      setMaterials(await apiFetch<SavedMaterial[]>("/api/v1/bank/materials"));
      setQuizzes(await apiFetch<SavedQuiz[]>("/api/v1/bank/quizzes"));
      setQuestions(await apiFetch<BankQuestion[]>("/api/v1/bank/questions"));
      setExploreMats(await apiFetch<ExploreMaterial[]>("/api/v1/bank/explore/materials"));
      setExploreQuizzes(await apiFetch<ExploreQuiz[]>("/api/v1/bank/explore/quizzes"));
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
        const awal = new URLSearchParams(window.location.search).get("tab");
        if (awal && ["materi", "kuis", "soal", "template", "jelajahi"].includes(awal)) {
          setTab(awal as TabKey);
        }
        load();
        loadTemplates();
      }
    });
  }, [router, load]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  function gantiTab(k: TabKey) {
    setTab(k);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", k);
    window.history.replaceState(null, "", url.toString());
  }

  function showOk(teks: string, jump?: { label: string; tab: TabKey }) {
    setOk(teks);
    setOkJump(jump ?? null);
  }

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
    showOk("Kuis bank dihapus.");
    load();
  }

  async function extractToBankSoal(q: SavedQuiz, kategoriId: number | null) {
    setError("");
    setOk("");
    setExtractFor(null);
    try {
      const qs = kategoriId ? `?kategori_id=${kategoriId}` : "";
      const r = await apiFetch<{ dimasukkan: number; dilewati: number }>(
        `/api/v1/bank/quizzes/${q.id}/extract-questions${qs}`,
        { method: "POST" },
      );
      showOk(
        `Dari kuis "${q.judul}": ${r.dimasukkan} soal dimasukkan ke bank soal` +
          (r.dilewati > 0 ? `, ${r.dilewati} dilewati karena sudah ada.` : "."),
        { label: "Lihat di Bank Soal →", tab: "soal" },
      );
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memasukkan ke bank soal.");
    }
  }

  async function setQuestionCategory(q: BankQuestion, value: string) {
    setError("");
    setOk("");
    try {
      await apiFetch(`/api/v1/bank/questions/${q.id}`, {
        method: "PATCH",
        body: {
          tipe: q.tipe,
          pertanyaan: q.pertanyaan,
          bobot: q.bobot,
          options: q.options,
          jawaban_referensi: q.jawaban_referensi,
          kategori_id: value ? Number(value) : null,
        },
      });
      showOk("Kategori soal diperbarui.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengubah kategori soal.");
    }
  }

  // -- Template Kelas --
  async function loadTemplates() {
    try {
      setTemplates(await apiFetch<TemplateRow[]>("/api/v1/class-templates"));
    } catch {
      /* abaikan */
    }
  }

  async function deleteTemplate(t: TemplateRow) {
    if (!window.confirm(`Hapus template kelas "${t.nama}"? Kelas yang sudah dibuat darinya tidak ikut terhapus.`)) return;
    await apiFetch(`/api/v1/class-templates/${t.id}`, { method: "DELETE" });
    showOk("Template kelas dihapus.");
    loadTemplates();
  }

  async function instantiateTemplate(t: TemplateRow) {
    const nama = window.prompt("Nama kelas baru:", t.nama);
    if (!nama) return;
    setError("");
    try {
      const r = await apiFetch<{ id: number }>(`/api/v1/class-templates/${t.id}/instantiate`, {
        method: "POST",
        body: { nama },
      });
      router.push(`/kelas/${r.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat kelas dari template.");
    }
  }

  async function addQuestion(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await apiFetch("/api/v1/bank/questions", {
        method: "POST",
        body: {
          tipe: qTipe,
          pertanyaan: qPertanyaan,
          bobot: Number(qBobot) || 1,
          kategori_id: qKategori ? Number(qKategori) : null,
          options:
            qTipe === "pilihan_ganda"
              ? qOptions.map((o, i) => ({
                  label: String.fromCharCode(65 + i),
                  teks: o.teks,
                  is_correct: o.benar,
                }))
              : null,
          jawaban_referensi: qTipe === "teks" ? qRef || null : null,
        },
      });
      setQPertanyaan("");
      setQRef("");
      setQOptions([
        { teks: "", benar: false },
        { teks: "", benar: true },
      ]);
      showOk("Soal ditambahkan ke bank soal.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menambah soal.");
    }
  }

  async function deleteQuestion(q: BankQuestion) {
    if (!window.confirm("Hapus soal ini dari bank soal?")) return;
    await apiFetch(`/api/v1/bank/questions/${q.id}`, { method: "DELETE" });
    load();
  }

  async function copyMaterial(id: number) {
    try {
      await apiFetch(`/api/v1/bank/materials/${id}/copy`, { method: "POST" });
      showOk("Materi disalin ke bank Anda.", { label: "Lihat Materi Saya →", tab: "materi" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyalin materi.");
    }
  }

  async function copyQuiz(id: number) {
    try {
      await apiFetch(`/api/v1/bank/quizzes/${id}/copy`, { method: "POST" });
      showOk("Kuis disalin ke bank Anda.", { label: "Lihat Kuis Saya →", tab: "kuis" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyalin kuis.");
    }
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>📚 Bank Materi & Kuis</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Koleksi pribadi Anda — pakai ulang ke kelas & pertemuan mana pun dari halaman kelas.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && (
        <div className="alert alert-ok">
          {ok}{" "}
          {okJump && (
            <button className="btn btn-sm" style={{ marginLeft: 8 }} onClick={() => gantiTab(okJump.tab)}>
              {okJump.label}
            </button>
          )}
        </div>
      )}

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

      <TabsBar
        active={tab}
        onChange={(k) => gantiTab(k as TabKey)}
        tabs={[
          { key: "materi", label: `📘 Materi (${materials.length})` },
          { key: "kuis", label: `🧪 Kuis (${quizzes.length})` },
          { key: "soal", label: `🎲 Bank Soal (${questions.length})` },
          { key: "template", label: `🏫 Template (${templates.length})` },
          { key: "jelajahi", label: `🔍 Jelajahi (${exploreMats.length + exploreQuizzes.length})` },
        ]}
      />

      <div style={{ display: tab === "materi" ? undefined : "none" }}>
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
      </div>

      <div style={{ display: tab === "kuis" ? undefined : "none" }}>
      <div className="card">
        <h3>Kuis Tersimpan ({quizzes.length})</h3>
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>Judul</th><th>Tipe</th><th>Soal</th><th>Kategori</th><th>Aksi</th></tr></thead>
          <tbody>
            {quizzes.map((q) => (
              <Fragment key={q.id}>
              <tr>
                <td><strong>{q.judul}</strong></td>
                <td>{q.tipe === "pilihan_ganda" ? "Pilihan Ganda" : "Esai/Teks"}</td>
                <td>{q.jumlah_soal}</td>
                <td>{catName(q.kategori_id)}</td>
                <td>
                  <span className="row-actions">
                    <button
                      className="btn btn-sm"
                      onClick={() => setExtractFor(extractFor === q.id ? null : q.id)}
                    >
                      📥 Ke Bank Soal
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => deleteQuiz(q)}>Hapus</button>
                  </span>
                </td>
              </tr>
              {extractFor === q.id && (
                <tr>
                  <td colSpan={5} style={{ background: "#f6f3ff" }}>
                    <span className="muted" style={{ marginRight: 8 }}>
                      Masukkan soal kuis ini ke bank soal dengan kategori:
                    </span>
                    <span className="row-actions" style={{ display: "inline-flex" }}>
                      <button className="btn btn-sm" onClick={() => extractToBankSoal(q, null)}>
                        Ikuti kategori kuis ({catName(q.kategori_id)})
                      </button>
                      {categories.map((c) => (
                        <button key={c.id} className="btn btn-sm" onClick={() => extractToBankSoal(q, c.id)}>
                          {c.nama}
                        </button>
                      ))}
                      <button className="btn btn-sm btn-danger" onClick={() => setExtractFor(null)}>Batal</button>
                    </span>
                  </td>
                </tr>
              )}
              </Fragment>
            ))}
            {quizzes.length === 0 && <tr><td colSpan={5} className="muted">Belum ada kuis di bank. Kuis dibuat dari pertemuan (modul kuis) lalu bisa disimpan ke bank.</td></tr>}
          </tbody>
        </table>
      </div>
      </div>

      <div style={{ display: tab === "soal" ? undefined : "none" }}>
      <div className="card" style={{ marginTop: 14 }}>
        <h3>🎲 Bank Soal ({questions.length})</h3>
        <p className="muted" style={{ margin: "6px 0 10px" }}>
          Soal lepas per butir. Susun kuis acak dari bank ini lewat tombol “Susun dari Bank Soal” di halaman kelas,
          atau ekstrak soal dari kuis yang sudah ada (halaman kuis → Ekstrak Soal).
        </p>
        {questions.map((q) => (
          <div key={q.id} style={{ padding: "7px 0", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", gap: 10 }}>
            <div>
              <strong>{q.pertanyaan}</strong>{" "}
              <span className="badge">{q.tipe === "pilihan_ganda" ? "PG" : "Esai"}</span>{" "}
              <span className="badge">bobot {q.bobot}</span>{" "}
              <select
                className="select"
                style={{ width: "auto", display: "inline-block", padding: "2px 6px", fontSize: "0.85rem" }}
                value={q.kategori_id ?? ""}
                onChange={(e) => setQuestionCategory(q, e.target.value)}
                title="Kategori soal — ubah untuk memindahkan"
              >
                <option value="">— tanpa kategori —</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.nama}</option>
                ))}
              </select>
              {q.options && (
                <div className="muted">
                  {q.options.map((o) => (
                    <span key={o.label} style={{ marginRight: 10, color: o.is_correct ? "var(--ok)" : undefined }}>
                      {o.is_correct ? "✅" : "▫️"} {o.label}. {o.teks}
                    </span>
                  ))}
                </div>
              )}
              {q.jawaban_referensi && <div className="muted">Referensi: {q.jawaban_referensi}</div>}
            </div>
            <button className="btn btn-sm btn-danger" onClick={() => deleteQuestion(q)}>Hapus</button>
          </div>
        ))}
        {questions.length === 0 && <p className="muted">Belum ada soal di bank soal.</p>}

        <form onSubmit={addQuestion} style={{ marginTop: 14 }}>
          <h4>Tambah soal baru</h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10, marginTop: 8 }}>
            <div>
              <label className="label">Tipe</label>
              <select className="select" value={qTipe} onChange={(e) => setQTipe(e.target.value as "pilihan_ganda" | "teks")}>
                <option value="pilihan_ganda">Pilihan Ganda</option>
                <option value="teks">Esai</option>
              </select>
            </div>
            <div>
              <label className="label">Bobot</label>
              <input className="input" type="number" step="0.5" min="0.5" value={qBobot} onChange={(e) => setQBobot(e.target.value)} />
            </div>
            <div>
              <label className="label">Kategori</label>
              <select className="select" value={qKategori} onChange={(e) => setQKategori(e.target.value)}>
                <option value="">— tanpa kategori —</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.nama}</option>
                ))}
              </select>
            </div>
          </div>
          <label className="label">Pertanyaan</label>
          <textarea className="textarea" rows={2} value={qPertanyaan} onChange={(e) => setQPertanyaan(e.target.value)} required />
          {qTipe === "pilihan_ganda" ? (
            <div style={{ marginTop: 8 }}>
              {qOptions.map((o, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center" }}>
                  <strong>{String.fromCharCode(65 + i)}.</strong>
                  <input
                    className="input"
                    placeholder={`Teks opsi ${String.fromCharCode(65 + i)}`}
                    value={o.teks}
                    onChange={(e) => {
                      const next = [...qOptions];
                      next[i] = { ...next[i], teks: e.target.value };
                      setQOptions(next);
                    }}
                    required
                  />
                  <label>
                    <input
                      type="checkbox"
                      checked={o.benar}
                      onChange={(e) => {
                        const next = [...qOptions];
                        next[i] = { ...next[i], benar: e.target.checked };
                        setQOptions(next);
                      }}
                    />{" "}
                    Benar
                  </label>
                  {qOptions.length > 2 && (
                    <button type="button" className="btn btn-sm" onClick={() => setQOptions(qOptions.filter((_, x) => x !== i))}>✕</button>
                  )}
                </div>
              ))}
              {qOptions.length < 6 && (
                <button type="button" className="btn btn-sm" onClick={() => setQOptions([...qOptions, { teks: "", benar: false }])}>➕ Opsi</button>
              )}
            </div>
          ) : (
            <div style={{ marginTop: 8 }}>
              <label className="label">Jawaban referensi (pedoman penilaian)</label>
              <textarea className="textarea" rows={2} value={qRef} onChange={(e) => setQRef(e.target.value)} />
            </div>
          )}
          <button className="btn btn-primary" type="submit" style={{ marginTop: 10 }}>➕ Tambah Soal</button>
        </form>
      </div>
      </div>

      <div style={{ display: tab === "template" ? undefined : "none" }}>
      <div className="card" style={{ marginTop: 14 }}>
        <h3>🏫 Template Kelas ({templates.length})</h3>
        <p className="muted" style={{ margin: "6px 0 10px" }}>
          Kelas utuh yang Anda simpan sebagai template — pertemuan, materi, dan kuisnya bisa
          dipakai ulang untuk membuka kelas baru (tanpa siswa & tanpa jadwal).
        </p>
        {templates.map((t) => (
          <div key={t.id} style={{ padding: "7px 0", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
            <div>
              <strong>{t.nama}</strong>{" "}
              <span className="muted">
                {t.jumlah_pertemuan} pertemuan · {t.jumlah_materi} materi · {t.jumlah_kuis} kuis
              </span>
              {t.deskripsi && <div className="muted">{t.deskripsi}</div>}
            </div>
            <span className="row-actions">
              <button className="btn btn-sm btn-primary" onClick={() => instantiateTemplate(t)}>➕ Buat Kelas</button>
              <button className="btn btn-sm btn-danger" onClick={() => deleteTemplate(t)}>Hapus</button>
            </span>
          </div>
        ))}
        {templates.length === 0 && (
          <p className="muted">Belum ada template. Simpan dari menu Kelas (tombol "Simpan Template") atau dari halaman kelas.</p>
        )}
      </div>
      </div>

      <div style={{ display: tab === "jelajahi" ? undefined : "none" }}>
      <div className="card" style={{ marginTop: 14 }}>
        <h3>🔍 Jelajahi Bank Guru Lain</h3>
        <p className="muted" style={{ margin: "6px 0 10px" }}>Salin materi/kuis guru lain ke bank Anda — aslinya tidak berubah.</p>
        {exploreMats.map((m) => (
          <div key={`m-${m.id}`} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
            <span>📄 {m.judul} <span className="muted">— oleh {m.pemilik.nama_lengkap ?? m.pemilik.username}</span></span>
            <button className="btn btn-sm" onClick={() => copyMaterial(m.id)}>📥 Salin</button>
          </div>
        ))}
        {exploreQuizzes.map((q) => (
          <div key={`q-${q.id}`} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
            <span>🧪 {q.judul} <span className="muted">({q.jumlah_soal} soal) — oleh {q.pemilik.nama_lengkap ?? q.pemilik.username}</span></span>
            <button className="btn btn-sm" onClick={() => copyQuiz(q.id)}>📥 Salin</button>
          </div>
        ))}
        {exploreMats.length === 0 && exploreQuizzes.length === 0 && (
          <p className="muted">Belum ada bank dari guru lain.</p>
        )}
      </div>
      </div>
    </main>
  );
}
