# Lifunze

**LMS modern dengan generate konten AI** — platform kelas online untuk guru dan siswa, penerus dari [Tenebris-Class](https://github.com/jeruk125/Tenebris-Class).

Guru mengelola mata pelajaran → pertemuan → materi & kuis. Siswa belajar dan mengerjakan kuis. Yang membedakan Lifunze:

- **TCML** — bahasa markup konten sendiri untuk materi, latihan, proyek, dan kuis yang kaya fitur (tabel dengan tombol copy-ke-Excel, blok formula/kode, rubrik, dll), dirender aman dari teks biasa.
- **Generate AI di dalam LMS** — materi, kuis pilihan ganda, dan kuis esai dibuat AI langsung dari aplikasi, memakai **Paket Parser** (komposisi modul tag TCML yang bisa disusun, dibagikan sesama guru, dan diekspor sebagai file `.md` untuk LLM eksternal).
- **Akun terkelola penuh** — tidak ada registrasi publik; akun siswa dibuat guru/admin, akun guru dibuat admin, dan setiap akun tercatat siapa pembuatnya.

## Status

🚧 **Blueprint selesai, pembangunan belum dimulai.** Arsitektur dan semua keputusan utama sudah terkunci; langkah berikutnya adalah penentuan branding, lalu Fase 0 (fondasi).

## Stack

| Lapisan | Teknologi |
|---|---|
| Frontend | Next.js (React + TypeScript) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 16 |
| AI | Provider OpenAI-compatible pilihan tiap guru/admin (base URL + API key sendiri) |
| Deploy | Docker Compose di VPS, reverse proxy Caddy — `lifunze.aditiamh.my.id` |

## Dokumen

- **[PROJECT.md](PROJECT.md)** — konteks utama proyek: keputusan terkunci, status terakhir, dan aturan kerja. *Wajib dibaca sebelum berkontribusi (manusia maupun AI).*
- **[docs/blueprint-v2.md](docs/blueprint-v2.md)** — blueprint arsitektur lengkap: model data, desain API, engine TCML modular, sistem Paket Parser, dan roadmap Fase 0–8.

## Lisensi

Belum ditentukan.
