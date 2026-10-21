"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface MaterialBrief {
  id: number;
  judul: string;
  jumlah_file: number;
  di_bank: boolean;
  grup_dokumen: string | null;
  jenis: string;
}
interface QuizBrief {
  id: number;
  judul: string;
  tipe: string;
  jumlah_soal: number;
  di_bank: boolean;
  grup_dokumen: string | null;
  jenis: string;
}
interface RencanaItem {
  judul: string;
  tujuan: string;
  konsep: string[];
  aktivitas: string[];
  alur: string | null;
  meeting_id?: number | null;
}
interface Meeting {
  id: number;
  judul: string;
  urutan: number;
  tanggal: string | null;
  deskripsi: string | null;
  rencana?: RencanaItem | null;
  ringkasan?: string | null;
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
  jenjang?: string | null;
  target_siswa?: string | null;
  tujuan_akhir?: string | null;
  kurikulum?: RencanaItem[] | null;
  template_default_id?: number | null;
  pack_default_id?: number | null;
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
  grup_dokumen: string | null;
  jenis: string;
}
interface SavedQuiz {
  id: number;
  judul: string;
  tipe: string;
  jumlah_soal: number;
  kategori_id: number | null;
  grup_dokumen: string | null;
  jenis: string;
}

/** Satu baris dokumen di daftar isi pertemuan: materi + kuis pasangannya. */
interface BarisDokumen {
  kunci: string;
  grup: string | null;
  judul: string;
  jenis: string;
  material: MaterialBrief | null;
  quizzes: QuizBrief[];
}

function kelompokkanDokumen(m: Meeting): BarisDokumen[] {
  const rows: BarisDokumen[] = [];
  const grupTerdaftar = new Set<string>();
  for (const mt of m.materials) {
    if (mt.grup_dokumen) {
      if (grupTerdaftar.has(mt.grup_dokumen)) continue;
      grupTerdaftar.add(mt.grup_dokumen);
      rows.push({
        kunci: `g-${mt.grup_dokumen}`,
        grup: mt.grup_dokumen,
        judul: mt.judul,
        jenis: mt.jenis,
        material: mt,
        quizzes: m.quizzes.filter((q) => q.grup_dokumen === mt.grup_dokumen),
      });
    } else {
      rows.push({ kunci: `m-${mt.id}`, grup: null, judul: mt.judul, jenis: mt.jenis, material: mt, quizzes: [] });
    }
  }
  for (const q of m.quizzes) {
    if (!q.grup_dokumen) {
      rows.push({ kunci: `q-${q.id}`, grup: null, judul: q.judul, jenis: q.jenis, material: null, quizzes: [q] });
    } else if (!grupTerdaftar.has(q.grup_dokumen)) {
      grupTerdaftar.add(q.grup_dokumen);
      rows.push({
        kunci: `g-${q.grup_dokumen}`,
        grup: q.grup_dokumen,
        judul: q.judul,
        jenis: q.jenis,
        material: null,
        quizzes: m.quizzes.filter((x) => x.grup_dokumen === q.grup_dokumen),
      });
    }
  }
  return rows;
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
  const [bankKategori, setBankKategori] = useState<{ id: number; nama: string }[]>([]);
  const [bankFilterKategori, setBankFilterKategori] = useState("");
  const [bankFilterTag, setBankFilterTag] = useState("");
  const [bankCari, setBankCari] = useState("");
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
  const [tab, setTab] = useState<"konten" | "pengumuman" | "siswa" | "progress" | "kurikulum">("konten");
  // Kurikulum & info kelas (2026-10-21, desain 3-AI)
  const [kJenjang, setKJenjang] = useState("");
  const [kTarget, setKTarget] = useState("");
  const [kTujuan, setKTujuan] = useState("");
  const [kTemplate, setKTemplate] = useState("");
  const [kPack, setKPack] = useState("");
  const [rencana, setRencana] = useState<RencanaItem[]>([]);
  const [tplOptions, setTplOptions] = useState<{ id: number; nama: string }[]>([]);
  const [packOptions, setPackOptions] = useState<{ id: number; nama: string }[]>([]);
  const [kurJumlah, setKurJumlah] = useState("8");
  const [kurMode, setKurMode] = useState<"nol" | "rapikan">("nol");
  const [kurTeks, setKurTeks] = useState("");
  const [kurBusy, setKurBusy] = useState(false);
  const kurSinkron = useRef<number | null>(null);
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

  // Sinkronkan form kurikulum dari data kelas SEKALI per kelas (editan guru
  // sesudahnya tidak ditimpa oleh pemuatan ulang biasa).
  useEffect(() => {
    if (!subject || kurSinkron.current === subject.id) return;
    kurSinkron.current = subject.id;
    setKJenjang(subject.jenjang ?? "");
    setKTarget(subject.target_siswa ?? "");
    setKTujuan(subject.tujuan_akhir ?? "");
    setKTemplate(subject.template_default_id ? String(subject.template_default_id) : "");
    setKPack(subject.pack_default_id ? String(subject.pack_default_id) : "");
    setRencana((subject.kurikulum ?? []).map((r) => ({ ...r, konsep: [...(r.konsep ?? [])], aktivitas: [...(r.aktivitas ?? [])] })));
  }, [subject]);

  async function muatOpsiKurikulum() {
    if (tplOptions.length > 0) return;
    try {
      const tpl = await apiFetch<{ preset: { id: number; nama: string }[]; saya: { id: number; nama: string }[]; dibagikan: { id: number; nama: string }[] }>("/api/v1/templates");
      setTplOptions([...tpl.preset, ...tpl.saya, ...tpl.dibagikan]);
      const mine = await apiFetch<{ id: number; nama: string }[]>("/api/v1/packs");
      const shared = await apiFetch<{ id: number; nama: string }[]>("/api/v1/packs/shared");
      setPackOptions([...mine, ...shared]);
    } catch { /* diam — opsi kosong tidak menghalangi jalur manual */ }
  }

  async function simpanInfoKelas() {
    setError("");
    try {
      await apiFetch(`/api/v1/subjects/${sid}`, {
        method: "PATCH",
        body: {
          jenjang: kJenjang, target_siswa: kTarget, tujuan_akhir: kTujuan,
          template_default_id: kTemplate ? Number(kTemplate) : undefined,
          pack_default_id: kPack ? Number(kPack) : undefined,
        },
      });
      setOk("Info kelas tersimpan — dipakai sebagai konteks generate AI.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan info kelas.");
    }
  }

  async function generateKurikulum() {
    setKurBusy(true);
    setError("");
    try {
      const r = await apiFetch<{ rencana: RencanaItem[] }>(`/api/v1/subjects/${sid}/kurikulum/generate`, {
        method: "POST",
        body: {
          mode: kurMode,
          jumlah_pertemuan: Number(kurJumlah) || 8,
          teks_kurikulum: kurMode === "rapikan" ? kurTeks : undefined,
        },
      });
      setRencana(r.rencana.map((x) => ({ ...x, meeting_id: null })));
      setOk("Draf kurikulum dibuat AI — periksa & edit di bawah, lalu Simpan Rencana.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate kurikulum gagal.");
    } finally {
      setKurBusy(false);
    }
  }

  async function simpanRencana() {
    setError("");
    try {
      const bersih = rencana.filter((r) => r.judul.trim());
      await apiFetch(`/api/v1/subjects/${sid}/kurikulum`, { method: "PUT", body: { pertemuan: bersih } });
      setOk("Rencana kurikulum tersimpan.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan rencana.");
    }
  }

  async function terapkanRencana() {
    setError("");
    try {
      const r = await apiFetch<{ dibuat: number; total: number }>(`/api/v1/subjects/${sid}/kurikulum/terapkan`, { method: "POST" });
      setOk(`Rencana diterapkan: ${r.dibuat} pertemuan baru dibuat (${r.total} total di rencana). Lihat di tab Konten.`);
      kurSinkron.current = null; // paksa sinkron ulang rencana (meeting_id baru)
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menerapkan rencana.");
    }
  }

  function ubahRencana(i: number, patch: Partial<RencanaItem>) {
    setRencana((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

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

  // -- Aksi per baris materi/kuis (paket perbaikan 2026-10-20) --
  async function saveMaterialBank(mt: MaterialBrief) {
    setError("");
    setOk("");
    try {
      await apiFetch(`/api/v1/materials/${mt.id}/save-to-bank`, { method: "POST" });
      setOk(`Materi "${mt.judul}" tersimpan ke bank.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan ke bank.");
    }
  }

  async function deleteMaterialRow(mt: MaterialBrief) {
    if (!window.confirm(`Hapus materi "${mt.judul}"? Pengumpulan tugas di dalamnya ikut terhapus.`)) return;
    await apiFetch(`/api/v1/materials/${mt.id}`, { method: "DELETE" });
    load();
  }

  async function saveQuizBank(q: QuizBrief) {
    setError("");
    setOk("");
    try {
      await apiFetch(`/api/v1/quizzes/${q.id}/save-to-bank`, { method: "POST", body: {} });
      setOk(`Kuis "${q.judul}" tersimpan ke bank.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan ke bank.");
    }
  }

  async function deleteQuizRow(q: QuizBrief) {
    if (!window.confirm(`Hapus kuis "${q.judul}"? PERINGATAN: hasil pengerjaan siswa pada kuis ini ikut terhapus.`)) return;
    await apiFetch(`/api/v1/quizzes/${q.id}`, { method: "DELETE" });
    load();
  }

  async function saveAsTemplate() {
    const nama = window.prompt("Nama template kelas:", subject?.nama ?? "");
    if (!nama) return;
    setError("");
    setOk("");
    try {
      await apiFetch(`/api/v1/subjects/${sid}/save-template`, { method: "POST", body: { nama } });
      setOk(`Kelas tersimpan sebagai template "${nama}". Template bisa dipakai lagi dari menu Kelas atau Bank.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan template.");
    }
  }

  async function openBank(meetingId: number) {
    if (bankFor === meetingId) {
      setBankFor(null);
      return;
    }
    try {
      setBankItems(await apiFetch<SavedMaterial[]>("/api/v1/bank/materials"));
      setBankQuizzes(await apiFetch<SavedQuiz[]>("/api/v1/bank/quizzes"));
      setBankKategori(await apiFetch<{ id: number; nama: string }[]>("/api/v1/bank/categories"));
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

  async function useBankQuiz(meetingId: number, savedId: number) {
    try {
      await apiFetch(`/api/v1/meetings/${meetingId}/quizzes/from-bank/${savedId}`, { method: "POST" });
      setOk("Kuis dari bank ditambahkan (pengaturan default — atur waktu/durasi lewat Edit).");
      setBankFor(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memakai kuis bank.");
    }
  }

  async function useBankDocument(meetingId: number, grup: string) {
    try {
      await apiFetch(`/api/v1/bank/documents/${grup}/use`, {
        method: "POST",
        body: { meeting_id: meetingId },
      });
      setOk("Dokumen dari bank ditambahkan utuh (materi + kuisnya).");
      setBankFor(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memakai dokumen bank.");
    }
  }

  /** Daftar dokumen bank terpadu (pasangan digabung) + filter tag/kategori/cari. */
  function bankDokumenRows() {
    interface BankBaris {
      kunci: string;
      grup: string | null;
      judul: string;
      kategori_id: number | null;
      material: SavedMaterial | null;
      quizzes: SavedQuiz[];
    }
    const rows: BankBaris[] = [];
    const terdaftar = new Set<string>();
    for (const b of bankItems) {
      if (b.grup_dokumen) {
        if (terdaftar.has(b.grup_dokumen)) continue;
        terdaftar.add(b.grup_dokumen);
        rows.push({
          kunci: `g-${b.grup_dokumen}`,
          grup: b.grup_dokumen,
          judul: b.judul,
          kategori_id: b.kategori_id,
          material: b,
          quizzes: bankQuizzes.filter((q) => q.grup_dokumen === b.grup_dokumen),
        });
      } else {
        rows.push({ kunci: `m-${b.id}`, grup: null, judul: b.judul, kategori_id: b.kategori_id, material: b, quizzes: [] });
      }
    }
    for (const q of bankQuizzes) {
      if (!q.grup_dokumen) {
        rows.push({ kunci: `q-${q.id}`, grup: null, judul: q.judul, kategori_id: q.kategori_id, material: null, quizzes: [q] });
      } else if (!terdaftar.has(q.grup_dokumen)) {
        terdaftar.add(q.grup_dokumen);
        rows.push({
          kunci: `g-${q.grup_dokumen}`,
          grup: q.grup_dokumen,
          judul: q.judul,
          kategori_id: q.kategori_id,
          material: null,
          quizzes: bankQuizzes.filter((x) => x.grup_dokumen === q.grup_dokumen),
        });
      }
    }
    return rows.filter((r) => {
      if (bankFilterTag === "materi" && !r.material) return false;
      if (bankFilterTag === "kuis_pg" && !r.quizzes.some((q) => q.tipe === "pilihan_ganda")) return false;
      if (bankFilterTag === "esai" && !r.quizzes.some((q) => q.tipe === "teks")) return false;
      if (bankFilterKategori && String(r.kategori_id ?? "") !== bankFilterKategori) return false;
      if (bankCari && !r.judul.toLowerCase().includes(bankCari.toLowerCase())) return false;
      return true;
    });
  }

  async function saveDocumentBank(row: BarisDokumen) {
    if (!row.grup) return;
    setError("");
    setOk("");
    try {
      await apiFetch(`/api/v1/documents/${row.grup}/save-to-bank`, { method: "POST", body: {} });
      setOk(`Dokumen "${row.judul}" tersimpan ke bank.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan ke bank.");
    }
  }

  async function deleteDocumentRow(row: BarisDokumen) {
    if (!row.grup) return;
    const bagian = [
      row.material ? "materi" : null,
      row.quizzes.length ? `${row.quizzes.length} kuis` : null,
    ].filter(Boolean).join(" + ");
    if (!window.confirm(`Hapus dokumen "${row.judul}" (${bagian})? PERINGATAN: hasil pengerjaan & pengumpulan siswa di dalamnya ikut terhapus.`)) return;
    await apiFetch(`/api/v1/documents/${row.grup}`, { method: "DELETE" });
    load();
  }

  async function openCompose(meetingId: number) {
    if (composeFor === meetingId) {
      setComposeFor(null);
      return;
    }
    // Audit #43: panel memakai state tunggal bersama — reset isian agar
    // parameter dari pertemuan lain tidak terbawa ke pertemuan ini.
    setCJudul("");
    setCJumlah("5");
    setCTipe("pilihan_ganda");
    setCKategori("");
    setCDurasi("");
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
            <button className="btn btn-sm" onClick={saveAsTemplate}>💾 Simpan sebagai Template</button>
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
            ...(kelola ? [["kurikulum", "🧭 Kurikulum"] as const] : []),
            ["pengumuman", "📢 Pengumuman"],
            ["siswa", `👥 Siswa (${members.length})`],
            ["progress", "📈 Progress"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => { setTab(key); if (key === "kurikulum") muatOpsiKurikulum(); }}
            style={{
              border: "none", background: "none", padding: "9px 14px", fontWeight: 700, cursor: "pointer",
              color: tab === key ? "var(--primary)" : "var(--muted)",
              borderBottom: tab === key ? "3px solid var(--primary)" : "3px solid transparent",
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
        const hasKurikulum = (subject.kurikulum ?? []).length > 0;
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
          <div className="card" style={{ marginTop: 14, borderLeft: "5px solid var(--primary)" }}>
            <h3>🚀 Mulai Kelas Ini</h3>
            <ul style={{ marginTop: 6 }}>
              {item(hasKurikulum, 1, <><strong>Susun kurikulum (opsional, disarankan)</strong>{hasKurikulum ? " — selesai" : <> — di tab <button className="btn btn-sm" onClick={() => { setTab("kurikulum"); muatOpsiKurikulum(); }}>🧭 Kurikulum</button>: AI menyusun rencana per pertemuan dari info kelas, lalu pertemuan dibuat otomatis dari rencana.</>}</>)}
              {item(hasMeeting, 2, <><strong>Buat pertemuan pertama</strong>{hasMeeting ? " — selesai" : " — pakai form Tambah Pertemuan di bawah daftar pertemuan, atau terapkan rencana kurikulum."}</>)}
              {item(hasContent, 3, <><strong>Tambah materi atau kuis</strong>{hasContent ? " — selesai" : " — tombol ➕ pada kartu pertemuan; editor kuis kini punya mode Formulir."}</>)}
              {item(hasStudents, 4, <><strong>Daftarkan siswa</strong>{hasStudents ? ` — ${members.length} siswa terdaftar` : <> — lewat tab <button className="btn btn-sm" onClick={() => setTab("siswa")}>👥 Siswa</button>: buat akun baru di sana, langsung terdaftar di kelas ini.</>}</>)}
            </ul>
          </div>
        );
      })()}

      {tab === "kurikulum" && kelola && (
        <>
          <div className="card" style={{ marginTop: 14 }}>
            <h3>🧭 Info Kelas untuk AI (semua opsional)</h3>
            <p className="muted" style={{ marginTop: 2 }}>
              Info ini menjadi konteks kurikulum &amp; generate konten — kelas tetap bisa berjalan tanpa mengisinya.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12, marginTop: 8 }}>
              <div>
                <label className="label">Jenjang / kelas</label>
                <input className="input" value={kJenjang} onChange={(e) => setKJenjang(e.target.value)} placeholder="mis. SD Kelas 5" />
              </div>
              <div>
                <label className="label">Alur mengajar default</label>
                <select className="select" value={kTemplate} onChange={(e) => setKTemplate(e.target.value)}>
                  <option value="">— ikuti rencana per pertemuan —</option>
                  {tplOptions.map((t) => (
                    <option key={t.id} value={t.id}>{t.nama}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Paket parser default</label>
                <select className="select" value={kPack} onChange={(e) => setKPack(e.target.value)}>
                  <option value="">— pilih saat generate —</option>
                  {packOptions.map((p) => (
                    <option key={p.id} value={p.id}>{p.nama}</option>
                  ))}
                </select>
              </div>
            </div>
            <label className="label">Target siswa</label>
            <input className="input" value={kTarget} onChange={(e) => setKTarget(e.target.value)} placeholder="mis. Anak usia 10–11 tahun, pemula komputer" />
            <label className="label">Tujuan akhir pembelajaran</label>
            <input className="input" value={kTujuan} onChange={(e) => setKTujuan(e.target.value)} placeholder="mis. Siswa mahir mengolah angka dasar dengan spreadsheet" />
            <div style={{ marginTop: 10 }}>
              <button className="btn btn-primary" onClick={simpanInfoKelas}>💾 Simpan Info Kelas</button>
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <h3>✨ Susun Kurikulum</h3>
            <div className="seg-toggle" role="tablist" aria-label="Mode kurikulum" style={{ marginTop: 6 }}>
              <button type="button" role="tab" aria-selected={kurMode === "nol"} className={kurMode === "nol" ? "on" : ""} onClick={() => setKurMode("nol")}>Buat dari Nol</button>
              <button type="button" role="tab" aria-selected={kurMode === "rapikan"} className={kurMode === "rapikan" ? "on" : ""} onClick={() => setKurMode("rapikan")}>Rapikan Kurikulum Saya</button>
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end", marginTop: 10 }}>
              <div>
                <label className="label">Jumlah pertemuan</label>
                <input className="input" type="number" min={1} max={60} style={{ maxWidth: 130 }} value={kurJumlah} onChange={(e) => setKurJumlah(e.target.value)} />
              </div>
              <button className="btn btn-primary" onClick={generateKurikulum} disabled={kurBusy}>
                {kurBusy ? "⏳ AI menyusun..." : "✨ Susun dengan AI"}
              </button>
            </div>
            {kurMode === "rapikan" && (
              <>
                <label className="label">Tempel kurikulum / silabus Anda</label>
                <textarea className="textarea" rows={7} value={kurTeks} onChange={(e) => setKurTeks(e.target.value)} placeholder="Tempel silabus apa adanya — AI memetakannya ke pertemuan tanpa mengubah isi & istilah Anda sebisa mungkin." />
              </>
            )}
            <p className="muted" style={{ marginTop: 8 }}>
              Hasil AI adalah <strong>draf rencana</strong> — edit bebas di bawah (atau tulis rencana manual tanpa AI), simpan, lalu terapkan menjadi pertemuan.
            </p>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <h3>📋 Rencana per Pertemuan ({rencana.length})</h3>
            {rencana.map((r, i) => (
              <div key={i} style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 10, marginTop: 10 }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <strong>{i + 1}.</strong>
                  <input className="input" style={{ flex: 1, minWidth: 200 }} value={r.judul} onChange={(e) => ubahRencana(i, { judul: e.target.value })} placeholder="Judul pertemuan" />
                  <select className="select" style={{ maxWidth: 210 }} value={r.alur ?? ""} onChange={(e) => ubahRencana(i, { alur: e.target.value || null })}>
                    <option value="">— alur default kelas —</option>
                    {tplOptions.map((t) => (
                      <option key={t.id} value={t.nama}>{t.nama}</option>
                    ))}
                  </select>
                  {r.meeting_id ? <span className="badge">✓ pertemuan dibuat</span> : <span className="badge badge-off">belum dibuat</span>}
                  <button className="btn btn-sm btn-danger" onClick={() => setRencana((prev) => prev.filter((_, j) => j !== i))}>✕</button>
                </div>
                <input className="input" style={{ marginTop: 8 }} value={r.tujuan} onChange={(e) => ubahRencana(i, { tujuan: e.target.value })} placeholder="Tujuan pertemuan (1 kalimat)" />
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10, marginTop: 8 }}>
                  <input className="input" value={r.konsep.join(", ")} onChange={(e) => ubahRencana(i, { konsep: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} placeholder="Konsep kunci, pisahkan koma" />
                  <input className="input" value={r.aktivitas.join(", ")} onChange={(e) => ubahRencana(i, { aktivitas: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} placeholder="Aktivitas, pisahkan koma (studi kasus, diskusi, ...)" />
                </div>
              </div>
            ))}
            {rencana.length === 0 && <p className="muted" style={{ marginTop: 8 }}>Belum ada rencana. Susun dengan AI di atas, atau tambah baris manual.</p>}
            <div className="row-actions" style={{ marginTop: 12 }}>
              <button className="btn" onClick={() => setRencana((prev) => [...prev, { judul: "", tujuan: "", konsep: [], aktivitas: [], alur: null, meeting_id: null }])}>➕ Baris Manual</button>
              <button className="btn btn-primary" onClick={simpanRencana} disabled={rencana.length === 0}>💾 Simpan Rencana</button>
              <button className="btn" onClick={terapkanRencana} disabled={rencana.length === 0}>🏗️ Buat Pertemuan dari Rencana</button>
            </div>
          </div>
        </>
      )}

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
                <div style={{ width: `${progress.ringkasan.persen_total}%`, background: "var(--primary)", height: "100%", borderRadius: 8 }} />
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
            {kelompokkanDokumen(m).map((row) => {
              const hrefUtama = row.material ? `/materi/${row.material.id}` : `/kuis/${row.quizzes[0].id}`;
              const semuaDiBank =
                (row.material ? row.material.di_bank : true) &&
                row.quizzes.every((q) => q.di_bank);
              return (
                <div key={row.kunci} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)", gap: 8, flexWrap: "wrap" }}>
                  <span>
                    <Link href={hrefUtama}>📄 {row.judul}</Link>{" "}
                    {row.material && <span className="badge">📖 Materi</span>}{" "}
                    {row.quizzes.map((q) => (
                      <span key={q.id} className="badge">
                        {q.tipe === "pilihan_ganda" ? `🧪 Kuis PG · ${q.jumlah_soal} soal` : `📝 Esai · ${q.jumlah_soal} soal`}
                      </span>
                    ))}{" "}
                    {row.jenis === "tugas" && <span className="badge">📝 Tugas</span>}
                    {row.jenis === "ujian" && <span className="badge">🏆 Ujian</span>}
                    {row.jenis === "kuis" && row.material && <span className="badge">🧪 Kuis</span>}
                    {row.material && row.material.jumlah_file > 0 && (
                      <span className="muted"> 📎 {row.material.jumlah_file}</span>
                    )}
                  </span>
                  {kelola && (
                    <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {row.grup ? (
                        <>
                          <Link className="btn btn-sm" href={`/editor/dokumen?grup=${row.grup}&kelas=${sid}`}>✏️ Edit</Link>
                          {!semuaDiBank && (
                            <button className="btn btn-sm" onClick={() => saveDocumentBank(row)}>📚 Simpan ke Bank</button>
                          )}
                          <button className="btn btn-sm btn-danger" onClick={() => deleteDocumentRow(row)}>🗑️ Hapus</button>
                        </>
                      ) : row.material ? (
                        <>
                          <Link className="btn btn-sm" href={`/editor/materi?material=${row.material.id}`}>✏️ Edit</Link>
                          {!row.material.di_bank && (
                            <button className="btn btn-sm" onClick={() => saveMaterialBank(row.material!)}>📚 Simpan ke Bank</button>
                          )}
                          <button className="btn btn-sm btn-danger" onClick={() => deleteMaterialRow(row.material!)}>🗑️ Hapus</button>
                        </>
                      ) : (
                        <>
                          <Link className="btn btn-sm" href={`/editor/kuis?quiz=${row.quizzes[0].id}&subject=${sid}&meeting=${m.id}`}>✏️ Edit</Link>
                          {!row.quizzes[0].di_bank && (
                            <button className="btn btn-sm" onClick={() => saveQuizBank(row.quizzes[0])}>📚 Simpan ke Bank</button>
                          )}
                          <button className="btn btn-sm btn-danger" onClick={() => deleteQuizRow(row.quizzes[0])}>🗑️ Hapus</button>
                        </>
                      )}
                    </span>
                  )}
                </div>
              );
            })}
            {m.materials.length === 0 && m.quizzes.length === 0 && (
              <p className="muted">Belum ada konten. Tambahkan lewat tombol ➕ Konten Baru di bawah.</p>
            )}
          </div>
          {kelola && (
            <div style={{ marginTop: 12 }}>
              <div className="row-actions">
                <Link className="btn btn-sm btn-primary" href={`/editor/dokumen?meeting=${m.id}&kelas=${sid}`}>➕ Konten Baru</Link>
                <Link className="btn btn-sm" href={`/generate?subject=${sid}&meeting=${m.id}&jenis=dokumen&topik=${encodeURIComponent(m.rencana?.tujuan ? `${m.judul} — ${m.rencana.tujuan}` : m.judul)}`}>
                  {m.rencana ? "✨ Generate dari Rencana" : "✨ Generate AI"}
                </Link>
                <button className="btn btn-sm" onClick={() => openBank(m.id)}>📚 Ambil dari Bank</button>
                <button className="btn btn-sm" onClick={() => openCompose(m.id)}>🎲 Susun dari Bank Soal</button>
              </div>
              {bankFor === m.id && (
                <div style={{ marginTop: 10 }} className="card">
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
                    <input
                      className="input"
                      style={{ maxWidth: 220 }}
                      placeholder="Cari judul dokumen..."
                      value={bankCari}
                      onChange={(e) => setBankCari(e.target.value)}
                    />
                    <select className="select" style={{ maxWidth: 180 }} value={bankFilterTag} onChange={(e) => setBankFilterTag(e.target.value)}>
                      <option value="">Semua tag</option>
                      <option value="materi">📖 Materi</option>
                      <option value="kuis_pg">🧪 Kuis PG</option>
                      <option value="esai">📝 Esai</option>
                    </select>
                    <select className="select" style={{ maxWidth: 200 }} value={bankFilterKategori} onChange={(e) => setBankFilterKategori(e.target.value)}>
                      <option value="">Semua kategori</option>
                      {bankKategori.map((c) => (
                        <option key={c.id} value={c.id}>{c.nama}</option>
                      ))}
                    </select>
                  </div>
                  {bankDokumenRows().length === 0 && (
                    <p className="muted">Tidak ada dokumen bank yang cocok (bank Anda mungkin masih kosong).</p>
                  )}
                  {bankDokumenRows().map((b) => (
                    <div key={b.kunci} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", gap: 8, flexWrap: "wrap" }}>
                      <span>
                        {b.judul}{" "}
                        {b.material && <span className="badge">📖 Materi</span>}{" "}
                        {b.quizzes.map((q) => (
                          <span key={q.id} className="badge">
                            {q.tipe === "pilihan_ganda" ? `🧪 PG · ${q.jumlah_soal} soal` : `📝 Esai · ${q.jumlah_soal} soal`}
                          </span>
                        ))}{" "}
                        {b.kategori_id && (
                          <span className="muted">
                            · {bankKategori.find((c) => c.id === b.kategori_id)?.nama ?? "kategori"}
                          </span>
                        )}
                      </span>
                      <button
                        className="btn btn-sm"
                        onClick={() =>
                          b.grup
                            ? useBankDocument(m.id, b.grup)
                            : b.material
                              ? useBank(m.id, b.material.id)
                              : useBankQuiz(m.id, b.quizzes[0].id)
                        }
                      >
                        Pakai
                      </button>
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
        <form className="card" onSubmit={createStudentInClass} style={{ marginTop: 16, borderLeft: "5px solid var(--primary)" }}>
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
