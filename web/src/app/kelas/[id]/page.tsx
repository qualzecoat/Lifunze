"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface MaterialBrief {
  id: number;
  judul: string;
  jumlah_file: number;
}
interface QuizBrief {
  id: number;
  judul: string;
  tipe: string;
  jumlah_soal: number;
}
interface Meeting {
  id: number;
  judul: string;
  urutan: number;
  tanggal: string | null;
  deskripsi: string | null;
  materials: MaterialBrief[];
  quizzes: QuizBrief[];
  jumlah_kuis: number;
}
interface SubjectDetail {
  id: number;
  nama: string;
  deskripsi: string | null;
  is_archived: boolean;
  bisa_kelola: boolean;
  meetings: Meeting[];
}
interface Member {
  id: number;
  username: string;
  nama_lengkap: string | null;
  is_active: boolean;
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
  jumlah_soal: number;
}

export default function KelasDetailPage() {
  const params = useParams<{ id: string }>();
  const sid = params.id;
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [subject, setSubject] = useState<SubjectDetail | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [candidates, setCandidates] = useState<Member[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bankItems, setBankItems] = useState<SavedMaterial[]>([]);
  const [bankFor, setBankFor] = useState<number | null>(null);
  const [bankQuizzes, setBankQuizzes] = useState<SavedQuiz[]>([]);
  const [bankQuizFor, setBankQuizFor] = useState<number | null>(null);
  const [composeFor, setComposeFor] = useState<number | null>(null);
  const [cJudul, setCJudul] = useState("");
  const [cJumlah, setCJumlah] = useState("5");
  const [cTipe, setCTipe] = useState<"pilihan_ganda" | "teks">("pilihan_ganda");
  const [cKategori, setCKategori] = useState("");
  const [cDurasi, setCDurasi] = useState("");
  const [cCategories, setCCategories] = useState<{ id: number; nama: string }[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [newMeeting, setNewMeeting] = useState({ judul: "", tanggal: "", deskripsi: "" });
  const [announcements, setAnnouncements] = useState<{ id: number; judul: string; isi: string; penulis: string | null; created_at: string | null }[]>([]);
  const [annJudul, setAnnJudul] = useState("");
  const [annIsi, setAnnIsi] = useState("");
  const [progress, setProgress] = useState<{
    mode: string;
    ringkasan?: { persen_total: number; persen_materi: number; persen_kuis: number; rata_skor: number | null; materi_dibaca: number; total_materi: number; kuis_dikerjakan: number; total_kuis: number };
    per_siswa?: { siswa: { username: string; nama_lengkap: string | null } | null; persen_total: number; persen_materi: number; persen_kuis: number; rata_skor: number | null }[];
  } | null>(null);

  // U2 audit UX: halaman kelas bertab (konten adalah tab bawaan).
  const [tab, setTab] = useState<"konten" | "pengumuman" | "siswa" | "progress">("konten");
  const [openMeetings, setOpenMeetings] = useState<Set<number> | null>(null);
  // U5: form siswa baru langsung di kelas.
  const [nsUsername, setNsUsername] = useState("");
  const [nsNama, setNsNama] = useState("");
  const [nsPassword, setNsPassword] = useState("");

  const load = useCallback(async () => {
    try {
      const detail = await apiFetch<SubjectDetail>(`/api/v1/subjects/${sid}`);
      setSubject(detail);
      setMembers(await apiFetch<Member[]>(`/api/v1/subjects/${sid}/students`));
      setAnnouncements(await apiFetch(`/api/v1/subjects/${sid}/announcements`));
      setProgress(await apiFetch(`/api/v1/subjects/${sid}/progress`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat kelas.");
    }
  }, [sid]);

  async function addAnnouncement(e: React.FormEvent) {
    e.preventDefault();
    try {
      await apiFetch(`/api/v1/subjects/${sid}/announcements`, {
        method: "POST",
        body: { judul: annJudul, isi: annIsi },
      });
      setAnnJudul("");
      setAnnIsi("");
      setOk("Pengumuman terkirim; siswa menerima notifikasi.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat pengumuman.");
    }
  }

  async function deleteAnnouncement(id: number) {
    if (!window.confirm("Hapus pengumuman ini?")) return;
    await apiFetch(`/api/v1/announcements/${id}`, { method: "DELETE" });
    load();
  }

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
  if (!subject) return <main className="page"><AppHeader user={user} />{error ? <div className="alert alert-error">{error}</div> : <p className="muted">Memuat kelas...</p>}</main>;

  const kelola = subject.bisa_kelola;

  async function addMeeting(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await apiFetch(`/api/v1/subjects/${sid}/meetings`, {
        method: "POST",
        body: {
          judul: newMeeting.judul,
          tanggal: newMeeting.tanggal || null,
          deskripsi: newMeeting.deskripsi || null,
        },
      });
      setNewMeeting({ judul: "", tanggal: "", deskripsi: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menambah pertemuan.");
    }
  }

  async function moveMeeting(idx: number, dir: -1 | 1) {
    if (!subject) return;
    const list = [...subject.meetings];
    const j = idx + dir;
    if (j < 0 || j >= list.length) return;
    [list[idx], list[j]] = [list[j], list[idx]];
    try {
      await apiFetch(`/api/v1/subjects/${sid}/meetings/reorder`, {
        method: "POST",
        body: { urutan: list.map((m) => m.id) },
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengubah urutan.");
    }
  }

  async function renameMeeting(m: Meeting) {
    const judul = window.prompt("Judul pertemuan:", m.judul);
    if (!judul) return;
    await apiFetch(`/api/v1/subjects/meetings/${m.id}`, {
      method: "PATCH",
      body: { judul, tanggal: m.tanggal, deskripsi: m.deskripsi },
    });
    load();
  }

  async function deleteMeeting(m: Meeting) {
    if (!window.confirm(`Hapus pertemuan "${m.judul}" beserta isinya?`)) return;
    await apiFetch(`/api/v1/subjects/meetings/${m.id}`, { method: "DELETE" });
    load();
  }

  async function openBank(meetingId: number) {
    if (bankFor === meetingId) {
      setBankFor(null);
      return;
    }
    try {
      setBankItems(await apiFetch<SavedMaterial[]>("/api/v1/bank/materials"));
      setBankFor(meetingId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat bank.");
    }
  }

  async function useBank(meetingId: number, savedId: number) {
    try {
      await apiFetch(`/api/v1/meetings/${meetingId}/materials/from-bank/${savedId}`, { method: "POST" });
      setOk("Materi dari bank ditambahkan.");
      setBankFor(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memakai materi bank.");
    }
  }

  async function openBankQuiz(meetingId: number) {
    if (bankQuizFor === meetingId) {
      setBankQuizFor(null);
      return;
    }
    try {
      setBankQuizzes(await apiFetch<SavedQuiz[]>("/api/v1/bank/quizzes"));
      setBankQuizFor(meetingId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat bank kuis.");
    }
  }

  async function useBankQuiz(meetingId: number, savedId: number) {
    try {
      await apiFetch(`/api/v1/meetings/${meetingId}/quizzes/from-bank/${savedId}`, { method: "POST" });
      setOk("Kuis dari bank ditambahkan (pengaturan default — atur waktu/durasi lewat Edit).");
      setBankQuizFor(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memakai kuis bank.");
    }
  }

  async function openCompose(meetingId: number) {
    if (composeFor === meetingId) {
      setComposeFor(null);
      return;
    }
    try {
      setCCategories(await apiFetch<{ id: number; nama: string }[]>("/api/v1/bank/categories"));
      setComposeFor(meetingId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuka panel susun kuis.");
    }
  }

  async function submitCompose(meetingId: number) {
    setError("");
    try {
      const q = await apiFetch<{ id: number }>(`/api/v1/meetings/${meetingId}/quizzes/from-bank-questions`, {
        method: "POST",
        body: {
          judul: cJudul,
          jumlah: Number(cJumlah),
          tipe: cTipe,
          kategori_id: cKategori ? Number(cKategori) : null,
          durasi_menit: cDurasi ? Number(cDurasi) : null,
          acak_soal: true,
          acak_opsi: true,
        },
      });
      router.push(`/kuis/${q.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyusun kuis.");
    }
  }

  async function loadCandidates() {
    try {
      const all = await apiFetch<Member[]>("/api/v1/users/students");
      const memberIds = new Set(members.map((m) => m.id));
      setCandidates(all.filter((s) => !memberIds.has(s.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat daftar siswa.");
    }
  }

  async function enrollSelected() {
    try {
      const res = await apiFetch<{ ditambahkan: number; dilewati: { pesan: string }[] }>(
        `/api/v1/subjects/${sid}/enroll`,
        { method: "POST", body: { siswa_ids: [...selected] } },
      );
      setOk(`${res.ditambahkan} siswa ditambahkan.${res.dilewati.length ? " Dilewati: " + res.dilewati.map((d) => d.pesan).join("; ") : ""}`);
      setSelected(new Set());
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mendaftarkan siswa.");
    }
  }

  async function removeMember(m: Member) {
    if (!window.confirm(`Keluarkan ${m.username} dari kelas ini?`)) return;
    await apiFetch(`/api/v1/subjects/${sid}/enroll/${m.id}`, { method: "DELETE" });
    load();
  }

  function meetingOpen(m: Meeting, idx: number): boolean {
    if (openMeetings === null) return idx === 0;
    return openMeetings.has(m.id);
  }

  function toggleMeeting(m: Meeting, idx: number) {
    const current = new Set<number>(
      openMeetings === null ? subject!.meetings.filter((_, i) => i === 0).map((x) => x.id) : openMeetings,
    );
    if (current.has(m.id)) current.delete(m.id);
    else current.add(m.id);
    setOpenMeetings(current);
  }

  async function createStudentInClass(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await apiFetch<{ username: string }>(`/api/v1/subjects/${sid}/students/create`, {
        method: "POST",
        body: { username: nsUsername, nama_lengkap: nsNama || null, password: nsPassword },
      });
      setOk(`Akun siswa "${res.username}" dibuat dan langsung terdaftar di kelas ini. Bagikan password sementaranya — siswa wajib mengganti saat login pertama.`);
      setNsUsername("");
      setNsNama("");
      setNsPassword("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat siswa.");
    }
  }

  async function deleteSubject() {
    if (!window.confirm(`Hapus mata pelajaran "${subject?.nama}" beserta seluruh pertemuan & materinya?`)) return;
    await apiFetch(`/api/v1/subjects/${sid}`, { method: "DELETE" });
    router.push("/kelas");
  }

  async function toggleArchive() {
    if (!subject) return;
    await apiFetch(`/api/v1/subjects/${sid}`, {
      method: "PATCH",
      body: { is_archived: !subject.is_archived },
    });
    setOk(subject.is_archived ? "Kelas dikeluarkan dari arsip." : "Kelas diarsipkan — tersembunyi dari daftar & siswa.");
    load();
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", flexWrap: "wrap", gap: 8 }}>
        <div>
          <h1 style={{ fontSize: "1.6rem" }}>
            {subject.nama} {subject.is_archived && <span className="badge badge-off">arsip</span>}
          </h1>
          <p className="muted">{subject.deskripsi ?? ""}</p>
        </div>
        {kelola && (
          <span className="row-actions">
            <button className="btn btn-sm" onClick={toggleArchive}>
              {subject.is_archived ? "Keluarkan dari Arsip" : "Arsipkan"}
            </button>
            <button className="btn btn-sm btn-danger" onClick={deleteSubject}>Hapus Kelas</button>
          </span>
        )}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <div style={{ display: "flex", gap: 4, borderBottom: "2px solid var(--border)", marginTop: 14, flexWrap: "wrap" }}>
        {(
          [
            ["konten", "📚 Konten"],
            ["pengumuman", "📢 Pengumuman"],
            ["siswa", `👥 Siswa (${members.length})`],
            ["progress", "📈 Progress"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              border: "none", background: "none", padding: "9px 14px", fontWeight: 700, cursor: "pointer",
              color: tab === key ? "var(--violet)" : "var(--muted)",
              borderBottom: tab === key ? "3px solid var(--violet)" : "3px solid transparent",
              marginBottom: -2, fontSize: ".95rem",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "konten" && kelola && (() => {
        const hasMeeting = subject.meetings.length > 0;
        const hasContent = subject.meetings.some((m) => m.materials.length > 0 || m.quizzes.length > 0);
        const hasStudents = members.length > 0;
        if (hasMeeting && hasContent && hasStudents) return null;
        const item = (done: boolean, n: number, teks: React.ReactNode) => (
          <li style={{ listStyle: "none", padding: "5px 0", display: "flex", gap: 9, alignItems: "flex-start" }}>
            <span style={{
              width: 21, height: 21, borderRadius: "50%", flex: "none", display: "inline-flex",
              alignItems: "center", justifyContent: "center", fontSize: ".75rem", fontWeight: 800,
              background: done ? "var(--ok)" : "#fff", color: done ? "#fff" : "#8a6100",
              border: done ? "none" : "2px solid var(--amber)",
            }}>{done ? "✓" : n}</span>
            <span>{teks}</span>
          </li>
        );
        return (
          <div className="card" style={{ marginTop: 14, borderLeft: "5px solid var(--violet)" }}>
            <h3>🚀 Mulai Kelas Ini</h3>
            <ul style={{ marginTop: 6 }}>
              {item(hasMeeting, 1, <><strong>Buat pertemuan pertama</strong>{hasMeeting ? " — selesai" : " — pakai form Tambah Pertemuan di bawah daftar pertemuan."}</>)}
              {item(hasContent, 2, <><strong>Tambah materi atau kuis</strong>{hasContent ? " — selesai" : " — tombol ➕ pada kartu pertemuan; editor kuis kini punya mode Formulir."}</>)}
              {item(hasStudents, 3, <><strong>Daftarkan siswa</strong>{hasStudents ? ` — ${members.length} siswa terdaftar` : <> — lewat tab <button className="btn btn-sm" onClick={() => setTab("siswa")}>👥 Siswa</button>: buat akun baru di sana, langsung terdaftar di kelas ini.</>}</>)}
            </ul>
          </div>
        );
      })()}

      {tab === "progress" && progress && (
        <div className="card" style={{ marginTop: 14 }}>
          <h3>📈 Progress Belajar</h3>
          {progress.mode === "siswa" && progress.ringkasan && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Progress keseluruhan</span>
                <strong>{progress.ringkasan.persen_total}%</strong>
              </div>
              <div style={{ background: "var(--border)", borderRadius: 8, height: 12, margin: "6px 0 10px" }}>
                <div style={{ width: `${progress.ringkasan.persen_total}%`, background: "var(--violet)", height: "100%", borderRadius: 8 }} />
              </div>
              <p className="muted">
                Materi dibaca: {progress.ringkasan.materi_dibaca}/{progress.ringkasan.total_materi} ({progress.ringkasan.persen_materi}%) ·
                Kuis dikerjakan: {progress.ringkasan.kuis_dikerjakan}/{progress.ringkasan.total_kuis} ({progress.ringkasan.persen_kuis}%)
                {progress.ringkasan.rata_skor !== null && <> · Rata-rata skor: {progress.ringkasan.rata_skor}</>}
              </p>
            </div>
          )}
          {progress.mode === "guru" && progress.per_siswa && (
            <table className="table" style={{ marginTop: 8 }}>
              <thead><tr><th>Siswa</th><th>Progress</th><th>Materi</th><th>Kuis</th><th>Rata-rata Skor</th></tr></thead>
              <tbody>
                {progress.per_siswa.map((r, i) => (
                  <tr key={i}>
                    <td>{r.siswa?.nama_lengkap ?? r.siswa?.username ?? "-"}</td>
                    <td><strong>{r.persen_total}%</strong></td>
                    <td>{r.persen_materi}%</td>
                    <td>{r.persen_kuis}%</td>
                    <td>{r.rata_skor ?? "—"}</td>
                  </tr>
                ))}
                {progress.per_siswa.length === 0 && <tr><td colSpan={5} className="muted">Belum ada siswa terdaftar.</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "pengumuman" && (<>
      <div className="card" style={{ marginTop: 14 }}>
        <h3>📢 Pengumuman</h3>
        {announcements.map((a) => (
          <div key={a.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <strong>{a.judul}</strong>
              {kelola && <button className="btn btn-sm btn-danger" onClick={() => deleteAnnouncement(a.id)}>Hapus</button>}
            </div>
            <p style={{ whiteSpace: "pre-wrap", margin: "4px 0" }}>{a.isi}</p>
            <p className="muted">{a.penulis} · {a.created_at ? new Date(a.created_at).toLocaleString("id-ID") : ""}</p>
          </div>
        ))}
        {announcements.length === 0 && <p className="muted" style={{ marginTop: 6 }}>Belum ada pengumuman.</p>}
        {kelola && (
          <form onSubmit={addAnnouncement} style={{ marginTop: 10 }}>
            <input className="input" placeholder="Judul pengumuman" value={annJudul} onChange={(e) => setAnnJudul(e.target.value)} required />
            <textarea className="textarea" rows={2} placeholder="Isi pengumuman..." value={annIsi} onChange={(e) => setAnnIsi(e.target.value)} required style={{ marginTop: 6 }} />
            <button className="btn btn-sm btn-primary" type="submit" style={{ marginTop: 6 }}>📢 Umumkan</button>
          </form>
        )}
      </div>

      </>)}

      {tab === "konten" && (<>
      {subject.meetings.map((m, idx) => (
        <div className="card" key={m.id} style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <h3>
              <button className="btn btn-sm" onClick={() => toggleMeeting(m, idx)} title="Buka/tutup isi pertemuan">{meetingOpen(m, idx) ? "▾" : "▸"}</button>{" "}
              {idx + 1}. {m.judul}
              {m.tanggal && <span className="muted" style={{ fontWeight: 400 }}> · {m.tanggal}</span>}
            </h3>
            {kelola && (
              <div className="row-actions">
                <button className="btn btn-sm" onClick={() => moveMeeting(idx, -1)} title="Naikkan">↑</button>
                <button className="btn btn-sm" onClick={() => moveMeeting(idx, 1)} title="Turunkan">↓</button>
                <button className="btn btn-sm" onClick={() => renameMeeting(m)}>Ubah</button>
                <button className="btn btn-sm btn-danger" onClick={() => deleteMeeting(m)}>Hapus</button>
              </div>
            )}
          </div>
          {meetingOpen(m, idx) && (<>
          {m.deskripsi && <p className="muted">{m.deskripsi}</p>}
          <div style={{ marginTop: 10 }}>
            {m.materials.map((mt) => (
              <div key={mt.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                <Link href={`/materi/${mt.id}`}>📄 {mt.judul}</Link>
                <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {mt.jumlah_file > 0 && <span className="muted">📎 {mt.jumlah_file}</span>}
                  {kelola && <Link href={`/editor/materi?material=${mt.id}`} className="muted">edit</Link>}
                </span>
              </div>
            ))}
            {m.materials.length === 0 && <p className="muted">Belum ada materi.</p>}
          </div>
          <div style={{ marginTop: 10 }}>
            {m.quizzes.map((q) => (
              <div key={q.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                <Link href={`/kuis/${q.id}`}>🧪 {q.judul}</Link>
                <span className="muted">{q.tipe === "pilihan_ganda" ? "Pilihan Ganda" : "Esai"} · {q.jumlah_soal} soal</span>
              </div>
            ))}
          </div>
          {kelola && (
            <div style={{ marginTop: 12 }}>
              <div className="row-actions">
                <Link className="btn btn-sm btn-primary" href={`/editor/materi?meeting=${m.id}&kelas=${sid}`}>➕ Materi Baru</Link>
                <button className="btn btn-sm" onClick={() => openBank(m.id)}>📚 Ambil dari Bank</button>
                <Link className="btn btn-sm btn-primary" href={`/editor/kuis?meeting=${m.id}&kelas=${sid}`}>➕ Kuis Baru</Link>
                <button className="btn btn-sm" onClick={() => openBankQuiz(m.id)}>🧪 Kuis dari Bank</button>
                <button className="btn btn-sm" onClick={() => openCompose(m.id)}>🎲 Susun dari Bank Soal</button>
              </div>
              {bankFor === m.id && (
                <div style={{ marginTop: 10 }}>
                  {bankItems.length === 0 && <p className="muted">Bank materi Anda kosong.</p>}
                  {bankItems.map((b) => (
                    <div key={b.id} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
                      <span>{b.judul}</span>
                      <button className="btn btn-sm" onClick={() => useBank(m.id, b.id)}>Pakai</button>
                    </div>
                  ))}
                </div>
              )}
              {bankQuizFor === m.id && (
                <div style={{ marginTop: 10 }}>
                  {bankQuizzes.length === 0 && <p className="muted">Bank kuis Anda kosong.</p>}
                  {bankQuizzes.map((b) => (
                    <div key={b.id} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
                      <span>🧪 {b.judul} <span className="muted">({b.jumlah_soal} soal)</span></span>
                      <button className="btn btn-sm" onClick={() => useBankQuiz(m.id, b.id)}>Pakai</button>
                    </div>
                  ))}
                </div>
              )}
              {composeFor === m.id && (
                <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 8 }}>
                  <div>
                    <label className="label">Judul kuis</label>
                    <input className="input" value={cJudul} onChange={(e) => setCJudul(e.target.value)} placeholder="Ulangan Acak 1" />
                  </div>
                  <div>
                    <label className="label">Jumlah soal</label>
                    <input className="input" type="number" min={1} value={cJumlah} onChange={(e) => setCJumlah(e.target.value)} />
                  </div>
                  <div>
                    <label className="label">Tipe soal</label>
                    <select className="select" value={cTipe} onChange={(e) => setCTipe(e.target.value as "pilihan_ganda" | "teks")}>
                      <option value="pilihan_ganda">Pilihan Ganda</option>
                      <option value="teks">Esai</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">Kategori bank</label>
                    <select className="select" value={cKategori} onChange={(e) => setCKategori(e.target.value)}>
                      <option value="">Semua kategori</option>
                      {cCategories.map((c) => (
                        <option key={c.id} value={c.id}>{c.nama}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Durasi (menit)</label>
                    <input className="input" type="number" min={1} value={cDurasi} onChange={(e) => setCDurasi(e.target.value)} placeholder="opsional" />
                  </div>
                  <div style={{ display: "flex", alignItems: "flex-end" }}>
                    <button className="btn btn-primary" disabled={!cJudul.trim()} onClick={() => submitCompose(m.id)}>🎲 Susun Kuis</button>
                  </div>
                  <p className="muted" style={{ gridColumn: "1 / -1" }}>Soal ditarik acak dari bank soal Anda; urutan soal & opsi ikut diacak per siswa.</p>
                </div>
              )}
            </div>
          )}
          </>)}
        </div>
      ))}
      {subject.meetings.length === 0 && <p className="muted" style={{ marginTop: 14 }}>Belum ada pertemuan.</p>}

      {kelola && (
        <form className="card" onSubmit={addMeeting} style={{ marginTop: 16 }}>
          <h3>➕ Tambah Pertemuan</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
            <div>
              <label className="label">Judul</label>
              <input className="input" value={newMeeting.judul} onChange={(e) => setNewMeeting({ ...newMeeting, judul: e.target.value })} required />
            </div>
            <div>
              <label className="label">Tanggal (opsional)</label>
              <input className="input" type="date" value={newMeeting.tanggal} onChange={(e) => setNewMeeting({ ...newMeeting, tanggal: e.target.value })} />
            </div>
            <div>
              <label className="label">Deskripsi (opsional)</label>
              <input className="input" value={newMeeting.deskripsi} onChange={(e) => setNewMeeting({ ...newMeeting, deskripsi: e.target.value })} />
            </div>
          </div>
          <button className="btn btn-primary" type="submit" style={{ marginTop: 12 }}>Tambah</button>
        </form>
      )}

      </>)}

      {tab === "siswa" && (<>
      {kelola && (
        <form className="card" onSubmit={createStudentInClass} style={{ marginTop: 16, borderLeft: "5px solid var(--violet)" }}>
          <h3>➕ Siswa Baru — langsung terdaftar di kelas ini</h3>
          <p className="muted" style={{ marginTop: 4 }}>Satu langkah: akun dibuat dan langsung masuk kelas ini. Untuk banyak siswa sekaligus, impor CSV di halaman Siswa kini bisa memilih kelas tujuan.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 12, marginTop: 8 }}>
            <div>
              <label className="label">Nama lengkap</label>
              <input className="input" value={nsNama} onChange={(e) => setNsNama(e.target.value)} placeholder="cth: Salsabila Zahra" />
            </div>
            <div>
              <label className="label">Username</label>
              <input className="input" value={nsUsername} onChange={(e) => setNsUsername(e.target.value)} placeholder="cth: salsabila" required />
            </div>
            <div>
              <label className="label">Password sementara (min. 8)</label>
              <input className="input" value={nsPassword} onChange={(e) => setNsPassword(e.target.value)} placeholder="dibagikan ke siswa" required />
            </div>
          </div>
          <button className="btn btn-primary" type="submit" style={{ marginTop: 12 }}>Buat &amp; Daftarkan</button>
        </form>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <h3>👩‍🎓 Siswa di Kelas Ini ({members.length})</h3>
        <div style={{ marginTop: 8 }}>
          {members.map((m) => (
            <div key={m.id} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid var(--border)" }}>
              <span>{m.nama_lengkap ?? m.username} <span className="muted">({m.username})</span></span>
              {kelola && <button className="btn btn-sm btn-danger" onClick={() => removeMember(m)}>Keluarkan</button>}
            </div>
          ))}
          {members.length === 0 && <p className="muted">Belum ada siswa.</p>}
        </div>
        {kelola && (
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-sm" onClick={loadCandidates}>➕ Daftarkan Siswa</button>
            {candidates.length > 0 && (
              <div style={{ marginTop: 10 }}>
                {candidates.map((c) => (
                  <label key={c.id} style={{ display: "block", padding: "3px 0" }}>
                    <input
                      type="checkbox"
                      checked={selected.has(c.id)}
                      onChange={(e) => {
                        const next = new Set(selected);
                        if (e.target.checked) next.add(c.id);
                        else next.delete(c.id);
                        setSelected(next);
                      }}
                    />{" "}
                    {c.nama_lengkap ?? c.username} <span className="muted">({c.username})</span>
                  </label>
                ))}
                <button className="btn btn-primary btn-sm" style={{ marginTop: 8 }} onClick={enrollSelected} disabled={selected.size === 0}>
                  Tambahkan {selected.size} Siswa
                </button>
              </div>
            )}
          </div>
        )}
      </div>
      </>)}
    </main>
  );
}
