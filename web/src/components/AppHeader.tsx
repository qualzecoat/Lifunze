"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Logo from "./Logo";
import { apiFetch, logout, type User } from "@/lib/api";

export default function AppHeader({ user }: { user: User }) {
  const router = useRouter();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    apiFetch<{ belum_dibaca: number }>("/api/v1/notifications/summary")
      .then((r) => setUnread(r.belum_dibaca))
      .catch(() => {});
  }, []);

  async function onLogout() {
    await logout();
    router.push("/login");
  }
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "14px 0 18px",
        flexWrap: "wrap",
      }}
    >
      <Link href="/dashboard">
        <Logo size={32} />
      </Link>
      <nav style={{ display: "flex", gap: 16, alignItems: "center", fontSize: ".92rem", flexWrap: "wrap" }}>
        <Link href="/dashboard">Dashboard</Link>
        <Link href="/kelas">Kelas</Link>
        {(user.role === "guru" || user.role === "admin") && <Link href="/siswa">Kelola Siswa</Link>}
        {user.role === "admin" && <Link href="/admin/users">Kelola User</Link>}
        {(user.role === "guru" || user.role === "admin") && <Link href="/bank">Bank</Link>}
        {(user.role === "guru" || user.role === "admin") && <Link href="/paket">Paket Parser</Link>}
        {(user.role === "guru" || user.role === "admin") && <Link href="/generate">✨ Generate AI</Link>}
        {(user.role === "guru" || user.role === "admin") && <Link href="/pengaturan-ai">Pengaturan AI</Link>}
        <Link href="/ganti-password">Ganti Password</Link>
        <Link href="/notifikasi" title="Notifikasi">
          🔔{unread > 0 && <span className="badge" style={{ marginLeft: 4 }}>{unread}</span>}
        </Link>
        <span className="muted">
          {user.nama_lengkap ?? user.username} · <span className="badge">{user.role}</span>
        </span>
        <button className="btn btn-sm" onClick={onLogout}>
          Keluar
        </button>
      </nav>
    </header>
  );
}
