# PROJECT.md — Konteks Utama Proyek Lifunze

> **UNTUK AI (Muse, Gemini, ChatGPT, atau agent apapun) & PENGEMBANG:**
> File ini adalah **sumber kebenaran konteks proyek Lifunze**. Isinya: proyek ini apa, keputusan apa saja yang sudah dikunci, dan status terakhir.
>
> **ATURAN WAJIB:**
> 1. **BACA file ini dulu** sebelum mengerjakan apapun terkait Lifunze.
> 2. **UPDATE file ini setiap ada aksi, perubahan, atau keputusan baru** — ubah bagian "Status Terkini", tambahkan keputusan ke "Log Keputusan", dan catat di "Log Pembaruan" paling bawah. Jangan biarkan file ini basi.
> 3. Blueprint lengkap ada di `docs/blueprint-v2.md` — file ini ringkasannya; kalau konflik, keputusan terbaru di file ini yang menang, lalu blueprint diperbarui menyusul.

---

## 1. Apa Itu Lifunze

**Lifunze** adalah Learning Management System (LMS) modern berbasis web — platform kelas online untuk guru dan siswa (mata pelajaran → pertemuan → materi & kuis), dengan dua kemampuan pembeda:

1. **TCML (Tenebris-Class Markup Language)** — bahasa markup konten sendiri (turunan proyek v1) untuk menulis materi, latihan, proyek, dan kuis yang kaya fitur tanpa HTML.
2. **Generate konten oleh AI langsung di dalam LMS** — materi, kuis pilihan ganda, dan kuis esai digenerate AI memakai **Paket Parser** (komposisi modul tag TCML) sebagai format keluarannya. Setiap guru/admin memakai koneksi AI-nya sendiri (base URL + API key, OpenAI-compatible).

Lifunze adalah **penerus/penulisan ulang** dari proyek v1 **Tenebris-Class** (Flask + SQLite): https://github.com/jeruk125/Tenebris-Class

- **Domain deploy:** `lifunze.aditiamh.my.id` (VPS "Sirius", Docker + Caddy)
- **Repo ini:** `qualzecoat/Lifunze`
- **Pemilik & pengambil keputusan:** Qualze (Aditia Muharam Hidayat) — bekerja solo

## 2. Status Terkini

- **2026-10-20:** Blueprint arsitektur v2 selesai & semua keputusan utama terkunci (lihat Bagian 3).
- **2026-10-20: FASE 0 — FONDASI SELESAI** ✅ — monorepo `web/` (Next.js) + `api/` (FastAPI), Docker Compose (web/api/db PostgreSQL 16), skema database lengkap **27 tabel** + migrasi Alembic awal, engine TCML modular hasil porting v1 (`api/app/tcml/`), endpoint parse (`POST /api/v1/parse/content`). Verifikasi: test parser v1 **8/8 hijau** sebagai baseline regresi, total pytest **12/12**, migrasi upgrade/downgrade bersih, `next build` sukses (standalone).
- **2026-10-20: FASE 1 — AKUN, RBAC & PENGATURAN AI SELESAI** ✅ — auth 1 portal (sesi server-side + cookie httpOnly + CSRF double-submit), seed admin via env (idempoten, jalan otomatis di Docker), provisioning guru oleh admin & siswa oleh guru/admin lengkap dengan `created_by`, import siswa CSV (savepoint per baris), audit log, soft-delete, ganti password + paksa ganti password pertama, menu Pengaturan AI per akun (API key terenkripsi Fernet & ter-masking, fetch model dari provider, tes koneksi). Frontend: login, dashboard, ganti password, kelola siswa, kelola user (admin), pengaturan AI. Verifikasi: pytest **23/23**, uji asap end-to-end di server sungguhan lolos, `next build` sukses (7 route).
- **2026-10-20: FASE 2 — PEMBELAJARAN INTI SELESAI** ✅ — CRUD subject (termasuk **arsip mapel**) + meeting (urutan otomatis & reorder) + enrollment (daftar siswa per kelas, hasil per siswa dilaporkan); materi TCML parse-gated (invalid ditolak + error per baris) dengan cache `rendered_html`; lampiran file (PNG/JPG/PDF/MP4 ≤16MB, unduh berotorisasi per enrollment); editor materi web (textarea + pratinjau langsung + daftar error) & tampilan baca siswa. **Bonus lebih awal dari jadwal:** bank dasar (kategori + simpan materi/kuis + pakai materi dari bank) sudah terbangun — sisa Fase 4: copy bank antar guru + bank soal & kuis acak. Verifikasi: pytest **31/31**, uji asap e2e lolos, `next build` sukses (12 route).
- **2026-10-20: FASE 3 — KUIS v2 SELESAI** ✅ — parser kuis baru `parse_quiz_v2` (soal ternormalisasi; ekstensi TCML `[WEIGHT]` untuk bobot & `[ANSWER]B, C` multi-jawaban-benar dengan aturan himpunan persis; fallback format legacy v1). Kuis CRUD parse-gated + pengaturan jendela buka/tutup, durasi, acak soal/opsi (deterministik per attempt), tampilkan kunci; soal terkunci setelah ada attempt. Attempt siswa: mulai/resume, simpan draf, submit, auto-expire durasi menilai draf terakhir; PG dinilai otomatis berbobot (skala 100), esai dinilai guru per soal (poin ≤ bobot) sampai status graded. Hasil per kuis + **export CSV/XLSX**; pakai kuis dari bank & simpan kuis ke bank (snapshot kini format v2 — endpoint bank ikut dimigrasikan dari parser v1). Frontend: editor kuis (pratinjau struktur soal), halaman kuis (pengerjaan siswa dengan timer + mode nilai guru). Verifikasi: pytest **39/39**, uji asap e2e alur kuis penuh lolos, `next build` sukses.
- **2026-10-20: FASE 4 — BANK LANJUTAN SELESAI** ✅ — (1) **Salin antar guru**: endpoint jelajah bank guru lain (materi & kuis, hanya-baca + info pemilik) dan salin ke bank sendiri (salinan tanpa kategori karena kategori personal; aslinya tak berubah). (2) **Bank soal**: tabel baru `bank_questions` (migrasi 0003; opsi JSON format v2) — CRUD soal lepas PG/esai dengan validasi (≥2 opsi, ≥1 benar, label unik), filter kategori/tipe, dan **ekstrak soal dari kuis mana pun** ke bank. (3) **Susun kuis acak**: tarik N soal acak dari bank soal sendiri (per kategori/tipe; error jujur bila stok kurang) menjadi kuis pertemuan baru — teks TCML kuis **digenerate ulang secara kanonis** dari data soal sehingga tetap bisa diedit di editor dan terbukti roundtrip lolos `parse_quiz_v2`; acak soal/opsi per attempt sudah tersedia sejak Fase 3. Frontend: seksi Bank Soal + Jelajahi Bank Guru Lain di /bank, panel "Susun dari Bank Soal" di halaman kelas, tombol ekstrak di halaman kuis. Verifikasi: pytest **44/44**, `next build` sukses.
- **2026-10-20: FASE 5 — PAKET PARSER & GENERATE AI SELESAI** ✅ (fitur pembeda utama) — registry modul TCML diperkaya deskripsi + spec_fragment + contoh per modul, disinkronkan idempoten ke `tag_modules`/`tag_examples`. **Paket Parser**: CRUD paket (komposisi modul; `allowed_roots` dihitung dari modul), **6 paket bawaan** otomatis per guru (Mapel Umum, Spreadsheet & Data, Pemrograman, Kuis PG, Kuis Esai, Kelas Lengkap), berbagi ke guru tertentu / semua guru (`parser_pack_shares.shared_with_id` NULL = semua guru) / privat, fork (penerima bisa pakai & fork; hanya pemilik yang edit/hapus), dan **ekspor .md** untuk LLM eksternal. **Generate AI**: prompt sistem dirakit HANYA dari modul paket terpilih (hemat konteks — terverifikasi di test), panggilan chat completion via Pengaturan AI milik guru (client generik OpenAI-compatible, error provider diterjemahkan jelas), keluaran bundle **dipecah per root block**, tiap dokumen **divalidasi 2 lapis** (sintaks parser + skema paket: root diizinkan, jenis sesuai, tag ⊆ modul paket) dan disimpan sebagai `content_drafts` — tidak pernah terbit otomatis. **Impor konten eksternal**: TCML hasil LLM luar ditempel → dipecah + divalidasi → draf. Draf invalid bisa **self-repair oleh AI maks 2x** (dihitung via audit log); draf valid bisa disimpan ke bank atau diterbitkan ke pertemuan. Frontend: /paket (kelola paket + berbagi + fork + ekspor) dan /generate (form brief, impor, daftar draf, perbaiki/simpan/terbitkan). Verifikasi: pytest **54/54** (provider AI di-mock; termasuk uji prompt hanya memuat modul terpilih, paket bawaan, impor, dan batas repair), `next build` sukses. **Penyederhanaan yang disadari** (dari blueprint): (1) generate berjalan sinkron dalam satu request — GenerationJob tetap tercatat (running/done/failed); worker async = kandidat Fase 8 bila latensi provider jadi masalah; (2) contoh yang dikirim ke AI adalah seluruh contoh milik modul terpilih (belum per-contoh dipilih satu-satu; skema tak punya tabel pemilih contoh).
- Langkah berikutnya: **Fase 6 — Pengalaman Belajar** (progress belajar siswa, pengumuman, notifikasi, tugas file [PROJECT] + rubrik, mode hemat kuota). Menunggu instruksi Qualze.
- **2026-10-20:** Repo GitHub `qualzecoat/Lifunze` dibuat oleh Qualze; commit pertama di-push Muse (README, PROJECT.md, blueprint, contoh branding).
- **Branding TERKUNCI (2026-10-20):** makna nama: **"Learning is Fun, Zero Effort"** — tempat belajar & mengajar yang seru dan mudah berkat bantuan teknologi. Tagline final: **"Serunya Belajar, Mudahnya Mengajar."** Warna: **Violet (Tema A)**. Logo & sample website final-terpilih ada di `docs/branding/` (logo-a = terpilih).

## 3. Keputusan Terkunci

| Tanggal | Keputusan |
|---|---|
| 2026-10-20 | Stack: **Next.js (React+TypeScript) + FastAPI (Python) + PostgreSQL 16**, Docker Compose di VPS Sirius, reverse proxy Caddy |
| 2026-10-20 | Domain: **lifunze.aditiamh.my.id** |
| 2026-10-20 | **Registrasi mandiri DIHAPUS.** Akun siswa hanya dibuat guru/admin; akun guru hanya dibuat admin; akun admin hanya via seed env |
| 2026-10-20 | Setiap akun wajib punya penanda pembuat: kolom `created_by_id` + audit log; bulk import siswa via CSV; password awal wajib diganti saat login pertama |
| 2026-10-20 | **Mulai dari nol bersih** — tidak ada migrasi data dari v1 |
| 2026-10-20 | Semua fitur usulan disetujui & masuk roadmap (blueprint Bagian 14, Fase 0–8) |
| 2026-10-20 | Generate konten AI di LMS; pengaturan AI **per akun** guru/admin (nama koneksi, base URL, API key terenkripsi Fernet, fetch model, pilih model) — pola OpenAI-compatible seperti Rephore |
| 2026-10-20 | Parser TCML dimodularisasi: **inti parser + modul tag + Paket Parser**. Hanya potongan spesifikasi milik paket terpilih yang dikirim ke AI. Paket bisa **diekspor jadi file .md** untuk dipakai di LLM eksternal; hasil LLM eksternal diimpor kembali lewat validator yang sama |
| 2026-10-20 | **Paket parser bisa dibagikan sesama guru** (ke guru tertentu atau semua guru), bukan hanya oleh admin. Penerima bisa memakai & menyalin (fork); hanya pemilik yang bisa mengedit/menghapus |
| 2026-10-20 | Hasil generate AI boleh **multi-dokumen (bundle)**: satu jawaban AI bisa berisi materi + latihan + kuis sekaligus; sistem memecah per root block, memvalidasi dua lapis (sintaks + skema paket), dan merutekan jadi draf sesuai jenisnya |
| 2026-10-20 | **Branding FINAL:** tagline **"Serunya Belajar, Mudahnya Mengajar."**; warna utama **Violet (Tema A)** — primer `#6D5DF6`, aksen amber `#FFB020`, tinta `#17142B`; font Plus Jakarta Sans (judul) + Inter (isi) |
| 2026-10-20 | Fitur **Kelas Live Scratch** (fork TurboWarp + WebSocket lock-based, dari rencana platform kursus coding 2026-10-09) **DIPARKIR sebagai Fase 9 masa depan** — tidak dikerjakan sekarang. Blueprint dicadangkan hook arsitekturnya (Bagian 16); analisis lengkap di `docs/kelas-live-scratch.md` |

## 4. Arsitektur Ringkas

```text
Browser ──▶ Caddy ──▶ web (Next.js) ──REST──▶ api (FastAPI) ──▶ PostgreSQL 16
                                              ├─ TCML engine (inti + registry modul tag)
                                              ├─ AI gateway ──▶ provider AI milik user (OpenAI-compatible)
                                              └─ file storage (volume lokal → siap S3)
```

- Hierarki konten: `Subject → Meeting → Material / Quiz`, enrollment siswa per subject.
- Model kuis baru: `questions` generik + `question_options` fleksibel (bukan kolom opsi_a..d), `quiz_attempts` + `attempt_answers` ternormalisasi (bukan blob JSON).
- Satu portal login untuk semua role (`admin`, `guru`, `siswa`), redirect per role.

Detail lengkap: `docs/blueprint-v2.md`.

## 5. Aturan Kerja untuk AI di Proyek Ini

1. Baca file ini + blueprint sebelum menulis kode atau mengubah desain.
2. **Setiap aksi/keputusan baru → update file ini** (Status Terkini, Log Keputusan, Log Pembaruan).
3. Dokumen perencanaan/teknis ditulis sebagai **Markdown (.md)**, bukan PDF.
4. Instruksi yang dijalankan Qualze di komputernya harus versi **Windows (Command Prompt)** atau ada alternatif via browser.
5. Jangan memulai fase pembangunan tanpa instruksi eksplisit dari Qualze.
6. Keamanan: tidak ada kredensial/API key yang ditulis ke repo ini — semua lewat env/secret. API key AI user selalu terenkripsi di database.

## 6. Dokumen Terkait

| Dokumen | Isi |
|---|---|
| `docs/blueprint-v2.md` | Blueprint arsitektur lengkap: model data, API, TCML modular, Paket Parser, roadmap Fase 0–8 |
| Repo v1: `jeruk125/Tenebris-Class` | Kode LMS lama (Flask) + `AI_GUIDE.md` (spesifikasi TCML v1) — referensi porting parser & test |

## 7. Log Pembaruan

- **2026-10-20** — File dibuat. Repo Lifunze disiapkan (README, PROJECT.md, blueprint). Status: blueprint terkunci, menunggu penentuan branding, belum mulai Fase 0.
- **2026-10-20** — Aturan berbagi paket diubah: paket parser bisa dibagikan sesama guru (bukan hanya admin). Contoh branding dibuat (3 logo SVG + sample website di `docs/branding/`) dan di-push sebagai commit pertama repo.
- **2026-10-20** — Branding dikunci Qualze: tagline "Serunya Belajar, Mudahnya Mengajar." + warna Violet (Tema A); sample website diperbarui ke tagline final. Analisis fitur Kelas Live Scratch selesai (`docs/kelas-live-scratch.md`) → diparkir sebagai Fase 9, hook dicadangkan di blueprint Bagian 16.
- **2026-10-20** — **Fase 0 selesai & di-push:** scaffold monorepo (web/api), TCML modular, model + migrasi 27 tabel, Docker Compose, endpoint parse & health. Semua verifikasi lolos (pytest 12/12, migrasi bersih, build Next.js OK).
- **2026-10-20** — **Fase 1 selesai & di-push:** auth sesi + CSRF, seed admin, provisioning + created_by + import CSV + audit + soft-delete, Pengaturan AI per akun (Fernet + fetch model + tes koneksi), 6 halaman frontend baru. Verifikasi: pytest 23/23, uji asap e2e lolos, build Next.js OK.
- **2026-10-20** — **Fase 2 selesai & di-push:** subject/meeting/enrollment + arsip mapel, materi TCML parse-gated + cache render + lampiran, editor TCML web + pratinjau, bank dasar (lebih awal dari jadwal Fase 4). Verifikasi: pytest 31/31, uji asap e2e lolos, build Next.js OK.
- **2026-10-20** — **Fase 3 selesai & di-push:** parser kuis v2 (bobot + multi-jawaban), jendela/durasi/acak, attempt + draf + auto-expire, penilaian PG otomatis & esai manual, export nilai CSV/XLSX, integrasi bank kuis v2. Verifikasi: pytest 39/39, uji asap e2e alur kuis lolos, build Next.js OK.
- **2026-10-20** — **Fase 4 selesai & di-push:** salin bank antar guru (jelajah + salin), bank soal (tabel bank_questions, migrasi 0003) + ekstrak soal dari kuis, susun kuis acak dari bank soal dengan TCML tergenerate (roundtrip terverifikasi). Verifikasi: pytest 44/44, build Next.js OK.
- **2026-10-20** — **Fase 5 selesai & di-push:** paket parser (CRUD, 6 paket bawaan, berbagi 3 mode, fork, ekspor .md, spec/contoh modul tersinkron ke DB) + generate AI (prompt hanya dari modul paket, bundle dipecah per root, validasi 2 lapis, draf, self-repair maks 2x, impor eksternal, simpan ke bank/terbitkan). Verifikasi: pytest 54/54 (AI di-mock), build Next.js OK. Menunggu instruksi Fase 6.
