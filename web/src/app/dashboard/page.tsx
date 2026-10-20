"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { getMe, type User } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    getMe().then((u) => {
      if (!u) router.push("/login");
      else setUser(u);
    });
  }, [router]);

  if (!user) return <main className="page"><p className="muted">Memuat...</p></main>;

  const staff = user.role === "guru" || user.role === "admin";

  return (
    <main className="page">
      <AppHeader user={user} />
      <h1 style={{ fontSize: "1.7rem", marginBottom: 4 }}>
        Halo, {user.nama_lengkap ?? user.username} 👋
      </h1>
      <p className="muted" style={{ marginBottom: 18 }}>
        Selamat datang di Lifunze — tempat belajar dan mengajar yang seru dan mudah.
      </p>

      {user.must_change_password && (
        <div className="alert alert-warn">
          Password Anda masih password sementara.{" "}
          <Link href="/ganti-password"><strong>Ganti sekarang</strong></Link> demi keamanan akun.
        </div>
      )}

      <div className="grid-cards">
        {staff && (
          <Link href="/siswa" className="card">
            <h3>👩‍🎓 Kelola Siswa</h3>
            <p className="muted">Buat akun siswa, import massal via CSV, reset password, aktif/nonaktifkan.</p>
          </Link>
        )}
        {user.role === "admin" && (
          <Link href="/admin/users" className="card">
            <h3>🧑‍🏫 Kelola User</h3>
            <p className="muted">Buat akun guru dan kelola semua user, lengkap dengan info pembuat akun.</p>
          </Link>
        )}
        {staff && (
          <Link href="/pengaturan-ai" className="card">
            <h3>🤖 Pengaturan AI</h3>
            <p className="muted">Hubungkan provider AI Anda sendiri untuk generate materi & kuis otomatis.</p>
          </Link>
        )}
        <Link href="/ganti-password" className="card">
          <h3>🔑 Ganti Password</h3>
          <p className="muted">Perbarui password akun Anda.</p>
        </Link>
      </div>

      {user.role === "siswa" && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>📚 Kelas saya</h3>
          <p className="muted">Daftar mata pelajaran akan tampil di sini pada fase berikutnya.</p>
        </div>
      )}
    </main>
  );
}
