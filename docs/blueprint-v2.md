# Blueprint Arsitektur — Tenebris-Class v2

> **Status:** Blueprint v2 — keputusan utama TERKUNCI (2026-10-20), siap masuk Fase 0
> **Referensi v1:** https://github.com/jeruk125/Tenebris-Class (Flask + SQLite, monolit)
> **Domain deploy:** `lifunze.aditiamh.my.id`
> **Tujuan:** Membangun ulang Tenebris-Class dengan stack modern dan ruang fitur yang lebih besar, tanpa kehilangan jiwa v1: **TCML** (bahasa markup konten sendiri), **Bank Materi & Kuis**, dan konten yang bisa **digenerate AI langsung di dalam LMS**.

---

## Keputusan Terkunci (2026-10-20)

1. **Stack:** Next.js + FastAPI + PostgreSQL (sesuai rekomendasi).
2. **Domain:** `lifunze.aditiamh.my.id`.
3. **Akun admin tambahan:** hanya via seed — tidak ada fitur "buat admin" di UI.
4. **Data:** mulai dari nol bersih — tidak ada migrasi data dari v1.
5. **Fitur:** semua fitur usulan disetujui dan masuk roadmap bertahap (Bagian 14), ditambah dua fitur besar baru dari Qualze: **generate konten AI di dalam LMS** (Bagian 9) dan **sistem Paket Parser** (Bagian 10).

---

## 1. Prinsip Desain v2

1. **TCML tetap jadi jantung.** Pipeline parser (Tokenizer → AST → Renderer) di-porting dan dibuat modular, bukan diganti markdown generik. Ini diferensiasi terbesar v1.
2. **AI adalah warga kelas satu.** Konten bisa digenerate AI langsung di LMS memakai TCML, dengan kunci API milik guru/admin itu sendiri. TCML yang sama dipakai untuk tiga jalur: tulis manual, generate AI internal, dan impor hasil LLM eksternal.
3. **API-first.** Backend menyediakan REST API; frontend adalah klien terpisah. Membuka jalan ke klien lain di masa depan tanpa menulis ulang backend.
4. **Model data ternormalisasi.** Soal tidak lagi kolom `opsi_a..d`, jawaban siswa tidak lagi blob JSON, dan setiap akun punya penanda pembuat.
5. **Provisioning-only.** Tidak ada registrasi publik. Semua akun dibuat oleh manusia yang berwenang dan tercatat siapa pembuatnya (Bagian 3).
6. **Satu portal login.** v1 punya dua portal (`/login` siswa, `/admin_login` guru/admin). v2: satu halaman login untuk semua role, redirect berdasarkan role.
7. **Deploy tetap di Sirius.** Docker Compose + Caddy yang sudah ada, pola yang sama dengan Rephore & SpellWar.

---

## 2. Stack (TERKUNCI)

| Lapisan | Pilihan | Alasan |
|---|---|---|
| Frontend | **Next.js (React + TypeScript)** | Konsisten dengan Rephore; ekosistem besar; editor konten & draf AI nyaman dibangun sebagai SPA |
| Backend | **FastAPI (Python)** | Parser TCML v1 sudah Python → porting murah, test suite v1 bisa dipakai ulang; konsisten dengan Rephore |
| Database | **PostgreSQL 16** | Menggantikan SQLite: konkurensi nyata, JSONB untuk snapshot & payload, siap skala |
| ORM & migrasi | SQLAlchemy 2 + Alembic | Migrasi terkontrol (v1 tidak punya migrasi sama sekali) |
| AI client | HTTP client generik **OpenAI-compatible** (`/chat/completions`, `/models`) | Pola yang sama dengan Pengaturan AI Rephore — guru bisa pakai provider apapun |
| Enkripsi API key | Fernet (kunci dari env) | Sama seperti Rephore: key tersimpan terenkripsi di DB, tidak pernah ditampilkan utuh |
| Auth | Session cookie httpOnly + CSRF token | Lebih aman dari pola v1 (tanpa CSRF) |
| File storage | Abstraksi storage: volume lokal Docker dulu, interface siap S3-compatible | File tidak lagi diserve dari folder static publik |
| Reverse proxy | Caddy (sirius-caddy yang sudah jalan) | Host baru `lifunze.aditiamh.my.id` |
| Kontainer | Docker Compose (web, api, db) | Di `/opt/sirius/compose/tenebris/` |

---

## 3. Sistem Akun (Provisioning-Only)

> Menggantikan perilaku v1 (dulu: siswa daftar sendiri via `/register`, guru dibuat admin, tanpa penanda pembuat).

| Hal | Aturan v2 |
|---|---|
| Akun siswa | Hanya dibuat oleh **guru atau admin**. Registrasi mandiri **dihapus total** (endpoint-nya tidak dibuat) |
| Akun guru | Hanya dibuat oleh **admin** |
| Akun admin | Hanya via **seed** env saat pertama start (TERKUNCI) — tidak ada UI pembuatan admin |
| Penanda pembuat | **Wajib:** kolom `created_by_id` di setiap akun; panel kelola user menampilkan kolom "Dibuat oleh" |
| Bulk import | Guru/admin bisa import siswa via **CSV**; semua akun hasil import tercatat pembuatnya = pengimpor |
| Password awal | Bersifat sementara: flag `must_change_password`, siswa wajib ganti saat login pertama |
| Hak kelola guru | Guru bisa reset password & nonaktifkan siswa **yang dia buat**; siswa buatan orang lain hanya bisa di-enroll ke mapelnya |
| Hak kelola admin | Semua akun (kecuali menghapus admin terakhir — dan admin memang tidak dibuat dari UI) |
| Penghapusan | **Soft-delete** (`is_active=false` / `deleted_at`) agar riwayat nilai tidak yatim; hapus permanen hanya admin |
| Audit | Semua aksi provisioning & kelola akun tercatat di `audit_logs` (siapa, aksi, target, kapan) |

---

## 4. Arsitektur Sistem

```text
                        ┌─────────────────────────────┐
   Browser ─── HTTPS ──▶│  Caddy (sirius-caddy, ada)  │  lifunze.aditiamh.my.id
                        └──────────────┬──────────────┘
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
          ┌───────────────────┐                 ┌───────────────────┐
          │  web (Next.js)    │ ── REST/JSON ─▶ │  api (FastAPI)    │
          │  UI 3 role        │                 │  - Auth & RBAC    │
          └───────────────────┘                 │  - TCML engine    │
                                                │    (inti + modul) │
                                                │  - Quiz engine    │
                                                │  - Bank           │
                                                │  - AI gateway ★   │── HTTPS ──▶ Provider AI milik user
                                                └────────┬──────────┘               (OpenAI-compatible:
                                                         │                 OpenAI/OpenRouter/Gemini/dll)
                                        ┌────────────────┴────────────┐
                                        ▼                             ▼
                               ┌─────────────────┐         ┌──────────────────┐
                               │ PostgreSQL 16   │         │ File storage     │
                               │ (data utama)    │         │ (volume / S3)    │
                               └─────────────────┘         └──────────────────┘
```

- **AI gateway** adalah modul backend yang merakit prompt (dari Paket Parser, Bagian 10), memanggil provider AI sesuai pengaturan akun pengguna yang sedang login (Bagian 9), memvalidasi hasilnya dengan TCML engine, dan menyimpannya sebagai draf.
- TCML engine hidup sebagai modul Python murni (tanpa dependensi web framework) — bisa dites unit terpisah, sama seperti `parsers.py` v1.
- Generate AI adalah proses yang bisa lama → dijalankan sebagai **job** (status bisa dipantau), bukan request yang menggantung.

---

## 5. Model Data v2

Perubahan besar dari v1 ditandai **★**.

### 5.1 Pengguna & audit

```text
users
  id, username (unique), nama_lengkap ★, email (nullable, unique) ★
  password_hash
  role                 : 'admin' | 'guru' | 'siswa'
  created_by_id ★      : FK users.id, NULL hanya untuk admin seed
  must_change_password ★ : bool
  is_active, created_at, updated_at, deleted_at ★ (soft delete)

audit_logs ★
  id, actor_id (FK users), action, target_type, target_id, metadata (JSONB), created_at
```

### 5.2 Pengaturan AI per akun ★ (baru — Bagian 9)

```text
ai_settings ★
  id, user_id (FK users — pemilik: guru atau admin)
  nama                 : label koneksi, mis. "OpenRouter pribadi"
  base_url             : endpoint OpenAI-compatible
  api_key_encrypted    : Fernet; tidak pernah dikembalikan utuh ke frontend
  model                : model terpilih (hasil fetch dari base_url)
  is_default           : koneksi utama milik user ini
  created_at, updated_at
```

### 5.3 Struktur pembelajaran

```text
subjects   : id, nama, deskripsi ★, dibuat_oleh (FK users), is_archived ★, created_at
enrollments ★ (pengganti tabel asosiasi student_subjects)
             student_id, subject_id, enrolled_by (FK users), enrolled_at
             PK gabungan (student_id, subject_id)
meetings   : id, subject_id, judul, urutan, tanggal ★ (opsional), deskripsi ★
materials  : id, meeting_id, judul, teks_mentah (TCML), rendered_html ★ (cache hasil render,
             di-invalidasi saat teks_mentah berubah), dibuat_oleh, timestamps
material_files : id, material_id, storage_key ★, original_filename, mime_type ★, size_bytes ★
```

### 5.4 Kuis — dirancang ulang ★

```text
quizzes
  id, meeting_id, judul
  tipe               : 'pilihan_ganda' | 'teks'   (tetap homogen per kuis)
  teks_mentah        : TCML kanonis ★ (v1 menyimpan format legacy untuk kuis dari UI — diperbaiki)
  dibuat_oleh
  durasi_menit ★     : NULL = tanpa batas waktu
  acak_soal ★, acak_opsi ★ : bool
  dibuka_pada ★, ditutup_pada ★ : jendela pengerjaan (NULL = selalu terbuka)
  tampilkan_kunci ★  : siswa boleh melihat kunci setelah selesai atau tidak

questions ★ (menggantikan QuestionMCQ + QuestionText yang terpisah)
  id, quiz_id, tipe ('pilihan_ganda' | 'teks'), pertanyaan, urutan
  bobot ★            : poin soal
  jawaban_referensi  : untuk soal teks (panduan guru)

question_options ★ (menggantikan kolom opsi_a..d — jumlah opsi fleksibel)
  id, question_id, label ('A', 'B', 'C', ...), teks, is_correct
                     (is_correct jamak → mendukung multi-jawaban-benar)

quiz_attempts ★ (pengganti QuizResult, ternormalisasi)
  id, quiz_id, siswa_id, started_at, submitted_at
  status             : 'in_progress' | 'submitted' | 'graded'
  skor               : NULL sampai dinilai (esai) / otomatis (PG)

attempt_answers ★ (pengganti blob JSON detail_jawaban)
  id, attempt_id, question_id
  option_id (FK question_options, nullable) | jawaban_teks (nullable)
  is_correct (nullable), poin (nullable — diisi saat penilaian esai)
```

### 5.5 Bank

```text
saved_categories : id, nama, dibuat_oleh
saved_materials  : id, judul, teks_mentah, dibuat_oleh, kategori_id
saved_quizzes    : id, judul, tipe, teks_mentah, snapshot ★ (JSONB struktur soal —
                   import tidak lagi bergantung pada parse ulang teks mentah)
```

### 5.6 Paket Parser & generate AI ★ (baru — Bagian 9 & 10)

```text
tag_modules ★
  id, slug (mis. 'inti-materi'), nama, deskripsi
  spec_fragment        : potongan spesifikasi prompt untuk modul ini (ringkas!)
  is_system            : modul bawaan (renderer-nya ada di kode)

tag_examples ★
  id, module_id (FK), judul, konten (contoh TCML valid), urutan

parser_packs ★
  id, nama, deskripsi
  dibuat_oleh (FK users)
  visibilitas ★        : 'private' | 'shared' — pemilik (guru maupun admin) bisa membagikan paketnya ke guru lain
  allowed_roots        : JSON — root block yang diizinkan, mis. ["MATERIAL","QUIZ"]

parser_pack_shares ★
  pack_id, shared_with_id (FK users — NULL berarti dibagikan ke SEMUA guru)
  Penerima bisa MEMAKAI dan MENYALIN (fork) paket ke koleksinya sendiri; hanya pemilik yang bisa mengedit/menghapus.

parser_pack_modules ★
  pack_id, module_id, urutan   (komposisi paket = daftar modul)

generation_jobs ★
  id, user_id (FK), pack_id (FK), ai_setting_id (FK)
  brief (JSONB)        : topik, jenjang, jumlah soal, kesulitan, catatan
  prompt_final         : prompt terakit yang dikirim (untuk audit & debug)
  status               : 'queued' | 'running' | 'done' | 'failed'
  raw_output           : jawaban mentah AI
  created_at, finished_at

content_drafts ★
  id, generation_job_id (nullable — NULL bila dari impor eksternal/manual)
  user_id (FK pemilik draf)
  jenis                : 'material' | 'quiz'
  tipe_quiz            : 'pilihan_ganda' | 'teks' | NULL
  judul, teks_mentah
  is_valid, errors (JSONB: baris + pesan)
  status               : 'draft' | 'published' | 'discarded'
  published_id         : id material/quiz hasil publikasi
```

### 5.7 Fitur lanjutan (skema disiapkan sejak awal)

```text
announcements ★ : id, subject_id, dibuat_oleh, judul, isi, created_at
notifications ★ : id, user_id, tipe, payload (JSONB), read_at, created_at
submissions ★   : id, material_id (konten PROJECT), siswa_id, storage_key,
                  catatan, skor, feedback_rubrik (JSONB), dinilai_oleh, timestamps
material_reads ★: id, material_id, siswa_id, read_at   (bahan progress belajar)
```

---
## 6. Desain API (REST, `/api/v1`)

### 6.1 Auth & akun

```text
POST   /api/v1/auth/login                  # semua role; session cookie httpOnly
POST   /api/v1/auth/logout
GET    /api/v1/auth/me
POST   /api/v1/auth/change-password
POST   /api/v1/auth/first-login-password    # wajib ganti password sementara

POST   /api/v1/admin/teachers              # admin saja → buat akun guru
GET    /api/v1/admin/users?role=&search=   # admin: semua akun + kolom "Dibuat oleh"
PATCH  /api/v1/admin/users/{id}            # reset password, aktif/nonaktif
DELETE /api/v1/admin/users/{id}            # soft delete

POST   /api/v1/users/students              # guru & admin → buat akun siswa
POST   /api/v1/users/students/import       # guru & admin → bulk CSV
GET    /api/v1/users/students              # guru: buatannya; admin: semua
                                               # (tidak ada endpoint register publik)
```

### 6.2 Pengaturan AI & generate ★

```text
GET/POST        /api/v1/ai/settings                 # koneksi AI milik user login
PATCH/DELETE    /api/v1/ai/settings/{id}
POST            /api/v1/ai/settings/fetch-models    # body: {base_url, api_key} → GET {base_url}/models
POST            /api/v1/ai/settings/{id}/test       # ping model terpilih

GET/POST        /api/v1/parser/modules              # admin: kelola modul tag & contoh
GET/POST        /api/v1/parser/packs                # susun paket (pemilik: guru/admin)
POST            /api/v1/parser/packs/{id}/share         # bagikan ke guru lain
POST            /api/v1/parser/packs/{id}/fork          # salin paket orang lain ke koleksi sendiri
GET             /api/v1/parser/packs/{id}/export    # unduh paket sebagai file .md

POST            /api/v1/generate                    # buat generation job (pilih paket + brief)
GET             /api/v1/generate/{job_id}           # status & hasil
POST            /api/v1/generate/{job_id}/repair    # kirim error parse kembali ke AI
GET             /api/v1/drafts                      # draf hasil generate / impor
PATCH           /api/v1/drafts/{id}                 # edit teks draf (re-validasi otomatis)
POST            /api/v1/drafts/{id}/publish         # body: {meeting_id} → jadi Material/Quiz nyata
POST            /api/v1/drafts/import               # tempel hasil LLM eksternal → validasi → draf
```

### 6.3 Pembelajaran, kuis, bank

```text
GET/POST         /api/v1/subjects
GET/PATCH/DELETE /api/v1/subjects/{id}
GET/POST         /api/v1/subjects/{id}/enrollments
GET/POST         /api/v1/subjects/{id}/meetings
GET/POST         /api/v1/meetings/{id}/materials
POST             /api/v1/materials/{id}/files
GET              /api/v1/materials/{id}/preview      # render TCML → HTML

POST             /api/v1/parse/content               # teks TCML → validasi + struktur
GET/POST         /api/v1/meetings/{id}/quizzes       # (pengganti /api/parse_quiz_raw v1)
POST             /api/v1/quizzes/{id}/attempts       # siswa: mulai
POST             /api/v1/attempts/{id}/submit        # siswa: kumpulkan
PATCH            /api/v1/attempts/{id}/grade         # guru: nilai esai
GET              /api/v1/quizzes/{id}/results/export # guru: export nilai CSV/Excel

GET/POST         /api/v1/bank/categories
POST             /api/v1/bank/{materials|quizzes}    # simpan ke bank / import ke pertemuan
```

### 6.4 RBAC di backend

- Dependency `require_roles('admin')`, `require_roles('admin','guru')` di setiap endpoint.
- Kepemilikan: guru hanya mengelola subject/materi/kuis miliknya (v1 membiarkan guru melihat semua subject — diperketat).
- Siswa hanya mengakses subject tempat dia enrolled; validasi enrollment di server, bukan hanya UI.
- Endpoint AI & paket: hanya `admin` dan `guru`. Siswa tidak punya akses AI sama sekali.

---

## 7. TCML v2 — Engine Modular: Inti + Modul Tag

Perubahan arsitektur terpenting dari v1: parser tidak lagi satu file monolit yang tahu semua tag, melainkan **inti generik + registry modul tag**.

```text
tcml/
├── core.py        # Tokenizer + ASTBuilder + validator struktural (tidak tahu tag spesifik)
├── registry.py    # daftar modul tag yang aktif & renderer-nya
├── modules/
│   ├── inti_materi.py     # TITLE, HEADING, PARAGRAPH, NOTE, WARNING, SUMMARY, EXAMPLE, OBJECTIVE, STEPS/STEP
│   ├── tabel_data.py      # DATASET/TABLE (+ tombol Copy Table)
│   ├── formula_kode.py    # FORMULA, CODE
│   ├── latihan.py         # TASKS/TASK, HINT, EXPECTED
│   ├── proyek.py          # DESCRIPTION, REQUIREMENTS/REQUIREMENT, OUTPUT, RUBRIC/CRITERIA
│   ├── kuis_pg.py         # root QUIZ tipe pilihan_ganda: QUESTION/OPTIONS/ANSWER
│   ├── kuis_esai.py       # root QUIZ tipe teks
│   └── scratch.py    ★    # (Fase 7) tag khusus Scratch: blok, sprite, stage
└── legacy.py      # fallback format lama v1 (JUDUL:/SOAL) — dipertahankan untuk kompatibilitas impor
```

- **Inti** hanya paham struktur: tag buka/tutup, nesting, error baris. Ia tidak peduli tag itu apa.
- **Modul tag** mendaftarkan: nama tag, renderer HTML-nya, potongan spesifikasi prompt (`spec_fragment`), dan contoh-contohnya. Spesifikasi & contoh tinggal di **database** (Bagian 5.6) agar bisa diedit lewat UI tanpa deploy; renderer tinggal di **kode**.
- Konsekuensi jujur: menambah tag yang *benar-benar baru* (mis. tag Scratch) tetap butuh kode renderer baru. Yang dibuat tanpa kode adalah **mengombinasikan modul yang sudah ada** menjadi paket baru — dan itulah 95% kebutuhan.
- Root block tetap `[MATERIAL]`, `[EXERCISE]`, `[PROJECT]`, `[QUIZ]`; konten TCML valid v1 tetap valid di v2.
- Hasil render materi di-cache (`materials.rendered_html`), invalidasi saat `teks_mentah` berubah.
- Test suite `test_parsers.py` v1 di-porting 1:1 sebagai baseline regresi engine baru.

---

## 8. Pemetaan Fitur v1 → v2

| Fitur v1 | Status di v2 |
|---|---|
| Login 2 portal | **Disederhanakan** → 1 portal, redirect per role |
| Registrasi siswa mandiri | **Dihapus** → provisioning guru/admin (Bagian 3) |
| Dashboard, pertemuan, baca materi | Dipertahankan, UI baru |
| Upload file materi | Dipertahankan + metadata mime/size, storage abstraction, serve via endpoint ber-auth |
| Kuis PG auto-grade + esai manual | Dipertahankan, model data dinormalisasi |
| Riwayat percobaan | Dipertahankan per attempt |
| Editor kuis + parse dari teks | Dipertahankan, endpoint parse baru |
| Bank Materi & Kuis + import | Dipertahankan + snapshot JSONB |
| Copy item bank antar guru (admin) | Dipertahankan |
| Kelola user oleh admin | Diperluas → provisioning + "Dibuat oleh" + audit + bulk CSV |
| Ganti password | Dipertahankan + wajib ganti saat login pertama |
| AI_GUIDE.md | **Berevolusi** → sistem Paket Parser (Bagian 10): panduan tidak lagi satu dokumen raksasa, melainkan paket-paket kecil yang bisa dirakit & diekspor per kebutuhan |

---
## 9. Fitur Baru: Generate Konten AI di Dalam LMS ★

> Guru/admin dapat membuat **materi, kuis pilihan ganda, dan kuis esai** yang digenerate AI langsung dari LMS, memakai parser TCML yang sudah ada sebagai format keluaran. (Keputusan Qualze, 2026-10-20.)

### 9.1 Pengaturan AI per akun

Setiap akun **guru dan admin punya pengaturan AI-nya sendiri** — menunya persis pola yang sudah terbukti di Rephore:

- **Nama koneksi** (label bebas, mis. "OpenRouter", "Gemini kantor")
- **Base URL** — endpoint OpenAI-compatible apapun
- **API Key** — tersimpan **terenkripsi (Fernet)**, di UI hanya tampil mask (`sk-...••••`), tidak pernah dikirim balik utuh
- **Fetch Model** — tombol yang memanggil `GET {base_url}/models` untuk menarik daftar model yang tersedia dari provider
- **Model** — dipilih dari daftar hasil fetch (atau ketik manual)
- **Tes koneksi** — tombol uji panggil singkat
- Satu user boleh punya banyak koneksi, satu ditandai sebagai default

Generate selalu memakai koneksi milik user yang sedang login. (Opsional nanti: admin menetapkan koneksi cadangan tingkat sistem untuk guru yang belum punya setting sendiri.)

### 9.2 Alur generate

```text
1. Guru membuka "Buat dengan AI"
2. Memilih PAKET PARSER (Bagian 10) → form menyesuaikan:
   jenis konten yang bisa diminta = root block yang diizinkan paket
3. Mengisi brief: topik, subtopik, jenjang/kelas, jumlah soal, tingkat kesulitan, catatan khusus
4. Sistem MERAKIT PROMPT (Bagian 10.3) → memanggil provider AI milik guru (job async)
5. Jawaban AI dipecah per dokumen, di-parse & divalidasi TCML engine
6. Hasil = DRAF-DRAF di halaman "Draf AI" (status valid / daftar error per baris)
7a. Valid → guru review → pilih pertemuan tujuan → Publish (jadi Material/Quiz nyata)
7b. Error → tombol "Perbaiki dengan AI" (error dikirim balik ke model, maks 2x)
    atau guru edit manual di editor TCML dengan penanda error
```

### 9.3 Kenapa hasil AI hampir pasti valid

Karena AI tidak diberi kebebasan format: ia hanya boleh menjawab dalam TCML paket yang dipilih, prompt berisi spesifikasi *hanya tag-tag paket itu* beserta contohnya, dan setiap keluaran melewati validator yang sama persis dengan yang dipakai untuk konten manual. Yang lolos validator = pasti bisa dirender.

---

## 10. Fitur Baru: Sistem Paket Parser ★

> Menjawab masalah inti: spesifikasi TCML lengkap itu besar (AI_GUIDE v1 ≈ 28KB). Mengirim semuanya untuk setiap generate itu boros token, memperlambat, dan membingungkan model dengan tag yang tidak relevan. Solusinya: **jangan kirim seluruh parser — kirim hanya potongan yang relevan dengan yang mau dibuat.**

### 10.1 Tiga lapisan

```text
LAPIS 1 — INTI PARSER (kode, tetap)
  Tokenizer, AST, validator struktural. Tidak pernah dikirim ke AI.

LAPIS 2 — MODUL TAG (kode renderer + data spesifikasi)
  Kelompok tag yang saling terkait. Tiap modul membawa:
  • daftar tag + renderer HTML (di kode)
  • spec_fragment: penjelasan ringkas tiap tag + aturan pakainya (di DB, bisa diedit)
  • contoh-contoh TCML valid (di DB, bisa ditambah/diedit)

LAPIS 3 — PAKET (data murni, disusun lewat menu)
  Kombinasi modul-modul + root block yang diizinkan.
  Paket = "resep prompt" untuk satu jenis kebutuhan.
```

Modul bawaan yang direncanakan: `inti-materi`, `tabel-data`, `formula-kode`, `latihan`, `proyek`, `kuis-pg`, `kuis-esai`, dan `scratch` (Fase 7). Paket bawaan (usul):

| Paket | Isi modul | Bisa menghasilkan |
|---|---|---|
| Materi Mapel Umum | inti-materi, tabel-data, latihan | `[MATERIAL]`, `[EXERCISE]` |
| Spreadsheet & Data | inti-materi, tabel-data, formula-kode, latihan, proyek | `[MATERIAL]`, `[EXERCISE]`, `[PROJECT]` |
| Pemrograman | inti-materi, formula-kode, latihan, proyek, kuis-pg, kuis-esai | semua root |
| Kuis PG | kuis-pg | `[QUIZ]` pilihan ganda |
| Kuis Esai | kuis-esai | `[QUIZ]` teks |
| Scratch | inti-materi, scratch, kuis-pg | `[MATERIAL]`, `[QUIZ]` PG (Fase 7) |
| Kelas Lengkap | semua modul | gabungan satu pertemuan penuh: materi + latihan + kuis sekaligus |

### 10.2 Menu "Paket Parser"

- Daftar modul dengan checkbox: admin/guru **memilih modul mana saja** yang masuk paket, mengurutkannya, dan memilih contoh mana yang ikut (contoh adalah bagian termahal secara token — jadi bisa dipilih, bukan wajib semua).
- Pratinjau rakitan: sebelum menyimpan, pengguna bisa melihat prompt final yang akan dikirim ke AI + estimasi ukuran (jumlah karakter/token kasar).
- Paket bersifat personal secara default; **pemiliknya (guru maupun admin) dapat membagikannya ke guru lain** — ke guru tertentu, atau ke semua guru sekaligus (perubahan aturan 2026-10-20, atas permintaan Qualze). Penerima bisa memakai dan menyalin (fork) paket ke koleksinya sendiri; hanya pemilik yang bisa mengedit atau menghapusnya.
- **Ekspor .md**: satu paket dapat diunduh sebagai satu file Markdown utuh (instruksi + spesifikasi modul terpilih + contoh terpilih + aturan emas yang relevan) — file inilah yang dikirim ke LLM **di luar** LMS untuk membuat materi/esai/soal di sana. AI_GUIDE v1 pada dasarnya adalah bentuk manual dari ekspor ini; v2 membuatnya otomatis dan per-paket.

### 10.3 Perakitan prompt (prompt builder)

```text
PROMPT FINAL =
  [Blok peran & aturan emas umum]            ← kecil, tetap (±15 baris)
+ [spec_fragment modul-modul TERPILIH]     ← hanya tag dalam paket
+ [contoh-contoh TERPILIH dari modul itu]  ← few-shot, per paket
+ [Brief pengguna]                          ← topik, jenjang, jumlah soal, kesulitan
```

Dampaknya: membuat 10 soal PG hanya mengirim spesifikasi modul `kuis-pg` (kecil), bukan seluruh TCML. Membuat materi Scratch hanya mengirim modul inti + scratch. Token sebanding dengan kebutuhan, dan model tidak tergoda memakai tag di luar yang diminta — karena ia tidak tahu tag lain ada.

### 10.4 Bagaimana LMS beradaptasi dengan paket (routing multi-dokumen)

Ini jawaban atas masalah "satu generate bisa jadi materi, esai, soal abc, atau gabungan":

1. AI boleh mengembalikan **beberapa dokumen sekaligus** dalam satu jawaban — masing-masing dibungkus root block-nya sendiri.
2. Backend **memecah** jawaban berdasarkan root block, lalu memvalidasi tiap dokumen **dua lapis**:
   - *Lapis sintaks:* struktur AST benar (semua tag tertutup, nesting sah).
   - *Lapis skema paket:* hanya tag milik modul dalam paket yang boleh muncul; root block harus termasuk yang diizinkan paket; kuis harus homogen (tidak campur PG + esai).
3. Tiap dokumen yang lolos menjadi **satu draf** dengan jenis yang ditentukan root-nya:
   - `[MATERIAL]` / `[EXERCISE]` / `[PROJECT]` → draf materi
   - `[QUIZ]` + `[TYPE]pilihan_ganda` → draf kuis PG
   - `[QUIZ]` + `[TYPE]teks` → draf kuis esai
4. Guru mereview draf-draf itu sebagai satu **bundle** ("Hasil generate: 1 materi, 1 latihan, 1 kuis PG"), memilih pertemuan tujuan untuk masing-masing, lalu publish. Dokumen yang gagal validasi tetap tampil sebagai draf error dengan pesan per baris — tidak dibuang diam-diam.
5. Jalur yang sama dipakai **impor eksternal**: hasil LLM luar (yang dibuat dengan file .md ekspor paket) ditempel ke menu Impor → dipecah, divalidasi dua lapis, menjadi draf. Satu definisi paket melayani dua jalur: generate internal dan eksternal.

### 10.5 Perbaikan otomatis (self-repair)

Jika validasi gagal, sistem dapat mengirim balik ke AI: dokumen yang rusak + daftar error terstruktur (baris & pesan) + instruksi "perbaiki hanya bagian ini". Maksimal **2 percobaan otomatis**; setelah itu draf diserahkan ke guru untuk diedit manual di editor TCML (yang menampilkan error per baris, meneruskan kebiasaan baik v1).

---
## 11. Fitur Besar yang Disetujui (semua masuk roadmap)

Seluruh usulan berikut **disetujui Qualze 2026-10-20** dan sudah didistribusikan ke fase-fase di Bagian 14:

1. Jendela waktu & durasi kuis (`dibuka_pada`, `ditutup_pada`, `durasi_menit`)
2. Progress belajar siswa (tracking materi dibaca via `material_reads` + kuis dikerjakan; ringkasan per siswa untuk guru)
3. Pengumuman per mapel (`announcements`)
4. Notifikasi in-app (nilai esai selesai, pengumuman baru, kuis akan ditutup) — kanal email opsional
5. Bank soal & penyusunan kuis acak dari bank; acak soal/opsi per siswa
6. Bobot soal per butir & soal PG multi-jawaban-benar
7. Export nilai per mapel/kuis ke CSV/Excel
8. Tugas file untuk `[PROJECT]`: siswa upload jawaban, guru menilai dengan rubrik TCML (`submissions`)
9. Arsip mapel (`is_archived`)
10. Mode hemat kuota: halaman baca materi & kuis dirender ringan, aset minimal

---

## 12. Keamanan

- `SECRET_KEY`, kredensial admin seed, dan kunci enkripsi Fernet **wajib dari env**; aplikasi menolak start tanpanya (meneruskan hardening v1).
- API key AI user: terenkripsi Fernet at-rest, tampil mask di UI, tidak pernah masuk log, tidak pernah dikembalikan utuh oleh API.
- Password: hashing adaptif (argon2/bcrypt); password awal hasil provisioning wajib diganti.
- Session cookie `httpOnly` + `Secure` + `SameSite=Lax`, CSRF token di semua mutasi (v1 tidak punya ini).
- Upload file: validasi ekstensi **dan magic bytes**, batas 16MB, nama acak, disimpan di luar web root, diserve via endpoint ber-auth.
- Rate limit login (mis. 10 percobaan/menit/IP) — permukaan serangan utama karena tidak ada registrasi publik.
- Generate AI: prompt & output tersimpan per job hanya bisa diakses pemilik job (dan admin); biaya token adalah tanggung jawab koneksi pemilik akun itu sendiri.

---

## 13. Deployment di Sirius

```text
/opt/sirius/compose/tenebris/
├── docker-compose.yml      # web (Next.js) + api (FastAPI) + db (PostgreSQL 16)
├── .env                    # SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD,
│                           # FERNET_KEY, DB creds (chmod 600)
└── backups/                # cron pg_dump harian, retensi 7 hari (pola backup Rephore)
```

- Caddy: host **`lifunze.aditiamh.my.id`** → reverse proxy ke `web`; path `/api/*` → `api`. TLS otomatis.
- Data dimulai **dari nol bersih** (TERKUNCI) — tidak ada script migrasi dari SQLite v1.
- Catatan lingkungan: jangan andalkan screenshot Playwright untuk QA visual di VM ini (download Chromium gagal) — verifikasi via curl + eyeball manual, pola yang sama dengan SpellWar.

---

## 14. Roadmap Bertahap (semua fitur terdistribusi)

| Fase | Isi | Keluaran |
|---|---|---|
| **0 — Fondasi** | Scaffold monorepo (web/api), Docker Compose, PostgreSQL + Alembic; TCML engine modular (inti + registry + modul bawaan v1) di-porting; test parser v1 jadi baseline regresi | Engine TCML v2 lolos test lama |
| **1 — Akun, RBAC & Pengaturan AI** | Auth 1 portal; provisioning guru/siswa + `created_by` + bulk CSV + audit log + soft-delete; panel kelola user; **menu Pengaturan AI per akun** (base URL, key terenkripsi, fetch model, tes koneksi) | Sistem akun & koneksi AI siap |
| **2 — Pembelajaran inti** | Subject → Meeting → Material (editor TCML + preview + cache render), upload file, enrollment, dashboard 3 role, **arsip mapel** (fitur 9) | Alur baca materi end-to-end |
| **3 — Kuis v2** | Engine kuis baru (questions/options/attempts ternormalisasi), **jendela waktu & durasi** (fitur 1), **bobot & multi-jawaban-benar** (fitur 6), editor + endpoint parse, penilaian esai, **export nilai** (fitur 7) | Alur kuis end-to-end, melampaui v1 |
| **4 — Bank** | Bank materi & kuis + kategori + snapshot JSONB + copy antar guru; **bank soal & susun kuis acak** (fitur 5) + acak soal/opsi saat pengerjaan | Bank fungsional penuh |
| **5 — Paket Parser & Generate AI** | Registry modul tag (spesifikasi & contoh di DB), **menu Paket Parser** (susun modul + pilih contoh + pratinjau prompt + **ekspor .md**), paket bawaan (Mapel Umum, Spreadsheet, Pemrograman, Kuis PG, Kuis Esai, Kelas Lengkap), **generate di LMS** (job async, bundle multi-dokumen, validasi 2 lapis, self-repair, draf → publish), **impor konten eksternal** | Fitur pembeda utama v2 live |
| **6 — Pengalaman belajar** | **Progress belajar** (fitur 2), **pengumuman mapel** (fitur 3), **notifikasi in-app** (fitur 4), **tugas file `[PROJECT]` + penilaian rubrik** (fitur 8), **mode hemat kuota** (fitur 10) | LMS terasa "besar" |
| **7 — Paket khusus** | Modul tag **Scratch** (renderer blok/sprite/stage + spesifikasi + contoh) + paket Scratch; pendalaman paket Mapel Umum | Parser tidak lagi bias pemrograman |
| **8 — Hardening & go-live** | Rate limiting, validasi magic bytes, review keamanan, backup terjadwal, deploy ke **lifunze.aditiamh.my.id**, data mulai bersih | v2 live |
| **9 — Masa depan (belum dijadwalkan)** | **Kelas Live Scratch**: fork editor TurboWarp (repo publik terpisah, GPL-3.0) + service WebSocket lock-based "gantian pegang kendali" + room per pertemuan + SSO dari Lifunze. Hanya diaktifkan atas keputusan eksplisit Qualze. Analisis: `docs/kelas-live-scratch.md` | Ruang praktik live Scratch |

---

## 15. Ringkasan Keputusan

| # | Keputusan | Status |
|---|---|---|
| 1 | Stack Next.js + FastAPI + PostgreSQL | ✅ Terkunci 2026-10-20 |
| 2 | Domain `lifunze.aditiamh.my.id` | ✅ Terkunci 2026-10-20 |
| 3 | Akun admin hanya via seed | ✅ Terkunci 2026-10-20 |
| 4 | Mulai dari nol bersih, tanpa migrasi v1 | ✅ Terkunci 2026-10-20 |
| 5 | Semua fitur usulan masuk roadmap | ✅ Disetujui 2026-10-20 |
| 6 | Registrasi mandiri dihapus; provisioning + `created_by` | ✅ Terkunci 2026-10-20 |
| 7 | Generate AI di LMS dengan pengaturan per akun (base URL, API key, fetch model, model) | ✅ Disetujui 2026-10-20 |
| 8 | Parser dimodularisasi; Paket Parser sebagai unit yang dikirim ke AI & bisa diekspor .md | ✅ Disetujui 2026-10-20 |
| 9 | Paket parser dapat dibagikan sesama guru (bukan hanya admin); penerima bisa memakai & fork | ✅ Terkunci 2026-10-20 |
| 10 | Branding final: tagline "Serunya Belajar, Mudahnya Mengajar." + warna Violet (Tema A) | ✅ Terkunci 2026-10-20 |
| 11 | Kelas Live Scratch diparkir sebagai Fase 9 masa depan; hook arsitektur dicadangkan (Bagian 16) | ✅ Terkunci 2026-10-20 |

---

## 16. Cadangan Masa Depan: Kelas Live Scratch (Fase 9 — belum dijadwalkan)

> Fitur dari rencana platform kursus coding anak (2026-10-09): room kelas live tempat tiap siswa punya project Scratch sendiri, guru bisa melihat semua dan **mengambil alih kendali** project siswa (lock-based "gantian pegang kendali", sync `vm.toJSON()` via WebSocket, penonton read-only, audio tetap via Meet). **Tidak dikerjakan di Fase 0–8.** Analisis lengkap: `docs/kelas-live-scratch.md`.

Dua penyesuaian besar yang sudah disepakati arahnya:

1. **Editor = layanan pendamping terpisah, bukan modul Lifunze.** Fork TurboWarp (GPL-3.0) hidup di repo publiknya sendiri + subdomain sendiri (usul `scratch.lifunze.aditiamh.my.id`), karena menggabungkannya ke frontend Lifunze mencemari lisensi & memberatkan build.
2. **Realtime = service WebSocket Node terpisah** (satu bahasa dengan editor), bukan di dalam FastAPI.

Hook yang **dicadangkan dari sekarang** (biaya ±nol, murni disiplin desain):

- Tabel live masa depan (`live_sessions`, `live_projects`) ber-FK ke `meetings.id` & `users.id` — tabel inti Lifunze **tidak perlu diubah** saat fitur ini datang; jaga desain kunci `users` & `meetings` tetap standar (integer PK).
- Slot container `live` dicadangkan di rencana Docker Compose + jalur WebSocket di Caddy (subdomain editor).
- Pola **token SSO sekali pakai** (berumur pendek, diterbitkan API Lifunze, divalidasi service pendamping) dicatat sebagai pola integrasi standar untuk layanan pendamping manapun.
- Ekstensi file **`.sb3`** dicatat sebagai tipe masa depan untuk storage (project Scratch siswa).
- Peran room diturunkan dari role + enrollment yang sudah ada: guru = host (bisa take-over), siswa = pemilik project, siswa lain = penonton.
- Paket Parser Scratch (Fase 7) dan fitur live ini **dua hal berbeda yang saling melengkapi**: paket = konten materi/kuis Scratch; live = ruang praktiknya.

---

*Dokumen hidup — diperbarui setiap ada keputusan baru. Terakhir diperbarui 2026-10-20 (blueprint v2.1: branding terkunci + cadangan Kelas Live Scratch).*
