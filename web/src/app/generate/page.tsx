"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface Pack {
  id: number;
  nama: string;
  punya_saya: boolean;
  pemilik: { username: string; nama_lengkap: string | null } | null;
}
interface Setting {
  id: number;
  nama: string;
  model: string | null;
  is_default: boolean;
}
interface Draft {
  id: number;
  jenis: string;
  tipe_quiz: string | null;
  judul: string;
  teks_mentah: string;
  is_valid: boolean;
  errors: { lapis: string; line?: number; message: string }[];
  status: string;
  published_id: number | null;
}
interface SubjectBrief {
  id: number;
  nama: string;
}
interface MeetingBrief {
  id: number;
  judul: string;
}

export default function GeneratePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [settings, setSettings] = useState<Setting[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  // form
  const [kind, setKind] = useState<"materi" | "kuis_pg" | "kuis_esai">("materi");
  const [packId, setPackId] = useState("");
  const [settingId, setSettingId] = useState("");
  const [topik, setTopik] = useState("");
  const [jenjang, setJenjang] = useState("");
  const [jumlahSoal, setJumlahSoal] = useState("5");
  const [instruksi, setInstruksi] = useState("");
  const [impTeks, setImpTeks] = useState("");
  // publish picker
  const [subjects, setSubjects] = useState<SubjectBrief[]>([]);
  const [meetings, setMeetings] = useState<MeetingBrief[]>([]);
  const [pubSubject, setPubSubject] = useState("");
  const [pubMeeting, setPubMeeting] = useState("");
  const [publishFor, setPublishFor] = useState<number | null>(null);

  const loadDrafts = useCallback(async () => {
    try {
      setDrafts(await apiFetch<Draft[]>("/api/v1/generate/drafts"));
    } catch { /* abaikan */ }
  }, []);

  useEffect(() => {
    getMe().then(async (u) => {
      if (!u) return router.push("/login");
      if (u.role === "siswa") return router.push("/dashboard");
      setUser(u);
      try {
        const mine = await apiFetch<Pack[]>("/api/v1/packs");
        const shared = await apiFetch<Pack[]>("/api/v1/packs/shared");
        setPacks([...mine, ...shared]);
        setSettings(await apiFetch<Setting[]>("/api/v1/ai/settings"));
        setSubjects(await apiFetch<SubjectBrief[]>("/api/v1/subjects"));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat data.");
      }
      loadDrafts();
    });
  }, [router, loadDrafts]);

  useEffect(() => {
    if (!pubSubject) {
      setMeetings([]);
      return;
    }
    apiFetch<{ meetings: MeetingBrief[] }>(`/api/v1/subjects/${pubSubject}`)
      .then((s) => setMeetings(s.meetings))
      .catch(() => setMeetings([]));
  }, [pubSubject]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  async function onGenerate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOk("");
    setBusy(true);
    try {
      const res = await apiFetch<{ drafts: Draft[] }>("/api/v1/generate", {
        method: "POST",
        body: {
          kind,
          pack_id: Number(packId),
          ai_setting_id: settingId ? Number(settingId) : null,
          brief: {
            topik,
            jenjang: jenjang || undefined,
            instruksi: instruksi || undefined,
            jumlah_soal: kind !== "materi" ? Number(jumlahSoal) || undefined : undefined,
          },
        },
      });
      setDrafts((prev) => [...res.drafts, ...prev]);
      const validCount = res.drafts.filter((d) => d.is_valid).length;
      setOk(
        `Generate selesai: ${res.drafts.length} dokumen, ${validCount} valid. ` +
          (validCount < res.drafts.length ? "Dokumen invalid bisa diperbaiki otomatis (maks 2x) atau diedit manual." : ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate gagal.");
    } finally {
      setBusy(false);
    }
  }

  async function onImport() {
    if (!packId) {
      setError("Pilih paket parser dulu — impor divalidasi terhadap paket yang dipilih.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const res = await apiFetch<{ drafts: Draft[] }>("/api/v1/generate/import", {
        method: "POST",
        body: { kind, pack_id: Number(packId), teks: impTeks },
      });
      setDrafts((prev) => [...res.drafts, ...prev]);
      setImpTeks("");
      setOk(`Impor selesai: ${res.drafts.length} dokumen menjadi draf.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impor gagal.");
    } finally {
      setBusy(false);
    }
  }

  async function repair(d: Draft) {
    setError("");
    try {
      const updated = await apiFetch<Draft>(`/api/v1/generate/drafts/${d.id}/repair`, { method: "POST" });
      setDrafts((prev) => prev.map((x) => (x.id === d.id ? updated : x)));
      setOk(updated.is_valid ? "Draf berhasil diperbaiki dan kini valid." : "Sudah diperbaiki, tapi masih ada error — lihat daftar errornya.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Perbaikan gagal.");
    }
  }

  async function saveBank(d: Draft) {
    try {
      await apiFetch(`/api/v1/generate/drafts/${d.id}/save-bank`, { method: "POST", body: {} });
      setOk(`Draf "${d.judul}" tersimpan ke Bank.`);
      loadDrafts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan ke bank.");
    }
  }

  async function publish(d: Draft) {
    if (!pubMeeting) return;
    try {
      const res = await apiFetch<{ material_id?: number; quiz_id?: number }>(
        `/api/v1/generate/drafts/${d.id}/publish`,
        { method: "POST", body: { meeting_id: Number(pubMeeting) } },
      );
      setOk(`Draf "${d.judul}" diterbitkan ke pertemuan.`);
      setPublishFor(null);
      loadDrafts();
      if (res.quiz_id) router.push(`/kuis/${res.quiz_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menerbitkan draf.");
    }
  }

  async function removeDraft(d: Draft) {
    if (!window.confirm("Hapus draf ini?")) return;
    await apiFetch(`/api/v1/generate/drafts/${d.id}`, { method: "DELETE" });
    setDrafts((prev) => prev.filter((x) => x.id !== d.id));
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.5rem", marginBottom: 4 }}>✨ Generate AI</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        AI menulis materi/kuis dalam format TCML memakai paket parser pilihan Anda. Hasilnya menjadi <strong>draf</strong> yang
        divalidasi dua lapis (sintaks + skema paket) — tidak pernah terbit otomatis; Anda meninjau dulu.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {ok && <div className="alert alert-ok">{ok}</div>}

      {settings.length === 0 && (
        <div className="alert alert-error">
          Anda belum punya Pengaturan AI. <Link href="/pengaturan-ai">Buat Pengaturan AI</Link> dulu (base URL, API key, model).
        </div>
      )}
      {packs.length === 0 && (
        <div className="alert alert-error">
          Belum ada paket yang bisa dipakai. <Link href="/paket">Buat Paket Parser</Link> dulu.
        </div>
      )}

      <form className="card" onSubmit={onGenerate}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
          <div>
            <label className="label">Jenis konten</label>
            <select className="select" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="materi">Materi / Latihan / Proyek</option>
              <option value="kuis_pg">Kuis Pilihan Ganda</option>
              <option value="kuis_esai">Kuis Esai</option>
            </select>
          </div>
          <div>
            <label className="label">Paket parser</label>
            <select className="select" value={packId} onChange={(e) => setPackId(e.target.value)} required>
              <option value="">— pilih paket —</option>
              {packs.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nama}{p.punya_saya ? "" : ` (dari ${p.pemilik?.nama_lengkap ?? p.pemilik?.username})`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Pengaturan AI</label>
            <select className="select" value={settingId} onChange={(e) => setSettingId(e.target.value)}>
              <option value="">Otomatis (default saya)</option>
              {settings.map((s) => (
                <option key={s.id} value={s.id}>{s.nama} — {s.model ?? "?"}{s.is_default ? " (default)" : ""}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Jenjang/kelas</label>
            <input className="input" value={jenjang} onChange={(e) => setJenjang(e.target.value)} placeholder="mis. SD kelas 5" />
          </div>
          {kind !== "materi" && (
            <div>
              <label className="label">Jumlah soal</label>
              <input className="input" type="number" min={1} max={30} value={jumlahSoal} onChange={(e) => setJumlahSoal(e.target.value)} />
            </div>
          )}
        </div>
        <label className="label">Topik</label>
        <input className="input" value={topik} onChange={(e) => setTopik(e.target.value)} required placeholder="mis. Pecahan senilai dan cara menyederhanakannya" />
        <label className="label">Instruksi tambahan</label>
        <textarea className="textarea" rows={2} value={instruksi} onChange={(e) => setInstruksi(e.target.value)} placeholder="mis. Sertakan 1 contoh soal cerita dan 1 catatan pengingat (opsional)" />
        <button className="btn btn-primary" type="submit" disabled={busy || !packId} style={{ marginTop: 12 }}>
          {busy ? "⏳ AI sedang menulis..." : "✨ Generate"}
        </button>
      </form>

      <div className="card" style={{ marginTop: 14 }}>
        <h3>📥 Impor TCML dari LLM Eksternal</h3>
        <p className="muted" style={{ margin: "6px 0" }}>
          Sudah memakai paket yang diekspor .md di ChatGPT/Claude/dll? Tempel hasilnya di sini — dokumen dipecah dan
          divalidasi terhadap paket & jenis konten yang dipilih di form atas, lalu menjadi draf.
        </p>
        <textarea
          className="textarea"
          rows={6}
          value={impTeks}
          onChange={(e) => setImpTeks(e.target.value)}
          placeholder={"[MATERIAL]\n[TITLE]...[/TITLE]\n...\n[/MATERIAL]"}
          style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: ".84rem" }}
        />
        <button className="btn" onClick={onImport} disabled={busy || !impTeks.trim()} style={{ marginTop: 8 }}>
          📥 Impor sebagai Draf
        </button>
      </div>

      <h3 style={{ margin: "20px 0 10px" }}>Draf Saya ({drafts.length})</h3>
      {drafts.map((d) => (
        <div className="card" key={d.id} style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <strong>{d.judul}</strong>
            <span>
              <span className="badge" style={{ marginRight: 6 }}>{d.jenis === "quiz" ? `Kuis ${d.tipe_quiz === "teks" ? "Esai" : "PG"}` : "Materi"}</span>
              {d.is_valid ? (
                <span className="badge">✅ valid</span>
              ) : (
                <span className="badge badge-off">❌ {d.errors.length} error</span>
              )}
              {d.status === "published" && <span className="badge" style={{ marginLeft: 6 }}>📤 terbit</span>}
            </span>
          </div>
          {!d.is_valid && d.errors.length > 0 && (
            <ul style={{ marginLeft: 18, marginTop: 6 }}>
              {d.errors.slice(0, 5).map((e, i) => (
                <li key={i} className="muted">
                  [{e.lapis}]{e.line ? ` baris ${e.line}: ` : ": "}{e.message}
                </li>
              ))}
            </ul>
          )}
          <details style={{ marginTop: 8 }}>
            <summary className="muted" style={{ cursor: "pointer" }}>Lihat teks TCML</summary>
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "'JetBrains Mono', monospace", fontSize: ".8rem", marginTop: 6 }}>{d.teks_mentah}</pre>
          </details>
          <div className="row-actions" style={{ marginTop: 10 }}>
            {!d.is_valid && <button className="btn btn-sm btn-primary" onClick={() => repair(d)}>🛠️ Perbaiki Otomatis</button>}
            {d.is_valid && d.status !== "published" && (
              <>
                <button className="btn btn-sm" onClick={() => saveBank(d)}>📚 Simpan ke Bank</button>
                <button className="btn btn-sm" onClick={() => setPublishFor(publishFor === d.id ? null : d.id)}>📤 Terbitkan ke Pertemuan</button>
              </>
            )}
            <button className="btn btn-sm btn-danger" onClick={() => removeDraft(d)}>Hapus</button>
          </div>
          {publishFor === d.id && (
            <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
              <select className="select" style={{ maxWidth: 220 }} value={pubSubject} onChange={(e) => { setPubSubject(e.target.value); setPubMeeting(""); }}>
                <option value="">— pilih kelas —</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>{s.nama}</option>
                ))}
              </select>
              <select className="select" style={{ maxWidth: 220 }} value={pubMeeting} onChange={(e) => setPubMeeting(e.target.value)}>
                <option value="">— pilih pertemuan —</option>
                {meetings.map((m) => (
                  <option key={m.id} value={m.id}>{m.judul}</option>
                ))}
              </select>
              <button className="btn btn-sm btn-primary" disabled={!pubMeeting} onClick={() => publish(d)}>Terbitkan</button>
            </div>
          )}
        </div>
      ))}
      {drafts.length === 0 && <p className="muted">Belum ada draf. Hasil generate akan muncul di sini.</p>}
    </main>
  );
}
