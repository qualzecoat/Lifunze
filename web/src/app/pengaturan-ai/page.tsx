"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";
import TabsBar from "@/components/TabsBar";

interface Setting {
  id: number;
  nama: string;
  base_url: string;
  model: string | null;
  is_default: boolean;
  api_key_masked: string | null;
  milik_saya: boolean;
  pemilik: string | null;
  dibagikan_mode: string;
  target_ids: number[];
}

interface Penerima {
  id: number;
  username: string;
  nama: string;
  role: string;
}

const MODE_BAGI: { nilai: string; label: string }[] = [
  { nilai: "tidak", label: "Tidak dibagikan (hanya saya)" },
  { nilai: "semua", label: "🌐 Semua akun guru & admin" },
  { nilai: "whitelist", label: "🎯 Hanya akun terpilih" },
  { nilai: "blacklist", label: "🚫 Semua, kecuali akun terpilih" },
];

function DaftarAkun({
  penerima,
  dipilih,
  onToggle,
}: {
  penerima: Penerima[];
  dipilih: number[];
  onToggle: (id: number) => void;
}) {
  if (penerima.length === 0) return <p className="muted">Belum ada akun guru/admin lain.</p>;
  return (
    <div style={{ display: "grid", gap: 4, maxHeight: 180, overflowY: "auto", margin: "6px 0" }}>
      {penerima.map((p) => (
        <label key={p.id} className="check-row">
          <input
            type="checkbox"
            checked={dipilih.includes(p.id)}
            onChange={() => onToggle(p.id)}
          />
          <span>
            {p.nama} <span className="muted">(@{p.username} · {p.role})</span>
          </span>
        </label>
      ))}
    </div>
  );
}

export default function PengaturanAiPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<Setting[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({ nama: "", base_url: "", api_key: "", model: "" });
  const [formModels, setFormModels] = useState<string[]>([]);
  const [itemModels, setItemModels] = useState<Record<number, string[]>>({});
  const [itemModelSel, setItemModelSel] = useState<Record<number, string>>({});
  const [penerima, setPenerima] = useState<Penerima[]>([]);
  const [formBagi, setFormBagi] = useState<{ mode: string; targets: number[] }>({
    mode: "tidak",
    targets: [],
  });
  const [bagiDraft, setBagiDraft] = useState<Record<number, { mode: string; targets: number[] }>>({});
  type TabKey = "koneksi" | "baru";
  const [tab, setTab] = useState<TabKey>("koneksi");

  const load = useCallback(async () => {
    try {
      setSettings(await apiFetch<Setting[]>("/api/v1/ai/settings"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memuat pengaturan AI.");
    }
  }, []);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else if (u.role === "siswa") router.push("/dashboard");
      else {
        setUser(u);
        const awal = new URLSearchParams(window.location.search).get("tab");
        if (awal && ["koneksi", "baru"].includes(awal)) setTab(awal as TabKey);
        load();
        if (u.role === "admin") {
          apiFetch<Penerima[]>("/api/v1/ai/settings/recipients")
            .then(setPenerima)
            .catch(() => setPenerima([]));
        }
      }
    });
  }, [router, load]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  function gantiTab(k: TabKey) {
    setTab(k);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", k);
    window.history.replaceState(null, "", url.toString());
  }

  async function fetchFormModels() {
    setError("");
    setBusy("form-fetch");
    try {
      const res = await apiFetch<{ models: string[] }>("/api/v1/ai/settings/fetch-models", {
        method: "POST",
        body: { base_url: form.base_url, api_key: form.api_key },
      });
      setFormModels(res.models);
      if (res.models.length) {
        // Audit #42: update fungsional — form bisa berubah selama await
        // (guru mengetik nama/base_url); spread `form` lama menimpanya.
        setForm((prev) =>
          res.models.includes(prev.model) ? prev : { ...prev, model: res.models[0] },
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengambil model.");
    } finally {
      setBusy("");
    }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      await apiFetch("/api/v1/ai/settings", {
        method: "POST",
        body: {
          ...form,
          model: form.model || null,
          ...(user?.role === "admin"
            ? { dibagikan_mode: formBagi.mode, target_ids: formBagi.targets }
            : {}),
        },
      });
      setOk("Koneksi AI ditambahkan.");
      setForm({ nama: "", base_url: "", api_key: "", model: "" });
      setFormModels([]);
      setFormBagi({ mode: "tidak", targets: [] });
      load();
      gantiTab("koneksi");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan koneksi.");
    }
  }

  function toggleTarget(
    ambil: () => { mode: string; targets: number[] },
    simpan: (v: { mode: string; targets: number[] }) => void,
    id: number,
  ) {
    const cur = ambil();
    simpan({
      ...cur,
      targets: cur.targets.includes(id)
        ? cur.targets.filter((t) => t !== id)
        : [...cur.targets, id],
    });
  }

  async function simpanBagi(s: Setting) {
    const d = bagiDraft[s.id] ?? { mode: s.dibagikan_mode, targets: s.target_ids };
    setError("");
    setOk("");
    try {
      await apiFetch(`/api/v1/ai/settings/${s.id}`, {
        method: "PATCH",
        body: { dibagikan_mode: d.mode, target_ids: d.targets },
      });
      setOk(`Pengaturan berbagi ${s.nama} disimpan.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan pengaturan berbagi.");
    }
  }

  async function fetchItemModels(s: Setting) {
    setError("");
    setBusy(`fetch-${s.id}`);
    try {
      const res = await apiFetch<{ models: string[] }>("/api/v1/ai/settings/fetch-models", {
        method: "POST",
        body: { base_url: s.base_url, setting_id: s.id },
      });
      // Audit #42: update fungsional agar dua ambil-model bersamaan
      // tidak saling menimpa.
      setItemModels((prev) => ({ ...prev, [s.id]: res.models }));
      setItemModelSel((prev) => ({ ...prev, [s.id]: prev[s.id] ?? s.model ?? res.models[0] ?? "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengambil model.");
    } finally {
      setBusy("");
    }
  }

  async function saveItemModel(s: Setting) {
    try {
      await apiFetch(`/api/v1/ai/settings/${s.id}`, {
        method: "PATCH",
        body: { model: itemModelSel[s.id] || null },
      });
      setOk(`Model untuk ${s.nama} disimpan.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan model.");
    }
  }

  async function testConn(s: Setting) {
    setError("");
    setOk("");
    setBusy(`test-${s.id}`);
    try {
      const res = await apiFetch<{ pesan: string; latency_ms: number }>(
        `/api/v1/ai/settings/${s.id}/test`,
        { method: "POST" },
      );
      setOk(`${s.nama}: ${res.pesan} (${res.latency_ms} ms)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tes koneksi gagal.");
    } finally {
      setBusy("");
    }
  }

  async function makeDefault(s: Setting) {
    await apiFetch(`/api/v1/ai/settings/${s.id}`, { method: "PATCH", body: { is_default: true } });
    load();
  }

  async function remove(s: Setting) {
    if (!window.confirm(`Hapus koneksi ${s.nama}?`)) return;
    await apiFetch(`/api/v1/ai/settings/${s.id}`, { method: "DELETE" });
    load();
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>Pengaturan AI</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Koneksi AI milik Anda sendiri (OpenAI-compatible: OpenRouter, OpenAI, Gemini, provider lokal, dll).
        API key tersimpan terenkripsi dan tidak pernah ditampilkan utuh.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      <TabsBar
        active={tab}
        onChange={(k) => gantiTab(k as TabKey)}
        tabs={[
          { key: "koneksi", label: `🔌 Koneksi Saya (${settings.length})` },
          { key: "baru", label: "➕ Koneksi Baru" },
        ]}
      />

      <div style={{ display: tab === "baru" ? undefined : "none" }}>
      <form className="card" onSubmit={onCreate} style={{ marginBottom: 16 }}>
        <h3>➕ Koneksi Baru</h3>
        <label className="label">Nama koneksi</label>
        <input className="input" placeholder="mis. OpenRouter" value={form.nama} onChange={(e) => setForm({ ...form, nama: e.target.value })} required />
        <label className="label">Base URL</label>
        <input className="input" placeholder="https://openrouter.ai/api/v1" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} required />
        <label className="label">API key</label>
        <input className="input" type="password" placeholder="sk-..." value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} required />
        <label className="label">Model</label>
        <div style={{ display: "flex", gap: 8 }}>
          {formModels.length > 0 ? (
            <select className="select" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })}>
              {formModels.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          ) : (
            <input className="input" placeholder="nama model (atau ambil daftarnya)" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
          )}
          <button className="btn" type="button" onClick={fetchFormModels} disabled={busy === "form-fetch" || !form.base_url || !form.api_key}>
            {busy === "form-fetch" ? "..." : "🔄 Ambil Daftar Model"}
          </button>
        </div>
        {user.role === "admin" && (
          <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
            <label className="label">🌐 Bagikan sebagai default untuk akun lain (khusus admin)</label>
            <select
              className="select"
              value={formBagi.mode}
              onChange={(e) => setFormBagi({ ...formBagi, mode: e.target.value })}
            >
              {MODE_BAGI.map((m) => (
                <option key={m.nilai} value={m.nilai}>{m.label}</option>
              ))}
            </select>
            {(formBagi.mode === "whitelist" || formBagi.mode === "blacklist") && (
              <DaftarAkun
                penerima={penerima}
                dipilih={formBagi.targets}
                onToggle={(id) => toggleTarget(() => formBagi, setFormBagi, id)}
              />
            )}
            <p className="muted" style={{ marginTop: 6 }}>
              Koneksi yang dibagikan menjadi cadangan otomatis bagi akun yang belum punya koneksi
              sendiri — kunci Anda tidak pernah ditampilkan ke mereka.
            </p>
          </div>
        )}
        <button className="btn btn-primary" type="submit" style={{ marginTop: 16 }}>Simpan Koneksi</button>
      </form>
      </div>

      <div style={{ display: tab === "koneksi" ? undefined : "none" }}>
      <div style={{ display: "grid", gap: 12 }}>
        {settings.map((s) => {
          const bagi = bagiDraft[s.id] ?? { mode: s.dibagikan_mode, targets: s.target_ids };
          return (
          <div className="card" key={s.id}>
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <h3>
                {s.nama} {s.is_default && s.milik_saya && <span className="badge">default</span>}
                {!s.milik_saya && <span className="badge">🌐 dari {s.pemilik ?? "admin"}</span>}
                {s.milik_saya && s.dibagikan_mode !== "tidak" && (
                  <span className="badge">🌐 dibagikan</span>
                )}
              </h3>
              <span className="muted">
                {s.milik_saya ? `key: ${s.api_key_masked}` : "key: dikelola admin"}
              </span>
            </div>
            <p className="muted">{s.base_url}</p>
            <p style={{ margin: "6px 0" }}>
              Model: <strong>{s.model ?? "(belum dipilih)"}</strong>
            </p>
            {!s.milik_saya && (
              <p className="muted">
                Koneksi ini dibagikan oleh admin dan dipakai otomatis bila Anda belum punya
                koneksi sendiri (atau dipilih manual di halaman Generate). Tidak dapat diubah dari sini.
              </p>
            )}
            {s.milik_saya && itemModels[s.id] && (
              <div style={{ display: "flex", gap: 8, margin: "8px 0" }}>
                <select
                  className="select"
                  value={itemModelSel[s.id] ?? ""}
                  onChange={(e) => setItemModelSel({ ...itemModelSel, [s.id]: e.target.value })}
                >
                  {itemModels[s.id].map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <button className="btn btn-sm" onClick={() => saveItemModel(s)}>Simpan Model</button>
              </div>
            )}
            {s.milik_saya && user.role === "admin" && (
              <div style={{ marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                <label className="label">🌐 Dibagikan ke akun lain sebagai default cadangan</label>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <select
                    className="select"
                    value={bagi.mode}
                    onChange={(e) =>
                      setBagiDraft((prev) => ({
                        ...prev,
                        [s.id]: { ...bagi, mode: e.target.value },
                      }))
                    }
                  >
                    {MODE_BAGI.map((m) => (
                      <option key={m.nilai} value={m.nilai}>{m.label}</option>
                    ))}
                  </select>
                  <button className="btn btn-sm" onClick={() => simpanBagi(s)}>Simpan Berbagi</button>
                </div>
                {(bagi.mode === "whitelist" || bagi.mode === "blacklist") && (
                  <DaftarAkun
                    penerima={penerima}
                    dipilih={bagi.targets}
                    onToggle={(id) =>
                      toggleTarget(
                        () => bagiDraft[s.id] ?? { mode: s.dibagikan_mode, targets: s.target_ids },
                        (v) => setBagiDraft((prev) => ({ ...prev, [s.id]: v })),
                        id,
                      )
                    }
                  />
                )}
              </div>
            )}
            {s.milik_saya && (
            <div className="row-actions" style={{ marginTop: 8 }}>
              <button className="btn btn-sm" onClick={() => fetchItemModels(s)} disabled={busy === `fetch-${s.id}`}>
                {busy === `fetch-${s.id}` ? "..." : "🔄 Ambil Model"}
              </button>
              <button className="btn btn-sm" onClick={() => testConn(s)} disabled={busy === `test-${s.id}`}>
                {busy === `test-${s.id}` ? "Menguji..." : "🧪 Tes Koneksi"}
              </button>
              {!s.is_default && (
                <button className="btn btn-sm" onClick={() => makeDefault(s)}>Jadikan Default</button>
              )}
              <button className="btn btn-sm btn-danger" onClick={() => remove(s)}>Hapus</button>
            </div>
            )}
          </div>
          );
        })}
        {settings.length === 0 && <p className="muted">Belum ada koneksi AI. Tambahkan lewat tab Koneksi Baru.</p>}
      </div>
      </div>
    </main>
  );
}
