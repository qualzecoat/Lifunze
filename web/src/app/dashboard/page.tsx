"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface NotifItem {
  id: number;
  tipe: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string | null;
}
interface DashData {
  mode: string;
  perlu_dinilai?: {
    esai: { quiz_id: number; judul: string; kelas: string | null; jumlah: number }[];
    tugas: { material_id: number; judul: string; kelas: string | null; jumlah: number }[];
  };
  kelas_saya?: { id: number; nama: string; jumlah_siswa: number; jumlah_pertemuan: number }[];
  kelas?: { id: number; nama: string; persen_total: number; materi_dibaca: number; total_materi: number; kuis_dikerjakan: number; total_kuis: number; rata_skor: number | null }[];
  aktivitas: NotifItem[];
  notifikasi_belum_dibaca: number;
}

function aktivitasTeks(n: NotifItem): string {
  const p = n.payload ?? {};
  const judul = String(p.judul ?? "");
  switch (n.tipe) {
    case "kuis_baru": return `🧪 Kuis baru "${judul}" diterbitkan di kelas Anda.`;
    case "pengumuman": return `📢 Pengumuman baru: "${judul}".`;
    case "attempt_masuk": return `✍️ Ada pengerjaan esai baru pada "${judul}" yang menunggu dinilai.`;
    case "nilai_keluar": return `🏅 Nilai untuk "${judul}" sudah keluar: ${p.skor ?? ""}.`;
    default: return "🔔 Aktivitas baru di kelas Anda.";
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [dash, setDash] = useState<DashData | null>(null);

  useEffect(() => {
    getMe().then(async (u) => {
      if (!u) {
        router.push("/login");
        return;
      }
      setUser(u);
      try {
        setDash(await apiFetch<DashData>("/api/v1/dashboard"));
      } catch { /* dashboard tetap tampil tanpa antrean */ }
    });
  }, [router]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  const staff = user.role === "guru" || user.role === "admin";
  const totalDinilai =
    (dash?.perlu_dinilai?.esai.reduce((a, r) => a + r.jumlah, 0) ?? 0) +
    (dash?.perlu_dinilai?.tugas.reduce((a, r) => a + r.jumlah, 0) ?? 0);

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.7rem", marginBottom: 4 }}>
        Halo, {user.nama_lengkap ?? user.username} 👋
      </h1>
      <p className="muted" style={{ marginBottom: 18 }}>
        Serunya Belajar, Mudahnya Mengajar.
      </p>

      {user.must_change_password && (
        <div className="alert alert-warn">
          Password Anda masih password sementara.{" "}
          <Link href="/ganti-password"><strong>Ganti sekarang</strong></Link> demi keamanan akun.
        </div>
      )}

      {staff && dash?.perlu_dinilai && (
        <div className="card" style={{ borderLeft: "5px solid var(--amber)", marginBottom: 16 }}>
          <h3>
            📥 Perlu Dinilai{" "}
            {totalDinilai > 0 ? <span className="badge">{totalDinilai} menunggu</span> : <span className="badge">bersih ✓</span>}
          </h3>
          {dash.perlu_dinilai.esai.map((r) => (
            <div key={`e${r.quiz_id}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 0", borderBottom: "1px solid var(--border)", gap: 8, flexWrap: "wrap" }}>
              <span>
                <strong>Esai: {r.judul}</strong>
                <span className="muted"> — {r.kelas} · {r.jumlah} pengerjaan belum dinilai</span>
              </span>
              <Link className="btn btn-sm btn-primary" href={`/kuis/${r.quiz_id}`}>Nilai sekarang →</Link>
            </div>
          ))}
          {dash.perlu_dinilai.tugas.map((r) => (
            <div key={`t${r.material_id}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 0", borderBottom: "1px solid var(--border)", gap: 8, flexWrap: "wrap" }}>
              <span>
                <strong>Tugas: {r.judul}</strong>
                <span className="muted"> — {r.kelas} · {r.jumlah} pengumpulan belum dinilai</span>
              </span>
              <Link className="btn btn-sm btn-primary" href={`/materi/${r.material_id}`}>Nilai sekarang →</Link>
            </div>
          ))}
          {totalDinilai === 0 && <p className="muted" style={{ marginTop: 6 }}>Tidak ada yang menunggu dinilai. Kerja bagus! 🎉</p>}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 14, marginBottom: 16 }}>
        <div className="card">
          <h3>🏫 {staff ? "Kelas Saya" : "Kelas yang Saya Ikuti"}</h3>
          {staff && dash?.kelas_saya?.map((k) => (
            <div key={k.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
              <span><strong>{k.nama}</strong><br /><span className="muted">{k.jumlah_siswa} siswa · {k.jumlah_pertemuan} pertemuan</span></span>
              <Link className="btn btn-sm" href={`/kelas/${k.id}`}>Buka →</Link>
            </div>
          ))}
          {staff && dash?.kelas_saya?.length === 0 && (
            <p className="muted">Belum ada kelas. <Link href="/kelas">Buat kelas pertama Anda →</Link></p>
          )}
          {!staff && dash?.kelas?.map((k) => (
            <div key={k.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>{k.nama}</strong>
                <Link className="btn btn-sm" href={`/kelas/${k.id}`}>Buka →</Link>
              </div>
              <div style={{ background: "var(--border)", borderRadius: 8, height: 10, margin: "6px 0" }}>
                <div style={{ width: `${k.persen_total}%`, background: "var(--violet)", height: "100%", borderRadius: 8 }} />
              </div>
              <p className="muted">Progress {k.persen_total}% · materi {k.materi_dibaca}/{k.total_materi} · kuis {k.kuis_dikerjakan}/{k.total_kuis}{k.rata_skor !== null ? ` · rata-rata ${k.rata_skor}` : ""}</p>
            </div>
          ))}
          {!staff && dash?.kelas?.length === 0 && <p className="muted">Anda belum terdaftar di kelas mana pun. Minta guru Anda mendaftarkan akun ini.</p>}
        </div>

        <div className="card">
          <h3>⚡ Aktivitas Terbaru</h3>
          {dash?.aktivitas.map((n) => (
            <p key={n.id} style={{ padding: "7px 0", borderBottom: "1px solid var(--border)" }}>
              {aktivitasTeks(n)}{" "}
              <span className="muted">· {n.created_at ? new Date(n.created_at).toLocaleString("id-ID") : ""}</span>
            </p>
          ))}
          {(!dash || dash.aktivitas.length === 0) && <p className="muted" style={{ marginTop: 6 }}>Belum ada aktivitas.</p>}
          <h3 style={{ marginTop: 16 }}>🚀 Jalan Pintas</h3>
          <p style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Link className="btn btn-sm" href="/kelas">🏫 Kelas</Link>
            {staff && <Link className="btn btn-sm" href="/siswa">👩‍🎓 Siswa</Link>}
            {staff && <Link className="btn btn-sm" href="/bank">📚 Bank</Link>}
            {staff && <Link className="btn btn-sm" href="/generate">✨ Generate AI</Link>}
            {user.role === "admin" && <Link className="btn btn-sm" href="/admin/users">🧑‍🏫 Kelola User</Link>}
            <Link className="btn btn-sm" href="/notifikasi">🔔 Notifikasi{dash && dash.notifikasi_belum_dibaca > 0 ? ` (${dash.notifikasi_belum_dibaca})` : ""}</Link>
          </p>
        </div>
      </div>

      <div className="grid-cards">
        {staff && (
          <Link href="/pengaturan-ai" className="card">
            <h3>🤖 Pengaturan AI</h3>
            <p className="muted">Hubungkan provider AI Anda sendiri untuk generate materi & kuis otomatis.</p>
          </Link>
        )}
        {staff && (
          <Link href="/paket" className="card">
            <h3>🧩 Paket Parser</h3>
            <p className="muted">Komposisi modul TCML untuk mengarahkan generate AI & berbagi antar guru.</p>
          </Link>
        )}
        <Link href="/ganti-password" className="card">
          <h3>🔑 Ganti Password</h3>
          <p className="muted">Perbarui password akun Anda.</p>
        </Link>
      </div>
    </main>
  );
}
