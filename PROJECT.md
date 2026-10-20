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

- **2026-10-20:** Blueprint arsitektur v2 selesai & semua keputusan utama terkunci (lihat Bagian 3). **Belum ada kode — fase pembangunan belum dimulai atas instruksi Qualze.**
- **2026-10-20:** Repo GitHub `qualzecoat/Lifunze` dibuat oleh Qualze; commit pertama di-push Muse (README, PROJECT.md, blueprint, contoh branding).
- **Branding (sedang ditentukan):** makna nama disepakati Qualze: **"Learning is Fun, Zero Effort"** — tempat belajar & mengajar yang seru dan mudah berkat bantuan teknologi. Contoh logo 3 palet (A Violet / B Teal / C Biru) + sample website ada di `docs/branding/`. Usulan tagline utama Muse: **"Belajar Makin Seru, Mengajar Makin Mudah."** Menunggu pilihan arah warna & tagline final dari Qualze.

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
