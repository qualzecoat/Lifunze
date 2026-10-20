"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Logo from "./Logo";
import { apiFetch, logout, type User } from "@/lib/api";

export default function AppHeader({ user }: { user: User }) {
  const router = useRouter();
  const pathname = usePathname();
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

  const staff = user.role === "guru" || user.role === "admin";
  const items: { href: string; label: string; show: boolean }[] = [
    { href: "/dashboard", label: "🏠 Dashboard", show: true },
    { href: "/kelas", label: "🏫 Kelas", show: true },
    { href: "/siswa", label: "👩‍🎓 Kelola Siswa", show: staff },
    { href: "/admin/users", label: "🧑‍🏫 Kelola User", show: user.role === "admin" },
    { href: "/bank", label: "📚 Bank", show: staff },
    { href: "/paket", label: "🧩 Paket Parser", show: staff },
    { href: "/generate", label: "✨ Generate AI", show: staff },
    { href: "/pengaturan-ai", label: "🤖 Pengaturan AI", show: staff },
    { href: "/ganti-password", label: "🔑 Ganti Password", show: true },
  ];
  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" : pathname === href || pathname.startsWith(href + "/");
  const nama = user.nama_lengkap ?? user.username;

  return (
    <header className="appbar">
      <div className="appbar-inner">
        <Link href="/dashboard" className="appbar-logo" aria-label="Lifunze — ke Dashboard">
          <Logo size={34} />
        </Link>
        <nav className="appnav">
          {items
            .filter((i) => i.show)
            .map((i) => (
              <Link key={i.href} href={i.href} className={isActive(i.href) ? "active" : undefined}>
                {i.label}
              </Link>
            ))}
        </nav>
        <div className="appbar-user">
          <Link href="/notifikasi" className="bell-btn" title="Notifikasi" aria-label="Notifikasi">
            🔔
            {unread > 0 && <span className="bell-badge">{unread}</span>}
          </Link>
          <div className="userchip">
            <span className="avatar-circle">{nama.charAt(0).toUpperCase()}</span>
            <span>
              <span className="uname">{nama}</span>
              <br />
              <span className="badge">{user.role}</span>
            </span>
          </div>
          <button className="btn btn-sm" onClick={onLogout}>
            Keluar
          </button>
        </div>
      </div>
    </header>
  );
}
