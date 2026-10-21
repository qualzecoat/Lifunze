"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import MaterialPreview, { type MaterialPreviewCek } from "@/components/MaterialPreview";
import { apiFetch, getMe, type User } from "@/lib/api";

interface TcmlError {
  line: number;
  message: string;
}
interface Category {
  id: number;
  nama: string;
}

/* ============================================================ model blok materi */
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

/* ============================================================ sisipan TCML materi (lengkap) */
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

const TEMPLATES: { nama: string; judul: string; teks: string }[] = [
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
];

/* ============================================================ model kartu soal */
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
interface CardSoal {
  pertanyaan: string;
  opsi: string[];
  kunci: number[];
  bobot: string;
  referensi: string;
  /** Terisi = kartu BLOK PENGANTAR (prolog/hint di dalam kuis), bukan soal. */
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

/* ============================================================ pecah dokumen gabungan (sisi klien) */
/** Gabungkan beberapa akar [QUIZ] sejenis menjadi SATU akar: isi digabung,
 * [TYPE] hanya dari akar pertama, nomor pembungkus soal diurutkan ulang. */
function gabungSegmenKuis(segments: string[]): string {
  if (segments.length === 1) return segments[0];
  const inners: string[][] = [];
  let typeLine = "";
  for (const seg of segments) {
    const ls = seg.split("\n");
    const mulai = ls.findIndex((l) => /^\s*\[QUIZ\]\s*$/.test(l));
    let akhir = -1;
    for (let i = ls.length - 1; i >= 0; i--) {
      if (/^\s*\[\/QUIZ\]\s*$/.test(ls[i])) { akhir = i; break; }
    }
    const inner = ls.slice(mulai + 1, akhir === -1 ? undefined : akhir);
    for (const l of inner) {
      if (!typeLine && /^\s*\[TYPE\].*\[\/TYPE\]\s*$/i.test(l)) typeLine = l.trim();
    }
    inners.push(inner.filter((l) => !/^\s*\[TYPE\].*\[\/TYPE\]\s*$/i.test(l)));
  }
  const gabungan: string[] = [];
  let nomor = 0;
  const tumpukan: number[] = [];
  for (const inner of inners) {
    for (const l of inner) {
      if (/^\s*\[QUESTION\s+\d+\]\s*$/.test(l)) {
        nomor += 1;
        tumpukan.push(nomor);
        gabungan.push(`[QUESTION ${nomor}]`);
      } else if (/^\s*\[\/QUESTION\s+\d+\]\s*$/.test(l)) {
        gabungan.push(`[/QUESTION ${tumpukan.pop() ?? nomor}]`);
      } else {
        gabungan.push(l);
      }
    }
  }
  return ["[QUIZ]", ...(typeLine ? [typeLine] : []), ...gabungan, "[/QUIZ]"].join("\n");
}

function pecahDokumen(teks: string): { materi: string | null; kuis_pg: string | null; kuis_esai: string | null } {
  // Audit #14: SEMUA akar dipertahankan. Dulu akar kedua sejenis dibuang
  // diam-diam (first-wins) — materi pendamping & soal AI hilang saat disimpan.
  const materiSeg: string[] = [];
  const pgSeg: string[] = [];
  const esaiSeg: string[] = [];
  const lines = teks.split("\n");
  let cur: string[] | null = null;
  let root = "";
  for (const ln of lines) {
    const open = ln.match(/^\s*\[(MATERIAL|EXERCISE|PROJECT|QUIZ)\]\s*$/);
    if (open && cur === null) {
      cur = [ln];
      root = open[1];
      continue;
    }
    if (cur !== null) {
      cur.push(ln);
      if (ln.trim() === `[/${root}]`) {
        const seg = cur.join("\n").trim();
        if (root === "QUIZ") {
          if (/\[TYPE\]\s*essay\s*\[\/TYPE\]/i.test(seg)) esaiSeg.push(seg);
          else pgSeg.push(seg);
        } else {
          materiSeg.push(seg);
        }
        cur = null;
        root = "";
      }
    }
  }
  return {
    materi: materiSeg.length ? materiSeg.join("\n\n") : null,
    kuis_pg: pgSeg.length ? gabungSegmenKuis(pgSeg) : null,
    kuis_esai: esaiSeg.length ? gabungSegmenKuis(esaiSeg) : null,
  };
}

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function keIso(local: string): string | null {
  return local ? new Date(local).toISOString() : null;
}

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
type JenisDok = "materi" | "tugas" | "kuis" | "ujian";
const JENIS_META: { nilai: JenisDok; label: string; ikon: string; hint: string }[] = [
  { nilai: "materi", label: "Materi Biasa", ikon: "📖", hint: "Dibaca siswa; progress = selesai dibaca." },
  { nilai: "tugas", label: "Tugas", ikon: "📝", hint: "Ada panel pengumpulan file untuk siswa (tenggat opsional)." },
  { nilai: "kuis", label: "Kuis", ikon: "🧪", hint: "Bagian kuis dinilai otomatis (PG) / manual (esai). Semua pengaturan opsional." },
  { nilai: "ujian", label: "Ujian", ikon: "🏆", hint: "Seperti kuis, dengan bawaan acak soal & opsi menyala. Semua tetap opsional." },
];

interface Pengaturan {
  durasi: string;
  dibuka: string;
  ditutup: string;
  acakSoal: boolean;
  acakOpsi: boolean;
  tampilkanKunci: boolean;
}
const PENGATURAN_AWAL: Pengaturan = {
  durasi: "", dibuka: "", ditutup: "", acakSoal: false, acakOpsi: false, tampilkanKunci: true,
};

/* ============================================================ komponen utama */
function EditorDokumenInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const meetingParam = sp.get("meeting");
  const grupParam = sp.get("grup");
  const bankGrupParam = sp.get("bank_grup");
  const kelasParam = sp.get("kelas");
  const isBank = sp.get("mode") === "bank" || !!bankGrupParam;
  const konteks = grupParam
    ? `g${grupParam}`
    : bankGrupParam
      ? `bg${bankGrupParam}`
      : meetingParam
        ? `p${meetingParam}`
        : isBank
          ? "bank-baru"
          : "baru";
  const draftKey = `lifunze-draf-dokumen:${konteks}`;

  const [user, setUser] = useState<User | null>(null);
  const [judul, setJudul] = useState("");
  const [jenisDok, setJenisDok] = useState<JenisDok>("materi");
  const [tenggat, setTenggat] = useState("");
  const [pengaturan, setPengaturan] = useState<Pengaturan>(PENGATURAN_AWAL);
  const [subjectId, setSubjectId] = useState<string | null>(kelasParam);
  const [categories, setCategories] = useState<Category[]>([]);
  const [kategoriId, setKategoriId] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [saving, setSaving] = useState(false);

  // Bagian-bagian dokumen
  const [aktifMateri, setAktifMateri] = useState(true);
  const [aktifPg, setAktifPg] = useState(false);
  const [aktifEsai, setAktifEsai] = useState(false);

  // Bagian materi
  const [modeMateri, setModeMateri] = useState<"blok" | "tcml">("blok");
  const [rootJenis, setRootJenis] = useState<RootJenis>("MATERIAL");
  const [blocks, setBlocks] = useState<Blok[]>([]);
  const [teksMateri, setTeksMateri] = useState("");
  const [noticeMateri, setNoticeMateri] = useState("");
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewCek, setPreviewCek] = useState<MaterialPreviewCek[]>([]);
  const [errorsMateri, setErrorsMateri] = useState<TcmlError[]>([]);

  // Bagian kuis
  const [modePg, setModePg] = useState<"form" | "tcml">("form");
  const [cardsPg, setCardsPg] = useState<CardSoal[]>([kartuKosong()]);
  const [teksPg, setTeksPg] = useState("");
  const [previewPg, setPreviewPg] = useState<ParsedQuestion[]>([]);
  const [errorsPg, setErrorsPg] = useState<TcmlError[]>([]);
  const [modeEsai, setModeEsai] = useState<"form" | "tcml">("form");
  const [cardsEsai, setCardsEsai] = useState<CardSoal[]>([kartuKosong()]);
  const [teksEsai, setTeksEsai] = useState("");
  const [previewEsai, setPreviewEsai] = useState<ParsedQuestion[]>([]);
  const [errorsEsai, setErrorsEsai] = useState<TcmlError[]>([]);

  const idBerikut = useRef(1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const taMateriRef = useRef<HTMLTextAreaElement>(null);

  // Autosave
  const [baseline, setBaseline] = useState<string | null>(null);
  const [restoreDraft, setRestoreDraft] = useState<(Record<string, unknown> & { ts: number }) | null>(null);

  // Panel AI
  const [aiOpen, setAiOpen] = useState(false);
  const [aiPacks, setAiPacks] = useState<PackRingkas[]>([]);
  const [aiSettings, setAiSettings] = useState<SettingRingkas[]>([]);
  const [aiPack, setAiPack] = useState("");
  const [aiSetting, setAiSetting] = useState("");
  const [aiTopik, setAiTopik] = useState("");
  const [aiJumlah, setAiJumlah] = useState("5");
  const [aiInstruksi, setAiInstruksi] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiMsg, setAiMsg] = useState("");
  const aiDimuat = useRef(false);

  const snapshot = useCallback((): string => {
    return JSON.stringify({
      judul, jenisDok, tenggat, pengaturan, kategoriId,
      aktifMateri, aktifPg, aktifEsai,
      teksMateri, teksPg, teksEsai,
    });
  }, [judul, jenisDok, tenggat, pengaturan, kategoriId, aktifMateri, aktifPg, aktifEsai, teksMateri, teksPg, teksEsai]);

  const kotor = baseline !== null && snapshot() !== baseline;

  /* ---------------- pratinjau & sinkronisasi bagian materi ---------------- */
  const runPreviewMateri = useCallback(async (value: string) => {
    if (!value.trim()) {
      setPreviewHtml("");
      setPreviewCek([]);
      setErrorsMateri([]);
      return;
    }
    try {
      const res = await apiFetch<{
        success: boolean;
        content: string | null;
        errors: TcmlError[];
        cek?: MaterialPreviewCek[];
      }>(
        "/api/v1/parse/content",
        { method: "POST", body: { teks: value, jenis: "material" } },
      );
      if (res.success) {
        setPreviewHtml(res.content ?? "");
        setPreviewCek(res.cek ?? []);
        setErrorsMateri([]);
      } else {
        setPreviewHtml("");
        setPreviewCek([]);
        setErrorsMateri(res.errors ?? []);
      }
    } catch { /* diam */ }
  }, []);

  function onTeksMateriChange(v: string, diam = false) {
    setTeksMateri(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runPreviewMateri(v), diam ? 50 : 600);
  }

  function terapkanBlok(next: Blok[], root: RootJenis = rootJenis) {
    setBlocks(next);
    onTeksMateriChange(susunTeks(root, next));
  }

  const strukturkanMateri = useCallback(async (teksStr: string, diam = false): Promise<boolean> => {
    try {
      const r = await apiFetch<StrukturResp>("/api/v1/parse/structure", {
        method: "POST",
        body: { teks: teksStr },
      });
      if (r.success && r.bisa_formulir && r.root) {
        setBlocks(r.blocks.map((b) => ({ ...b, bobot: b.bobot != null ? String(b.bobot) : undefined, id: idBerikut.current++ })));
        setRootJenis(r.root);
        setModeMateri("blok");
        setNoticeMateri("");
        return true;
      }
      if (!diam) {
        setNoticeMateri(
          (r.alasan ?? "Bagian materi ini belum bisa dibuka di Mode Blok.") +
            " Anda tetap bisa mengeditnya di Mode TCML.",
        );
      }
      setModeMateri("tcml");
      return false;
    } catch {
      if (!diam) setNoticeMateri("Gagal memeriksa struktur — tetap di Mode TCML.");
      setModeMateri("tcml");
      return false;
    }
  }, []);

  /* ---------------- pratinjau & sinkronisasi bagian kuis ---------------- */
  async function parseKuis(value: string, tipe: "pilihan_ganda" | "teks") {
    return apiFetch<{ success: boolean; content: { questions: ParsedQuestion[]; items?: { jenis: string; tipe?: string; teks?: string }[] } | null; errors: TcmlError[] }>(
      "/api/v1/parse/quiz",
      { method: "POST", body: { teks: value, tipe } },
    );
  }

  async function runPreviewKuis(
    value: string,
    tipe: "pilihan_ganda" | "teks",
    setPreview: (q: ParsedQuestion[]) => void,
    setErrors: (e: TcmlError[]) => void,
  ) {
    if (!value.trim()) {
      setPreview([]);
      setErrors([]);
      return;
    }
    try {
      const res = await parseKuis(value, tipe);
      if (res.success && res.content) {
        setPreview(res.content.questions);
        setErrors([]);
      } else {
        setPreview([]);
        setErrors(res.errors ?? []);
      }
    } catch { /* diam */ }
  }

  function sinkronKartuPg(next: CardSoal[]) {
    setCardsPg(next);
    const built = kartuKeTeks(next, "pilihan_ganda");
    setTeksPg(built);
    void runPreviewKuis(built, "pilihan_ganda", setPreviewPg, setErrorsPg);
  }
  function sinkronKartuEsai(next: CardSoal[]) {
    setCardsEsai(next);
    const built = kartuKeTeks(next, "teks");
    setTeksEsai(built);
    void runPreviewKuis(built, "teks", setPreviewEsai, setErrorsEsai);
  }

  async function uraiKartu(
    value: string,
    tipe: "pilihan_ganda" | "teks",
    setCards: (c: CardSoal[]) => void,
    setErrors: (e: TcmlError[]) => void,
  ): Promise<boolean> {
    if (!value.trim()) {
      setCards([kartuKosong()]);
      return true;
    }
    try {
      const res = await parseKuis(value, tipe);
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

  /* ---------------- aktif/nonaktifkan bagian ---------------- */
  function toggleBagian(bagian: "materi" | "pg" | "esai", aktif: boolean) {
    if (!aktif) {
      const teksAda =
        bagian === "materi" ? teksMateri.trim() : bagian === "pg" ? teksPg.trim() : teksEsai.trim();
      if (teksAda && !window.confirm("Nonaktifkan bagian ini? Isinya akan dibuang dari dokumen saat disimpan.")) return;
    }
    if (bagian === "materi") {
      setAktifMateri(aktif);
      if (aktif && !teksMateri.trim()) {
        const awal: Blok[] = [
          { id: idBerikut.current++, jenis: "judul", teks: "" },
          { id: idBerikut.current++, jenis: "paragraf", teks: "" },
        ];
        setBlocks(awal);
        setRootJenis("MATERIAL");
        setModeMateri("blok");
        onTeksMateriChange(susunTeks("MATERIAL", awal));
      }
    } else if (bagian === "pg") {
      setAktifPg(aktif);
      if (aktif && !teksPg.trim()) sinkronKartuPg([kartuKosong()]);
    } else {
      setAktifEsai(aktif);
      if (aktif && !teksEsai.trim()) sinkronKartuEsai([kartuKosong()]);
    }
  }

  function gantiJenis(j: JenisDok) {
    setJenisDok(j);
    if (j === "ujian") {
      setPengaturan((p) => ({ ...p, acakSoal: true, acakOpsi: true }));
    }
    if ((j === "kuis" || j === "ujian") && !aktifPg && !aktifEsai) {
      setAktifPg(true);
      if (!teksPg.trim()) sinkronKartuPg([kartuKosong()]);
    }
  }

  /* ---------------- muat awal ---------------- */
  interface DokumenResp {
    grup: string;
    subject_id: number | null;
    judul: string;
    jenis: JenisDok;
    tenggat: string | null;
    material: { id: number; teks_mentah: string } | null;
    quizzes: { id: number; tipe: string; teks_mentah: string }[];
    pengaturan_kuis: {
      durasi_menit: number | null;
      acak_soal: boolean;
      acak_opsi: boolean;
      dibuka_pada: string | null;
      ditutup_pada: string | null;
      tampilkan_kunci: boolean;
    };
  }
  interface BankDokumenResp {
    grup: string;
    judul: string;
    jenis: JenisDok;
    kategori_id: number | null;
    material: { teks_mentah: string } | null;
    quizzes: { tipe: string; teks_mentah: string }[];
    pengaturan_kuis: {
      durasi_menit: number | null;
      acak_soal: boolean;
      acak_opsi: boolean;
      tampilkan_kunci: boolean;
    };
  }

  async function muatDariBagian(d: {
    judul: string;
    jenis: JenisDok;
    teksMateri: string | null;
    teksPg: string | null;
    teksEsai: string | null;
  }) {
    setJudul(d.judul);
    setJenisDok(d.jenis);
    if (d.teksMateri) {
      setAktifMateri(true);
      setTeksMateri(d.teksMateri);
      runPreviewMateri(d.teksMateri);
      await strukturkanMateri(d.teksMateri, true);
    } else {
      setAktifMateri(false);
    }
    if (d.teksPg) {
      setAktifPg(true);
      setTeksPg(d.teksPg);
      void runPreviewKuis(d.teksPg, "pilihan_ganda", setPreviewPg, setErrorsPg);
      await uraiKartu(d.teksPg, "pilihan_ganda", setCardsPg, setErrorsPg);
    } else {
      setAktifPg(false);
    }
    if (d.teksEsai) {
      setAktifEsai(true);
      setTeksEsai(d.teksEsai);
      void runPreviewKuis(d.teksEsai, "teks", setPreviewEsai, setErrorsEsai);
      await uraiKartu(d.teksEsai, "teks", setCardsEsai, setErrorsEsai);
    } else {
      setAktifEsai(false);
    }
  }

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

      // Audit #13: baseline dirakit EKSPLISIT dari nilai yang dimuat —
      // dulu diambil dari snapshot() di dalam setTimeout, tetapi closure
      // effect menangkap snapshot render PERTAMA (state kosong) sehingga
      // dokumen yang baru dibuka langsung terbaca "kotor".
      let baselineAwal: Record<string, unknown> = {
        judul: "", jenisDok: "materi", tenggat: "", pengaturan: PENGATURAN_AWAL, kategoriId: "",
        aktifMateri: true, aktifPg: false, aktifEsai: false,
        teksMateri: "", teksPg: "", teksEsai: "",
      };
      try {
        if (grupParam) {
          const d = await apiFetch<DokumenResp>(`/api/v1/documents/${grupParam}`);
          if (d.subject_id) setSubjectId(String(d.subject_id));
          const tenggatAwal = toLocalInput(d.tenggat);
          const pengaturanAwal: Pengaturan = {
            durasi: d.pengaturan_kuis.durasi_menit ? String(d.pengaturan_kuis.durasi_menit) : "",
            dibuka: toLocalInput(d.pengaturan_kuis.dibuka_pada),
            ditutup: toLocalInput(d.pengaturan_kuis.ditutup_pada),
            acakSoal: d.pengaturan_kuis.acak_soal,
            acakOpsi: d.pengaturan_kuis.acak_opsi,
            tampilkanKunci: d.pengaturan_kuis.tampilkan_kunci,
          };
          setTenggat(tenggatAwal);
          setPengaturan(pengaturanAwal);
          const teksMateriAwal = d.material?.teks_mentah ?? null;
          const teksPgAwal = d.quizzes.find((q) => q.tipe === "pilihan_ganda")?.teks_mentah ?? null;
          const teksEsaiAwal = d.quizzes.find((q) => q.tipe === "teks")?.teks_mentah ?? null;
          await muatDariBagian({
            judul: d.judul,
            jenis: d.jenis,
            teksMateri: teksMateriAwal,
            teksPg: teksPgAwal,
            teksEsai: teksEsaiAwal,
          });
          baselineAwal = {
            judul: d.judul, jenisDok: d.jenis, tenggat: tenggatAwal, pengaturan: pengaturanAwal, kategoriId: "",
            aktifMateri: !!teksMateriAwal, aktifPg: !!teksPgAwal, aktifEsai: !!teksEsaiAwal,
            teksMateri: teksMateriAwal ?? "", teksPg: teksPgAwal ?? "", teksEsai: teksEsaiAwal ?? "",
          };
        } else if (bankGrupParam) {
          const d = await apiFetch<BankDokumenResp>(`/api/v1/bank/documents/${bankGrupParam}`);
          const kategoriAwal = d.kategori_id ? String(d.kategori_id) : "";
          const pengaturanAwal: Pengaturan = {
            durasi: d.pengaturan_kuis.durasi_menit ? String(d.pengaturan_kuis.durasi_menit) : "",
            dibuka: "", ditutup: "",
            acakSoal: d.pengaturan_kuis.acak_soal,
            acakOpsi: d.pengaturan_kuis.acak_opsi,
            tampilkanKunci: d.pengaturan_kuis.tampilkan_kunci,
          };
          setKategoriId(kategoriAwal);
          setPengaturan(pengaturanAwal);
          const teksMateriAwal = d.material?.teks_mentah ?? null;
          const teksPgAwal = d.quizzes.find((q) => q.tipe === "pilihan_ganda")?.teks_mentah ?? null;
          const teksEsaiAwal = d.quizzes.find((q) => q.tipe === "teks")?.teks_mentah ?? null;
          await muatDariBagian({
            judul: d.judul,
            jenis: d.jenis,
            teksMateri: teksMateriAwal,
            teksPg: teksPgAwal,
            teksEsai: teksEsaiAwal,
          });
          baselineAwal = {
            judul: d.judul, jenisDok: d.jenis, tenggat: "", pengaturan: pengaturanAwal, kategoriId: kategoriAwal,
            aktifMateri: !!teksMateriAwal, aktifPg: !!teksPgAwal, aktifEsai: !!teksEsaiAwal,
            teksMateri: teksMateriAwal ?? "", teksPg: teksPgAwal ?? "", teksEsai: teksEsaiAwal ?? "",
          };
        } else {
          // Dokumen baru: bagian materi dengan blok awal.
          const awal: Blok[] = [
            { id: idBerikut.current++, jenis: "judul", teks: "" },
            { id: idBerikut.current++, jenis: "paragraf", teks: "" },
          ];
          const teksAwal = susunTeks("MATERIAL", awal);
          setBlocks(awal);
          setTeksMateri(teksAwal);
          baselineAwal = { ...baselineAwal, teksMateri: teksAwal };
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat dokumen.");
      }
      setBaseline(JSON.stringify(baselineAwal));

      try {
        const mentah = localStorage.getItem(draftKey);
        if (mentah) {
          const d = JSON.parse(mentah) as Record<string, unknown> & { ts: number };
          // Tawarkan pulihkan hanya bila isi draf lokal BERBEDA dari muatan.
          const isi: Record<string, unknown> = { ...d };
          delete isi.ts;
          if (JSON.stringify(isi) !== JSON.stringify(baselineAwal)) {
            setRestoreDraft(d);
          }
        }
      } catch { /* abaikan */ }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, grupParam, bankGrupParam]);

  /* ---------------- autosave ---------------- */
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
        const data = JSON.parse(snapshot()) as Record<string, unknown>;
        localStorage.setItem(draftKey, JSON.stringify({ ...data, ts: Date.now() }));
      } catch { /* abaikan */ }
    }, 800);
    return () => clearTimeout(t);
  }, [snapshot, kotor, baseline, draftKey]);

  async function pulihkanDraf() {
    if (!restoreDraft) return;
    const d = restoreDraft;
    setJudul(String(d.judul ?? ""));
    setJenisDok((d.jenisDok as JenisDok) ?? "materi");
    setTenggat(String(d.tenggat ?? ""));
    setPengaturan((d.pengaturan as Pengaturan) ?? PENGATURAN_AWAL);
    setKategoriId(String(d.kategoriId ?? ""));
    await muatDariBagian({
      judul: String(d.judul ?? ""),
      jenis: (d.jenisDok as JenisDok) ?? "materi",
      teksMateri: d.aktifMateri ? String(d.teksMateri ?? "") || null : null,
      teksPg: d.aktifPg ? String(d.teksPg ?? "") || null : null,
      teksEsai: d.aktifEsai ? String(d.teksEsai ?? "") || null : null,
    });
    setRestoreDraft(null);
    setOk("Draf yang belum tersimpan dipulihkan.");
  }
  function buangDraf() {
    try {
      localStorage.removeItem(draftKey);
    } catch { /* abaikan */ }
    setRestoreDraft(null);
  }
  function tandaiBersih() {
    setBaseline(snapshot());
    try {
      localStorage.removeItem(draftKey);
    } catch { /* abaikan */ }
  }

  /* ---------------- Judul <-> [TITLE] ---------------- */
  const cocokTitle = teksMateri.match(/\[TITLE\]([\s\S]*?)\[\/TITLE\]/i);
  const titleDalam = cocokTitle ? cocokTitle[1].trim() : null;
  const judulBeda = aktifMateri && !!titleDalam && !!judul.trim() && titleDalam !== judul.trim();
  const tanpaTitle = aktifMateri && !titleDalam && /\[(MATERIAL|EXERCISE|PROJECT)\]/.test(teksMateri);

  function tulisTitleKeDokumen() {
    if (modeMateri === "blok") {
      const ada = blocks.some((b) => b.jenis === "judul");
      const next = ada
        ? blocks.map((b) => (b.jenis === "judul" ? { ...b, teks: judul } : b))
        : [{ id: idBerikut.current++, jenis: "judul" as JenisBlok, teks: judul }, ...blocks];
      terapkanBlok(next);
    } else {
      const baru = cocokTitle
        ? teksMateri.replace(/\[TITLE\][\s\S]*?\[\/TITLE\]/i, `[TITLE]${judul}[/TITLE]`)
        : teksMateri.replace(/\[(MATERIAL|EXERCISE|PROJECT)\]/, (m) => `${m}\n[TITLE]${judul}[/TITLE]`);
      onTeksMateriChange(baru);
    }
  }

  function sisipMateri(s: (typeof SISIPAN)[number]) {
    const el = taMateriRef.current;
    const start = el ? el.selectionStart : teksMateri.length;
    const end = el ? el.selectionEnd : teksMateri.length;
    const sebelum = teksMateri.slice(0, start);
    const sesudah = teksMateri.slice(end);
    const awalan = sebelum && !sebelum.endsWith("\n") ? "\n" : "";
    onTeksMateriChange(sebelum + awalan + s.teks + "\n" + sesudah);
    requestAnimationFrame(() => {
      const el2 = taMateriRef.current;
      if (!el2) return;
      el2.focus();
      const dasar = start + awalan.length;
      const i = s.teks.indexOf(s.tandai);
      el2.setSelectionRange(dasar + i, dasar + i + s.tandai.length);
    });
  }

  /* ---------------- simpan ---------------- */
  function payloadBagian() {
    return {
      judul,
      jenis: jenisDok,
      tenggat: jenisDok === "tugas" ? keIso(tenggat) : null,
      teks_materi: aktifMateri ? teksMateri : null,
      teks_kuis_pg: aktifPg ? teksPg : null,
      teks_kuis_esai: aktifEsai ? teksEsai : null,
      pengaturan_kuis: {
        durasi_menit: pengaturan.durasi ? Number(pengaturan.durasi) : null,
        acak_soal: pengaturan.acakSoal,
        acak_opsi: pengaturan.acakOpsi,
        dibuka_pada: keIso(pengaturan.dibuka),
        ditutup_pada: keIso(pengaturan.ditutup),
        tampilkan_kunci: pengaturan.tampilkanKunci,
      },
    };
  }

  async function onSave() {
    setError("");
    setOk("");
    if (!aktifMateri && !aktifPg && !aktifEsai) {
      setError("Aktifkan minimal satu bagian (materi / kuis PG / kuis esai).");
      return;
    }
    setSaving(true);
    try {
      if (isBank) {
        const p = payloadBagian();
        const body = {
          judul: p.judul,
          jenis: p.jenis,
          kategori_id: kategoriId ? Number(kategoriId) : null,
          teks_materi: p.teks_materi,
          teks_kuis_pg: p.teks_kuis_pg,
          teks_kuis_esai: p.teks_kuis_esai,
          // Audit #9: pengaturan pengerjaan ikut disimpan di bank
          // (jendela diabaikan server — itu jadwal, bukan sifat kuis).
          pengaturan_kuis: p.pengaturan_kuis,
        };
        if (bankGrupParam) {
          await apiFetch(`/api/v1/bank/documents/${bankGrupParam}`, { method: "PATCH", body });
          tandaiBersih();
          setOk("Dokumen bank diperbarui.");
        } else {
          await apiFetch("/api/v1/bank/documents", { method: "POST", body });
          tandaiBersih();
          router.push("/bank?tab=dokumen");
        }
        return;
      }
      const body = payloadBagian();
      let doc: DokumenResp;
      if (grupParam) {
        doc = await apiFetch<DokumenResp>(`/api/v1/documents/${grupParam}`, { method: "PATCH", body });
      } else if (meetingParam) {
        doc = await apiFetch<DokumenResp>(`/api/v1/meetings/${meetingParam}/documents`, { method: "POST", body });
      } else {
        setError("Konteks pertemuan tidak diketahui.");
        return;
      }
      tandaiBersih();
      if (doc.material) {
        router.push(`/materi/${doc.material.id}`);
      } else if (doc.quizzes.length > 0) {
        router.push(`/kuis/${doc.quizzes[0].id}`);
      } else if (subjectId) {
        router.push(`/kelas/${subjectId}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Gagal menyimpan.";
      setError(msg);
      try {
        const parsed = JSON.parse(msg);
        if (parsed?.errors) {
          const errs = parsed.errors as TcmlError[];
          if (/materi/i.test(String(parsed.pesan ?? ""))) setErrorsMateri(errs);
        }
      } catch { /* bukan JSON */ }
    } finally {
      setSaving(false);
    }
  }

  /* ---------------- Panel AI ---------------- */
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
      } catch { /* panel menampilkan keadaan kosong */ }
    }
    if (next && !aiTopik && judul.trim()) setAiTopik(judul);
  }

  async function generateAi() {
    if (!aiPack) {
      setAiMsg("Pilih paket parser dulu — paket menentukan modul materi & kuis yang boleh dipakai AI.");
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
          kind: "dokumen",
          pack_id: Number(aiPack),
          ai_setting_id: aiSetting ? Number(aiSetting) : null,
          brief: {
            topik: aiTopik,
            jumlah_soal: aiJumlah ? Number(aiJumlah) : undefined,
            instruksi: aiInstruksi || undefined,
            jenis_dokumen: jenisDok,
          },
        },
      });
      const d = res.drafts[0];
      if (!d) {
        setAiMsg("AI tidak menghasilkan dokumen.");
        return;
      }
      if (!d.is_valid) {
        setAiMsg(
          `Hasil AI belum valid (${d.errors.length} error). Drafnya tersimpan di menu Generate AI — perbaiki di sana, atau coba generate ulang.`,
        );
        return;
      }
      const bagian = pecahDokumen(d.teks_mentah);
      if (!judul.trim()) setJudul(d.judul);
      await muatDariBagian({
        judul: judul.trim() ? judul : d.judul,
        jenis: jenisDok,
        teksMateri: bagian.materi,
        teksPg: bagian.kuis_pg,
        teksEsai: bagian.kuis_esai,
      });
      if (bagian.kuis_pg || bagian.kuis_esai) {
        if (jenisDok === "materi") setJenisDok("kuis");
      }
      setAiMsg("Dokumen AI dimasukkan ke editor — tinjau & sesuaikan, lalu klik Simpan Dokumen.");
    } catch (err) {
      setAiMsg(err instanceof Error ? err.message : "Generate gagal.");
    } finally {
      setAiBusy(false);
    }
  }

  /* ---------------- operasi blok materi ---------------- */
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
    const dibuang = blocks.filter((b) => !BLOK_PER_ROOT[root].includes(b.jenis));
    if (
      dibuang.length > 0 &&
      !window.confirm(
        `${dibuang.length} blok tidak dikenal di dokumen ${root} dan akan dibuang. Lanjutkan?`,
      )
    ) {
      return;
    }
    const next = blocks.filter((b) => BLOK_PER_ROOT[root].includes(b.jenis));
    setRootJenis(root);
    terapkanBlok(next, root);
  }

  const debouncePg = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debounceEsai = useRef<ReturnType<typeof setTimeout> | null>(null);
  function onTeksPgChange(v: string) {
    setTeksPg(v);
    if (debouncePg.current) clearTimeout(debouncePg.current);
    debouncePg.current = setTimeout(
      () => void runPreviewKuis(v, "pilihan_ganda", setPreviewPg, setErrorsPg),
      600,
    );
  }
  function onTeksEsaiChange(v: string) {
    setTeksEsai(v);
    if (debounceEsai.current) clearTimeout(debounceEsai.current);
    debounceEsai.current = setTimeout(
      () => void runPreviewKuis(v, "teks", setPreviewEsai, setErrorsEsai),
      600,
    );
  }

  async function pakaiTemplateMateri(t: (typeof TEMPLATES)[number]) {
    if (teksMateri.trim() && kotor && !window.confirm(`Ganti bagian materi dengan template "${t.nama}"?`)) return;
    setAktifMateri(true);
    if (!judul.trim()) setJudul(t.judul);
    onTeksMateriChange(t.teks);
    await strukturkanMateri(t.teks, true);
  }

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  const adaJudul = blocks.some((b) => b.jenis === "judul");
  const jenisAktif = JENIS_META.find((j) => j.nilai === jenisDok);

  return (
    <main className="page" style={{ maxWidth: 1200 }}>
      <AppHeader user={user} />
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: "1.4rem" }}>
          {isBank ? "📚 Editor Dokumen Bank" : "✏️ Editor Dokumen"}
        </h1>
        {subjectId && <Link href={`/kelas/${subjectId}`}>← Kembali ke Kelas</Link>}
      </div>
      <p className="muted" style={{ marginTop: 4 }}>
        Satu dokumen bisa berisi bacaan, soal pilihan ganda, dan soal esai sekaligus —
        perannya mengikuti blok yang Anda pakai.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}
      {restoreDraft && (
        <div className="alert" style={{ background: "#fff7e0", border: "1px solid var(--amber)" }}>
          💾 Ada draf belum tersimpan dari {new Date(restoreDraft.ts).toLocaleString("id-ID")}.{" "}
          <button className="btn btn-sm btn-primary" onClick={() => void pulihkanDraf()}>Pulihkan</button>{" "}
          <button className="btn btn-sm" onClick={buangDraf}>Buang</button>
        </div>
      )}

      <label className="label">Judul dokumen</label>
      <input className="input" value={judul} onChange={(e) => setJudul(e.target.value)} placeholder="mis. Pecahan Dasar + Latihannya" />
      {judulBeda && (
        <p className="muted" style={{ marginTop: 6 }}>
          Judul di dalam dokumen: <strong>"{titleDalam}"</strong> — berbeda dari judul dokumen.{" "}
          <button className="btn btn-sm" onClick={() => setJudul(titleDalam ?? "")}>Pakai judul dokumen-dalam</button>{" "}
          <button className="btn btn-sm" onClick={tulisTitleKeDokumen}>Tulis judul ke dokumen</button>
        </p>
      )}
      {tanpaTitle && (
        <p className="muted" style={{ marginTop: 6 }}>
          Bagian materi belum punya [TITLE].{" "}
          <button className="btn btn-sm" onClick={tulisTitleKeDokumen} disabled={!judul.trim()}>
            Tambahkan dari judul dokumen
          </button>
        </p>
      )}

      {/* ---------- jenis dokumen ---------- */}
      <label className="label" style={{ marginTop: 16 }}>Jenis dokumen</label>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {JENIS_META.map((j) => (
          <button
            key={j.nilai}
            className={`btn${jenisDok === j.nilai ? " btn-primary" : ""}`}
            onClick={() => gantiJenis(j.nilai)}
          >
            {j.ikon} {j.label}
          </button>
        ))}
      </div>
      <p className="muted" style={{ marginTop: 6 }}>{jenisAktif?.hint}</p>

      {jenisDok === "tugas" && (
        <div className="card" style={{ marginTop: 10 }}>
          <label className="label" style={{ marginTop: 0 }}>Tenggat pengumpulan (opsional)</label>
          <input
            type="datetime-local"
            className="input"
            value={tenggat}
            onChange={(e) => setTenggat(e.target.value)}
            style={{ maxWidth: 320 }}
          />
          <p className="muted" style={{ marginTop: 6 }}>
            Panel pengumpulan file muncul di halaman materi untuk dokumen berjenis Tugas —
            atau bila akar bagian materinya [PROJECT].
          </p>
        </div>
      )}

      {(jenisDok === "kuis" || jenisDok === "ujian") && (
        <div className="card" style={{ marginTop: 10 }}>
          <h3 style={{ marginTop: 0 }}>⚙️ Pengaturan Kuis</h3>
          <p className="muted" style={{ margin: "4px 0 10px" }}>
            Semua pengaturan ini <strong>opsional</strong> — kosongkan bila tidak perlu.
            Berlaku untuk bagian kuis PG & esai dokumen ini.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
            <div>
              <label className="label">Durasi (menit, opsional)</label>
              <input
                type="number" min={1} className="input" value={pengaturan.durasi}
                onChange={(e) => setPengaturan({ ...pengaturan, durasi: e.target.value })}
                placeholder="tanpa batas"
              />
            </div>
            <div>
              <label className="label">Dibuka pada (opsional)</label>
              <input
                type="datetime-local" className="input" value={pengaturan.dibuka}
                onChange={(e) => setPengaturan({ ...pengaturan, dibuka: e.target.value })}
              />
            </div>
            <div>
              <label className="label">Ditutup pada (opsional)</label>
              <input
                type="datetime-local" className="input" value={pengaturan.ditutup}
                onChange={(e) => setPengaturan({ ...pengaturan, ditutup: e.target.value })}
              />
            </div>
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 10 }}>
            <label><input type="checkbox" checked={pengaturan.acakSoal} onChange={(e) => setPengaturan({ ...pengaturan, acakSoal: e.target.checked })} /> Acak urutan soal</label>
            <label><input type="checkbox" checked={pengaturan.acakOpsi} onChange={(e) => setPengaturan({ ...pengaturan, acakOpsi: e.target.checked })} /> Acak opsi jawaban</label>
            <label><input type="checkbox" checked={pengaturan.tampilkanKunci} onChange={(e) => setPengaturan({ ...pengaturan, tampilkanKunci: e.target.checked })} /> Tampilkan kunci setelah selesai</label>
          </div>
        </div>
      )}

      {isBank && (
        <>
          <label className="label" style={{ marginTop: 14 }}>Kategori bank</label>
          <select className="select" value={kategoriId} onChange={(e) => setKategoriId(e.target.value)}>
            <option value="">(tanpa kategori)</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.nama}</option>
            ))}
          </select>
        </>
      )}

      {/* ---------- AI ---------- */}
      <div style={{ marginTop: 14 }}>
        <button className="btn" onClick={bukaAi}>✨ Buat dengan AI</button>
        <span className="muted" style={{ marginLeft: 8 }}>
          AI menulis materi + kuisnya sekaligus dalam satu dokumen.
        </span>
      </div>
      {aiOpen && (
        <div className="card" style={{ marginTop: 10 }}>
          <h3 style={{ marginTop: 0 }}>✨ Buat Dokumen dengan AI</h3>
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
            <div>
              <label className="label">Jumlah soal kuis</label>
              <input type="number" min={1} max={30} className="input" value={aiJumlah} onChange={(e) => setAiJumlah(e.target.value)} />
            </div>
          </div>
          <label className="label">Topik</label>
          <input className="input" value={aiTopik} onChange={(e) => setAiTopik(e.target.value)} placeholder="mis. Pecahan senilai dan cara menyederhanakannya" />
          <label className="label">Instruksi tambahan (opsional)</label>
          <textarea className="textarea" rows={2} value={aiInstruksi} onChange={(e) => setAiInstruksi(e.target.value)} placeholder="mis. Kuisnya campur PG dan esai; materi pakai contoh soal cerita" />
          {aiMsg && <p className="muted" style={{ marginTop: 8 }}>{aiMsg}</p>}
          <button className="btn btn-primary" onClick={generateAi} disabled={aiBusy || aiSettings.length === 0} style={{ marginTop: 10 }}>
            {aiBusy ? "⏳ AI sedang menulis..." : "✨ Tulis Dokumen"}
          </button>
        </div>
      )}

      {/* ---------- pemilih bagian ---------- */}
      <label className="label" style={{ marginTop: 18 }}>Isi dokumen</label>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className={`btn${aktifMateri ? " btn-primary" : ""}`} onClick={() => toggleBagian("materi", !aktifMateri)}>
          📖 Bagian Materi {aktifMateri ? "✓" : ""}
        </button>
        <button className={`btn${aktifPg ? " btn-primary" : ""}`} onClick={() => toggleBagian("pg", !aktifPg)}>
          🧪 Soal Pilihan Ganda {aktifPg ? "✓" : ""}
        </button>
        <button className={`btn${aktifEsai ? " btn-primary" : ""}`} onClick={() => toggleBagian("esai", !aktifEsai)}>
          📝 Soal Esai {aktifEsai ? "✓" : ""}
        </button>
      </div>

      {/* ---------- bagian materi ---------- */}
      {aktifMateri && (
        <section className="card" style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>📖 Bagian Materi</h3>
            <div className="seg-toggle" role="tablist" aria-label="Mode bagian materi">
              <button className={modeMateri === "blok" ? "on" : ""} onClick={() => void strukturkanMateri(teksMateri)}>🧩 Mode Blok</button>
              <button className={modeMateri === "tcml" ? "on" : ""} onClick={() => setModeMateri("tcml")}>{"</>"} Mode TCML</button>
            </div>
          </div>
          {noticeMateri && <div className="alert" style={{ marginTop: 10 }}>{noticeMateri}</div>}
          <p style={{ marginTop: 10 }}>
            <span className="muted">Template: </span>
            {TEMPLATES.map((t) => (
              <button key={t.nama} className="btn btn-sm" style={{ marginRight: 6, marginBottom: 6 }} onClick={() => void pakaiTemplateMateri(t)}>
                {t.nama}
              </button>
            ))}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 16, marginTop: 8 }}>
            <div>
              {modeMateri === "blok" ? (
                <>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
                    <span className="muted">Akar dokumen:</span>
                    {(["MATERIAL", "EXERCISE", "PROJECT"] as RootJenis[]).map((r) => (
                      <button key={r} className={`btn btn-sm${rootJenis === r ? " btn-primary" : ""}`} onClick={() => gantiRoot(r)}>
                        {r === "MATERIAL" ? "📖 Materi" : r === "EXERCISE" ? "🎯 Latihan" : "🧩 Proyek"}
                      </button>
                    ))}
                  </div>
                  {blocks.map((b, idx) => (
                    <div key={b.id} className="card" style={{ padding: 12, marginBottom: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        <strong>{BLOK_META[b.jenis].ikon} {BLOK_META[b.jenis].label}</strong>
                        <span className="row-actions">
                          <button className="btn btn-sm" onClick={() => pindahBlok(b.id, -1)} disabled={idx === 0} title="Naik">↑</button>
                          <button className="btn btn-sm" onClick={() => pindahBlok(b.id, 1)} disabled={idx === blocks.length - 1} title="Turun">↓</button>
                          <button className="btn btn-sm btn-danger" onClick={() => terapkanBlok(blocks.filter((x) => x.id !== b.id))} title="Hapus blok">✕</button>
                        </span>
                      </div>
                      <BlokIsi blok={b} onChange={(patch) => ubahBlok(b.id, patch)} />
                    </div>
                  ))}
                  {blocks.length === 0 && <p className="muted">Belum ada blok. Tambahkan blok pertama lewat tombol di bawah.</p>}
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <span className="muted">Tambah blok:</span>
                    {BLOK_PER_ROOT[rootJenis]
                      .filter((j) => j !== "judul" || !adaJudul)
                      .map((j) => (
                        <button key={j} className="btn btn-sm" onClick={() => terapkanBlok([...blocks, blokBaru(j, idBerikut.current++)])}>
                          {BLOK_META[j].ikon} {BLOK_META[j].label}
                        </button>
                      ))}
                  </div>
                  <p className="muted" style={{ marginTop: 8 }}>
                    🧠 <strong>Cek Pemahaman</strong> = soal latihan sisipan di tengah bacaan (otomatis dinilai, masuk nilai materi). Soal untuk kuis/ujian berwaktu diisi di bagian Soal PG/Esai di bawah.
                  </p>
                </>
              ) : (
                <>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                    {SISIPAN.map((s) => (
                      <button key={s.label} type="button" className="btn btn-sm" onClick={() => sisipMateri(s)}>
                        ＋ {s.label}
                      </button>
                    ))}
                  </div>
                  <textarea
                    ref={taMateriRef}
                    className="textarea"
                    value={teksMateri}
                    onChange={(e) => onTeksMateriChange(e.target.value)}
                    rows={20}
                    spellCheck={false}
                    style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" }}
                  />
                </>
              )}
              {errorsMateri.length > 0 && (
                <div className="alert alert-error">
                  <strong>{errorsMateri.length} masalah pada bagian materi:</strong>
                  <ul style={{ marginLeft: 18 }}>
                    {errorsMateri.map((e, i) => (
                      <li key={i}>Baris {e.line}: {e.message}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <label className="label" style={{ marginTop: 0 }}>Pratinjau materi</label>
                <button type="button" className="btn btn-sm" onClick={() => runPreviewMateri(teksMateri)}>🔄 Refresh</button>
              </div>
              {previewHtml ? (
                <MaterialPreview html={previewHtml} cek={previewCek} className="card tcml" />
              ) : (
                <div className="card"><p className="muted">Pratinjau muncul setelah teks valid.</p></div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ---------- bagian kuis PG ---------- */}
      {aktifPg && (
        <section className="card" style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>🧪 Soal Pilihan Ganda</h3>
            <div className="seg-toggle" role="tablist" aria-label="Mode soal PG">
              <button
                className={modePg === "form" ? "on" : ""}
                onClick={async () => {
                  if (await uraiKartu(teksPg, "pilihan_ganda", setCardsPg, setErrorsPg)) setModePg("form");
                }}
              >
                📝 Formulir
              </button>
              <button className={modePg === "tcml" ? "on" : ""} onClick={() => setModePg("tcml")}>{"</>"} Mode TCML</button>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 16, marginTop: 10 }}>
            <div>
              {modePg === "form" ? (
                <DaftarKartuSoal cards={cardsPg} tipe="pilihan_ganda" onChange={sinkronKartuPg} />
              ) : (
                <textarea
                  className="textarea"
                  value={teksPg}
                  onChange={(e) => onTeksPgChange(e.target.value)}
                  rows={18}
                  spellCheck={false}
                  style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" }}
                />
              )}
              {errorsPg.length > 0 && (
                <div className="alert alert-error">
                  <strong>{errorsPg.length} masalah pada soal PG:</strong>
                  <ul style={{ marginLeft: 18 }}>
                    {errorsPg.map((e, i) => (
                      <li key={i}>Baris {e.line}: {e.message}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div>
              <label className="label" style={{ marginTop: 0 }}>Pratinjau soal PG</label>
              <PratinjauSoal questions={previewPg} />
            </div>
          </div>
        </section>
      )}

      {/* ---------- bagian kuis esai ---------- */}
      {aktifEsai && (
        <section className="card" style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>📝 Soal Esai</h3>
            <div className="seg-toggle" role="tablist" aria-label="Mode soal esai">
              <button
                className={modeEsai === "form" ? "on" : ""}
                onClick={async () => {
                  if (await uraiKartu(teksEsai, "teks", setCardsEsai, setErrorsEsai)) setModeEsai("form");
                }}
              >
                📝 Formulir
              </button>
              <button className={modeEsai === "tcml" ? "on" : ""} onClick={() => setModeEsai("tcml")}>{"</>"} Mode TCML</button>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 16, marginTop: 10 }}>
            <div>
              {modeEsai === "form" ? (
                <DaftarKartuSoal cards={cardsEsai} tipe="teks" onChange={sinkronKartuEsai} />
              ) : (
                <textarea
                  className="textarea"
                  value={teksEsai}
                  onChange={(e) => onTeksEsaiChange(e.target.value)}
                  rows={18}
                  spellCheck={false}
                  style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".86rem" }}
                />
              )}
              {errorsEsai.length > 0 && (
                <div className="alert alert-error">
                  <strong>{errorsEsai.length} masalah pada soal esai:</strong>
                  <ul style={{ marginLeft: 18 }}>
                    {errorsEsai.map((e, i) => (
                      <li key={i}>Baris {e.line}: {e.message}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div>
              <label className="label" style={{ marginTop: 0 }}>Pratinjau soal esai</label>
              <PratinjauSoal questions={previewEsai} />
            </div>
          </div>
        </section>
      )}

      {/* ---------- simpan ---------- */}
      <div className="row-actions" style={{ marginTop: 18 }}>
        <button className="btn btn-primary" onClick={onSave} disabled={saving || !judul.trim()}>
          {saving ? "Menyimpan..." : isBank ? "💾 Simpan Dokumen Bank" : "💾 Simpan Dokumen"}
        </button>
        {kotor && <span className="muted">● Ada perubahan belum tersimpan (draf tersimpan otomatis di perangkat ini)</span>}
      </div>
      <p className="muted" style={{ marginTop: 10 }}>
        Bagian dengan TCML tidak valid tidak bisa disimpan — perbaiki error yang ditampilkan di bagiannya.
      </p>
    </main>
  );
}

/* ============================================================ daftar kartu soal */
function DaftarKartuSoal({
  cards,
  tipe,
  onChange,
}: {
  cards: CardSoal[];
  tipe: "pilihan_ganda" | "teks";
  onChange: (next: CardSoal[]) => void;
}) {
  function ubah(i: number, patch: Partial<CardSoal>) {
    onChange(cards.map((c, x) => (x === i ? { ...c, ...patch } : c)));
  }
  function pindah(i: number, arah: -1 | 1) {
    const j = i + arah;
    if (j < 0 || j >= cards.length) return;
    const next = [...cards];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }
  return (
    <div>
      {cards.map((c, i) => (
        <div key={i} className="card" style={{ padding: 12, marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <strong>{c.konten ? "📖 Blok Pengantar" : `Soal ${cards.slice(0, i + 1).filter((x) => !x.konten).length}`}</strong>
            <span className="row-actions">
              <button className="btn btn-sm" onClick={() => pindah(i, -1)} disabled={i === 0} title="Naik">↑</button>
              <button className="btn btn-sm" onClick={() => pindah(i, 1)} disabled={i === cards.length - 1} title="Turun">↓</button>
              <button className="btn btn-sm btn-danger" onClick={() => onChange(cards.filter((_, x) => x !== i))} disabled={cards.length <= 1} title="Hapus soal">✕</button>
            </span>
          </div>
          {c.konten ? (
            <>
              <p className="muted" style={{ marginBottom: 8 }}>
                Teks ini tampil di kuis sebagai pengantar/selingan — bukan soal, tidak dinilai. Cocok untuk prolog cerita, bacaan, atau petunjuk di tengah kuis.
              </p>
              <select
                className="input"
                style={{ maxWidth: 220, marginBottom: 8 }}
                value={c.konten.tipe}
                onChange={(e) => ubah(i, { konten: { ...c.konten!, tipe: e.target.value as NonNullable<CardSoal["konten"]>["tipe"] } })}
              >
                <option value="paragraf">📄 Paragraf biasa</option>
                <option value="note">📝 Catatan</option>
                <option value="hint">💡 Petunjuk (hint)</option>
                <option value="example">📘 Contoh</option>
                <option value="warning">⚠️ Peringatan</option>
              </select>
              <textarea
                className="textarea"
                rows={3}
                value={c.konten.teks}
                placeholder="Tulis teks pengantarnya di sini..."
                onChange={(e) => ubah(i, { konten: { ...c.konten!, teks: e.target.value } })}
              />
            </>
          ) : (
            <>
          <textarea
            className="textarea"
            rows={2}
            value={c.pertanyaan}
            placeholder="Tulis pertanyaan..."
            onChange={(e) => ubah(i, { pertanyaan: e.target.value })}
          />
          {tipe === "pilihan_ganda" ? (
            <div style={{ marginTop: 8 }}>
              {c.opsi.map((o, j) => (
                <div key={j} style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={c.kunci.includes(j)}
                    title="Tandai sebagai jawaban benar (boleh lebih dari satu)"
                    onChange={(e) => {
                      const kunci = e.target.checked
                        ? [...c.kunci, j].sort((a, b) => a - b)
                        : c.kunci.filter((k) => k !== j);
                      ubah(i, { kunci });
                    }}
                  />
                  <span className="muted" style={{ minWidth: 16 }}>{HURUF[j]}.</span>
                  <input
                    className="input"
                    value={o}
                    placeholder={`Opsi ${HURUF[j]}`}
                    onChange={(e) => {
                      const opsi = [...c.opsi];
                      opsi[j] = e.target.value;
                      ubah(i, { opsi });
                    }}
                  />
                  <button
                    className="btn btn-sm"
                    onClick={() => ubah(i, {
                      opsi: c.opsi.filter((_, x) => x !== j),
                      kunci: c.kunci.filter((k) => k !== j).map((k) => (k > j ? k - 1 : k)),
                    })}
                    disabled={c.opsi.length <= 2}
                    title="Hapus opsi"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <button className="btn btn-sm" onClick={() => ubah(i, { opsi: [...c.opsi, ""] })} disabled={c.opsi.length >= 5}>
                  ➕ Opsi
                </button>
                <span className="muted">Centang kotak = jawaban benar (boleh lebih dari satu).</span>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: 8 }}>
              <label className="label">Jawaban referensi untuk guru (opsional)</label>
              <textarea
                className="textarea"
                rows={2}
                value={c.referensi}
                placeholder="Pedoman jawaban ideal saat menilai..."
                onChange={(e) => ubah(i, { referensi: e.target.value })}
              />
            </div>
          )}
          <div style={{ marginTop: 8, maxWidth: 160 }}>
            <label className="label">Bobot</label>
            <input
              type="number" min={0} step="0.5" className="input" value={c.bobot}
              onChange={(e) => ubah(i, { bobot: e.target.value })}
            />
          </div>
            </>
          )}
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="btn" onClick={() => onChange([...cards, kartuKosong()])}>
          ➕ Tambah Soal
        </button>
        <button className="btn" onClick={() => onChange([...cards, kartuKonten()])}>
          📖 ＋ Blok Pengantar
        </button>
      </div>
      <p className="muted" style={{ marginTop: 8 }}>
        📖 <strong>Blok Pengantar</strong> = teks di dalam kuis (prolog, bacaan, hint) — tampil mengikuti urutan kartu, bukan soal dan tidak dinilai.
      </p>
    </div>
  );
}

function PratinjauSoal({ questions }: { questions: ParsedQuestion[] }) {
  if (questions.length === 0) {
    return (
      <div className="card"><p className="muted">Pratinjau muncul setelah soal valid.</p></div>
    );
  }
  return (
    <div className="card">
      {questions.map((q, i) => (
        <div key={i} style={{ marginBottom: 14 }}>
          <p style={{ margin: 0 }}>
            <strong>{i + 1}.</strong> {q.pertanyaan}{" "}
            <span className="muted">(bobot {q.bobot})</span>
          </p>
          {q.options.length > 0 && (
            <ul style={{ margin: "6px 0 0 18px" }}>
              {q.options.map((o, j) => (
                <li key={j}>
                  {o.label}. {o.teks} {o.is_correct ? "✓" : ""}
                </li>
              ))}
            </ul>
          )}
          {q.jawaban_referensi && (
            <p className="muted" style={{ marginTop: 4 }}>Referensi: {q.jawaban_referensi}</p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ============================================================ isi blok materi */
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

export default function EditorDokumenPage() {
  return (
    <Suspense fallback={<main className="page"><p className="muted">Memuat editor...</p></main>}>
      <EditorDokumenInner />
    </Suspense>
  );
}
