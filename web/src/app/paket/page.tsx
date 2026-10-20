"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { API_BASE, apiFetch, getMe, type User } from "@/lib/api";

interface ModuleInfo {
  slug: string;
  nama: string;
  deskripsi: string | null;
  roots: string[];
  tags: string[];
  examples: { judul: string; konten: string }[];
}
interface Pack {
  id: number;
  nama: string;
  deskripsi: string | null;
  visibilitas: string;
  punya_saya: boolean;
  pemilik: { username: string; nama_lengkap: string | null } | null;
  modules: { slug: string; nama: string }[];
  allowed_roots: string[];
  dibagikan_ke_semua: boolean;
  shared_with_ids: number[];
}
interface Recipient {
  id: number;
  username: string;
  nama_lengkap: string | null;
  role: string;
}

export default function PaketPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [shared, setShared] = useState<Pack[]>([]);
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  // form buat/edit
  const [editId, setEditId] = useState<number | null>(null);
  const [nama, setNama] = useState("");
  const [deskripsi, setDeskripsi] = useState("");
  const [picked, setPicked] = useState<string[]>(["inti-materi"]);
  // panel bagikan
  const [shareFor, setShareFor] = useState<number | null>(null);
  const [shareMode, setShareMode] = useState<"private" | "all" | "users">("private");
  const [shareUsers, setShareUsers] = useState<number[]>([]);

  const load = useCallback(async () => {
    try {
      setModules(await apiFetch<ModuleInfo[]>("/api/v1/packs/modules"));
      setPacks(await apiFetch<Pack[]>("/api/v1/packs"));
      setShared(await apiFetch<Pack[]>("/api/v1/packs/shared"));
      setRecipients(await apiFetch<Recipient[]>("/api/v1/packs/recipients"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat paket.");
    }
  }, []);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else if (u.role === "siswa") router.push("/dashboard");
      else {
        setUser(u);
        load();
      }
    });
  }, [router, load]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  function toggleModule(slug: string) {
    setPicked((p) => (p.includes(slug) ? p.filter((s) => s !== slug) : [...p, slug]));
  }

  async function submitPack(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      if (editId) {
        await apiFetch(`/api/v1/packs/${editId}`, {
          method: "PATCH",
          body: { nama, deskripsi: deskripsi || null, module_slugs: picked },
        });
        setOk("Paket diperbarui.");
      } else {
        await apiFetch("/api/v1/packs", {
          method: "POST",
          body: { nama, deskripsi: deskripsi || null, module_slugs: picked },
        });
        setOk("Paket dibuat.");
      }
      setEditId(null);
      setNama("");
      setDeskripsi("");
      setPicked(["inti-materi"]);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan paket.");
    }
  }

  function startEdit(p: Pack) {
    setEditId(p.id);
    setNama(p.nama);
    setDeskripsi(p.deskripsi ?? "");
    setPicked(p.modules.map((m) => m.slug));
    setShareFor(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function remove(p: Pack) {
    if (!window.confirm(`Hapus paket "${p.nama}"?`)) return;
    await apiFetch(`/api/v1/packs/${p.id}`, { method: "DELETE" });
    setOk("Paket dihapus.");
    load();
  }

  async function fork(p: Pack) {
    try {
      await apiFetch(`/api/v1/packs/${p.id}/fork`, { method: "POST" });
      setOk(`Paket "${p.nama}" di-fork ke paket Anda.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mem-fork paket.");
    }
  }

  function openShare(p: Pack) {
    setShareFor(shareFor === p.id ? null : p.id);
    setShareMode(p.dibagikan_ke_semua ? "all" : p.shared_with_ids.length ? "users" : "private");
    setShareUsers(p.shared_with_ids);
  }

  async function submitShare(p: Pack) {
    try {
      await apiFetch(`/api/v1/packs/${p.id}/share`, {
        method: "PUT",
        body: { mode: shareMode, user_ids: shareUsers },
      });
      setOk("Pengaturan berbagi disimpan.");
      setShareFor(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan berbagi.");
    }
  }

  function packCard(p: Pack, mine: boolean) {
    return (
      <div className="card" key={p.id} style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <strong>{p.nama}</strong>
          <span className="badge">{p.visibilitas === "shared" ? "🔗 dibagikan" : "🔒 privat"}</span>
        </div>
        {p.deskripsi && <p className="muted" style={{ marginTop: 4 }}>{p.deskripsi}</p>}
        {!mine && p.pemilik && (
          <p className="muted">Pemilik: {p.pemilik.nama_lengkap ?? p.pemilik.username}</p>
        )}
        <div style={{ marginTop: 6 }}>
          {p.modules.map((m) => (
            <span key={m.slug} className="badge" style={{ marginRight: 6 }}>{m.nama}</span>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 4 }}>Root: {p.allowed_roots.join(", ") || "-"}</p>
        <div className="row-actions" style={{ marginTop: 8 }}>
          {mine && <button className="btn btn-sm" onClick={() => startEdit(p)}>✏️ Edit</button>}
          {mine && <button className="btn btn-sm" onClick={() => openShare(p)}>🔗 Bagikan</button>}
          <button className="btn btn-sm" onClick={() => fork(p)}>🍴 Fork</button>
          <a className="btn btn-sm" href={`${API_BASE}/api/v1/packs/${p.id}/export`}>⬇️ Ekspor .md</a>
          {mine && <button className="btn btn-sm btn-danger" onClick={() => remove(p)}>Hapus</button>}
        </div>
        {mine && shareFor === p.id && (
          <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
            <label className="label">Mode berbagi</label>
            <select className="select" style={{ maxWidth: 260 }} value={shareMode} onChange={(e) => setShareMode(e.target.value as typeof shareMode)}>
              <option value="private">Privat (hanya saya)</option>
              <option value="all">Semua guru</option>
              <option value="users">Guru tertentu</option>
            </select>
            {shareMode === "users" && (
              <div style={{ marginTop: 8 }}>
                {recipients.map((r) => (
                  <label key={r.id} style={{ display: "block" }}>
                    <input
                      type="checkbox"
                      checked={shareUsers.includes(r.id)}
                      onChange={(e) =>
                        setShareUsers(e.target.checked ? [...shareUsers, r.id] : shareUsers.filter((x) => x !== r.id))
                      }
                    />{" "}
                    {r.nama_lengkap ?? r.username} <span className="muted">(@{r.username}, {r.role})</span>
                  </label>
                ))}
                {recipients.length === 0 && <p className="muted">Belum ada guru/admin lain.</p>}
              </div>
            )}
            <button className="btn btn-sm btn-primary" style={{ marginTop: 10 }} onClick={() => submitShare(p)}>💾 Simpan Berbagi</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>🧩 Paket Parser</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Paket adalah komposisi modul tag TCML. Saat Generate AI, hanya spesifikasi modul dalam paket yang dikirim ke AI —
        hemat konteks dan hasil lebih patuh format. Paket bisa dibagikan ke guru lain dan diekspor sebagai file .md untuk LLM eksternal.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <div className="card" style={{ marginBottom: 14 }}>
        <h3>{editId ? "Edit Paket" : "Buat Paket Baru"}</h3>
        <form onSubmit={submitPack} style={{ marginTop: 10 }}>
          <label className="label">Nama paket</label>
          <input className="input" value={nama} onChange={(e) => setNama(e.target.value)} required placeholder="mis. Paket Kuis Matematika SD" />
          <label className="label">Deskripsi</label>
          <input className="input" value={deskripsi} onChange={(e) => setDeskripsi(e.target.value)} placeholder="opsional" />
          <label className="label">Modul yang dipakai</label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 8 }}>
            {modules.map((m) => (
              <label key={m.slug} className="card" style={{ cursor: "pointer", marginBottom: 0 }}>
                <input type="checkbox" checked={picked.includes(m.slug)} onChange={() => toggleModule(m.slug)} />{" "}
                <strong>{m.nama}</strong>
                <div className="muted">{m.deskripsi}</div>
                <div className="muted">Tag: {m.tags.join(", ")}</div>
              </label>
            ))}
          </div>
          <div className="row-actions" style={{ marginTop: 12 }}>
            <button className="btn btn-primary" type="submit" disabled={picked.length === 0}>
              {editId ? "💾 Simpan Perubahan" : "➕ Buat Paket"}
            </button>
            {editId && (
              <button className="btn" type="button" onClick={() => { setEditId(null); setNama(""); setDeskripsi(""); setPicked(["inti-materi"]); }}>
                Batal Edit
              </button>
            )}
          </div>
        </form>
      </div>

      <h3 style={{ margin: "18px 0 10px" }}>Paket Saya ({packs.length})</h3>
      {packs.map((p) => packCard(p, true))}
      {packs.length === 0 && <p className="muted">Belum ada paket. Buat paket pertama Anda di atas.</p>}

      <h3 style={{ margin: "18px 0 10px" }}>Dibagikan ke Saya ({shared.length})</h3>
      {shared.map((p) => packCard(p, false))}
      {shared.length === 0 && <p className="muted">Belum ada paket yang dibagikan ke Anda.</p>}
    </main>
  );
}
