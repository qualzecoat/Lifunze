# Analisis: Fitur Kelas Live Scratch ("Scratch ala Figma") untuk Lifunze

> **Tanggal:** 2026-10-20 · **Status:** Analisis & persiapan — **fitur TIDAK dikerjakan sekarang** (keputusan Qualze), diparkir sebagai **Fase 9 (masa depan, belum dijadwalkan)**.
> **Sumber rencana asli:** `~/workspace/your_files/kursus-coding/platform-mvp-plan.md` (2026-10-09) & business plan kursus coding anak (goal `bisnis-kursus-coding-online-anak`).

---

## Ringkasan Vonis

**Sebagian besar COCOK** dengan blueprint Lifunze v2 — stack-nya bahkan identik (Next.js + PostgreSQL + Docker + Caddy, pola Rephore). Tapi ada **dua penyesuaian besar** yang harus diterima sejak awal:

1. **Editor Scratch BUKAN modul di dalam Lifunze.** Ia adalah **layanan pendamping terpisah** (fork TurboWarp, repo publik sendiri karena GPL-3.0) yang dihubungkan ke Lifunze lewat tombol masuk dari pertemuan + token SSO sekali pakai. Lifunze tetap "rumahnya" (akun, kelas, kurikulum, bank); editor adalah "ruang praktiknya".
2. **Lifunze saat ini murni REST — fitur ini butuh komponen realtime.** Sebuah service WebSocket kecil (Node, sesuai rencana lama) harus dicadangkan slotnya di Docker Compose & Caddy sejak sekarang, supaya nanti tinggal pasang tanpa membongkar arsitektur.

Dengan dua penyesuaian itu, sisanya justru **saling menguatkan**: sistem akun & enrollment Lifunze lebih rapi daripada rencana lama (yang masih mengandalkan link undangan), dan Paket Parser Scratch (Fase 7) menyediakan sisi kontennya (materi & kuis tentang Scratch), sedangkan fitur live ini menyediakan sisi praktiknya.

---

## 1. Fitur Ini Sebenarnya Apa (dari rencana 2026-10-09)

Satu **room kelas live** di browser: tiap siswa punya project Scratch-nya sendiri, guru bisa melihat semua project, dan guru bisa **mengambil alih** project siswa manapun untuk mendemonstrasikan/mem­betulkan — siswa lain menonton read-only. Google Meet dipakai **audio-only**; platform tidak menyediakan video call.

Keputusan teknis yang sudah dicek di riset lama:

- **Editor: fork TurboWarp** (`turbowarp/scratch-gui` + `scratch-vm`) — lebih ringan di laptop spek rendah daripada Scratch upstream.
- **Sinkronisasi lock-based, BUKAN kolaborasi simultan (CRDT):** satu project = satu pemegang kendali (pemiliknya, atau guru saat take-over). Pemegang lock mengirim `vm.toJSON()` via WebSocket (debounce ±1–2 detik); penonton menerima state & editor mereka read-only. Tombol guru: "Ambil alih" / "Kembalikan".
- **Bandwidth:** project anak tipikal puluhan KB → sync aktif ≈ 200 kbps, idle = 0. Sekitar **7× lebih ringan dari screen share 720p** — inilah USP "lancar di internet lemot".
- **Lisensi GPL-3.0:** fork editor yang disajikan ke browser **wajib dibuka source-nya** → strategi open-core: repo fork editor = publik, backend kelas = privat. Branding TurboWarp wajib diganti (file TRADEMARK di repo mereka).
- Yang **ditolak** sejak riset lama: iframe embed turbowarp.org (tidak bisa disuntik logika lock) dan CRDT ala Figma penuh (effort 3–4×, tidak dibutuhkan model gantian).

## 2. Yang Dibutuhkan untuk Memasukkan Fitur Ini

| # | Komponen | Keterangan |
|---|---|---|
| 1 | **Fork editor TurboWarp** | Repo terpisah & publik (GPL-3.0). Ditambah: mode read-only, load project dari JSON, indikator pemegang kendali, branding Lifunze |
| 2 | **Service WebSocket (Node)** | Mengelola room, lock per project, relay state `toJSON`, presence/roster. Satu bahasa dengan editor (sesuai rencana lama: library `ws` cukup) |
| 3 | **Room & sesi live** | Room menempel pada **Meeting**: guru membuka sesi dari pertemuan → siswa yang enrolled bisa masuk; roster tampil untuk guru |
| 4 | **Penyimpanan project** | Project Scratch per siswa (state JSON / file `.sb3`) tersimpan di PostgreSQL + file storage, bisa dibuka lagi pertemuan berikutnya |
| 5 | **Integrasi SSO dari Lifunze** | Tombol "Masuk Kelas Live" di pertemuan menerbitkan **token sekali pakai berumur pendek**; service live memvalidasinya ke API Lifunze (tidak ada login kedua, tidak ada akun terpisah) |
| 6 | **Pemetaan peran room** | Guru = host (bisa take-over lock siapa pun), siswa = pemilik project-nya, siswa lain = penonton read-only. Diturunkan dari role + enrollment Lifunze |
| 7 | **Audio eksternal** | Tetap di luar platform (Meet audio-only), sesuai rencana lama — platform hanya menyediakan link/tautan jadwal |
| 8 | **Subdomain & routing** | Editor statis + WS di subdomain sendiri (usul: `scratch.lifunze.aditiamh.my.id`), di belakang Caddy yang sama |

**Estimasi effort (dari riset lama, masih berlaku):** ±6–10 minggu solo untuk MVP live-nya saja (fork + lock + multi-murid + simpan project + hardening), di luar pembangunan Lifunze inti.

## 3. Kesesuaian dengan Blueprint Lifunze v2

| Aspek | Status | Catatan |
|---|---|---|
| Stack (Next.js, PostgreSQL, Docker, Caddy) | ✅ Cocok persis | Service WS Node tinggal container tambahan |
| Struktur Subject → Meeting | ✅ Cocok | Sesi live menempel di Meeting yang sudah ada |
| Akun & enrollment | ✅ Lebih baik dari rencana lama | Rencana lama: link undangan tanpa akun. Lifunze: akun terprovisioning + cek enrollment = kontrol akses room yang rapi |
| Paket Parser Scratch (Fase 7) | ✅ Saling melengkapi | Paket = konten (materi/kuis Scratch); live = praktik. Dua hal berbeda, jangan dicampur |
| Mode hemat kuota (Fitur 10) | ✅ Sejalan | Fitur live ini perwujudan ekstrem prinsip yang sama |
| File storage abstraction | ✅ Siap | Tinggal menambah `.sb3` ke tipe yang didukung |
| Arsitektur REST-only | ⚠️ Perlu cadangan | Belum ada komponen realtime/WebSocket sama sekali |
| Frontend Next.js Lifunze | ⚠️ Jangan digabung | Menyatukan fork editor ke frontend Lifunze mencemari lisensi (GPL) & memberatkan build — wajib layanan terpisah |
| Skema data saat ini | ⚠️ Belum ada | Belum ada konsep `live_sessions` / project Scratch — dicadangkan, bukan dibuat sekarang |

## 4. Arsitektur yang Disarankan (saat nanti dikerjakan)

```text
lifunze.aditiamh.my.id          → Lifunze (web + api + db) — tidak berubah
scratch.lifunze.aditiamh.my.id  → Editor TurboWarp fork (statis, repo publik GPL)
                                   └─ WebSocket ─▶ service "live" (Node, privat)
                                                      ├─ validasi token SSO ke API Lifunze
                                                      ├─ room, lock, relay state
                                                      └─ simpan project → PostgreSQL Lifunze (skema terpisah)
```

Prinsip: **satu-satunya jembatan** antara Lifunze dan dunia live adalah (a) token SSO dan (b) tabel project/sesi milik service live. Kalau suatu hari fitur live dihentikan, Lifunze inti tidak ikut rusak.

## 5. Persiapan yang Ditanam Sekarang (tanpa mengerjakan fiturnya)

1. **Blueprint Bagian 16** mencatat cadangan ini secara resmi + **Fase 9** di roadmap (berlabel masa depan, belum dijadwalkan).
2. **Skema disiapkan dari sisi yang benar:** tabel live nanti ber-FK ke `meetings.id` & `users.id` — artinya **tidak perlu mengubah tabel inti Lifunze sama sekali** saat fitur ini datang. Yang dijaga dari sekarang: `meetings` dan `users` tidak dirombak desain kuncinya (tetap integer PK + FK standar).
3. **Slot service `live`** dicatat dalam rencana compose (Bagian 13 blueprint) sebagai container masa depan + jalur WebSocket di Caddy.
4. **Pola SSO token sekali pakai** dicatat sebagai pola endpoint masa depan di Bagian 6 blueprint (dipakai juga bila nanti ada integrasi lain).
5. **`.sb3`** dicatat sebagai ekstensi file masa depan untuk storage (di samping whitelist saat ini).
6. **Repo fork editor = repo terpisah & publik** sejak hari pertama ia dibuat nanti — tidak masuk monorepo Lifunze.

## 6. Yang Sengaja TIDAK Disiapkan Sekarang

- Tidak ada kode editor, service WS, atau tabel live yang dibuat di Fase 0–8. Persiapan di atas murni dokumentasi & disiplin desain (±nol biaya).
- Tidak ada janji jadwal: Fase 9 aktif hanya atas keputusan eksplisit Qualze, idealnya setelah Lifunze inti (Fase 0–3) live dan terbukti dipakai mengajar.
- Branding editor mengikuti branding Lifunze (violet) saat nanti dibangun — bukan branding TurboWarp dan bukan brand kursus terpisah.

## 7. Implikasi Bisnis (bonus dari penggabungan ini)

Bisnis **kursus coding online anak** (goal terpisah) selama ini direncanakan punya platform sendiri. Dengan cadangan ini, jalur yang lebih hemat muncul: **Lifunze menjadi platform bisnis itu** — Qualze sebagai guru memakai Lifunze untuk mengelola grup, kurikulum Scratch (via Paket Parser), dan kelas live-nya; yang perlu dibangun khusus tinggal editor fork + service live-nya saja. Keputusan bisnisnya (nama kursus, harga, domain terpisah untuk kursus) tetap terpisah dari keputusan platform di dokumen ini.
