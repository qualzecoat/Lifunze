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
  grup_dokumen: string | null;
  jenis: string;
}
interface SavedQuiz {
  id: number;
  judul: string;
  tipe: string;
  kategori_id: number | null;
  jumlah_soal: number;
  grup_dokumen: string | null;
  jenis: string;
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
  const [cariSoal, setCariSoal] = useState("");
  const [filterKatSoal, setFilterKatSoal] = useState("");
  const [newCat, setNewCat] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  type TabKey = "dokumen" | "soal" | "template" | "jelajahi";
  const [tab, setTab] = useState<TabKey>("dokumen");
  const [cariDok, setCariDok] = useState("");
  const [filterTagDok, setFilterTagDok] = useState("");
  const [filterKatDok, setFilterKatDok] = useState("");
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
        if (awal && ["dokumen", "soal", "template", "jelajahi"].includes(awal)) {
          setTab(awal as TabKey);
        } else if (awal === "materi" || awal === "kuis") {
          setTab("dokumen"); // tab lama digabung menjadi Dokumen
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

  const kataSoal = cariSoal.trim().toLowerCase();
  const questionsTampil = questions.filter((q) => {
    if (filterKatSoal === "tanpa") {
      if (q.kategori_id !== null) return false;
    } else if (filterKatSoal) {
      if (q.kategori_id !== Number(filterKatSoal)) return false;
    }
    if (kataSoal && !q.pertanyaan.toLowerCase().includes(kataSoal)) return false;
    return true;
  });

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
      showOk("Materi disalin ke bank Anda.", { label: "Lihat Dokumen Saya →", tab: "dokumen" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyalin materi.");
    }
  }

  async function copyQuiz(id: number) {
    try {
      await apiFetch(`/api/v1/bank/quizzes/${id}/copy`, { method: "POST" });
      showOk("Kuis disalin ke bank Anda.", { label: "Lihat Dokumen Saya →", tab: "dokumen" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyalin kuis.");
    }
  }

  async function copyBankDocument(grup: string) {
    try {
      await apiFetch(`/api/v1/bank/documents/${grup}/copy`, { method: "POST" });
      showOk("Dokumen disalin utuh ke bank Anda.", { label: "Lihat Dokumen Saya →", tab: "dokumen" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyalin dokumen.");
    }
  }

  async function deleteBankDocument(grup: string, judul: string) {
    if (!window.confirm(`Hapus dokumen bank "${judul}" (semua bagiannya)?`)) return;
    await apiFetch(`/api/v1/bank/documents/${grup}`, { method: "DELETE" });
    showOk("Dokumen bank dihapus.");
    load();
  }

  /** Dokumen bank terpadu: pasangan materi+kuis digabung jadi satu baris. */
  function dokumenBankRows() {
    interface BankBaris {
      kunci: string;
      grup: string | null;
      judul: string;
      jenis: string;
      kategori_id: number | null;
      material: SavedMaterial | null;
      quizzes: SavedQuiz[];
    }
    const rows: BankBaris[] = [];
    const terdaftar = new Set<string>();
    for (const m of materials) {
      if (m.grup_dokumen) {
        if (terdaftar.has(m.grup_dokumen)) continue;
        terdaftar.add(m.grup_dokumen);
        rows.push({
          kunci: `g-${m.grup_dokumen}`,
          grup: m.grup_dokumen,
          judul: m.judul,
          jenis: m.jenis,
          kategori_id: m.kategori_id,
          material: m,
          quizzes: quizzes.filter((q) => q.grup_dokumen === m.grup_dokumen),
        });
      } else {
        rows.push({ kunci: `m-${m.id}`, grup: null, judul: m.judul, jenis: m.jenis, kategori_id: m.kategori_id, material: m, quizzes: [] });
      }
    }
    for (const q of quizzes) {
      if (!q.grup_dokumen) {
        rows.push({ kunci: `q-${q.id}`, grup: null, judul: q.judul, jenis: q.jenis, kategori_id: q.kategori_id, material: null, quizzes: [q] });
      } else if (!terdaftar.has(q.grup_dokumen)) {
        terdaftar.add(q.grup_dokumen);
        rows.push({
          kunci: `g-${q.grup_dokumen}`,
          grup: q.grup_dokumen,
          judul: q.judul,
          jenis: q.jenis,
          kategori_id: q.kategori_id,
          material: null,
          quizzes: quizzes.filter((x) => x.grup_dokumen === q.grup_dokumen),
        });
      }
    }
    const kata = cariDok.trim().toLowerCase();
    return rows.filter((r) => {
      if (filterTagDok === "materi" && !r.material) return false;
      if (filterTagDok === "kuis_pg" && !r.quizzes.some((q) => q.tipe === "pilihan_ganda")) return false;
      if (filterTagDok === "esai" && !r.quizzes.some((q) => q.tipe === "teks")) return false;
      if (filterKatDok && String(r.kategori_id ?? "") !== filterKatDok) return false;
      if (kata && !r.judul.toLowerCase().includes(kata)) return false;
      return true;
    });
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
          { key: "dokumen", label: `📁 Dokumen (${dokumenBankRows().length})` },
          { key: "soal", label: `🎲 Bank Soal (${questions.length})` },
          { key: "template", label: `🏫 Template (${templates.length})` },
          { key: "jelajahi", label: `🔍 Jelajahi (${exploreMats.length + exploreQuizzes.length})` },
        ]}
      />

      <div style={{ display: tab === "dokumen" ? undefined : "none" }}>
      <div className="card" style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <h3>Dokumen Tersimpan ({dokumenBankRows().length})</h3>
          <Link className="btn btn-sm btn-primary" href="/editor/dokumen?mode=bank">➕ Dokumen Bank Baru</Link>
        </div>
        <p className="muted" style={{ margin: "4px 0 10px" }}>
          Materi dan kuis kini satu kesatuan dokumen — dibedakan lewat tag isinya, bukan tab terpisah.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
          <input
            className="input"
            style={{ maxWidth: 220 }}
            placeholder="Cari judul dokumen..."
            value={cariDok}
            onChange={(e) => setCariDok(e.target.value)}
          />
          <select className="select" style={{ maxWidth: 180 }} value={filterTagDok} onChange={(e) => setFilterTagDok(e.target.value)}>
            <option value="">Semua tag</option>
            <option value="materi">📖 Materi</option>
            <option value="kuis_pg">🧪 Kuis PG</option>
            <option value="esai">📝 Esai</option>
          </select>
          <select className="select" style={{ maxWidth: 200 }} value={filterKatDok} onChange={(e) => setFilterKatDok(e.target.value)}>
            <option value="">Semua kategori</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.nama}</option>
            ))}
          </select>
        </div>
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>Judul</th><th>Isi</th><th>Kategori</th><th>Aksi</th></tr></thead>
          <tbody>
            {dokumenBankRows().map((r) => {
              const kuisEkstrak = r.quizzes.find((q) => q.id === extractFor) ?? null;
              return (
                <Fragment key={r.kunci}>
                  <tr>
                    <td>
                      <strong>{r.judul}</strong>
                      {r.jenis === "tugas" && <> <span className="badge">📝 Tugas</span></>}
                      {r.jenis === "ujian" && <> <span className="badge">🏆 Ujian</span></>}
                      {r.jenis === "kuis" && r.material && <> <span className="badge">🧪 Kuis</span></>}
                    </td>
                    <td>
                      {r.material && <span className="badge">📖 Materi</span>}{" "}
                      {r.quizzes.map((q) => (
                        <span key={q.id} className="badge">
                          {q.tipe === "pilihan_ganda" ? `🧪 PG · ${q.jumlah_soal} soal` : `📝 Esai · ${q.jumlah_soal} soal`}
                        </span>
                      ))}
                    </td>
                    <td>{catName(r.kategori_id)}</td>
                    <td>
                      <div className="row-actions">
                        {r.grup ? (
                          <Link className="btn btn-sm" href={`/editor/dokumen?bank_grup=${r.grup}`}>✏️ Edit</Link>
                        ) : r.material ? (
                          <Link className="btn btn-sm" href={`/editor/materi?bank=${r.material.id}`}>✏️ Edit</Link>
                        ) : null}
                        {r.quizzes.map((q) => (
                          <button
                            key={q.id}
                            className="btn btn-sm"
                            onClick={() => setExtractFor(extractFor === q.id ? null : q.id)}
                          >
                            📥 {q.tipe === "pilihan_ganda" ? "PG" : "Esai"} ke Bank Soal
                          </button>
                        ))}
                        {r.grup ? (
                          <button className="btn btn-sm btn-danger" onClick={() => deleteBankDocument(r.grup!, r.judul)}>Hapus</button>
                        ) : r.material ? (
                          <button className="btn btn-sm btn-danger" onClick={() => deleteMaterial(r.material!)}>Hapus</button>
                        ) : (
                          <button className="btn btn-sm btn-danger" onClick={() => deleteQuiz(r.quizzes[0])}>Hapus</button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {kuisEkstrak && (
                    <tr>
                      <td colSpan={4} style={{ background: "#f6f3ff" }}>
                        <span className="muted" style={{ marginRight: 8 }}>
                          Masukkan soal {kuisEkstrak.tipe === "pilihan_ganda" ? "PG" : "esai"} "{kuisEkstrak.judul}" ke bank soal dengan kategori:
                        </span>
                        <span className="row-actions" style={{ display: "inline-flex" }}>
                          <button className="btn btn-sm" onClick={() => extractToBankSoal(kuisEkstrak, null)}>
                            Ikuti kategori dokumen ({catName(kuisEkstrak.kategori_id)})
                          </button>
                          {categories.map((c) => (
                            <button key={c.id} className="btn btn-sm" onClick={() => extractToBankSoal(kuisEkstrak, c.id)}>
                              {c.nama}
                            </button>
                          ))}
                          <button className="btn btn-sm btn-danger" onClick={() => setExtractFor(null)}>Batal</button>
                        </span>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {dokumenBankRows().length === 0 && (
              <tr><td colSpan={4} className="muted">Tidak ada dokumen yang cocok. Buat dokumen bank baru, atau simpan dokumen dari halaman kelas.</td></tr>
            )}
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
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
          <input
            className="input"
            style={{ maxWidth: 320 }}
            placeholder="🔍 Cari teks pertanyaan..."
            value={cariSoal}
            onChange={(e) => setCariSoal(e.target.value)}
          />
          <select className="select" style={{ maxWidth: 240 }} value={filterKatSoal} onChange={(e) => setFilterKatSoal(e.target.value)}>
            <option value="">Semua kategori</option>
            <option value="tanpa">— tanpa kategori —</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.nama}</option>
            ))}
          </select>
          {(cariSoal || filterKatSoal) && (
            <span className="muted" style={{ alignSelf: "center" }}>
              Menampilkan {questionsTampil.length} dari {questions.length} soal
            </span>
          )}
        </div>
        {questionsTampil.map((q) => (
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
        {questions.length > 0 && questionsTampil.length === 0 && (
          <p className="muted">Tidak ada soal yang cocok dengan filter.</p>
        )}

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
            {m.grup_dokumen ? (
              <button className="btn btn-sm" onClick={() => copyBankDocument(m.grup_dokumen!)}>📥 Salin Dokumen Utuh</button>
            ) : (
              <button className="btn btn-sm" onClick={() => copyMaterial(m.id)}>📥 Salin</button>
            )}
          </div>
        ))}
        {exploreQuizzes.map((q) => (
          <div key={`q-${q.id}`} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
            <span>🧪 {q.judul} <span className="muted">({q.jumlah_soal} soal) — oleh {q.pemilik.nama_lengkap ?? q.pemilik.username}</span></span>
            {q.grup_dokumen ? (
              <button className="btn btn-sm" onClick={() => copyBankDocument(q.grup_dokumen!)}>📥 Salin Dokumen Utuh</button>
            ) : (
              <button className="btn btn-sm" onClick={() => copyQuiz(q.id)}>📥 Salin</button>
            )}
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
