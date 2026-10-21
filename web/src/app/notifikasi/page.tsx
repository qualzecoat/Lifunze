"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { apiFetch, getMe, type User } from "@/lib/api";

interface Notif {
  id: number;
  tipe: string;
  payload: Record<string, unknown>;
  sudah_dibaca: boolean;
  created_at: string | null;
}

function describe(n: Notif): { teks: string; href: string | null } {
  const p = n.payload as Record<string, string | number>;
  switch (n.tipe) {
    case "pengumuman":
      return {
        teks: `📢 Pengumuman baru di ${p.kelas ?? "kelas"}: “${p.judul}”`,
        href: p.subject_id ? `/kelas/${p.subject_id}` : null,
      };
    case "kuis_baru":
      return {
        teks: `🧪 Kuis baru tersedia: “${p.judul}”`,
        href: p.quiz_id ? `/kuis/${p.quiz_id}` : null,
      };
    case "attempt_masuk":
      return {
        teks: `📝 Ada pengerjaan esai yang perlu dinilai: “${p.judul}”`,
        href: p.quiz_id ? `/kuis/${p.quiz_id}` : null,
      };
    case "nilai_keluar":
      if (p.submission_id) {
        return {
          teks: `🏅 Tugas “${p.judul}” sudah dinilai: skor ${p.skor}`,
          href: p.material_id ? `/materi/${p.material_id}` : null,
        };
      }
      return {
        teks: `🏅 Nilai kuis “${p.judul}” keluar: ${p.skor}`,
        href: p.quiz_id ? `/kuis/${p.quiz_id}` : null,
      };
    default:
      return { teks: `🔔 ${n.tipe}`, href: null };
  }
}

export default function NotifikasiPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [items, setItems] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);

  const load = useCallback(async () => {
    const res = await apiFetch<{ items: Notif[]; belum_dibaca: number }>("/api/v1/notifications");
    setItems(res.items);
    setUnread(res.belum_dibaca);
  }, []);

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

  async function readAll() {
    await apiFetch("/api/v1/notifications/read-all", { method: "POST" });
    // Audit #31: beri tahu header agar lencana bel langsung nol.
    window.dispatchEvent(new Event("lifunze:notif-berubah"));
    load();
  }

  async function open(n: Notif) {
    const { href } = describe(n);
    if (!n.sudah_dibaca) {
      await apiFetch(`/api/v1/notifications/${n.id}/read`, { method: "POST" }).catch(() => {});
    }
    if (href) router.push(href);
    else load();
  }

  return (
    <main className="page">
      <AppHeader user={user} />
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: "1.5rem" }}>🔔 Notifikasi</h1>
        {unread > 0 && <button className="btn btn-sm" onClick={readAll}>Tandai semua dibaca ({unread})</button>}
      </div>
      <div style={{ marginTop: 12 }}>
        {items.map((n) => {
          const { teks } = describe(n);
          return (
            <div
              key={n.id}
              className="card"
              onClick={() => open(n)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                // Audit #31: baris notifikasi bisa dibuka lewat keyboard.
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  void open(n);
                }
              }}
              style={{ marginBottom: 8, cursor: "pointer", opacity: n.sudah_dibaca ? 0.72 : 1 }}
            >
              <span>{n.sudah_dibaca ? "" : "🔵 "}{teks}</span>
              <div className="muted">{n.created_at ? new Date(n.created_at).toLocaleString("id-ID") : ""}</div>
            </div>
          );
        })}
        {items.length === 0 && <p className="muted">Belum ada notifikasi.</p>}
      </div>
    </main>
  );
}
