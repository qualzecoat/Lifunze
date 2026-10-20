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

export default function MateriPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [material, setMaterial] = useState<Material | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setMaterial(await apiFetch<Material>(`/api/v1/materials/${params.id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat materi.");
    }
  }, [params.id]);

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
          <div className="card" style={{ marginTop: 14 }}>
            <h3>📎 Lampiran ({material.files.length})</h3>
            {material.files.map((f) => (
              <div key={f.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                <a href={`${API_BASE}/api/v1/files/${f.id}`} target="_blank" rel="noreferrer">
                  {f.original_filename} <span className="muted">{formatSize(f.size_bytes)}</span>
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
        </>
      )}
    </main>
  );
}
