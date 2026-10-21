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

/* ============================================================ model blok */
type RootJenis = "MATERIAL" | "EXERCISE" | "PROJECT";
type JenisBlok =
  | "judul" | "heading" | "paragraf" | "catatan" | "peringatan" | "ringkasan"
  | "contoh" | "tujuan" | "deskripsi" | "luaran" | "petunjuk" | "harapan"
  | "rumus" | "kode" | "blok-scratch" | "scratch"
  | "langkah" | "tugas" | "syarat" | "rubrik" | "tabel" | "sprite"
  | "cek-pg" | "cek-esai";

interface Blok {
  id: number;
  jenis: JenisBlok;
  teks?: string;
  items?: string[];
  baris?: string[][];
  nama?: string;
  deskripsi?: string;
  pertanyaan?: string;
  opsi?: { teks: string; benar: boolean }[];
  referensi?: string;
  bobot?: string;
}

const BLOK_META: Record<JenisBlok, { label: string; ikon: string }> = {
  judul: { label: "Judul", ikon: "🏷️" },
  heading: { label: "Judul Bagian", ikon: "🔖" },
  paragraf: { label: "Paragraf", ikon: "📄" },
  catatan: { label: "Catatan", ikon: "📝" },
  peringatan: { label: "Peringatan", ikon: "⚠️" },
  ringkasan: { label: "Ringkasan", ikon: "📌" },
  contoh: { label: "Contoh", ikon: "💡" },
  tujuan: { label: "Tujuan", ikon: "🎯" },
  deskripsi: { label: "Deskripsi Proyek", ikon: "📋" },
  luaran: { label: "Luaran / Output", ikon: "📦" },
  petunjuk: { label: "Petunjuk", ikon: "🧭" },
  harapan: { label: "Hasil Diharapkan", ikon: "✅" },
  rumus: { label: "Rumus", ikon: "🧮" },
  kode: { label: "Kode", ikon: "💻" },
  "blok-scratch": { label: "Blok Scratch (teks)", ikon: "🧱" },
  scratch: { label: "Proyek Scratch", ikon: "🐱" },
  langkah: { label: "Langkah-langkah", ikon: "👣" },
  tugas: { label: "Daftar Tugas", ikon: "✏️" },
  syarat: { label: "Syarat Proyek", ikon: "📜" },
  rubrik: { label: "Rubrik Penilaian", ikon: "📊" },
  tabel: { label: "Tabel Data", ikon: "📋" },
  sprite: { label: "Kartu Sprite", ikon: "👾" },
  "cek-pg": { label: "Cek Pemahaman — Pilihan Ganda", ikon: "🧠" },
  "cek-esai": { label: "Cek Pemahaman — Esai", ikon: "🧠" },
};

const BLOK_PER_ROOT: Record<RootJenis, JenisBlok[]> = {
  MATERIAL: [
    "judul", "heading", "paragraf", "catatan", "peringatan", "ringkasan",
    "contoh", "tujuan", "langkah", "tabel", "rumus", "kode",
    "scratch", "sprite", "blok-scratch", "cek-pg", "cek-esai",
  ],
  EXERCISE: [
    "judul", "heading", "paragraf", "catatan", "peringatan",
    "tugas", "langkah", "petunjuk", "harapan", "cek-pg", "cek-esai",
  ],
  PROJECT: [
    "judul", "deskripsi", "paragraf", "catatan", "syarat", "luaran",
    "rubrik", "langkah", "scratch", "sprite", "blok-scratch", "cek-pg", "cek-esai",
  ],
};

const TAG_TEKS: Partial<Record<JenisBlok, string>> = {
  judul: "TITLE", heading: "HEADING", paragraf: "PARAGRAPH", catatan: "NOTE",
  peringatan: "WARNING", ringkasan: "SUMMARY", contoh: "EXAMPLE", tujuan: "OBJECTIVE",
  deskripsi: "DESCRIPTION", luaran: "OUTPUT", petunjuk: "HINT", harapan: "EXPECTED",
  rumus: "FORMULA", kode: "CODE", "blok-scratch": "BLOCKS",
};
const TAG_WADAH: Partial<Record<JenisBlok, [string, string]>> = {
  langkah: ["STEPS", "STEP"],
  tugas: ["TASKS", "TASK"],
  syarat: ["REQUIREMENTS", "REQUIREMENT"],
  rubrik: ["RUBRIC", "CRITERIA"],
};
const LABEL_ITEM: Partial<Record<JenisBlok, string>> = {
  langkah: "Langkah", tugas: "Tugas", syarat: "Syarat", rubrik: "Kriteria",
};

function susunBlok(b: Blok): string {
  if (b.jenis === "cek-pg") {
    const opsi = (b.opsi ?? []).map((o, i) => `${String.fromCharCode(65 + i)}. ${o.teks}`).join("\n");
    const kunci = (b.opsi ?? []).map((o, i) => (o.benar ? String.fromCharCode(65 + i) : "")).filter(Boolean).join(", ");
    const bobot = b.bobot && b.bobot !== "1" ? `\n[WEIGHT]${b.bobot}[/WEIGHT]` : "";
    return `[CEK]\n[QUESTION]${(b.pertanyaan ?? "").trim()}[/QUESTION]\n[OPTIONS]\n${opsi}\n[/OPTIONS]\n[ANSWER]${kunci}[/ANSWER]${bobot}\n[/CEK]`;
  }
  if (b.jenis === "cek-esai") {
    const bobot = b.bobot && b.bobot !== "1" ? `\n[WEIGHT]${b.bobot}[/WEIGHT]` : "";
    return `[CEK]\n[TYPE]essay[/TYPE]\n[QUESTION]${(b.pertanyaan ?? "").trim()}[/QUESTION]\n[ANSWER]${(b.referensi ?? "").trim()}[/ANSWER]${bobot}\n[/CEK]`;
  }
  if (b.jenis === "tabel") {
    const isi = (b.baris ?? []).map((r) => r.join(" | ")).join("\n");
    return `[DATASET]\n[TABLE]\n${isi}\n[/TABLE]\n[/DATASET]`;
  }
  if (b.jenis === "sprite") {
    return `[SPRITE]\n${b.nama ?? ""}${b.deskripsi ? `\n${b.deskripsi}` : ""}\n[/SPRITE]`;
  }
  if (b.jenis === "scratch") {
    return `[SCRATCH]${(b.teks ?? "").trim()}[/SCRATCH]`;
  }
  const wadah = TAG_WADAH[b.jenis];
  if (wadah) {
    const [luar, dalam] = wadah;
    const isi = (b.items ?? []).map((i) => `[${dalam}]${i}[/${dalam}]`).join("\n");
    return `[${luar}]\n${isi}\n[/${luar}]`;
  }
  const tag = TAG_TEKS[b.jenis] ?? "PARAGRAPH";
  if (b.jenis === "judul" || b.jenis === "heading") {
    return `[${tag}]${(b.teks ?? "").trim()}[/${tag}]`;
  }
  return `[${tag}]\n${b.teks ?? ""}\n[/${tag}]`;
}

function susunTeks(root: RootJenis, blocks: Blok[]): string {
  return `[${root}]\n${blocks.map(susunBlok).join("\n")}\n[/${root}]`;
}

function blokBaru(jenis: JenisBlok, id: number): Blok {
  switch (jenis) {
    case "langkah": case "tugas": case "syarat": case "rubrik":
      return { id, jenis, items: [""] };
    case "tabel":
      return { id, jenis, baris: [["Kolom 1", "Kolom 2"], ["", ""]] };
    case "sprite":
      return { id, jenis, nama: "", deskripsi: "" };
    case "cek-pg":
      return { id, jenis, pertanyaan: "", opsi: [{ teks: "", benar: true }, { teks: "", benar: false }], bobot: "1" };
    case "cek-esai":
      return { id, jenis, pertanyaan: "", referensi: "", bobot: "1" };
    default:
      return { id, jenis, teks: "" };
  }
}

/* ============================================================ template */
const CONTOH = `[MATERIAL]
[TITLE]Judul Materi[/TITLE]
[PARAGRAPH]
Tulis isi materi di sini.
[/PARAGRAPH]
[NOTE]Catatan penting untuk siswa.[/NOTE]
[/MATERIAL]`;

const TEMPLATES: { nama: string; judul: string; teks: string }[] = [
  { nama: "📖 Materi Biasa", judul: "Materi Baru", teks: CONTOH },
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

/* ============================================================ sisipan TCML */
const SISIPAN: { label: string; teks: string; tandai: string }[] = [
  { label: "Judul Bagian", teks: "[HEADING]Judul bagian[/HEADING]", tandai: "Judul bagian" },
  { label: "Catatan", teks: "[NOTE]Isi catatan[/NOTE]", tandai: "Isi catatan" },
  { label: "Peringatan", teks: "[WARNING]Isi peringatan[/WARNING]", tandai: "Isi peringatan" },
  { label: "Ringkasan", teks: "[SUMMARY]Isi ringkasan[/SUMMARY]", tandai: "Isi ringkasan" },
  { label: "Contoh", teks: "[EXAMPLE]Isi contoh[/EXAMPLE]", tandai: "Isi contoh" },
  { label: "Tujuan", teks: "[OBJECTIVE]Tujuan pembelajaran[/OBJECTIVE]", tandai: "Tujuan pembelajaran" },
  { label: "Langkah", teks: "[STEPS]\n[STEP]Langkah pertama[/STEP]\n[STEP]Langkah kedua[/STEP]\n[/STEPS]", tandai: "Langkah pertama" },
  { label: "Daftar Tugas", teks: "[TASKS]\n[TASK]Tugas pertama[/TASK]\n[TASK]Tugas kedua[/TASK]\n[/TASKS]", tandai: "Tugas pertama" },
  { label: "Petunjuk", teks: "[HINT]Isi petunjuk[/HINT]", tandai: "Isi petunjuk" },
  { label: "Hasil Diharapkan", teks: "[EXPECTED]Hasil yang diharapkan[/EXPECTED]", tandai: "Hasil yang diharapkan" },
  { label: "Deskripsi Proyek", teks: "[DESCRIPTION]Deskripsi proyek[/DESCRIPTION]", tandai: "Deskripsi proyek" },
  { label: "Syarat Proyek", teks: "[REQUIREMENTS]\n[REQUIREMENT]Syarat pertama[/REQUIREMENT]\n[/REQUIREMENTS]", tandai: "Syarat pertama" },
  { label: "Luaran", teks: "[OUTPUT]Luaran yang dikumpulkan[/OUTPUT]", tandai: "Luaran yang dikumpulkan" },
  { label: "Rubrik", teks: "[RUBRIC]\n[CRITERIA]Kriteria — 50 poin[/CRITERIA]\n[/RUBRIC]", tandai: "Kriteria" },
  { label: "Cek Pemahaman PG", teks: "[CEK]\n[QUESTION]Pertanyaannya?[/QUESTION]\n[OPTIONS]\nA. Pilihan A\nB. Pilihan B\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/CEK]", tandai: "Pertanyaannya?" },
  { label: "Cek Pemahaman Esai", teks: "[CEK]\n[TYPE]essay[/TYPE]\n[QUESTION]Pertanyaannya?[/QUESTION]\n[ANSWER]Jawaban referensinya.[/ANSWER]\n[/CEK]", tandai: "Pertanyaannya?" },
  { label: "Tabel", teks: "[DATASET]\n[TABLE]\nKolom 1 | Kolom 2\nIsi 1 | Isi 2\n[/TABLE]\n[/DATASET]", tandai: "Kolom 1" },
  { label: "Rumus", teks: "[FORMULA]\nrumus di sini\n[/FORMULA]", tandai: "rumus di sini" },
  { label: "Kode", teks: "[CODE]\nkode di sini\n[/CODE]", tandai: "kode di sini" },
  { label: "Scratch", teks: "[SCRATCH]id-proyek[/SCRATCH]", tandai: "id-proyek" },
  { label: "Sprite", teks: "[SPRITE]\nNama Sprite\nDeskripsi sprite.\n[/SPRITE]", tandai: "Nama Sprite" },
  { label: "Blok Scratch", teks: "[BLOCKS]\nwhen green flag clicked\n[/BLOCKS]", tandai: "when green flag clicked" },
];

interface StrukturResp {
  success: boolean;
  root: RootJenis | null;
  blocks: Omit<Blok, "id">[];
  bisa_formulir: boolean;
  alasan: string | null;
  errors: TcmlError[];
}
interface PackRingkas {
  id: number;
  nama: string;
  punya_saya: boolean;
  pemilik: { username: string; nama_lengkap: string | null } | null;
}
interface SettingRingkas {
  id: number;
  nama: string;
  model: string | null;
  is_default: boolean;
}
interface DrafAI {
  id: number;
  judul: string;
  teks_mentah: string;
  is_valid: boolean;
  errors: unknown[];
}

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
  const [teks, setTeks] = useState("");
  const [subjectId, setSubjectId] = useState<string | null>(kelasParam);
  const [previewHtml, setPreviewHtml] = useState("");
  const [errors, setErrors] = useState<TcmlError[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [kategoriId, setKategoriId] = useState<string>("");

  // Mode Blok
  const [editorMode, setEditorMode] = useState<"blok" | "tcml">("blok");
  const [rootJenis, setRootJenis] = useState<RootJenis>("MATERIAL");
  const [blocks, setBlocks] = useState<Blok[]>([]);
  const [modeNotice, setModeNotice] = useState("");
  const idBerikut = useRef(1);

  // Autosave
  const [baseline, setBaseline] = useState<{ judul: string; teks: string; kategoriId: string } | null>(null);
  const [restoreDraft, setRestoreDraft] = useState<{ judul: string; teks: string; kategoriId: string; ts: number } | null>(null);
  const draftKey = `lifunze-draf-materi:${
    materialParam ? `m${materialParam}` : bankParam ? `b${bankParam}` : meetingParam ? `p${meetingParam}` : mode === "bank" ? "bank-baru" : "baru"
  }`;

  // Panel AI
  const [aiOpen, setAiOpen] = useState(false);
  const [aiPacks, setAiPacks] = useState<PackRingkas[]>([]);
  const [aiSettings, setAiSettings] = useState<SettingRingkas[]>([]);
  const [aiPack, setAiPack] = useState("");
  const [aiSetting, setAiSetting] = useState("");
  const [aiTopik, setAiTopik] = useState("");
  const [aiInstruksi, setAiInstruksi] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiMsg, setAiMsg] = useState("");
  const aiDimuat = useRef(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

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

  function onTeksChange(v: string) {
    setTeks(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runPreview(v), 600);
  }

  /* ---- Mode Blok: terapkan daftar blok -> susun teks + pratinjau ---- */
  function terapkanBlok(next: Blok[], root: RootJenis = rootJenis) {
    setBlocks(next);
    onTeksChange(susunTeks(root, next));
  }

  const strukturkan = useCallback(
    async (teksStr: string, diam = false): Promise<boolean> => {
      try {
        const r = await apiFetch<StrukturResp>("/api/v1/parse/structure", {
          method: "POST",
          body: { teks: teksStr },
        });
        if (r.success && r.bisa_formulir && r.root) {
          setBlocks(r.blocks.map((b) => ({ ...b, bobot: b.bobot != null ? String(b.bobot) : undefined, id: idBerikut.current++ })));
          setRootJenis(r.root);
          setEditorMode("blok");
          setModeNotice("");
          return true;
        }
        if (!diam) {
          setModeNotice(
            (r.alasan ?? "Dokumen ini belum bisa dibuka di Mode Blok.") +
              " Anda tetap bisa mengeditnya di Mode TCML.",
          );
        }
        setEditorMode("tcml");
        return false;
      } catch {
        if (!diam) setModeNotice("Gagal memeriksa struktur dokumen — tetap di Mode TCML.");
        setEditorMode("tcml");
        return false;
      }
    },
    [],
  );

  /* ---- muat awal ---- */
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

      let judulAwal = "";
      let teksAwal = "";
      let kategoriAwal = "";
      try {
        if (materialParam) {
          const m = await apiFetch<{ judul: string; teks_mentah: string; subject_id: number | null }>(
            `/api/v1/materials/${materialParam}`,
          );
          judulAwal = m.judul;
          teksAwal = m.teks_mentah;
          if (m.subject_id) setSubjectId(String(m.subject_id));
        } else if (bankParam) {
          const s = await apiFetch<{ judul: string; teks_mentah: string; kategori_id: number | null }>(
            `/api/v1/bank/materials/${bankParam}`,
          );
          judulAwal = s.judul;
          teksAwal = s.teks_mentah;
          kategoriAwal = s.kategori_id ? String(s.kategori_id) : "";
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat konten.");
      }

      if (materialParam || bankParam) {
        setJudul(judulAwal);
        setTeks(teksAwal);
        setKategoriId(kategoriAwal);
        runPreview(teksAwal);
        await strukturkan(teksAwal, true);
        setBaseline({ judul: judulAwal, teks: teksAwal, kategoriId: kategoriAwal });
      } else {
        // Dokumen baru: mulai dari Mode Blok.
        const awal: Blok[] =
          mode === "bank"
            ? [
                { id: idBerikut.current++, jenis: "judul", teks: "Judul Materi" },
                { id: idBerikut.current++, jenis: "paragraf", teks: "Tulis isi materi di sini." },
                { id: idBerikut.current++, jenis: "catatan", teks: "Catatan penting untuk siswa." },
              ]
            : [
                { id: idBerikut.current++, jenis: "judul", teks: "" },
                { id: idBerikut.current++, jenis: "paragraf", teks: "" },
              ];
        const teksSusun = susunTeks("MATERIAL", awal);
        setBlocks(awal);
        setRootJenis("MATERIAL");
        setEditorMode("blok");
        setTeks(teksSusun);
        setBaseline({ judul: "", teks: teksSusun, kategoriId: "" });
      }

      // Tawaran pulihkan draf lokal yang belum tersimpan.
      try {
        const mentah = localStorage.getItem(draftKey);
        if (mentah) {
          const d = JSON.parse(mentah) as { judul: string; teks: string; kategoriId: string; ts: number };
          if (d.teks !== teksAwal || d.judul !== judulAwal) setRestoreDraft(d);
        }
      } catch { /* abaikan */ }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, materialParam, bankParam]);

  /* ---- autosave + peringatan belum tersimpan ---- */
  const kotor =
    baseline !== null &&
    (judul !== baseline.judul || teks !== baseline.teks || kategoriId !== baseline.kategoriId);
  const kotorRef = useRef(false);
  useEffect(() => {
    kotorRef.current = kotor;
  }, [kotor]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (kotorRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);
  useEffect(() => {
    if (!baseline || !kotor) return;
    const t = setTimeout(() => {
      try {
        localStorage.setItem(draftKey, JSON.stringify({ judul, teks, kategoriId, ts: Date.now() }));
      } catch { /* abaikan */ }
    }, 800);
    return () => clearTimeout(t);
  }, [judul, teks, kategoriId, kotor, baseline, draftKey]);

  function pulihkanDraf() {
    if (!restoreDraft) return;
    setJudul(restoreDraft.judul);
    setKategoriId(restoreDraft.kategoriId);
    onTeksChange(restoreDraft.teks);
    void strukturkan(restoreDraft.teks, true);
    setRestoreDraft(null);
    setOk("Draf yang belum tersimpan dipulihkan.");
  }
  function buangDraf() {
    try {
      localStorage.removeItem(draftKey);
    } catch { /* abaikan */ }
    setRestoreDraft(null);
  }

  /* ---- Judul <-> [TITLE] ---- */
  const cocokTitle = teks.match(/\[TITLE\]([\s\S]*?)\[\/TITLE\]/i);
  const titleDalam = cocokTitle ? cocokTitle[1].trim() : null;
  const judulBeda = !!titleDalam && !!judul.trim() && titleDalam !== judul.trim();
  const tanpaTitle = !titleDalam && /\[(MATERIAL|EXERCISE|PROJECT)\]/.test(teks);

  function tulisTitleKeDokumen() {
    if (editorMode === "blok") {
      const ada = blocks.some((b) => b.jenis === "judul");
      const next = ada
        ? blocks.map((b) => (b.jenis === "judul" ? { ...b, teks: judul } : b))
        : [{ id: idBerikut.current++, jenis: "judul" as JenisBlok, teks: judul }, ...blocks];
      terapkanBlok(next);
    } else {
      const baru = cocokTitle
        ? teks.replace(/\[TITLE\][\s\S]*?\[\/TITLE\]/i, `[TITLE]${judul}[/TITLE]`)
        : teks.replace(/\[(MATERIAL|EXERCISE|PROJECT)\]/, (m) => `${m}\n[TITLE]${judul}[/TITLE]`);
      onTeksChange(baru);
    }
  }

  /* ---- sisip blok di Mode TCML ---- */
  function sisip(s: (typeof SISIPAN)[number]) {
    const el = taRef.current;
    const start = el ? el.selectionStart : teks.length;
    const end = el ? el.selectionEnd : teks.length;
    const sebelum = teks.slice(0, start);
    const sesudah = teks.slice(end);
    const awalan = sebelum && !sebelum.endsWith("\n") ? "\n" : "";
    onTeksChange(sebelum + awalan + s.teks + "\n" + sesudah);
    requestAnimationFrame(() => {
      const el2 = taRef.current;
      if (!el2) return;
      el2.focus();
      const dasar = start + awalan.length;
      const i = s.teks.indexOf(s.tandai);
      el2.setSelectionRange(dasar + i, dasar + i + s.tandai.length);
    });
  }

  /* ---- simpan ---- */
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
          tandaiBersih();
          setTimeout(() => router.push("/bank"), 700);
          return;
        }
      } else if (materialParam) {
        const m = await apiFetch<{ id: number }>(`/api/v1/materials/${materialParam}`, {
          method: "PATCH",
          body: { judul, teks_mentah: teks },
        });
        tandaiBersih();
        router.push(`/materi/${m.id}`);
        return;
      } else if (meetingParam) {
        const m = await apiFetch<{ id: number }>(`/api/v1/meetings/${meetingParam}/materials`, {
          method: "POST",
          body: { judul, teks_mentah: teks },
        });
        tandaiBersih();
        router.push(`/materi/${m.id}`);
        return;
      }
      tandaiBersih();
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

  function tandaiBersih() {
    setBaseline({ judul, teks, kategoriId });
    try {
      localStorage.removeItem(draftKey);
    } catch { /* abaikan */ }
  }

  async function saveToBank() {
    setError("");
    setOk("");
    try {
      if (materialParam) {
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

  /* ---- template ---- */
  async function pakaiTemplate(t: (typeof TEMPLATES)[number]) {
    const perluKonfirmasi =
      teks.trim() !== "" && (kotor || materialParam || bankParam);
    if (perluKonfirmasi && !window.confirm(`Ganti isi editor dengan template "${t.nama}"?`)) return;
    if (!judul.trim()) setJudul(t.judul);
    onTeksChange(t.teks);
    await strukturkan(t.teks, true);
  }

  /* ---- Panel AI ---- */
  async function bukaAi() {
    const next = !aiOpen;
    setAiOpen(next);
    if (next && !aiDimuat.current) {
      aiDimuat.current = true;
      try {
        const mine = await apiFetch<PackRingkas[]>("/api/v1/packs");
        const shared = await apiFetch<PackRingkas[]>("/api/v1/packs/shared");
        setAiPacks([...mine, ...shared]);
        setAiSettings(await apiFetch<SettingRingkas[]>("/api/v1/ai/settings"));
      } catch { /* panel menampilkan pesan kosong */ }
    }
    if (next && !aiTopik && judul.trim()) setAiTopik(judul);
  }

  async function generateAi() {
    if (!aiPack) {
      setAiMsg("Pilih paket parser dulu.");
      return;
    }
    if (!aiTopik.trim()) {
      setAiMsg("Isi topiknya dulu.");
      return;
    }
    setAiBusy(true);
    setAiMsg("");
    try {
      const res = await apiFetch<{ drafts: DrafAI[] }>("/api/v1/generate", {
        method: "POST",
        body: {
          kind: "materi",
          pack_id: Number(aiPack),
          ai_setting_id: aiSetting ? Number(aiSetting) : null,
          brief: { topik: aiTopik, instruksi: aiInstruksi || undefined },
        },
      });
      const d = res.drafts[0];
      if (!d) {
        setAiMsg("AI tidak menghasilkan dokumen.");
        return;
      }
      if (!d.is_valid) {
        setAiMsg(
          `Hasil AI belum valid (${d.errors.length} error). Drafnya tersimpan di menu Generate AI — bisa diperbaiki di sana.`,
        );
        return;
      }
      if (teks.trim() && kotor && !window.confirm("Ganti isi editor dengan hasil AI?")) return;
      if (!judul.trim()) setJudul(d.judul);
      onTeksChange(d.teks_mentah);
      await strukturkan(d.teks_mentah, true);
      setAiMsg("Hasil AI dimasukkan ke editor — tinjau & sesuaikan, lalu klik Simpan Materi.");
    } catch (err) {
      setAiMsg(err instanceof Error ? err.message : "Generate gagal.");
    } finally {
      setAiBusy(false);
    }
  }

  /* ---- operasi blok ---- */
  function ubahBlok(id: number, patch: Partial<Blok>) {
    terapkanBlok(blocks.map((b) => (b.id === id ? { ...b, ...patch } : b)));
  }
  function pindahBlok(id: number, arah: -1 | 1) {
    const i = blocks.findIndex((b) => b.id === id);
    const j = i + arah;
    if (i < 0 || j < 0 || j >= blocks.length) return;
    const next = [...blocks];
    [next[i], next[j]] = [next[j], next[i]];
    terapkanBlok(next);
  }
  function gantiRoot(root: RootJenis) {
    if (root === rootJenis) return;
    const dibuang = blocks.filter(
      (b) => !BLOK_PER_ROOT[root].includes(b.jenis),
    );
    if (
      dibuang.length > 0 &&
      !window.confirm(
        `${dibuang.length} blok tidak dikenal di dokumen ${root === "MATERIAL" ? "Materi" : root === "EXERCISE" ? "Latihan" : "Proyek"} dan akan dibuang. Lanjutkan?`,
      )
    ) {
      return;
    }
    const next = blocks.filter((b) => BLOK_PER_ROOT[root].includes(b.jenis));
    setRootJenis(root);
    terapkanBlok(next, root);
  }

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  const adaJudul = blocks.some((b) => b.jenis === "judul");

  return (
    <main className="page" style={{ maxWidth: 1200 }}>
      <AppHeader user={user} />
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: "1.4rem" }}>
          {mode === "bank" ? "📚 Editor Materi Bank" : "✏️ Editor Materi"}
        </h1>
        {subjectId && <Link href={`/kelas/${subjectId}`}>← Kembali ke Kelas</Link>}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}
      {restoreDraft && (
        <div className="alert" style={{ background: "#fff7e0", border: "1px solid var(--amber)" }}>
          💾 Ada draf belum tersimpan dari{" "}
          {new Date(restoreDraft.ts).toLocaleString("id-ID")}.{" "}
          <button className="btn btn-sm btn-primary" onClick={pulihkanDraf}>Pulihkan</button>{" "}
          <button className="btn btn-sm" onClick={buangDraf}>Buang</button>
        </div>
      )}

      <label className="label">Judul materi</label>
      <input className="input" value={judul} onChange={(e) => setJudul(e.target.value)} placeholder="mis. Pecahan Dasar" />
      {judulBeda && (
        <p className="muted" style={{ marginTop: 6 }}>
          Judul di dalam dokumen: <strong>"{titleDalam}"</strong> — berbeda dari judul materi.{" "}
          <button className="btn btn-sm" onClick={() => setJudul(titleDalam ?? "")}>Pakai judul dokumen</button>{" "}
          <button className="btn btn-sm" onClick={tulisTitleKeDokumen}>Tulis judul materi ke dokumen</button>
        </p>
      )}
      {tanpaTitle && (
        <p className="muted" style={{ marginTop: 6 }}>
          Dokumen ini belum punya [TITLE].{" "}
          <button className="btn btn-sm" onClick={tulisTitleKeDokumen} disabled={!judul.trim()}>
            Tambahkan dari judul materi
          </button>
        </p>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12, alignItems: "center" }}>
        <div className="seg-toggle" role="tablist" aria-label="Mode editor">
          <button className={editorMode === "blok" ? "on" : ""} onClick={() => void strukturkan(teks)}>
            🧩 Mode Blok
          </button>
          <button className={editorMode === "tcml" ? "on" : ""} onClick={() => setEditorMode("tcml")}>
            {"</>"} Mode TCML
          </button>
        </div>
        <button className="btn btn-sm" onClick={bukaAi}>
          ✨ Buat dengan AI
        </button>
        <span className="muted">
          {editorMode === "blok"
            ? "Susun materi dari blok-blok — tanpa menulis kode TCML."
            : "Tulis TCML langsung (mode ahli)."}
        </span>
      </div>
      {modeNotice && <div className="alert" style={{ marginTop: 10 }}>{modeNotice}</div>}

      {aiOpen && (
        <div className="card" style={{ marginTop: 12 }}>
          <h3>✨ Buat dengan AI</h3>
          <p className="muted" style={{ margin: "6px 0 10px" }}>
            AI menulis draf materi memakai paket parser & pengaturan AI Anda; hasilnya masuk ke
            editor untuk ditinjau dan diubah dulu — belum tersimpan sebelum Anda klik Simpan Materi.
          </p>
          {aiSettings.length === 0 && (
            <p className="muted">
              Belum ada Pengaturan AI. <Link href="/pengaturan-ai">Buat dulu</Link> (base URL, API key, model).
            </p>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
            <div>
              <label className="label">Paket parser</label>
              <select className="select" value={aiPack} onChange={(e) => setAiPack(e.target.value)}>
                <option value="">— pilih paket —</option>
                {aiPacks.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nama}{p.punya_saya ? "" : ` (dari ${p.pemilik?.nama_lengkap ?? p.pemilik?.username})`}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Pengaturan AI</label>
              <select className="select" value={aiSetting} onChange={(e) => setAiSetting(e.target.value)}>
                <option value="">Otomatis (default saya)</option>
                {aiSettings.map((s) => (
                  <option key={s.id} value={s.id}>{s.nama} — {s.model ?? "?"}{s.is_default ? " (default)" : ""}</option>
                ))}
              </select>
            </div>
          </div>
          <label className="label">Topik</label>
          <input className="input" value={aiTopik} onChange={(e) => setAiTopik(e.target.value)} placeholder="mis. Pecahan senilai dan cara menyederhanakannya" />
          <label className="label">Instruksi tambahan (opsional)</label>
          <textarea className="textarea" rows={2} value={aiInstruksi} onChange={(e) => setAiInstruksi(e.target.value)} placeholder="mis. Sertakan 1 contoh soal cerita dan 1 catatan pengingat" />
          {aiMsg && <p className="muted" style={{ marginTop: 8 }}>{aiMsg}</p>}
          <button className="btn btn-primary" onClick={generateAi} disabled={aiBusy || aiSettings.length === 0} style={{ marginTop: 10 }}>
            {aiBusy ? "⏳ AI sedang menulis..." : "✨ Tulis Materi"}
          </button>
        </div>
      )}

      <p style={{ marginTop: 12 }}>
        <span className="muted">Mulai dari template: </span>
        {TEMPLATES.map((t) => (
          <button
            key={t.nama}
            className="btn btn-sm"
            style={{ marginRight: 6, marginBottom: 6 }}
            onClick={() => void pakaiTemplate(t)}
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
          {editorMode === "blok" ? (
            <>
              <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
                <span className="muted">Jenis dokumen:</span>
                {(["MATERIAL", "EXERCISE", "PROJECT"] as RootJenis[]).map((r) => (
                  <button
                    key={r}
                    className={`btn btn-sm${rootJenis === r ? " btn-primary" : ""}`}
                    onClick={() => gantiRoot(r)}
                  >
                    {r === "MATERIAL" ? "📖 Materi" : r === "EXERCISE" ? "🎯 Latihan" : "🧩 Proyek"}
                  </button>
                ))}
              </div>
              {blocks.map((b, idx) => (
                <div key={b.id} className="card" style={{ padding: 12, marginBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <strong>
                      {BLOK_META[b.jenis].ikon} {BLOK_META[b.jenis].label}
                    </strong>
                    <span className="row-actions">
                      <button className="btn btn-sm" onClick={() => pindahBlok(b.id, -1)} disabled={idx === 0} title="Naik">↑</button>
                      <button className="btn btn-sm" onClick={() => pindahBlok(b.id, 1)} disabled={idx === blocks.length - 1} title="Turun">↓</button>
                      <button className="btn btn-sm btn-danger" onClick={() => terapkanBlok(blocks.filter((x) => x.id !== b.id))} title="Hapus blok">✕</button>
                    </span>
                  </div>
                  <BlokIsi blok={b} onChange={(patch) => ubahBlok(b.id, patch)} />
                </div>
              ))}
              {blocks.length === 0 && (
                <p className="muted">Belum ada blok. Tambahkan blok pertama lewat tombol di bawah.</p>
              )}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                <span className="muted">Tambah blok:</span>
                {BLOK_PER_ROOT[rootJenis]
                  .filter((j) => j !== "judul" || !adaJudul)
                  .map((j) => (
                    <button
                      key={j}
                      className="btn btn-sm"
                      onClick={() => terapkanBlok([...blocks, blokBaru(j, idBerikut.current++)])}
                    >
                      {BLOK_META[j].ikon} {BLOK_META[j].label}
                    </button>
                  ))}
              </div>
              <p className="muted" style={{ marginTop: 8 }}>
                🧠 <strong>Cek Pemahaman</strong> = soal latihan sisipan di tengah bacaan (otomatis dinilai, masuk nilai materi). Kuis/ujian berwaktu dibuat sebagai dokumen terpisah lewat jenis dokumen.
              </p>
            </>
          ) : (
            <>
              <label className="label" style={{ marginTop: 0 }}>Teks TCML</label>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                {SISIPAN.map((s) => (
                  <button key={s.label} type="button" className="btn btn-sm" onClick={() => sisip(s)}>
                    ＋ {s.label}
                  </button>
                ))}
              </div>
              <textarea
                ref={taRef}
                className="textarea"
                value={teks}
                onChange={(e) => onTeksChange(e.target.value)}
                rows={22}
                spellCheck={false}
                style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" }}
                placeholder={CONTOH}
              />
            </>
          )}
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
        {kotor && <span className="muted">● Ada perubahan belum tersimpan (draf tersimpan otomatis di perangkat ini)</span>}
      </div>
      <p className="muted" style={{ marginTop: 10 }}>
        Materi dengan TCML tidak valid tidak bisa disimpan — perbaiki error yang ditampilkan.
      </p>
    </main>
  );
}

/* ============================================================ isi blok */
function BlokIsi({ blok, onChange }: { blok: Blok; onChange: (patch: Partial<Blok>) => void }) {
  const j = blok.jenis;
  if (j === "langkah" || j === "tugas" || j === "syarat" || j === "rubrik") {
    const items = blok.items ?? [];
    return (
      <div>
        {items.map((it, i) => (
          <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6 }}>
            <span className="muted" style={{ alignSelf: "center", minWidth: 20 }}>{i + 1}.</span>
            <input
              className="input"
              value={it}
              placeholder={`${LABEL_ITEM[j]} ${i + 1}`}
              onChange={(e) => {
                const next = [...items];
                next[i] = e.target.value;
                onChange({ items: next });
              }}
            />
            <button
              className="btn btn-sm"
              onClick={() => onChange({ items: items.filter((_, x) => x !== i) })}
              disabled={items.length <= 1}
              title="Hapus item"
            >
              ✕
            </button>
          </div>
        ))}
        <button className="btn btn-sm" onClick={() => onChange({ items: [...items, ""] })}>
          ➕ {LABEL_ITEM[j]}
        </button>
      </div>
    );
  }
  if (j === "cek-pg" || j === "cek-esai") {
    const opsi = blok.opsi ?? [];
    return (
      <div>
        <p className="muted" style={{ marginBottom: 8 }}>
          🧠 Soal latihan di tengah materi — {j === "cek-pg" ? "dinilai otomatis" : "dicek mandiri siswa dengan referensi"}, masuk nilai materi, boleh diulang, tanpa batas waktu. Untuk ujian berwaktu, buat dokumen jenis Kuis/Ujian.
        </p>
        <label className="label">Pertanyaan</label>
        <textarea
          className="textarea"
          rows={2}
          value={blok.pertanyaan ?? ""}
          onChange={(e) => onChange({ pertanyaan: e.target.value })}
          placeholder="Tulis pertanyaan cek pemahaman..."
        />
        {j === "cek-pg" ? (
          <>
            <label className="label">Pilihan jawaban — centang yang benar (boleh lebih dari satu)</label>
            {opsi.map((o, i) => (
              <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center" }}>
                <strong style={{ minWidth: 18 }}>{String.fromCharCode(65 + i)}.</strong>
                <input type="checkbox" checked={o.benar} onChange={(e) => {
                  const next = [...opsi];
                  next[i] = { ...next[i], benar: e.target.checked };
                  onChange({ opsi: next });
                }} />
                <input
                  className="input"
                  value={o.teks}
                  placeholder={`Teks pilihan ${String.fromCharCode(65 + i)}`}
                  onChange={(e) => {
                    const next = [...opsi];
                    next[i] = { ...next[i], teks: e.target.value };
                    onChange({ opsi: next });
                  }}
                />
                <button className="btn btn-sm" disabled={opsi.length <= 2} onClick={() => onChange({ opsi: opsi.filter((_, x) => x !== i) })} title="Hapus pilihan">✕</button>
              </div>
            ))}
            {opsi.length < 5 && (
              <button className="btn btn-sm" onClick={() => onChange({ opsi: [...opsi, { teks: "", benar: false }] })}>➕ Pilihan</button>
            )}
          </>
        ) : (
          <>
            <label className="label">Jawaban referensi — dibuka siswa SETELAH menjawab, untuk cek mandiri</label>
            <textarea
              className="textarea"
              rows={2}
              value={blok.referensi ?? ""}
              onChange={(e) => onChange({ referensi: e.target.value })}
              placeholder="Jawaban yang benar / poin-poin pentingnya..."
            />
          </>
        )}
        <label className="label">Bobot (untuk nilai materi)</label>
        <input
          className="input"
          style={{ maxWidth: 110 }}
          type="number"
          min="0.5"
          step="0.5"
          value={blok.bobot ?? "1"}
          onChange={(e) => onChange({ bobot: e.target.value })}
        />
      </div>
    );
  }
  if (j === "tabel") {
    const baris = blok.baris ?? [];
    const kolom = Math.max(1, ...baris.map((r) => r.length));
    const setSel = (r: number, c: number, v: string) => {
      const next = baris.map((row) => {
        const copy = [...row];
        while (copy.length < kolom) copy.push("");
        return copy;
      });
      next[r][c] = v;
      onChange({ baris: next });
    };
    return (
      <div>
        <p className="muted" style={{ marginBottom: 8 }}>Baris pertama menjadi judul kolom.</p>
        {baris.map((row, r) => (
          <div key={r} style={{ display: "flex", gap: 6, marginBottom: 6 }}>
            {Array.from({ length: kolom }).map((_, c) => (
              <input
                key={c}
                className="input"
                style={r === 0 ? { fontWeight: 700 } : undefined}
                value={row[c] ?? ""}
                placeholder={r === 0 ? `Kolom ${c + 1}` : ""}
                onChange={(e) => setSel(r, c, e.target.value)}
              />
            ))}
            <button
              className="btn btn-sm"
              onClick={() => onChange({ baris: baris.filter((_, x) => x !== r) })}
              disabled={baris.length <= 1}
              title="Hapus baris"
            >
              ✕
            </button>
          </div>
        ))}
        <span className="row-actions">
          <button className="btn btn-sm" onClick={() => onChange({ baris: [...baris, Array(kolom).fill("")] })}>
            ➕ Baris
          </button>
          <button
            className="btn btn-sm"
            onClick={() => onChange({ baris: baris.map((row) => [...row, ""]) })}
          >
            ➕ Kolom
          </button>
          <button
            className="btn btn-sm"
            onClick={() => onChange({ baris: baris.map((row) => row.slice(0, -1)) })}
            disabled={kolom <= 1}
          >
            − Kolom
          </button>
        </span>
      </div>
    );
  }
  if (j === "sprite") {
    return (
      <div>
        <input
          className="input"
          value={blok.nama ?? ""}
          placeholder="Nama sprite, mis. Kucing"
          onChange={(e) => onChange({ nama: e.target.value })}
          style={{ marginBottom: 8 }}
        />
        <textarea
          className="textarea"
          rows={2}
          value={blok.deskripsi ?? ""}
          placeholder="Deskripsi sprite ini..."
          onChange={(e) => onChange({ deskripsi: e.target.value })}
        />
      </div>
    );
  }
  if (j === "judul" || j === "heading") {
    return (
      <input
        className="input"
        value={blok.teks ?? ""}
        placeholder={j === "judul" ? "Judul di dalam dokumen" : "Judul bagian"}
        onChange={(e) => onChange({ teks: e.target.value })}
      />
    );
  }
  if (j === "scratch") {
    return (
      <input
        className="input"
        value={blok.teks ?? ""}
        placeholder="ID proyek (angka) atau URL scratch.mit.edu/projects/..."
        onChange={(e) => onChange({ teks: e.target.value })}
      />
    );
  }
  const mono = j === "rumus" || j === "kode" || j === "blok-scratch";
  return (
    <textarea
      className="textarea"
      rows={j === "paragraf" || j === "deskripsi" ? 4 : 3}
      value={blok.teks ?? ""}
      placeholder={`Isi ${BLOK_META[j].label.toLowerCase()}...`}
      onChange={(e) => onChange({ teks: e.target.value })}
      style={mono ? { fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" } : undefined}
      spellCheck={!mono}
    />
  );
}

export default function EditorMateriPage() {
  return (
    <Suspense fallback={<main className="page"><p className="muted">Memuat editor...</p></main>}>
      <EditorInner />
    </Suspense>
  );
}
