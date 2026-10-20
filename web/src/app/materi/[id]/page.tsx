"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
                <Link className="btn btn-sm" href={`/editor/materi?material=${material.id}`}>✏️ Edit Materi</Link>
                <button className="btn btn-sm btn-danger" onClick={deleteMaterial}>Hapus</button>
              </span>
            )}
          </div>
          <article
            className="card tcml"
            dangerouslySetInnerHTML={{ __html: material.rendered_html ?? "" }}
          />
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
                <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.pdf,.mp4" />{" "}
                <button className="btn btn-sm" onClick={upload}>Unggah Lampiran</button>
                <p className="muted">PNG/JPG/PDF/MP4, maks 16 MB.</p>
              </div>
            )}
          </div>
          <SubmissionPanel materialId={material.id} user={user} kelola={!!kelola} />
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
