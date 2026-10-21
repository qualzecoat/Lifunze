"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { API_BASE, apiFetch, getMe, type User } from "@/lib/api";

interface MaterialFile {
  id: number;
  original_filename: string;
  mime_type: string | null;
  size_bytes: number | null;
}
interface Material {
  id: number;
  meeting_id: number;
  subject_id: number | null;
  judul: string;
  teks_mentah: string;
  rendered_html: string | null;
  dibuat_oleh: number;
  files: MaterialFile[];
  grup_dokumen?: string | null;
  jenis?: string;
  tenggat?: string | null;
  dokumen_kuis?: {
    id: number;
    judul: string;
    tipe: string;
    dibuka_pada: string | null;
    ditutup_pada: string | null;
    durasi_menit: number | null;
  }[];
  navigasi?: {
    sebelumnya: { id: number; judul: string } | null;
    berikutnya: { id: number; judul: string } | null;
  } | null;
  cek?: {
    daftar: CekItem[];
    skor: { diperoleh: number; maksimal: number; persen: number } | null;
  };
}

interface CekItem {
  indeks: number;
  tipe: string;
  pertanyaan: string;
  bobot: number;
  multi?: boolean;
  options: { label: string; teks: string }[];
  kunci?: string[];
  jawaban_referensi?: string;
  jawabanku?: { jawaban: string; benar: boolean | null } | null;
}

function formatSize(n: number | null): string {
  if (!n) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

interface RubrikItem {
  kriteria: string;
  poin: number;
  maks: number;
  komentar?: string;
}
interface Submission {
  id: number;
  siswa: { id: number; username: string; nama_lengkap: string | null } | null;
  nama_file: string;
  catatan: string | null;
  skor: number | null;
  feedback_rubrik: { items?: RubrikItem[] } | null;
  updated_at: string | null;
}

export default function MateriPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [material, setMaterial] = useState<Material | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [sudahDibaca, setSudahDibaca] = useState(false);
  const [hemat, setHemat] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const articleRef = useRef<HTMLElement>(null);
  const [cekSlots, setCekSlots] = useState<HTMLElement[]>([]);
  const [skorCek, setSkorCek] = useState<{ diperoleh: number; maksimal: number; persen: number } | null>(null);

  // Panel Cek Pemahaman hidup di dalam placeholder [data-cek-index]
  // pada HTML materi — kumpulkan elemennya setelah materi termuat.
  useEffect(() => {
    if (!material || !articleRef.current) {
      setCekSlots([]);
      return;
    }
    setSkorCek(material.cek?.skor ?? null);
    const found = Array.from(articleRef.current.querySelectorAll<HTMLElement>("[data-cek-index]"));
    // Placeholder renderer hanya penanda posisi; kosongkan teksnya agar
    // tidak dobel dengan judul panel interaktif yang dipasang via portal.
    found.forEach((el) => el.replaceChildren());
    setCekSlots(found);
  }, [material]);

  const load = useCallback(async () => {
    try {
      setMaterial(await apiFetch<Material>(`/api/v1/materials/${params.id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat materi.");
    }
  }, [params.id]);

  useEffect(() => {
    setHemat(typeof window !== "undefined" && localStorage.getItem("lifunze-hemat") === "1");
    getMe().then((u) => {
      if (!u) router.push("/login");
      else {
        setUser(u);
        load();
        if (u.role === "siswa") {
          apiFetch(`/api/v1/materials/${params.id}/read`, { method: "POST" })
            .then(() => setSudahDibaca(true))
            .catch(() => {});
        }
      }
    });
  }, [router, load, params.id]);

  function toggleHemat(v: boolean) {
    setHemat(v);
    localStorage.setItem("lifunze-hemat", v ? "1" : "0");
  }

  // Render notasi [BLOCKS] menjadi blok Scratch visual (scratchblocks).
  // Bila CDN tidak terjangkau, notasi tetap tampil sebagai teks yang terbaca.
  useEffect(() => {
    if (!material?.rendered_html?.includes("scratchblocks")) return;
    const render = () => {
      const w = window as unknown as { scratchblocks?: { renderMatching: (sel: string, opts: Record<string, unknown>) => void } };
      try {
        w.scratchblocks?.renderMatching("pre.scratchblocks", {
          style: "scratch3",
          languages: ["en"],
        });
      } catch { /* abaikan: fallback teks */ }
    };
    const existing = document.getElementById("scratchblocks-js") as HTMLScriptElement | null;
    if (existing) {
      render();
      return;
    }
    const s = document.createElement("script");
    s.id = "scratchblocks-js";
    s.src = "https://scratchblocks.github.io/js/scratchblocks-v3.6-min.js";
    s.onload = render;
    document.body.appendChild(s);
  }, [material]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  const kelola = user.role === "admin" || (user.role === "guru" && material?.dibuat_oleh === user.id);

  async function upload() {
    const file = fileRef.current?.files?.[0];
    if (!file || !material) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await apiFetch(`/api/v1/materials/${material.id}/files`, { method: "POST", formData: fd });
      setOk("Lampiran terunggah.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload gagal.");
    }
  }

  async function deleteFile(f: MaterialFile) {
    if (!material) return;
    if (!window.confirm(`Hapus lampiran ${f.original_filename}?`)) return;
    await apiFetch(`/api/v1/materials/${material.id}/files/${f.id}`, { method: "DELETE" });
    load();
  }

  async function deleteMaterial() {
    if (!material) return;
    if (!window.confirm(`Hapus materi "${material.judul}"?`)) return;
    await apiFetch(`/api/v1/materials/${material.id}`, { method: "DELETE" });
    router.push(material.subject_id ? `/kelas/${material.subject_id}` : "/kelas");
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}
      {!material && !error && <p className="muted">Memuat materi...</p>}
      {material && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
            {material.subject_id && <Link href={`/kelas/${material.subject_id}`}>← Kembali ke Kelas</Link>}
            {kelola && (
              <span className="row-actions">
                {material.grup_dokumen ? (
                  <Link className="btn btn-sm" href={`/editor/dokumen?grup=${material.grup_dokumen}`}>✏️ Edit Dokumen</Link>
                ) : (
                  <Link className="btn btn-sm" href={`/editor/materi?material=${material.id}`}>✏️ Edit Materi</Link>
                )}
                <button className="btn btn-sm btn-danger" onClick={deleteMaterial}>Hapus</button>
              </span>
            )}
          </div>
          <article
            ref={articleRef}
            className="card tcml"
            dangerouslySetInnerHTML={{ __html: material.rendered_html ?? "" }}
          />
          {(material.cek?.daftar ?? []).map((item) => {
            const slot = cekSlots.find(
              (el) => el.dataset.cekIndex === String(item.indeks),
            );
            if (!slot) return null;
            return createPortal(
              <PanelCek
                key={item.indeks}
                materialId={material.id}
                item={item}
                peran={user.role === "siswa" ? "siswa" : "staf"}
                onSkorBaru={(s) => setSkorCek(s)}
              />,
              slot,
              `cek-${item.indeks}`,
            );
          })}
          {user.role === "siswa" && skorCek && (
            <p style={{ marginTop: 10 }}>
              <span className="badge">🧠 Nilai Cek Pemahaman materi ini: {skorCek.persen} (bobot {skorCek.diperoleh}/{skorCek.maksimal})</span>
            </p>
          )}
          {user.role === "siswa" && sudahDibaca && (
            <p style={{ marginTop: 10 }}><span className="badge">✓ Sudah dibaca — tercatat di progress Anda</span></p>
          )}
          <div className="card" style={{ marginTop: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <h3>📎 Lampiran ({material.files.length})</h3>
              <label className="muted">
                <input type="checkbox" checked={hemat} onChange={(e) => toggleHemat(e.target.checked)} />{" "}
                Mode hemat kuota (gambar dikompresi)
              </label>
            </div>
            {material.files.map((f) => (
              <div key={f.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                <a
                  href={`${API_BASE}/api/v1/files/${f.id}${hemat && (f.mime_type ?? "").startsWith("image/") ? "?hemat=true" : ""}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {f.original_filename} <span className="muted">{formatSize(f.size_bytes)}</span>
                  {hemat && (f.mime_type ?? "").startsWith("image/") && <span className="badge" style={{ marginLeft: 6 }}>hemat</span>}
                </a>
                {kelola && <button className="btn btn-sm btn-danger" onClick={() => deleteFile(f)}>Hapus</button>}
              </div>
            ))}
            {material.files.length === 0 && <p className="muted">Tidak ada lampiran.</p>}
            {kelola && (
              <div style={{ marginTop: 12 }}>
                <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.pdf,.mp4,.sb3" />{" "}
                <button className="btn btn-sm" onClick={upload}>Unggah Lampiran</button>
                <p className="muted">PNG/JPG/PDF/MP4/SB3 (proyek Scratch), maks 16 MB.</p>
              </div>
            )}
          </div>
          {material.jenis === "tugas" && material.tenggat && (
            <p style={{ marginTop: 10 }}>
              <span className="badge">⏰ Tenggat pengumpulan: {new Date(material.tenggat).toLocaleString("id-ID")}</span>
            </p>
          )}
          {material.dokumen_kuis && material.dokumen_kuis.length > 0 && (
            <div className="card" style={{ marginTop: 14, borderLeft: "4px solid var(--primary)" }}>
              <h3 style={{ marginTop: 0 }}>🧪 Kuis dalam Dokumen Ini</h3>
              {material.dokumen_kuis.map((q) => (
                <div
                  key={q.id}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap", padding: "6px 0" }}
                >
                  <span>
                    <strong>{q.judul}</strong>{" "}
                    <span className="muted">
                      · {q.tipe === "pilihan_ganda" ? "Pilihan Ganda" : "Esai"}
                      {q.durasi_menit ? ` · ${q.durasi_menit} menit` : ""}
                      {q.dibuka_pada ? ` · dibuka ${new Date(q.dibuka_pada).toLocaleString("id-ID")}` : ""}
                      {q.ditutup_pada ? ` · ditutup ${new Date(q.ditutup_pada).toLocaleString("id-ID")}` : ""}
                    </span>
                  </span>
                  <Link className="btn btn-primary btn-sm" href={`/kuis/${q.id}`}>
                    {user.role === "siswa" ? "Mulai Kuis →" : "Buka Kuis →"}
                  </Link>
                </div>
              ))}
              <p className="muted" style={{ marginTop: 6 }}>
                Kuis ini satu dokumen dengan materi di atas — nilainya tercatat terpisah di progress kelas.
              </p>
            </div>
          )}
          {kelola && (material.cek?.daftar.length ?? 0) > 0 && (
            <HasilCekCard materialId={material.id} />
          )}
          <SubmissionPanel materialId={material.id} user={user} kelola={!!kelola} />
          {material.navigasi && (material.navigasi.sebelumnya || material.navigasi.berikutnya) && (
            <nav
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 10,
                marginTop: 16,
                flexWrap: "wrap",
              }}
            >
              {material.navigasi.sebelumnya ? (
                <Link className="btn" href={`/materi/${material.navigasi.sebelumnya.id}`}>
                  ← Sebelumnya: {material.navigasi.sebelumnya.judul}
                </Link>
              ) : (
                <span />
              )}
              {material.navigasi.berikutnya ? (
                <Link className="btn btn-primary" href={`/materi/${material.navigasi.berikutnya.id}`}>
                  Berikutnya: {material.navigasi.berikutnya.judul} →
                </Link>
              ) : (
                <span />
              )}
            </nav>
          )}
        </>
      )}
    </main>
  );
}

/* ================================================= Panel Tugas [PROJECT] */
function SubmissionPanel({ materialId, user, kelola }: { materialId: number; user: User; kelola: boolean }) {
  const [isProject, setIsProject] = useState(false);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [catatan, setCatatan] = useState("");
  const [msg, setMsg] = useState("");
  const subFileRef = useRef<HTMLInputElement>(null);
  const [gradeFor, setGradeFor] = useState<number | null>(null);
  const [gSkor, setGSkor] = useState("");
  const [gItems, setGItems] = useState<RubrikItem[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ is_project: boolean; submissions: Submission[] }>(
        `/api/v1/materials/${materialId}/submissions`,
      );
      setIsProject(res.is_project);
      setSubs(res.submissions);
    } catch { /* abaikan */ }
  }, [materialId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!isProject) return null;

  async function uploadSubmission() {
    const file = subFileRef.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    if (catatan) fd.append("catatan", catatan);
    try {
      await apiFetch(`/api/v1/materials/${materialId}/submissions`, { method: "POST", formData: fd });
      setMsg("Tugas terkumpul. Mengumpulkan ulang akan menggantikan file sebelumnya dan mengosongkan nilai.");
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Gagal mengumpulkan tugas.");
    }
  }

  function openGrade(s: Submission) {
    setGradeFor(gradeFor === s.id ? null : s.id);
    setGSkor(s.skor !== null ? String(s.skor) : "");
    setGItems(s.feedback_rubrik?.items ?? [{ kriteria: "", poin: 0, maks: 0, komentar: "" }]);
  }

  async function submitGrade(s: Submission) {
    try {
      await apiFetch(`/api/v1/submissions/${s.id}/grade`, {
        method: "POST",
        body: {
          skor: Number(gSkor),
          feedback_rubrik: { items: gItems.filter((i) => i.kriteria.trim()) },
        },
      });
      setMsg("Nilai tersimpan; siswa menerima notifikasi.");
      setGradeFor(null);
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Gagal menyimpan nilai.");
    }
  }

  const mine = user.role === "siswa" ? subs[0] : undefined;

  return (
    <div className="card" style={{ marginTop: 14 }}>
      <h3>📤 Pengumpulan Tugas Proyek</h3>
      {msg && <div className="alert alert-ok" style={{ marginTop: 8 }}>{msg}</div>}

      {user.role === "siswa" && (
        <div style={{ marginTop: 10 }}>
          {mine ? (
            <div>
              <p>
                File terkumpul:{" "}
                <a href={`${API_BASE}/api/v1/submissions/${mine.id}/download`} target="_blank" rel="noreferrer">
                  {mine.nama_file}
                </a>{" "}
                <span className="muted">({mine.updated_at ? new Date(mine.updated_at).toLocaleString("id-ID") : ""})</span>
              </p>
              {mine.skor !== null ? (
                <div style={{ marginTop: 6 }}>
                  <p><strong>Skor: {mine.skor}</strong></p>
                  {(mine.feedback_rubrik?.items ?? []).map((it, i) => (
                    <p key={i} className="muted">
                      • {it.kriteria}: {it.poin}/{it.maks}{it.komentar ? ` — ${it.komentar}` : ""}
                    </p>
                  ))}
                </div>
              ) : (
                <p className="muted">Belum dinilai guru.</p>
              )}
            </div>
          ) : (
            <p className="muted">Anda belum mengumpulkan tugas ini.</p>
          )}
          <div style={{ marginTop: 10 }}>
            <input ref={subFileRef} type="file" accept=".png,.jpg,.jpeg,.pdf,.mp4,.zip,.txt,.sb3" />{" "}
            <input
              className="input"
              style={{ maxWidth: 240, display: "inline-block" }}
              placeholder="Catatan (opsional)"
              value={catatan}
              onChange={(e) => setCatatan(e.target.value)}
            />{" "}
            <button className="btn btn-sm btn-primary" onClick={uploadSubmission}>
              {mine ? "Kumpulkan Ulang" : "Kumpulkan Tugas"}
            </button>
            <p className="muted">PNG/JPG/PDF/MP4/ZIP/TXT/SB3 (Scratch), maks 16 MB.</p>
          </div>
        </div>
      )}

      {kelola && (
        <div style={{ marginTop: 10 }}>
          {subs.length === 0 && <p className="muted">Belum ada siswa yang mengumpulkan.</p>}
          {subs.map((s) => (
            <div key={s.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <span>
                  <strong>{s.siswa?.nama_lengkap ?? s.siswa?.username}</strong> —{" "}
                  <a href={`${API_BASE}/api/v1/submissions/${s.id}/download`} target="_blank" rel="noreferrer">{s.nama_file}</a>
                  {s.catatan && <span className="muted"> · “{s.catatan}”</span>}
                </span>
                <span className="row-actions">
                  <span className="badge">{s.skor !== null ? `Skor ${s.skor}` : "belum dinilai"}</span>
                  <button className="btn btn-sm" onClick={() => openGrade(s)}>Nilai</button>
                </span>
              </div>
              {gradeFor === s.id && (
                <div style={{ marginTop: 8 }}>
                  <label className="label">Skor total (0–100)</label>
                  <input className="input" style={{ maxWidth: 140 }} type="number" min={0} max={100} value={gSkor} onChange={(e) => setGSkor(e.target.value)} />
                  <label className="label">Rincian rubrik</label>
                  {gItems.map((it, i) => (
                    <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
                      <input className="input" style={{ maxWidth: 180 }} placeholder="Kriteria" value={it.kriteria} onChange={(e) => { const n = [...gItems]; n[i] = { ...n[i], kriteria: e.target.value }; setGItems(n); }} />
                      <input className="input" style={{ maxWidth: 80 }} type="number" placeholder="Poin" value={it.poin} onChange={(e) => { const n = [...gItems]; n[i] = { ...n[i], poin: Number(e.target.value) }; setGItems(n); }} />
                      <input className="input" style={{ maxWidth: 80 }} type="number" placeholder="Maks" value={it.maks} onChange={(e) => { const n = [...gItems]; n[i] = { ...n[i], maks: Number(e.target.value) }; setGItems(n); }} />
                      <input className="input" style={{ maxWidth: 220 }} placeholder="Komentar" value={it.komentar ?? ""} onChange={(e) => { const n = [...gItems]; n[i] = { ...n[i], komentar: e.target.value }; setGItems(n); }} />
                    </div>
                  ))}
                  <div className="row-actions">
                    <button className="btn btn-sm" onClick={() => setGItems([...gItems, { kriteria: "", poin: 0, maks: 0, komentar: "" }])}>➕ Kriteria</button>
                    <button className="btn btn-sm btn-primary" onClick={() => submitGrade(s)}>💾 Simpan Nilai</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Panel satu soal Cek Pemahaman — dirender lewat portal ke placeholder
 * [data-cek-index] di dalam HTML materi. PG dinilai seketika oleh server;
 * esai membuka referensi setelah siswa menjawab (cek mandiri). */
function PanelCek({
  materialId,
  item,
  peran,
  onSkorBaru,
}: {
  materialId: number;
  item: CekItem;
  peran: "siswa" | "staf";
  onSkorBaru: (skor: { diperoleh: number; maksimal: number; persen: number } | null) => void;
}) {
  const [pilihan, setPilihan] = useState<string[]>(
    item.jawabanku && item.tipe === "pilihan_ganda"
      ? item.jawabanku.jawaban.split(",").map((s) => s.trim()).filter(Boolean)
      : [],
  );
  const [teksJawaban, setTeksJawaban] = useState(
    item.jawabanku && item.tipe === "teks" ? item.jawabanku.jawaban : "",
  );
  const [benar, setBenar] = useState<boolean | null>(item.jawabanku?.benar ?? null);
  const [kunci, setKunci] = useState<string[] | null>(null);
  const [referensi, setReferensi] = useState<string | null>(item.jawaban_referensi ?? null);
  const [sibuk, setSibuk] = useState(false);
  const [pesan, setPesan] = useState("");
  const sudahJawab = item.jawabanku != null || benar !== null || referensi !== null;

  async function kirim() {
    const jawaban = item.tipe === "pilihan_ganda" ? pilihan.join(",") : teksJawaban.trim();
    if (!jawaban) {
      setPesan(item.tipe === "pilihan_ganda" ? "Pilih jawaban dulu." : "Tulis jawaban dulu.");
      return;
    }
    setSibuk(true);
    setPesan("");
    try {
      const r = await apiFetch<{
        benar: boolean | null;
        kunci?: string[];
        jawaban_referensi?: string;
        skor: { diperoleh: number; maksimal: number; persen: number } | null;
      }>(`/api/v1/materials/${materialId}/cek/${item.indeks}/jawab`, {
        method: "POST",
        body: { jawaban },
      });
      setBenar(r.benar);
      if (r.kunci) setKunci(r.kunci);
      if (r.jawaban_referensi) setReferensi(r.jawaban_referensi);
      onSkorBaru(r.skor);
    } catch (err) {
      setPesan(err instanceof Error ? err.message : "Gagal mengirim jawaban.");
    } finally {
      setSibuk(false);
    }
  }

  const gaya: React.CSSProperties = {
    border: "2px dashed #FFB020",
    background: "#FFFBEB",
    borderRadius: 12,
    padding: 14,
    margin: "14px 0",
  };

  if (peran === "staf") {
    return (
      <div style={gaya}>
        <p style={{ margin: "0 0 6px" }}>
          <strong>🧠 Cek Pemahaman {item.indeks + 1}</strong>{" "}
          <span className="badge">bobot {item.bobot}</span>
        </p>
        <p style={{ margin: "0 0 6px" }}>{item.pertanyaan}</p>
        {item.tipe === "pilihan_ganda" ? (
          <ul style={{ margin: "0 0 0 18px" }}>
            {item.options.map((o) => (
              <li key={o.label} style={{ color: item.kunci?.includes(o.label) ? "var(--ok)" : undefined }}>
                {o.label}. {o.teks} {item.kunci?.includes(o.label) ? "✅" : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ margin: 0 }}>Referensi: {item.jawaban_referensi}</p>
        )}
      </div>
    );
  }

  return (
    <div style={gaya}>
      <p style={{ margin: "0 0 6px" }}>
        <strong>🧠 Cek Pemahaman {item.indeks + 1}</strong>{" "}
        <span className="badge">latihan · boleh diulang</span>{" "}
        <span className="badge">bobot {item.bobot}</span>
      </p>
      <p style={{ margin: "0 0 8px" }}>{item.pertanyaan}</p>
      {item.tipe === "pilihan_ganda" ? (
        <div>
          {item.options.map((o) => {
            const aktif = pilihan.includes(o.label);
            return (
              <label key={o.label} style={{ display: "block", padding: "4px 0", cursor: "pointer" }}>
                <input
                  type={item.multi ? "checkbox" : "radio"}
                  name={`cek-${materialId}-${item.indeks}`}
                  checked={aktif}
                  onChange={() => {
                    setBenar(null);
                    setKunci(null);
                    setPilihan(item.multi
                      ? (aktif ? pilihan.filter((p) => p !== o.label) : [...pilihan, o.label])
                      : [o.label]);
                  }}
                />{" "}
                <strong>{o.label}.</strong> {o.teks}
              </label>
            );
          })}
          {item.multi && <p className="muted" style={{ margin: "4px 0" }}>Soal ini punya lebih dari satu jawaban benar — pilih semuanya.</p>}
        </div>
      ) : (
        <textarea
          className="textarea"
          rows={3}
          placeholder="Tulis jawabanmu dengan bahasamu sendiri..."
          value={teksJawaban}
          onChange={(e) => setTeksJawaban(e.target.value)}
        />
      )}
      <div className="row-actions" style={{ marginTop: 8 }}>
        <button className="btn btn-sm btn-primary" onClick={kirim} disabled={sibuk}>
          {sibuk ? "Memeriksa..." : sudahJawab ? "Jawab Ulang" : "Periksa Jawaban"}
        </button>
        {benar === true && <span className="badge">✅ Benar!</span>}
        {benar === false && <span className="badge badge-off">❌ Belum tepat — coba lagi</span>}
      </div>
      {pesan && <p className="muted" style={{ marginTop: 6 }}>{pesan}</p>}
      {item.tipe === "pilihan_ganda" && kunci && (
        <p style={{ marginTop: 8 }}>
          Kunci: <strong>{kunci.join(", ")}</strong>
        </p>
      )}
      {item.tipe === "teks" && referensi && (
        <div style={{ marginTop: 8, background: "#fff", border: "1px solid var(--border)", borderRadius: 8, padding: 10 }}>
          <strong>📖 Jawaban referensi — bandingkan dengan jawabanmu:</strong>
          <p style={{ margin: "4px 0 0" }}>{referensi}</p>
        </div>
      )}
    </div>
  );
}

/** Ringkasan hasil Cek Pemahaman kelas ini untuk guru/admin. */
function HasilCekCard({ materialId }: { materialId: number }) {
  const [data, setData] = useState<{
    total_cek: number;
    siswa: { siswa_id: number; nama: string; terjawab: number; total: number; skor_persen: number | null }[];
  } | null>(null);
  useEffect(() => {
    apiFetch(`/api/v1/materials/${materialId}/cek/hasil`)
      .then((d) => setData(d as typeof data))
      .catch(() => {});
  }, [materialId]);
  if (!data) return null;
  return (
    <div className="card" style={{ marginTop: 14 }}>
      <h3>🧠 Hasil Cek Pemahaman</h3>
      <table className="table" style={{ marginTop: 8 }}>
        <thead>
          <tr><th>Siswa</th><th>Terjawab</th><th>Nilai Materi (PG)</th></tr>
        </thead>
        <tbody>
          {data.siswa.map((s) => (
            <tr key={s.siswa_id}>
              <td>{s.nama}</td>
              <td>{s.terjawab}/{s.total}</td>
              <td>{s.skor_persen !== null ? s.skor_persen : "—"}</td>
            </tr>
          ))}
          {data.siswa.length === 0 && (
            <tr><td colSpan={3} className="muted">Belum ada siswa terdaftar.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
