"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { API_BASE, apiFetch, getMe, type User } from "@/lib/api";

interface TagMeta {
  tag: string;
  nama: string;
  desc: string;
  wajib: boolean;
  spec: string;
  contoh: string;
  jenis: "material" | "kuis-pg" | "kuis-esai";
}
interface ModuleInfo {
  slug: string;
  nama: string;
  deskripsi: string | null;
  ikon: string;
  roots: string[];
  tags: string[];
  tags_meta: TagMeta[];
  examples: { judul: string; konten: string; jenis: "material" | "kuis-pg" | "kuis-esai" }[];
}
interface Pack {
  id: number;
  nama: string;
  deskripsi: string | null;
  visibilitas: string;
  punya_saya: boolean;
  pemilik: { username: string; nama_lengkap: string | null } | null;
  modules: { slug: string; nama: string }[];
  tag_pilihan: Record<string, string[]> | null;
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
interface ParsedQ {
  pertanyaan: string;
  options: { teks: string; is_correct: boolean }[];
  bobot?: number;
  jawaban_referensi?: string;
}
type Selection = Record<string, string[]>;

/* ---------------------------------- render contoh hidup (parse asli) */
const contohCache = new Map<string, Promise<{ html?: string; questions?: ParsedQ[]; gagal?: boolean }>>();

function ambilContoh(jenis: string, konten: string) {
  const kunci = jenis + "::" + konten;
  let p = contohCache.get(kunci);
  if (!p) {
    p = (async () => {
      try {
        if (jenis === "material") {
          const res = await apiFetch<{ success: boolean; content: string | null }>(
            "/api/v1/parse/content",
            { method: "POST", body: { teks: konten, jenis: "material" } },
          );
          return res.success ? { html: res.content ?? "" } : { gagal: true };
        }
        const res = await apiFetch<{ success: boolean; content: { questions: ParsedQ[] } | null }>(
          "/api/v1/parse/quiz",
          { method: "POST", body: { teks: konten, tipe: jenis === "kuis-pg" ? "pilihan_ganda" : "teks" } },
        );
        return res.success && res.content ? { questions: res.content.questions } : { gagal: true };
      } catch {
        return { gagal: true };
      }
    })();
    contohCache.set(kunci, p);
  }
  return p;
}

function ContohRender({ jenis, konten }: { jenis: string; konten: string }) {
  const [state, setState] = useState<{ html?: string; questions?: ParsedQ[]; gagal?: boolean } | null>(null);
  useEffect(() => {
    let hidup = true;
    setState(null);
    ambilContoh(jenis, konten).then((r) => {
      if (hidup) setState(r);
    });
    return () => {
      hidup = false;
    };
  }, [jenis, konten]);

  if (!state) return <p className="muted">Memuat contoh…</p>;
  if (state.gagal) return <p className="muted">Contoh tidak dapat dirender.</p>;
  if (state.html !== undefined) {
    return <article className="tcml" dangerouslySetInnerHTML={{ __html: state.html }} />;
  }
  return (
    <div>
      {(state.questions ?? []).map((q, i) => (
        <div key={i} className="card" style={{ marginBottom: 10 }}>
          <strong>
            {i + 1}. {q.pertanyaan}
          </strong>
          {q.bobot && q.bobot !== 1 ? <span className="badge" style={{ marginLeft: 8 }}>bobot {q.bobot}</span> : null}
          {q.options.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {q.options.map((o, j) => (
                <div key={j}>
                  {String.fromCharCode(65 + j)}. {o.teks}
                  {o.is_correct && <span style={{ color: "var(--ok)", fontWeight: 700 }}> 🔑</span>}
                </div>
              ))}
            </div>
          )}
          {q.jawaban_referensi && (
            <p className="muted" style={{ marginTop: 6 }}>
              🔑 <strong>Jawaban referensi:</strong> {q.jawaban_referensi}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- halaman */
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
  const [mode, setMode] = useState<"mudah" | "lanjut">("mudah");
  const [sel, setSel] = useState<Selection>({});
  const [contohSlug, setContohSlug] = useState<string | null>(null);
  const [openTag, setOpenTag] = useState<string | null>(null);
  const [cari, setCari] = useState("");
  const [specPreview, setSpecPreview] = useState<{ spec: string; karakter: number } | null>(null);
  const [ujiKind, setUjiKind] = useState<"materi" | "kuis_pg" | "kuis_esai">("materi");
  const [ujiTeks, setUjiTeks] = useState(
    "[MATERIAL]\n[TITLE]Uji Coba[/TITLE]\n[PARAGRAPH]Contoh isi.[/PARAGRAPH]\n[/MATERIAL]",
  );
  const [ujiHasil, setUjiHasil] = useState<{ valid: boolean; errors: { lapis: string; message: string }[] } | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // panel bagikan
  const [shareFor, setShareFor] = useState<number | null>(null);
  const [shareMode, setShareMode] = useState<"private" | "all" | "users">("private");
  const [shareUsers, setShareUsers] = useState<number[]>([]);

  const load = useCallback(async () => {
    try {
      const mods = await apiFetch<ModuleInfo[]>("/api/v1/packs/modules");
      setModules(mods);
      setSel((prev) => {
        if (Object.keys(prev).length > 0) return prev;
        const inti = mods.find((m) => m.slug === "inti-materi");
        return inti ? { "inti-materi": [...inti.tags] } : {};
      });
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

  /* ---- turunan pilihan ---- */
  const moduleBySlug = useCallback(
    (slug: string) => modules.find((m) => m.slug === slug),
    [modules],
  );
  const selectedSlugs = modules.filter((m) => (sel[m.slug] ?? []).length > 0).map((m) => m.slug);
  const totalTags = selectedSlugs.reduce((n, s) => n + (sel[s] ?? []).length, 0);
  const isClassic =
    selectedSlugs.length > 0 &&
    selectedSlugs.every((s) => (sel[s] ?? []).length === (moduleBySlug(s)?.tags.length ?? -1));
  const selectionPayload = useCallback((): { module_slugs: string[]; tag_pilihan: Selection | null } => {
    const slugs = modules.filter((m) => (sel[m.slug] ?? []).length > 0).map((m) => m.slug);
    const classic =
      slugs.length > 0 &&
      slugs.every((s) => (sel[s] ?? []).length === (moduleBySlug(s)?.tags.length ?? -1));
    if (classic) return { module_slugs: slugs, tag_pilihan: null };
    const tp: Selection = {};
    slugs.forEach((s) => {
      tp[s] = sel[s];
    });
    return { module_slugs: slugs, tag_pilihan: tp };
  }, [modules, sel, moduleBySlug]);

  /* ---- pratinjau spec (debounce) ---- */
  useEffect(() => {
    if (!user || modules.length === 0) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const payload = selectionPayload();
        if (payload.module_slugs.length === 0) {
          setSpecPreview({ spec: "", karakter: 0 });
          return;
        }
        const res = await apiFetch<{ spec: string; karakter: number }>("/api/v1/packs/preview-spec", {
          method: "POST",
          body: payload,
        });
        setSpecPreview(res);
      } catch {
        /* abaikan */
      }
    }, 400);
  }, [sel, modules, user, selectionPayload]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  /* ---- aksi pilihan ---- */
  function toggleModule(slug: string) {
    const m = moduleBySlug(slug);
    if (!m) return;
    setSel((prev) => {
      const next = { ...prev };
      if ((next[slug] ?? []).length > 0) delete next[slug];
      else next[slug] = [...m.tags];
      return next;
    });
    setUjiHasil(null);
  }

  function toggleTag(slug: string, tag: string, on: boolean) {
    setSel((prev) => {
      const cur = new Set(prev[slug] ?? []);
      if (on) cur.add(tag);
      else cur.delete(tag);
      const next = { ...prev };
      const m = moduleBySlug(slug);
      const ordered = (m?.tags ?? []).filter((t) => cur.has(t));
      if (ordered.length > 0) next[slug] = ordered;
      else delete next[slug];
      return next;
    });
    setUjiHasil(null);
  }

  function groupToggle(slug: string, on: boolean) {
    const m = moduleBySlug(slug);
    if (!m) return;
    setSel((prev) => {
      const next = { ...prev };
      if (on) next[slug] = [...m.tags];
      else delete next[slug];
      return next;
    });
    setUjiHasil(null);
  }

  function resetForm() {
    setEditId(null);
    setNama("");
    setDeskripsi("");
    const inti = moduleBySlug("inti-materi");
    setSel(inti ? { "inti-materi": [...inti.tags] } : {});
    setMode("mudah");
    setContohSlug(null);
    setOpenTag(null);
    setUjiHasil(null);
  }

  async function submitPack(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const payload = { nama, deskripsi: deskripsi || null, ...selectionPayload() };
      if (editId) {
        await apiFetch(`/api/v1/packs/${editId}`, { method: "PATCH", body: payload });
        setOk("Paket diperbarui.");
      } else {
        await apiFetch("/api/v1/packs", { method: "POST", body: payload });
        setOk("Paket dibuat.");
      }
      resetForm();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan paket.");
    }
  }

  function startEdit(p: Pack) {
    setEditId(p.id);
    setNama(p.nama);
    setDeskripsi(p.deskripsi ?? "");
    const next: Selection = {};
    if (p.tag_pilihan) {
      Object.entries(p.tag_pilihan).forEach(([slug, tags]) => {
        next[slug] = [...tags];
      });
    } else {
      p.modules.forEach((pm) => {
        const m = moduleBySlug(pm.slug);
        if (m) next[pm.slug] = [...m.tags];
      });
    }
    setSel(next);
    const classic =
      Object.keys(next).length > 0 &&
      Object.entries(next).every(
        ([slug, tags]) => tags.length === (moduleBySlug(slug)?.tags.length ?? -1),
      );
    setMode(p.tag_pilihan && !classic ? "lanjut" : "mudah");
    setShareFor(null);
    setUjiHasil(null);
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

  async function jalankanUji() {
    setError("");
    try {
      const res = await apiFetch<{ valid: boolean; errors: { lapis: string; message: string }[] }>(
        "/api/v1/packs/test",
        { method: "POST", body: { kind: ujiKind, teks: ujiTeks, ...selectionPayload() } },
      );
      setUjiHasil(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Meja uji gagal.");
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
          {p.tag_pilihan && <span className="badge" style={{ marginRight: 6 }}>🎛️ pilihan per parser</span>}
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

  const contohModul = contohSlug ? moduleBySlug(contohSlug) : undefined;
  const q = cari.trim().toLowerCase();

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>🧩 Paket Parser</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Paket menentukan format apa saja yang boleh dibuat AI untuk Anda. Saat Generate AI, hanya spesifikasi
        dalam paket yang dikirim ke AI — hemat konteks dan hasil lebih patuh format. Paket bisa dibagikan ke
        guru lain dan diekspor sebagai file .md untuk LLM eksternal.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <div className="card" style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
          <h3 style={{ margin: 0 }}>{editId ? "Edit Paket" : "Buat Paket Baru"}</h3>
          <div className="seg-toggle" role="tablist" aria-label="Mode penyusunan">
            <button type="button" className={mode === "mudah" ? "on" : ""} onClick={() => setMode("mudah")}>🌱 Mode Mudah</button>
            <button type="button" className={mode === "lanjut" ? "on" : ""} onClick={() => setMode("lanjut")}>🛠️ Mode Lanjutan</button>
          </div>
        </div>
        <form onSubmit={submitPack} style={{ marginTop: 10 }}>
          <label className="label">Nama paket</label>
          <input className="input" value={nama} onChange={(e) => setNama(e.target.value)} required placeholder="mis. Paket Kuis Matematika SD" />
          <label className="label">Deskripsi</label>
          <input className="input" value={deskripsi} onChange={(e) => setDeskripsi(e.target.value)} placeholder="opsional" />

          {mode === "mudah" ? (
            <>
              <label className="label">Pilih modul — klik kartu untuk memakai modulnya</label>
              <div className="modgrid">
                {modules.map((m) => {
                  const aktif = (sel[m.slug] ?? []).length > 0;
                  const sebagian = aktif && (sel[m.slug] ?? []).length < m.tags.length;
                  return (
                    <div
                      key={m.slug}
                      className={`modcard${aktif ? " on" : ""}`}
                      onClick={() => toggleModule(m.slug)}
                      role="button"
                      aria-pressed={aktif}
                    >
                      <div className="check-badge">✓</div>
                      <div className="modcard-ikon">{m.ikon}</div>
                      <div className="modcard-nama">{m.nama}</div>
                      <div className="modcard-desc">{m.deskripsi}</div>
                      <div className="modcard-ft">
                        <span className="muted" style={{ fontSize: ".8rem", fontWeight: 600 }}>
                          {m.tags.length} parser{sebagian ? " · sebagian dipilih (Mode Lanjutan)" : ""}
                        </span>
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setContohSlug(contohSlug === m.slug ? null : m.slug);
                          }}
                        >
                          👁 Contoh
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
              {contohModul && (
                <div className="card" style={{ marginTop: 14, marginBottom: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <strong>Contoh hasil — {contohModul.nama}</strong>
                    <button type="button" className="btn btn-sm" onClick={() => setContohSlug(null)}>Tutup ✕</button>
                  </div>
                  <p className="muted" style={{ marginTop: 2 }}>
                    Seperti inilah dokumen yang akan dibuat AI bila modul ini dipakai dalam paket.
                  </p>
                  {contohModul.examples.map((ex, i) => (
                    <div key={i} style={{ marginTop: 10 }}>
                      <ContohRender jenis={ex.jenis} konten={ex.konten} />
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <>
              <label className="label">Semua parser — nyalakan/matikan satu per satu</label>
              <input
                className="input"
                placeholder="🔎 Cari parser… coba: tabel, peringatan, soal"
                value={cari}
                onChange={(e) => setCari(e.target.value)}
                style={{ marginBottom: 10 }}
              />
              {modules.map((m) => {
                const cocok = m.tags_meta.filter(
                  (t) =>
                    !q ||
                    t.nama.toLowerCase().includes(q) ||
                    t.tag.toLowerCase().includes(q) ||
                    t.desc.toLowerCase().includes(q),
                );
                if (q && cocok.length === 0) return null;
                return (
                  <div key={m.slug} className="card" style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                      <strong>{m.ikon} {m.nama}</strong>
                      <span>
                        <button type="button" className="btn btn-sm" onClick={() => groupToggle(m.slug, true)}>Pilih semua</button>{" "}
                        <button type="button" className="btn btn-sm" onClick={() => groupToggle(m.slug, false)}>Kosongkan</button>
                      </span>
                    </div>
                    {(q ? cocok : m.tags_meta).map((t) => {
                      const kunci = `${m.slug}:${t.tag}`;
                      const aktif = (sel[m.slug] ?? []).includes(t.tag);
                      const terbuka = openTag === kunci;
                      return (
                        <div key={t.tag} style={{ borderTop: "1px solid var(--border)", padding: "10px 0" }}>
                          <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                            <input
                              type="checkbox"
                              checked={aktif}
                              onChange={(e) => toggleTag(m.slug, t.tag, e.target.checked)}
                              style={{ width: 19, height: 19, marginTop: 2, accentColor: "var(--primary)" }}
                            />
                            <div style={{ flex: 1 }}>
                              <strong>{t.nama}</strong>{" "}
                              <span className="tagcode">[{t.tag}]</span>
                              {t.wajib && <span className="badge" style={{ marginLeft: 6 }}>disarankan wajib</span>}
                              <div className="muted">{t.desc}</div>
                              {t.wajib && !aktif && (
                                <div className="alert alert-error" style={{ marginTop: 6, padding: "6px 10px" }}>
                                  ⚠️ Parser ini biasanya wajib untuk jenis dokumennya — mematikannya bisa membuat paket menghasilkan dokumen rusak.
                                </div>
                              )}
                            </div>
                            <button
                              type="button"
                              className="btn btn-sm"
                              onClick={() => setOpenTag(terbuka ? null : kunci)}
                            >
                              {terbuka ? "Tutup" : "👁 Contoh"}
                            </button>
                          </div>
                          {terbuka && (
                            <div style={{ margin: "10px 0 2px 29px" }}>
                              <p className="muted" style={{ marginBottom: 4 }}>Ditulis seperti ini:</p>
                              <pre className="codebox">{t.contoh}</pre>
                              <p className="muted" style={{ margin: "8px 0 4px" }}>Hasilnya seperti ini:</p>
                              <ContohRender jenis={t.jenis} konten={t.contoh} />
                              <p className="muted" style={{ marginTop: 8 }}>
                                📤 <strong>Spec untuk AI:</strong> {t.spec}
                              </p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}

              <div className="card" style={{ marginBottom: 10 }}>
                <strong>🔍 Pratinjau Prompt</strong>
                <p className="muted">Teks spec persis yang akan dikirim ke AI untuk pilihan saat ini.</p>
                <pre className="codebox" style={{ maxHeight: 300, overflow: "auto" }}>
                  {specPreview?.spec || "(belum ada pilihan)"}
                </pre>
                {specPreview && (
                  <p className="muted" style={{ marginTop: 6 }}>
                    Panjang spec: {specPreview.karakter.toLocaleString("id-ID")} karakter · {totalTags} parser aktif —
                    makin pendek spec, makin hemat &amp; fokus AI-nya.
                  </p>
                )}
              </div>

              <div className="card" style={{ marginBottom: 0 }}>
                <strong>🧪 Meja Uji</strong>
                <p className="muted">Tempel contoh TCML, lalu uji apakah ia lolos aturan paket ini.</p>
                <label className="label">Jenis dokumen</label>
                <select className="select" style={{ maxWidth: 240 }} value={ujiKind} onChange={(e) => setUjiKind(e.target.value as typeof ujiKind)}>
                  <option value="materi">Materi / Latihan / Proyek</option>
                  <option value="kuis_pg">Kuis Pilihan Ganda</option>
                  <option value="kuis_esai">Kuis Esai</option>
                </select>
                <label className="label">Teks TCML</label>
                <textarea className="input" rows={7} value={ujiTeks} onChange={(e) => setUjiTeks(e.target.value)} style={{ fontFamily: "ui-monospace, monospace" }} />
                <div style={{ marginTop: 10 }}>
                  <button type="button" className="btn btn-primary" onClick={jalankanUji} disabled={selectedSlugs.length === 0}>
                    Uji terhadap paket ini
                  </button>
                </div>
                {ujiHasil &&
                  (ujiHasil.valid ? (
                    <div className="alert alert-ok" style={{ marginTop: 10 }}>✅ <strong>Lolos.</strong> Dokumen ini sesuai aturan paket.</div>
                  ) : (
                    <div className="alert alert-error" style={{ marginTop: 10 }}>
                      ❌ <strong>Ditolak paket ini:</strong>
                      <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                        {ujiHasil.errors.map((er, i) => (
                          <li key={i}>[{er.lapis}] {er.message}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
              </div>
            </>
          )}

          <div className="sumbar-inline">
            <span><strong>{selectedSlugs.length}</strong> modul aktif</span>
            <span>·</span>
            <span><strong>{totalTags}</strong> parser aktif</span>
            <span>·</span>
            <span>spec ±<strong>{(specPreview?.karakter ?? 0).toLocaleString("id-ID")}</strong> karakter</span>
            <span>·</span>
            <span>{isClassic ? "pilihan modul utuh" : "🎛️ pilihan per parser"}</span>
          </div>

          <div className="row-actions" style={{ marginTop: 12 }}>
            <button className="btn btn-primary" type="submit" disabled={selectedSlugs.length === 0}>
              {editId ? "💾 Simpan Perubahan" : "➕ Buat Paket"}
            </button>
            {editId && (
              <button className="btn" type="button" onClick={resetForm}>
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
