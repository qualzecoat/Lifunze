"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { API_BASE, apiFetch, getMe, type User } from "@/lib/api";

interface QOption {
  id: number;
  teks: string;
  label?: string;
  is_correct?: boolean;
}
interface AttemptQuestion {
  id: number;
  tipe: string;
  pertanyaan: string;
  bobot: number;
  multi: boolean;
  options: QOption[];
  jawaban_option_ids: number[];
  jawaban_teks: string | null;
  poin?: number | null;
  is_correct?: boolean | null;
  kunci_option_ids?: number[];
  jawaban_referensi?: string | null;
}
interface AttemptView {
  attempt: {
    id: number;
    status: string;
    skor: number | null;
    started_at: string | null;
    submitted_at: string | null;
    deadline: string | null;
    siswa_id: number;
  };
  quiz: { id: number; judul: string; tipe: string; tampilkan_kunci: boolean };
  questions: AttemptQuestion[];
  pesan?: string;
}
interface QuizPublic {
  id: number;
  judul: string;
  tipe: string;
  durasi_menit: number | null;
  dibuka_pada: string | null;
  ditutup_pada: string | null;
  jumlah_soal: number;
  total_bobot: number;
  bisa_mulai: boolean;
  alasan: string | null;
  attempt_saya: { id: number; status: string; skor: number | null } | null;
}
interface QuizFull {
  id: number;
  judul: string;
  tipe: string;
  meeting_id: number;
  durasi_menit: number | null;
  questions: {
    id: number;
    pertanyaan: string;
    bobot: number;
    jawaban_referensi: string | null;
    options: { id: number; label: string; teks: string; is_correct: boolean }[];
  }[];
}
interface ResultRow {
  attempt_id: number;
  siswa: { id: number; username: string; nama_lengkap: string | null } | null;
  status: string;
  skor: number | null;
  submitted_at: string | null;
}

type AnyQuiz = QuizPublic & Partial<QuizFull>;

export default function KuisPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [quiz, setQuiz] = useState<AnyQuiz | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getMe().then(async (u) => {
      if (!u) return router.push("/login");
      setUser(u);
      try {
        setQuiz(await apiFetch<AnyQuiz>(`/api/v1/quizzes/${params.id}`));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat kuis.");
      }
    });
  }, [router, params.id]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;
  if (error) return <main className="page"><AppHeader user={user} /><div className="alert alert-error">{error}</div></main>;
  if (!quiz) return <main className="page"><AppHeader user={user} /><p className="muted">Memuat kuis...</p></main>;

  const isManager = (user.role === "admin" || user.role === "guru") && Array.isArray(quiz.questions);
  return (
    <main className="page">
      <AppHeader user={user} />
      {isManager ? (
        <GuruView quiz={quiz as QuizFull} />
      ) : (
        <SiswaView quiz={quiz as QuizPublic} />
      )}
    </main>
  );
}

/* ================================================================ SISWA */
function SiswaView({ quiz }: { quiz: QuizPublic }) {
  const [attempt, setAttempt] = useState<AttemptView | null>(null);
  const [answers, setAnswers] = useState<Record<number, number[] | string>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [nowTick, setNowTick] = useState(Date.now());

  const loadAttempt = useCallback(async (attemptId: number) => {
    const view = await apiFetch<AttemptView>(`/api/v1/attempts/${attemptId}`);
    setAttempt(view);
    const prefill: Record<number, number[] | string> = {};
    for (const q of view.questions) {
      prefill[q.id] = q.tipe === "pilihan_ganda" ? q.jawaban_option_ids : (q.jawaban_teks ?? "");
    }
    setAnswers(prefill);
  }, []);

  useEffect(() => {
    if (quiz.attempt_saya) loadAttempt(quiz.attempt_saya.id).catch(() => {});
  }, [quiz.attempt_saya, loadAttempt]);

  useEffect(() => {
    const t = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const remaining = useMemo(() => {
    if (!attempt?.attempt.deadline || attempt.attempt.status !== "in_progress") return null;
    const ms = new Date(attempt.attempt.deadline).getTime() - nowTick;
    return ms;
  }, [attempt, nowTick]);

  useEffect(() => {
    if (remaining !== null && remaining <= 0 && attempt) {
      loadAttempt(attempt.attempt.id).catch(() => {});
    }
  }, [remaining, attempt, loadAttempt]);

  async function start() {
    setErr("");
    setBusy(true);
    try {
      const view = await apiFetch<AttemptView>(`/api/v1/quizzes/${quiz.id}/attempts`, { method: "POST" });
      setAttempt(view);
      const prefill: Record<number, number[] | string> = {};
      for (const q of view.questions) {
        prefill[q.id] = q.tipe === "pilihan_ganda" ? q.jawaban_option_ids : (q.jawaban_teks ?? "");
      }
      setAnswers(prefill);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal memulai kuis.");
    } finally {
      setBusy(false);
    }
  }

  function buildPayload() {
    if (!attempt) return [];
    return attempt.questions.map((q) =>
      q.tipe === "pilihan_ganda"
        ? { question_id: q.id, option_ids: (answers[q.id] as number[]) ?? [] }
        : { question_id: q.id, jawaban_teks: (answers[q.id] as string) ?? "" },
    );
  }

  async function saveDraft() {
    if (!attempt) return;
    setErr("");
    try {
      const res = await apiFetch<{ pesan: string }>(`/api/v1/attempts/${attempt.attempt.id}/answers`, {
        method: "PUT",
        body: { answers: buildPayload() },
      });
      setMsg(res.pesan);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal menyimpan draf.");
    }
  }

  async function submit() {
    if (!attempt) return;
    if (!window.confirm("Kumpulkan jawaban sekarang? Setelah terkumpul tidak bisa diubah.")) return;
    setErr("");
    setBusy(true);
    try {
      const view = await apiFetch<AttemptView>(`/api/v1/attempts/${attempt.attempt.id}/submit`, {
        method: "POST",
        body: { answers: buildPayload() },
      });
      setAttempt(view);
      if (view.pesan) setMsg(view.pesan);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal mengumpulkan.");
    } finally {
      setBusy(false);
    }
  }

  const fmtRemaining = (ms: number) => {
    const s = Math.max(0, Math.floor(ms / 1000));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };

  return (
    <div>
      <h1 style={{ fontSize: "1.5rem" }}>🧪 {quiz.judul}</h1>
      <p className="muted">
        {quiz.tipe === "pilihan_ganda" ? "Pilihan Ganda" : "Esai"} · {quiz.jumlah_soal} soal ·
        total bobot {quiz.total_bobot}
        {quiz.durasi_menit ? ` · durasi ${quiz.durasi_menit} menit` : " · tanpa batas waktu"}
      </p>
      {quiz.dibuka_pada && <p className="muted">Dibuka: {new Date(quiz.dibuka_pada).toLocaleString("id-ID")}</p>}
      {quiz.ditutup_pada && <p className="muted">Ditutup: {new Date(quiz.ditutup_pada).toLocaleString("id-ID")}</p>}
      {err && <div className="alert alert-error">{err}</div>}
      {msg && <div className="alert alert-ok">{msg}</div>}

      {!attempt && (
        <div className="card" style={{ marginTop: 14 }}>
          {quiz.bisa_mulai ? (
            <>
              <p>Siap mengerjakan? Waktu {quiz.durasi_menit ? "mulai dihitung" : "pengerjaan"} sejak Anda menekan tombol mulai.</p>
              <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={start} disabled={busy}>
                {busy ? "Memulai..." : "▶️ Mulai Mengerjakan"}
              </button>
            </>
          ) : (
            <p>{quiz.alasan ?? "Kuis belum bisa dikerjakan."}</p>
          )}
        </div>
      )}

      {attempt && (
        <div style={{ marginTop: 14 }}>
          <div className="card" style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <span>
              Status: <strong>{attempt.attempt.status}</strong>
              {attempt.attempt.skor !== null && <> · Skor: <strong>{attempt.attempt.skor}</strong></>}
            </span>
            {remaining !== null && attempt.attempt.status === "in_progress" && (
              <span className="badge" style={{ fontSize: ".95rem" }}>⏱ Sisa waktu: {fmtRemaining(remaining)}</span>
            )}
          </div>

          {attempt.questions.map((q, i) => {
            const inProgress = attempt.attempt.status === "in_progress";
            const selected = (answers[q.id] as number[]) ?? [];
            return (
              <div className="card" key={q.id} style={{ marginTop: 12 }}>
                <p>
                  <strong>{i + 1}. {q.pertanyaan}</strong>{" "}
                  <span className="badge">bobot {q.bobot}</span>
                  {q.is_correct === true && <span className="badge" style={{ marginLeft: 6 }}>✅ benar · {q.poin} poin</span>}
                  {q.is_correct === false && attempt.attempt.status !== "in_progress" && (
                    <span className="badge badge-off" style={{ marginLeft: 6 }}>❌ · {q.poin ?? 0} poin</span>
                  )}
                </p>
                {q.tipe === "pilihan_ganda" ? (
                  <div style={{ marginTop: 8 }}>
                    {q.options.map((o, oi) => {
                      const checked = selected.includes(o.id);
                      const isKey = q.kunci_option_ids?.includes(o.id);
                      return (
                        <label key={o.id} style={{ display: "block", padding: "4px 0", color: isKey ? "var(--ok)" : undefined }}>
                          <input
                            type={q.multi ? "checkbox" : "radio"}
                            name={`q-${q.id}`}
                            disabled={!inProgress}
                            checked={checked}
                            onChange={(e) => {
                              if (q.multi) {
                                const next = e.target.checked
                                  ? [...selected, o.id]
                                  : selected.filter((x) => x !== o.id);
                                setAnswers({ ...answers, [q.id]: next });
                              } else {
                                setAnswers({ ...answers, [q.id]: [o.id] });
                              }
                            }}
                          />{" "}
                          <strong>{String.fromCharCode(65 + oi)}.</strong> {o.teks}
                          {isKey && " ✅"}
                        </label>
                      );
                    })}
                    {q.multi && <p className="muted">Soal ini memiliki lebih dari satu jawaban benar — pilih semua yang benar.</p>}
                  </div>
                ) : (
                  <div style={{ marginTop: 8 }}>
                    <textarea
                      className="textarea"
                      rows={4}
                      disabled={!inProgress}
                      value={(answers[q.id] as string) ?? ""}
                      onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                      placeholder="Tulis jawaban Anda..."
                    />
                    {q.jawaban_referensi && attempt.attempt.status !== "in_progress" && (
                      <p className="muted" style={{ marginTop: 6 }}>Referensi jawaban: {q.jawaban_referensi}</p>
                    )}
                    {attempt.attempt.status !== "in_progress" && (
                      <p className="muted">Poin: {q.poin ?? "belum dinilai"}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {attempt.attempt.status === "in_progress" && (
            <div className="row-actions" style={{ marginTop: 14 }}>
              <button className="btn" onClick={saveDraft}>💾 Simpan Draf</button>
              <button className="btn btn-primary" onClick={submit} disabled={busy}>📤 Kumpulkan</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ================================================================ GURU */
function GuruView({ quiz }: { quiz: QuizFull }) {
  const [results, setResults] = useState<ResultRow[]>([]);
  const [detail, setDetail] = useState<AttemptView | null>(null);
  const [grades, setGrades] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const loadResults = useCallback(async () => {
    try {
      setResults(await apiFetch<ResultRow[]>(`/api/v1/quizzes/${quiz.id}/results`));
    } catch { /* abaikan */ }
  }, [quiz.id]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  async function openAttempt(attemptId: number) {
    setErr("");
    try {
      const view = await apiFetch<AttemptView>(`/api/v1/attempts/${attemptId}`);
      setDetail(view);
      const g: Record<number, string> = {};
      for (const q of view.questions) {
        if (q.poin !== null && q.poin !== undefined) g[q.id] = String(q.poin);
      }
      setGrades(g);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal membuka attempt.");
    }
  }

  async function saveGrades() {
    if (!detail) return;
    setErr("");
    setMsg("");
    try {
      const payload = Object.entries(grades).map(([qid, poin]) => ({
        question_id: Number(qid),
        poin: Number(poin),
      }));
      const view = await apiFetch<AttemptView>(`/api/v1/attempts/${detail.attempt.id}/grade`, {
        method: "POST",
        body: { grades: payload },
      });
      setDetail(view);
      setMsg("Nilai tersimpan.");
      loadResults();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal menyimpan nilai.");
    }
  }

  async function remove() {
    if (!window.confirm(`Hapus kuis "${quiz.judul}" beserta seluruh attempt-nya?`)) return;
    await apiFetch(`/api/v1/quizzes/${quiz.id}`, { method: "DELETE" });
    window.history.back();
  }

  async function extract() {
    setErr("");
    try {
      const res = await apiFetch<{ jumlah_diekstrak: number }>(`/api/v1/quizzes/${quiz.id}/extract-questions`, {
        method: "POST",
        body: {},
      });
      setMsg(`${res.jumlah_diekstrak} soal tersimpan ke Bank Soal.`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal mengekstrak soal.");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: "1.5rem" }}>🧪 {quiz.judul}</h1>
        <span className="row-actions">
          <Link className="btn btn-sm" href={`/editor/kuis?quiz=${quiz.id}`}>✏️ Edit</Link>
          <button className="btn btn-sm" onClick={extract}>📥 Ekstrak ke Bank Soal</button>
          <a className="btn btn-sm" href={`${API_BASE}/api/v1/quizzes/${quiz.id}/export?format=csv`}>⬇️ CSV</a>
          <a className="btn btn-sm" href={`${API_BASE}/api/v1/quizzes/${quiz.id}/export?format=xlsx`}>⬇️ XLSX</a>
          <button className="btn btn-sm btn-danger" onClick={remove}>Hapus</button>
        </span>
      </div>
      <p className="muted">
        {quiz.tipe === "pilihan_ganda" ? "Pilihan Ganda" : "Esai"} · {quiz.questions.length} soal ·
        durasi: {quiz.durasi_menit ? `${quiz.durasi_menit} menit` : "tanpa batas"}
      </p>
      {err && <div className="alert alert-error">{err}</div>}
      {msg && <div className="alert alert-ok">{msg}</div>}

      <div className="card" style={{ marginTop: 12 }}>
        <h3>Soal & Kunci</h3>
        {quiz.questions.map((q, i) => (
          <div key={q.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
            <p><strong>{i + 1}. {q.pertanyaan}</strong> <span className="badge">bobot {q.bobot}</span></p>
            {q.options.map((o) => (
              <p key={o.id} style={{ color: o.is_correct ? "var(--ok)" : undefined }}>
                {o.is_correct ? "✅" : "▫️"} {o.label}. {o.teks}
              </p>
            ))}
            {q.jawaban_referensi && <p className="muted">Referensi: {q.jawaban_referensi}</p>}
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <h3>Hasil Siswa ({results.length})</h3>
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>Siswa</th><th>Status</th><th>Skor</th><th>Submit</th><th>Aksi</th></tr></thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.attempt_id}>
                <td>{r.siswa?.nama_lengkap ?? r.siswa?.username ?? "-"}</td>
                <td>{r.status}</td>
                <td>{r.skor ?? "—"}</td>
                <td>{r.submitted_at ? new Date(r.submitted_at).toLocaleString("id-ID") : "—"}</td>
                <td><button className="btn btn-sm" onClick={() => openAttempt(r.attempt_id)}>{quiz.tipe === "teks" ? "Nilai" : "Lihat"}</button></td>
              </tr>
            ))}
            {results.length === 0 && <tr><td colSpan={5} className="muted">Belum ada siswa yang mengerjakan.</td></tr>}
          </tbody>
        </table>
      </div>

      {detail && (
        <div className="card" style={{ marginTop: 12 }}>
          <h3>Detail Attempt #{detail.attempt.id} — status {detail.attempt.status}, skor {detail.attempt.skor ?? "—"}</h3>
          {detail.questions.map((q, i) => (
            <div key={q.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
              <p><strong>{i + 1}. {q.pertanyaan}</strong> <span className="badge">bobot {q.bobot}</span></p>
              {q.tipe === "pilihan_ganda" ? (
                <p className="muted">
                  Jawaban siswa: {q.jawaban_option_ids.length ? q.jawaban_option_ids.map((id) => q.options.find((o) => o.id === id)?.teks ?? id).join("; ") : "(kosong)"} ·
                  Poin otomatis: {q.poin ?? "—"}
                </p>
              ) : (
                <>
                  <p style={{ whiteSpace: "pre-wrap", margin: "6px 0" }}>{q.jawaban_teks || "(kosong)"}</p>
                  {q.jawaban_referensi && <p className="muted">Referensi: {q.jawaban_referensi}</p>}
                  <label className="label">Poin (0 – {q.bobot})</label>
                  <input
                    className="input"
                    style={{ maxWidth: 140 }}
                    type="number"
                    step="0.5"
                    min={0}
                    max={q.bobot}
                    value={grades[q.id] ?? ""}
                    onChange={(e) => setGrades({ ...grades, [q.id]: e.target.value })}
                  />
                </>
              )}
            </div>
          ))}
          {quiz.tipe === "teks" && detail.attempt.status !== "in_progress" && (
            <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={saveGrades}>💾 Simpan Nilai</button>
          )}
        </div>
      )}
    </div>
  );
}
