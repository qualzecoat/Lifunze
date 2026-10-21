"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import QuizItemsPreview, { type ItemPratinjau } from "@/components/QuizItemsPreview";
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

/** Satu kartu soal pada mode Formulir (U1 audit UX).
 * Bila `konten` terisi, kartu ini adalah BLOK PENGANTAR (prolog/hint/
 * catatan di dalam kuis) — bukan soal dan tidak dinilai. */
interface CardSoal {
  pertanyaan: string;
  opsi: string[];
  kunci: number[]; // indeks opsi yang benar (boleh >1 = multi-benar)
  bobot: string;
  referensi: string;
  konten?: { tipe: "paragraf" | "note" | "hint" | "example" | "warning"; teks: string };
}

function kartuKonten(): CardSoal {
  return { pertanyaan: "", opsi: [], kunci: [], bobot: "1", referensi: "", konten: { tipe: "paragraf", teks: "" } };
}

const HURUF = ["A", "B", "C", "D", "E"];

function kartuKosong(): CardSoal {
  return { pertanyaan: "", opsi: ["", "", "", ""], kunci: [0], bobot: "1", referensi: "" };
}

function kartuKeTeks(cards: CardSoal[], tipe: "pilihan_ganda" | "teks"): string {
  const lines: string[] = ["[QUIZ]", `[TYPE]${tipe === "pilihan_ganda" ? "pilihan_ganda" : "essay"}[/TYPE]`];
  let nomor = 0;
  cards.forEach((c) => {
    if (c.konten) {
      const isi = c.konten.teks.trim();
      if (!isi) return;
      if (c.konten.tipe === "paragraf") lines.push(isi);
      else {
        const tag = { note: "NOTE", hint: "HINT", example: "EXAMPLE", warning: "WARNING" }[c.konten.tipe];
        lines.push(`[${tag}]${isi}[/${tag}]`);
      }
      return;
    }
    nomor++;
    lines.push(`[QUESTION ${nomor}]`);
    lines.push(`[QUESTION]${c.pertanyaan.trim()}[/QUESTION]`);
    if (tipe === "pilihan_ganda") {
      lines.push("[OPTIONS]");
      c.opsi.forEach((o, j) => lines.push(`${HURUF[j]}. ${o.trim()}`));
      lines.push("[/OPTIONS]");
      if (c.bobot && c.bobot !== "1") lines.push(`[WEIGHT]${c.bobot}[/WEIGHT]`);
      const kunci = [...c.kunci].sort((a, b) => a - b).map((k) => HURUF[k]).join(", ");
      lines.push(`[ANSWER]${kunci}[/ANSWER]`);
    } else {
      if (c.referensi.trim()) lines.push(`[ANSWER]${c.referensi.trim()}[/ANSWER]`);
      if (c.bobot && c.bobot !== "1") lines.push(`[WEIGHT]${c.bobot}[/WEIGHT]`);
    }
    lines.push(`[/QUESTION ${nomor}]`);
  });
  lines.push("[/QUIZ]");
  return lines.join("\n");
}

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
  const [mode, setMode] = useState<"form" | "tcml">("form");
  const [cards, setCards] = useState<CardSoal[]>([kartuKosong()]);
  const [subjectId] = useState<string | null>(kelasParam);
  const [durasi, setDurasi] = useState("");
  const [dibuka, setDibuka] = useState("");
  const [ditutup, setDitutup] = useState("");
  const [acakSoal, setAcakSoal] = useState(false);
  const [acakOpsi, setAcakOpsi] = useState(false);
  const [tampilkanKunci, setTampilkanKunci] = useState(true);
  const [preview, setPreview] = useState<ParsedQuestion[]>([]);
  const [previewItems, setPreviewItems] = useState<ItemPratinjau[]>([]);
  const [errors, setErrors] = useState<TcmlError[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [saving, setSaving] = useState(false);

  async function parseTeks(value: string, t: string) {
    const res = await apiFetch<{ success: boolean; content: { questions: ParsedQuestion[]; items?: { jenis: string; tipe?: string; teks?: string }[] } | null; errors: TcmlError[] }>(
      "/api/v1/parse/quiz",
      { method: "POST", body: { teks: value, tipe: t } },
    );
    return res;
  }

  async function runPreview(value: string, t: string) {
    if (!value.trim()) {
      setPreview([]);
      setPreviewItems([]);
      setErrors([]);
      return;
    }
    try {
      const res = await parseTeks(value, t);
      if (res.success && res.content) {
        setPreview(res.content.questions);
        // Audit #21: pratinjau menggambar urutan dokumen (blok konten
        // terseling soal), bukan daftar soal saja.
        const mentah = (res.content.items ?? []) as unknown as ItemPratinjau[];
        setPreviewItems(
          mentah.length > 0
            ? mentah
            : res.content.questions.map((soal) => ({ jenis: "soal" as const, soal })),
        );
        setErrors([]);
      } else {
        setPreview([]);
        setPreviewItems([]);
        setErrors(res.errors ?? []);
      }
    } catch { /* abaikan */ }
  }

  /** Sinkronkan kartu -> teks TCML + pratinjau. */
  function sinkronDariKartu(next: CardSoal[], t: "pilihan_ganda" | "teks" = tipe) {
    setCards(next);
    const built = kartuKeTeks(next, t);
    setTeks(built);
    runPreview(built, t);
  }

  /** Urai teks TCML menjadi kartu (untuk beralih ke mode Formulir / memuat kuis). */
  async function uraiKeKartu(value: string, t: "pilihan_ganda" | "teks"): Promise<boolean> {
    if (!value.trim()) {
      setCards([kartuKosong()]);
      return true;
    }
    try {
      const res = await parseTeks(value, t);
      if (res.success && res.content) {
        const soalKeKartu = (q: ParsedQuestion): CardSoal => ({
          pertanyaan: q.pertanyaan,
          opsi: q.options.length ? q.options.map((o) => o.teks) : ["", "", "", ""],
          kunci: q.options.map((o, idx) => (o.is_correct ? idx : -1)).filter((x) => x >= 0),
          bobot: String(q.bobot ?? 1),
          referensi: q.jawaban_referensi ?? "",
        });
        const mapped: CardSoal[] = [];
        if (res.content.items?.length) {
          let qi = 0;
          for (const it of res.content.items) {
            if (it.jenis === "konten") {
              const tp = (["paragraf", "note", "hint", "example", "warning"].includes(it.tipe ?? "") ? it.tipe : "paragraf") as NonNullable<CardSoal["konten"]>["tipe"];
              mapped.push({ ...kartuKonten(), konten: { tipe: tp, teks: it.teks ?? "" } });
            } else {
              const q = res.content.questions[qi++];
              if (q) mapped.push(soalKeKartu(q));
            }
          }
        } else {
          mapped.push(...res.content.questions.map(soalKeKartu));
        }
        setCards(mapped.length ? mapped : [kartuKosong()]);
        setErrors([]);
        return true;
      }
      setErrors(res.errors ?? []);
      return false;
    } catch {
      return false;
    }
  }

  async function gantiMode(m: "form" | "tcml") {
    if (m === mode) return;
    if (m === "form") {
      const berhasil = await uraiKeKartu(teks, tipe);
      if (!berhasil) {
        setError("Teks TCML belum valid — perbaiki dulu di Mode TCML agar bisa diurai menjadi formulir.");
        return;
      }
      setError("");
    }
    setMode(m);
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
          // Muat sebagai formulir bila teksnya bisa diurai (umumnya selalu bisa).
          const okParse = await uraiKeKartu(q.teks_mentah, q.tipe);
          if (!okParse) setMode("tcml");
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

  function updateCard(i: number, patch: Partial<CardSoal>) {
    const next = cards.map((c, idx) => (idx === i ? { ...c, ...patch } : c));
    sinkronDariKartu(next);
  }

  function pakaiContohPG() {
    if (cards.some((c) => c.pertanyaan.trim()) && !window.confirm("Ganti isi formulir dengan contoh soal PG?")) return;
    setTipe("pilihan_ganda");
    sinkronDariKartu(
      [
        { pertanyaan: "Ibu kota Indonesia adalah...", opsi: ["Bandung", "Jakarta", "Surabaya", "Medan"], kunci: [1], bobot: "1", referensi: "" },
        { pertanyaan: "Pilih bilangan prima berikut ini (boleh lebih dari satu).", opsi: ["2", "4", "5", "9"], kunci: [0, 2], bobot: "2", referensi: "" },
      ],
      "pilihan_ganda",
    );
  }

  function pakaiContohEsai() {
    if (cards.some((c) => c.pertanyaan.trim()) && !window.confirm("Ganti isi formulir dengan contoh soal esai?")) return;
    setTipe("teks");
    sinkronDariKartu(
      [{ pertanyaan: "Jelaskan proses fotosintesis dengan bahasamu sendiri.", opsi: [], kunci: [], bobot: "1", referensi: "Jawaban referensi untuk pedoman penilaian guru." }],
      "teks",
    );
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

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 12 }}>
        <div>
          <label className="label">Judul kuis</label>
          <input className="input" value={judul} onChange={(e) => setJudul(e.target.value)} placeholder="cth: Latihan Bab 2" />
        </div>
        <div>
          <label className="label">Jenis soal</label>
          <select
            className="select"
            value={tipe}
            disabled={!!quizParam}
            onChange={(e) => {
              const t = e.target.value as "pilihan_ganda" | "teks";
              setTipe(t);
              if (mode === "form") sinkronDariKartu(cards, t);
              else runPreview(teks, t);
            }}
          >
            <option value="pilihan_ganda">Pilihan Ganda</option>
            <option value="teks">Esai / Teks</option>
          </select>
        </div>
        <div>
          <label className="label">Cara mengisi soal</label>
          <div style={{ display: "flex", gap: 6 }}>
            <button className={`btn btn-sm ${mode === "form" ? "btn-primary" : ""}`} onClick={() => gantiMode("form")}>📝 Formulir</button>
            <button className={`btn btn-sm ${mode === "tcml" ? "btn-primary" : ""}`} onClick={() => gantiMode("tcml")}>⌨️ Mode TCML (ahli)</button>
          </div>
          <p className="muted" style={{ marginTop: 6 }}>
            {mode === "form" ? "Isi kartu soal — format tersusun otomatis." : "Tulis format TCML langsung; beralih ke Formulir akan menguraikannya."}
          </p>
        </div>
      </div>

      <p style={{ marginTop: 10 }}>
        <span className="muted">Mulai cepat: </span>
        <button className="btn btn-sm" onClick={pakaiContohPG}>🧪 Contoh PG</button>{" "}
        <button className="btn btn-sm" onClick={pakaiContohEsai}>✍️ Contoh Esai</button>
      </p>

      <details style={{ border: "1px dashed var(--border)", borderRadius: 10, padding: "10px 12px", marginTop: 12 }}>
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>⚙️ Pengaturan lanjutan (opsional)</summary>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12, marginTop: 10 }}>
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
          <label><input type="checkbox" checked={tampilkanKunci} onChange={(e) => setTampilkanKunci(e.target.checked)} /> Tampilkan kunci ke siswa setelah selesai</label>
        </div>
      </details>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 16, marginTop: 14 }}>
        <div>
          {mode === "form" ? (
            <>
              {cards.map((c, i) => (
                <div className="card" key={i} style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong>{c.konten ? "📖 Blok Pengantar" : `Soal ${cards.slice(0, i + 1).filter((x) => !x.konten).length}`}</strong>
                    <span>
                      {!c.konten && <span className="muted">Bobot </span>}
                      {!c.konten && (
                        <input
                          type="number" min={0.5} step={0.5} value={c.bobot} style={{ width: 62 }}
                          className="input"
                          onChange={(e) => updateCard(i, { bobot: e.target.value })}
                        />
                      )}{" "}
                      <button className="btn btn-sm btn-danger" onClick={() => sinkronDariKartu(cards.filter((_, idx) => idx !== i))}>Hapus</button>
                    </span>
                  </div>
                  {c.konten ? (
                    <>
                      <p className="muted" style={{ marginTop: 6 }}>
                        Teks ini tampil di kuis sebagai pengantar/selingan — bukan soal, tidak dinilai. Cocok untuk prolog cerita, bacaan, atau petunjuk di tengah kuis.
                      </p>
                      <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                        <select
                          className="input"
                          style={{ maxWidth: 220 }}
                          value={c.konten.tipe}
                          onChange={(e) => updateCard(i, { konten: { ...c.konten!, tipe: e.target.value as NonNullable<CardSoal["konten"]>["tipe"] } })}
                        >
                          <option value="paragraf">📄 Paragraf biasa</option>
                          <option value="note">📝 Catatan</option>
                          <option value="hint">💡 Petunjuk (hint)</option>
                          <option value="example">📘 Contoh</option>
                          <option value="warning">⚠️ Peringatan</option>
                        </select>
                      </div>
                      <textarea
                        className="textarea" rows={3} style={{ marginTop: 8 }}
                        placeholder="Tulis teks pengantarnya di sini..."
                        value={c.konten.teks}
                        onChange={(e) => updateCard(i, { konten: { ...c.konten!, teks: e.target.value } })}
                      />
                    </>
                  ) : (
                  <textarea
                    className="textarea" rows={2} style={{ marginTop: 8 }}
                    placeholder="Tulis pertanyaan di sini..."
                    value={c.pertanyaan}
                    onChange={(e) => updateCard(i, { pertanyaan: e.target.value })}
                  />
                  )}
                  {!c.konten && (tipe === "pilihan_ganda" ? (
                    <>
                      {c.opsi.map((o, j) => (
                        <div key={j} style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 7 }}>
                          <input
                            type="checkbox"
                            title="Tandai sebagai jawaban benar (boleh lebih dari satu)"
                            checked={c.kunci.includes(j)}
                            onChange={(e) =>
                              updateCard(i, { kunci: e.target.checked ? [...c.kunci, j] : c.kunci.filter((k) => k !== j) })
                            }
                          />
                          <b>{HURUF[j]}.</b>
                          <input
                            className="input" style={{ flex: 1 }} placeholder={`Opsi ${HURUF[j]}`}
                            value={o}
                            onChange={(e) => {
                              const opsi = [...c.opsi];
                              opsi[j] = e.target.value;
                              updateCard(i, { opsi });
                            }}
                          />
                          {c.kunci.includes(j) && <span className="badge">kunci</span>}
                          {c.opsi.length > 2 && (
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={() => {
                                const opsi = c.opsi.filter((_, idx) => idx !== j);
                                const kunci = c.kunci.filter((k) => k !== j).map((k) => (k > j ? k - 1 : k));
                                updateCard(i, { opsi, kunci });
                              }}
                            >✕</button>
                          )}
                        </div>
                      ))}
                      <p className="muted" style={{ marginTop: 6 }}>Centang kotak di kiri opsi untuk menandai jawaban benar — boleh lebih dari satu (siswa harus memilih persis himpunan itu).</p>
                      {c.opsi.length < 5 && (
                        <button
                          className="btn btn-sm"
                          onClick={() => updateCard(i, { opsi: [...c.opsi, ""] })}
                        >＋ Tambah Opsi</button>
                      )}
                    </>
                  ) : (
                    <>
                      <label className="label">Jawaban referensi (pedoman penilaian guru, tidak dilihat siswa)</label>
                      <textarea
                        className="textarea" rows={2}
                        value={c.referensi}
                        onChange={(e) => updateCard(i, { referensi: e.target.value })}
                      />
                    </>
                  ))}
                </div>
              ))}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn" style={{ flex: 1, padding: 11 }} onClick={() => sinkronDariKartu([...cards, kartuKosong()])}>
                  ＋ Tambah Soal
                </button>
                <button className="btn" style={{ flex: 1, padding: 11 }} onClick={() => sinkronDariKartu([...cards, kartuKonten()])}>
                  📖 ＋ Blok Pengantar
                </button>
              </div>
              <p className="muted" style={{ marginTop: 8 }}>
                📖 <strong>Blok Pengantar</strong> = teks di dalam kuis (prolog, bacaan, hint) — tampil mengikuti urutan kartu, bukan soal dan tidak dinilai. Soal latihan di tengah <em>materi</em> memakai blok 🧠 Cek Pemahaman di editor materi.
              </p>
            </>
          ) : (
            <>
              <label className="label">Teks TCML kuis</label>
              <textarea
                className="textarea"
                value={teks}
                onChange={(e) => {
                  setTeks(e.target.value);
                  runPreview(e.target.value, tipe);
                }}
                rows={24}
                spellCheck={false}
                style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" }}
              />
              <p className="muted">
                Ekstensi v2: <code>[WEIGHT]2[/WEIGHT]</code> untuk bobot soal, <code>[ANSWER]B, C[/ANSWER]</code> untuk multi-jawaban-benar.
              </p>
            </>
          )}
          {errors.length > 0 && (
            <div className="alert alert-error" style={{ marginTop: 10 }}>
              <strong>{errors.length} masalah pada format kuis:</strong>
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
            <label className="label">Pratinjau soal ({preview.length})</label>
            <button type="button" className="btn btn-sm" onClick={() => runPreview(teks, tipe)}>
              🔄 Refresh Pratinjau
            </button>
          </div>
          {preview.length > 0 ? (
            <QuizItemsPreview items={previewItems} />
          ) : (
            <div className="card"><p className="muted">Pratinjau soal muncul di sini setelah format valid.</p></div>
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
