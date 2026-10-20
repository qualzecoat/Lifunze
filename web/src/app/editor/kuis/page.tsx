"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface TcmlError {
  line: number;
  message: string;
}
interface ParsedOption {
  label: string;
  teks: string;
  is_correct: boolean;
}
interface ParsedQuestion {
  pertanyaan: string;
  bobot: number;
  options: ParsedOption[];
  jawaban_referensi: string | null;
}

const CONTOH_PG = `[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]Ibu kota Indonesia adalah...[/QUESTION]
[OPTIONS]
A. Bandung
B. Jakarta
C. Surabaya
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 1]
[/QUIZ]`;

const CONTOH_ESAI = `[QUIZ]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Jelaskan proses fotosintesis.[/QUESTION]
[ANSWER]Jawaban referensi untuk pedoman penilaian guru.[/ANSWER]
[WEIGHT]2[/WEIGHT]
[/QUESTION 1]
[/QUIZ]`;

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function EditorKuisInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const meetingParam = sp.get("meeting");
  const quizParam = sp.get("quiz");
  const kelasParam = sp.get("kelas");

  const [user, setUser] = useState<User | null>(null);
  const [judul, setJudul] = useState("");
  const [tipe, setTipe] = useState<"pilihan_ganda" | "teks">("pilihan_ganda");
  const [teks, setTeks] = useState("");
  const [subjectId, setSubjectId] = useState<string | null>(kelasParam);
  const [durasi, setDurasi] = useState("");
  const [dibuka, setDibuka] = useState("");
  const [ditutup, setDitutup] = useState("");
  const [acakSoal, setAcakSoal] = useState(false);
  const [acakOpsi, setAcakOpsi] = useState(false);
  const [tampilkanKunci, setTampilkanKunci] = useState(true);
  const [preview, setPreview] = useState<ParsedQuestion[]>([]);
  const [errors, setErrors] = useState<TcmlError[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [saving, setSaving] = useState(false);

  async function runPreview(value: string, t: string) {
    if (!value.trim()) {
      setPreview([]);
      setErrors([]);
      return;
    }
    try {
      const res = await apiFetch<{ success: boolean; content: { questions: ParsedQuestion[] } | null; errors: TcmlError[] }>(
        "/api/v1/parse/quiz",
        { method: "POST", body: { teks: value, tipe: t } },
      );
      if (res.success && res.content) {
        setPreview(res.content.questions);
        setErrors([]);
      } else {
        setPreview([]);
        setErrors(res.errors ?? []);
      }
    } catch { /* abaikan */ }
  }

  useEffect(() => {
    getMe().then(async (u) => {
      if (!u) return router.push("/login");
      if (u.role === "siswa") return router.push("/dashboard");
      setUser(u);
      if (quizParam) {
        try {
          const q = await apiFetch<{
            judul: string; tipe: "pilihan_ganda" | "teks"; teks_mentah: string;
            durasi_menit: number | null; dibuka_pada: string | null; ditutup_pada: string | null;
            acak_soal: boolean; acak_opsi: boolean; tampilkan_kunci: boolean; meeting_id: number;
          }>(`/api/v1/quizzes/${quizParam}`);
          setJudul(q.judul);
          setTipe(q.tipe);
          setTeks(q.teks_mentah);
          setDurasi(q.durasi_menit ? String(q.durasi_menit) : "");
          setDibuka(toLocalInput(q.dibuka_pada));
          setDitutup(toLocalInput(q.ditutup_pada));
          setAcakSoal(q.acak_soal);
          setAcakOpsi(q.acak_opsi);
          setTampilkanKunci(q.tampilkan_kunci);
          runPreview(q.teks_mentah, q.tipe);
          // subject id untuk tombol kembali: ambil dari meeting lewat detail kelas tidak langsung tersedia; pakai kelasParam bila ada
        } catch (err) {
          setError(err instanceof Error ? err.message : "Gagal memuat kuis.");
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, quizParam]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  function settingsBody() {
    return {
      durasi_menit: durasi ? Number(durasi) : null,
      dibuka_pada: dibuka ? new Date(dibuka).toISOString() : null,
      ditutup_pada: ditutup ? new Date(ditutup).toISOString() : null,
      acak_soal: acakSoal,
      acak_opsi: acakOpsi,
      tampilkan_kunci: tampilkanKunci,
    };
  }

  async function onSave() {
    setError("");
    setOk("");
    setSaving(true);
    try {
      if (quizParam) {
        await apiFetch(`/api/v1/quizzes/${quizParam}`, {
          method: "PATCH",
          body: { judul, teks_mentah: teks, ...settingsBody() },
        });
        router.push(`/kuis/${quizParam}`);
      } else if (meetingParam) {
        const q = await apiFetch<{ id: number }>(`/api/v1/meetings/${meetingParam}/quizzes`, {
          method: "POST",
          body: { judul, tipe, teks_mentah: teks, ...settingsBody() },
        });
        router.push(`/kuis/${q.id}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Gagal menyimpan kuis.";
      setError(msg);
      try {
        const parsed = JSON.parse(msg);
        if (parsed?.errors) setErrors(parsed.errors);
      } catch { /* abaikan */ }
    } finally {
      setSaving(false);
    }
  }

  async function saveToBank() {
    if (!quizParam) return;
    try {
      await apiFetch(`/api/v1/quizzes/${quizParam}/save-to-bank`, { method: "POST", body: {} });
      setOk("Kuis tersimpan ke Bank.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan ke bank.");
    }
  }

  return (
    <main className="page" style={{ maxWidth: 1200 }}>
      <AppHeader user={user} />
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: "1.4rem" }}>🧪 {quizParam ? "Edit Kuis" : "Buat Kuis"}</h1>
        {subjectId && <Link href={`/kelas/${subjectId}`}>← Kembali ke Kelas</Link>}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
        <div>
          <label className="label">Judul kuis</label>
          <input className="input" value={judul} onChange={(e) => setJudul(e.target.value)} />
        </div>
        <div>
          <label className="label">Tipe</label>
          <select
            className="select"
            value={tipe}
            disabled={!!quizParam}
            onChange={(e) => {
              const t = e.target.value as "pilihan_ganda" | "teks";
              setTipe(t);
              runPreview(teks, t);
            }}
          >
            <option value="pilihan_ganda">Pilihan Ganda</option>
            <option value="teks">Esai / Teks</option>
          </select>
        </div>
        <div>
          <label className="label">Durasi (menit, kosongkan = tanpa batas)</label>
          <input className="input" type="number" min={1} value={durasi} onChange={(e) => setDurasi(e.target.value)} />
        </div>
        <div>
          <label className="label">Dibuka pada</label>
          <input className="input" type="datetime-local" value={dibuka} onChange={(e) => setDibuka(e.target.value)} />
        </div>
        <div>
          <label className="label">Ditutup pada</label>
          <input className="input" type="datetime-local" value={ditutup} onChange={(e) => setDitutup(e.target.value)} />
        </div>
      </div>
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginTop: 10 }}>
        <label><input type="checkbox" checked={acakSoal} onChange={(e) => setAcakSoal(e.target.checked)} /> Acak urutan soal</label>
        <label><input type="checkbox" checked={acakOpsi} onChange={(e) => setAcakOpsi(e.target.checked)} /> Acak urutan opsi</label>
        <label><input type="checkbox" checked={tampilkanKunci} onChange={(e) => setTampilkanKunci(e.target.checked)} /> Tampilkan kunci ke siswa setelah submit</label>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 16, marginTop: 8 }}>
        <div>
          <label className="label">Teks TCML kuis</label>
          <textarea
            className="textarea"
            value={teks}
            onChange={(e) => {
              setTeks(e.target.value);
              runPreview(e.target.value, tipe);
            }}
            rows={22}
            spellCheck={false}
            style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" }}
            placeholder={tipe === "pilihan_ganda" ? CONTOH_PG : CONTOH_ESAI}
          />
          <p className="muted">
            Ekstensi v2: <code>[WEIGHT]2[/WEIGHT]</code> untuk bobot soal, <code>[ANSWER]B, C[/ANSWER]</code> untuk multi-jawaban-benar (siswa harus memilih himpunan yang persis sama).
          </p>
          {errors.length > 0 && (
            <div className="alert alert-error">
              <strong>{errors.length} error TCML:</strong>
              <ul style={{ marginLeft: 18 }}>
                {errors.map((e, i) => (
                  <li key={i}>Baris {e.line}: {e.message}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div>
          <label className="label">Pratinjau soal ({preview.length})</label>
          {preview.map((q, i) => (
            <div className="card" key={i} style={{ marginBottom: 10 }}>
              <p><strong>{i + 1}. {q.pertanyaan}</strong> <span className="badge">bobot {q.bobot}</span></p>
              {q.options.map((o) => (
                <p key={o.label} style={{ color: o.is_correct ? "var(--ok)" : undefined }}>
                  {o.is_correct ? "✅" : "▫️"} {o.label}. {o.teks}
                </p>
              ))}
              {q.jawaban_referensi && <p className="muted">Referensi: {q.jawaban_referensi}</p>}
            </div>
          ))}
          {preview.length === 0 && (
            <div className="card"><p className="muted">Pratinjau soal muncul di sini setelah TCML valid.</p></div>
          )}
        </div>
      </div>

      <div className="row-actions" style={{ marginTop: 16 }}>
        <button className="btn btn-primary" onClick={onSave} disabled={saving || !judul.trim() || !teks.trim()}>
          {saving ? "Menyimpan..." : "💾 Simpan Kuis"}
        </button>
        {quizParam && <button className="btn" onClick={saveToBank}>📚 Simpan ke Bank</button>}
      </div>
      <p className="muted" style={{ marginTop: 8 }}>
        Catatan: soal kuis tidak bisa diubah setelah ada siswa yang mengerjakan (pengaturan waktu & judul masih bisa).
      </p>
    </main>
  );
}

export default function EditorKuisPage() {
  return (
    <Suspense fallback={<main className="page"><p className="muted">Memuat editor...</p></main>}>
      <EditorKuisInner />
    </Suspense>
  );
}
