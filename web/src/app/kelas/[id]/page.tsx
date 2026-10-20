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
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [newMeeting, setNewMeeting] = useState({ judul: "", tanggal: "", deskripsi: "" });

  const load = useCallback(async () => {
    try {
      const detail = await apiFetch<SubjectDetail>(`/api/v1/subjects/${sid}`);
      setSubject(detail);
      setMembers(await apiFetch<Member[]>(`/api/v1/subjects/${sid}/students`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat kelas.");
    }
  }, [sid]);

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

      {subject.meetings.map((m, idx) => (
        <div className="card" key={m.id} style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <h3>
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
            </div>
          )}
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
    </main>
  );
}
