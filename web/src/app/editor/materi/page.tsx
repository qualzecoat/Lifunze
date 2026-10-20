"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface TcmlError {
  line: number;
  message: string;
}
interface Category {
  id: number;
  nama: string;
}

const CONTOH = `[MATERIAL]
[TITLE]Judul Materi[/TITLE]
[PARAGRAPH]
Tulis isi materi di sini.
[/PARAGRAPH]
[NOTE]Catatan penting untuk siswa.[/NOTE]
[/MATERIAL]`;

const TEMPLATES: { nama: string; judul: string; teks: string }[] = [
  {
    nama: "📖 Materi Biasa",
    judul: "Materi Baru",
    teks: CONTOH,
  },
  {
    nama: "🎯 Latihan",
    judul: "Latihan",
    teks: `[EXERCISE]
[TITLE]Latihan[/TITLE]
[TASKS]
[TASK]Tugas pertama yang harus dikerjakan siswa.[/TASK]
[TASK]Tugas kedua.[/TASK]
[/TASKS]
[HINT]Petunjuk untuk membantu siswa.[/HINT]
[/EXERCISE]`,
  },
  {
    nama: "🐱 Proyek Scratch",
    judul: "Proyek Scratch",
    teks: `[PROJECT]
[TITLE]Proyek Scratch[/TITLE]
[DESCRIPTION]Buat proyek Scratch sesuai tema pertemuan ini. Kumpulkan file .sb3 lewat panel pengumpulan di halaman materi.[/DESCRIPTION]
[REQUIREMENTS]
[REQUIREMENT]Minimal 2 sprite[/REQUIREMENT]
[REQUIREMENT]Memakai blok perulangan[/REQUIREMENT]
[/REQUIREMENTS]
[OUTPUT]File proyek Scratch (.sb3).[/OUTPUT]
[RUBRIC]
[CRITERIA]Kreativitas — 50 poin[/CRITERIA]
[CRITERIA]Kesesuaian tema — 50 poin[/CRITERIA]
[/RUBRIC]
[/PROJECT]`,
  },
  {
    nama: "🧩 Materi Scratch",
    judul: "Materi Scratch",
    teks: `[MATERIAL]
[TITLE]Belajar Scratch[/TITLE]
Coba proyek contoh berikut — tekan bendera hijau untuk menjalankannya.
[SCRATCH]104[/SCRATCH]
[SPRITE]
Kucing
Sprite utama pada proyek contoh.
[/SPRITE]
[BLOCKS]
when green flag clicked
move (10) steps
[/BLOCKS]
[NOTE]Ganti angka pada blok move untuk mengubah jarak langkah.[/NOTE]
[/MATERIAL]`,
  },
];

function EditorInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const meetingParam = sp.get("meeting");
  const materialParam = sp.get("material");
  const bankParam = sp.get("bank");
  const kelasParam = sp.get("kelas");
  const mode = bankParam || sp.get("mode") === "bank" ? "bank" : "material";

  const [user, setUser] = useState<User | null>(null);
  const [judul, setJudul] = useState("");
  const [teks, setTeks] = useState(mode === "bank" && !bankParam ? CONTOH : "");
  const [subjectId, setSubjectId] = useState<string | null>(kelasParam);
  const [previewHtml, setPreviewHtml] = useState("");
  const [errors, setErrors] = useState<TcmlError[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [kategoriId, setKategoriId] = useState<string>("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runPreview = useCallback(async (value: string) => {
    if (!value.trim()) {
      setPreviewHtml("");
      setErrors([]);
      return;
    }
    try {
      const res = await apiFetch<{ success: boolean; content: string | null; errors: TcmlError[] }>(
        "/api/v1/parse/content",
        { method: "POST", body: { teks: value, jenis: "material" } },
      );
      if (res.success) {
        setPreviewHtml(res.content ?? "");
        setErrors([]);
      } else {
        setPreviewHtml("");
        setErrors(res.errors ?? []);
      }
    } catch {
      /* pratinjau gagal diam-diam; simpan tetap divalidasi server */
    }
  }, []);

  useEffect(() => {
    getMe().then(async (u) => {
      if (!u) {
        router.push("/login");
        return;
      }
      if (u.role === "siswa") {
        router.push("/dashboard");
        return;
      }
      setUser(u);
      try {
        setCategories(await apiFetch<Category[]>("/api/v1/bank/categories"));
      } catch { /* abaikan */ }
      try {
        if (materialParam) {
          const m = await apiFetch<{ judul: string; teks_mentah: string; subject_id: number | null }>(
            `/api/v1/materials/${materialParam}`,
          );
          setJudul(m.judul);
          setTeks(m.teks_mentah);
          if (m.subject_id) setSubjectId(String(m.subject_id));
          runPreview(m.teks_mentah);
        } else if (bankParam) {
          const s = await apiFetch<{ judul: string; teks_mentah: string; kategori_id: number | null }>(
            `/api/v1/bank/materials/${bankParam}`,
          );
          setJudul(s.judul);
          setTeks(s.teks_mentah);
          setKategoriId(s.kategori_id ? String(s.kategori_id) : "");
          runPreview(s.teks_mentah);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat konten.");
      }
    });
  }, [router, materialParam, bankParam, runPreview]);

  function onTeksChange(v: string) {
    setTeks(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runPreview(v), 600);
  }

  async function onSave() {
    setError("");
    setOk("");
    setSaving(true);
    try {
      if (mode === "bank") {
        const body = { judul, teks_mentah: teks, kategori_id: kategoriId ? Number(kategoriId) : null };
        if (bankParam) {
          await apiFetch(`/api/v1/bank/materials/${bankParam}`, { method: "PATCH", body });
          setOk("Materi bank diperbarui.");
        } else {
          await apiFetch("/api/v1/bank/materials", { method: "POST", body });
          setOk("Tersimpan ke bank.");
          setTimeout(() => router.push("/bank"), 700);
        }
      } else if (materialParam) {
        const m = await apiFetch<{ id: number }>(`/api/v1/materials/${materialParam}`, {
          method: "PATCH",
          body: { judul, teks_mentah: teks },
        });
        router.push(`/materi/${m.id}`);
      } else if (meetingParam) {
        const m = await apiFetch<{ id: number }>(`/api/v1/meetings/${meetingParam}/materials`, {
          method: "POST",
          body: { judul, teks_mentah: teks },
        });
        router.push(`/materi/${m.id}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Gagal menyimpan.";
      setError(msg);
      try {
        const parsed = JSON.parse(msg);
        if (parsed?.errors) setErrors(parsed.errors);
      } catch { /* bukan JSON */ }
    } finally {
      setSaving(false);
    }
  }

  async function saveToBank() {
    setError("");
    setOk("");
    try {
      if (materialParam) {
        // Materi yang sudah ada: endpoint berpenanda asal — sekali tersimpan
        // tidak bisa disimpan lagi walau diedit (keputusan Qualze).
        await apiFetch(`/api/v1/materials/${materialParam}/save-to-bank`, { method: "POST" });
      } else {
        await apiFetch("/api/v1/bank/materials", {
          method: "POST",
          body: { judul, teks_mentah: teks, kategori_id: null },
        });
      }
      setOk("Salinan tersimpan ke Bank Materi.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan ke bank.");
    }
  }

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  return (
    <main className="page" style={{ maxWidth: 1200 }}>
      <AppHeader user={user} />
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: "1.4rem" }}>
          {mode === "bank" ? "📚 Editor Materi Bank" : "✏️ Editor Materi TCML"}
        </h1>
        {subjectId && <Link href={`/kelas/${subjectId}`}>← Kembali ke Kelas</Link>}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <label className="label">Judul materi</label>
      <input className="input" value={judul} onChange={(e) => setJudul(e.target.value)} placeholder="mis. Pecahan Dasar" />

      <p style={{ marginTop: 10 }}>
        <span className="muted">Mulai dari template: </span>
        {TEMPLATES.map((t) => (
          <button
            key={t.nama}
            className="btn btn-sm"
            style={{ marginRight: 6, marginBottom: 6 }}
            onClick={() => {
              if (teks.trim() && teks !== CONTOH && !window.confirm(`Ganti isi editor dengan template "${t.nama}"?`)) return;
              if (!judul.trim()) setJudul(t.judul);
              onTeksChange(t.teks);
            }}
          >
            {t.nama}
          </button>
        ))}
      </p>

      {mode === "bank" && (
        <>
          <label className="label">Kategori bank</label>
          <select className="select" value={kategoriId} onChange={(e) => setKategoriId(e.target.value)}>
            <option value="">(tanpa kategori)</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.nama}</option>
            ))}
          </select>
        </>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 16, marginTop: 14 }}>
        <div>
          <label className="label" style={{ marginTop: 0 }}>Teks TCML</label>
          <textarea
            className="textarea"
            value={teks}
            onChange={(e) => onTeksChange(e.target.value)}
            rows={22}
            spellCheck={false}
            style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" }}
            placeholder={CONTOH}
          />
          {errors.length > 0 && (
            <div className="alert alert-error">
              <strong>{errors.length} masalah pada format materi:</strong>
              <ul style={{ marginLeft: 18 }}>
                {errors.map((e, i) => (
                  <li key={i}>Baris {e.line}: {e.message}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <label className="label" style={{ marginTop: 0 }}>Pratinjau</label>
            <button type="button" className="btn btn-sm" onClick={() => runPreview(teks)}>
              🔄 Refresh Pratinjau
            </button>
          </div>
          {previewHtml ? (
            <article className="card tcml" dangerouslySetInnerHTML={{ __html: previewHtml }} />
          ) : (
            <div className="card"><p className="muted">Pratinjau muncul di sini setelah teks valid.</p></div>
          )}
        </div>
      </div>

      <div className="row-actions" style={{ marginTop: 16 }}>
        <button className="btn btn-primary" onClick={onSave} disabled={saving || !judul.trim() || !teks.trim()}>
          {saving ? "Menyimpan..." : "💾 Simpan Materi"}
        </button>
        {mode === "material" && (
          <button className="btn" onClick={saveToBank} disabled={!judul.trim() || !teks.trim()}>
            📚 Simpan Juga ke Bank
          </button>
        )}
      </div>
      <p className="muted" style={{ marginTop: 10 }}>
        Materi dengan TCML tidak valid tidak bisa disimpan — perbaiki error yang ditampilkan.
      </p>
    </main>
  );
}

export default function EditorMateriPage() {
  return (
    <Suspense fallback={<main className="page"><p className="muted">Memuat editor...</p></main>}>
      <EditorInner />
    </Suspense>
  );
}
