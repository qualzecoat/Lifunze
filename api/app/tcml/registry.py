# Registry modul tag TCML.
#
# Engine inti (core.py) tidak tahu tag spesifik; renderer (renderers.py)
# mengimplementasikan tag-tag di bawah ini. Registry ini adalah metadata
# pengelompokan tag per MODUL — fondasi sistem Paket Parser (Fase 5):
# sebuah paket adalah komposisi modul-modul dari daftar ini, dan hanya
# spesifikasi (spec_fragment) + contoh modul terpilih yang dikirim ke AI.
# spec/contoh registry ini disinkronkan ke tabel tag_modules/tag_examples.
#
# Menambah tag baru = tambah renderer di renderers.py + daftarkan di sini.

MODULES = {
    "inti-materi": {
        "nama": "Inti Materi",
        "roots": ["MATERIAL", "EXERCISE", "PROJECT"],
        "tags": [
            "TITLE", "HEADING", "PARAGRAPH", "NOTE", "WARNING", "SUMMARY",
            "EXAMPLE", "OBJECTIVE", "STEPS", "STEP",
        ],
        "deskripsi": "Struktur dasar dokumen belajar: judul, subjudul, paragraf, catatan, peringatan, ringkasan, contoh, tujuan, dan langkah-langkah. Hampir selalu dipakai.",
        "spec": (
            "Dokumen materi diawali salah satu root: [MATERIAL], [EXERCISE], atau [PROJECT], dan diakhiri tag penutupnya.\n"
            "Di dalam root, blok-blok berikut tersedia:\n"
            "- [TITLE]Judul utama dokumen[/TITLE] (wajib, satu kali, paling atas)\n"
            "- [HEADING]Subjudul bagian[/HEADING]\n"
            "- [PARAGRAPH]Teks paragraf biasa.[/PARAGRAPH] (teks bebas di luar blok juga dianggap paragraf)\n"
            "- [NOTE]Catatan tambahan/pengingat.[/NOTE]\n"
            "- [WARNING]Peringatan penting.[/WARNING]\n"
            "- [SUMMARY]Ringkasan isi.[/SUMMARY]\n"
            "- [EXAMPLE]Contoh penerapan.[/EXAMPLE]\n"
            "- [OBJECTIVE]Tujuan pembelajaran.[/OBJECTIVE]\n"
            "- [STEPS] berisi satu atau lebih [STEP]Langkah ke-n[/STEP] [/STEPS]"
        ),
        "contoh": [
            {
                "judul": "Materi singkat dengan langkah",
                "konten": (
                    "[MATERIAL]\n"
                    "[TITLE]Mengenal Pecahan[/TITLE]\n"
                    "[OBJECTIVE]Siswa dapat membaca dan menulis pecahan sederhana.[/OBJECTIVE]\n"
                    "[PARAGRAPH]Pecahan menyatakan bagian dari keseluruhan.[/PARAGRAPH]\n"
                    "[NOTE]Pembilang adalah angka di atas, penyebut di bawah.[/NOTE]\n"
                    "[STEPS]\n"
                    "[STEP]Perhatikan gambar pizza yang dibagi 4 sama besar.[/STEP]\n"
                    "[STEP]Satu potong ditulis 1/4.[/STEP]\n"
                    "[/STEPS]\n"
                    "[SUMMARY]Pecahan ditulis pembilang/penyebut.[/SUMMARY]\n"
                    "[/MATERIAL]"
                ),
            }
        ],
    },
    "tabel-data": {
        "nama": "Tabel & Dataset",
        "roots": [],
        "tags": ["DATASET", "TABLE"],
        "deskripsi": "Menampilkan data tabular: dataset (dari teks CSV) dan tabel manual di dalam materi.",
        "spec": (
            "- [DATASET] baris pertama [TITLE]Judul dataset[/TITLE], baris berikutnya data CSV "
            "(baris pertama CSV = header kolom, pemisah koma). [/DATASET]\n"
            "- [TABLE] sama seperti DATASET: [TITLE] opsional lalu baris-baris CSV. [/TABLE]"
        ),
        "contoh": [
            {
                "judul": "Dataset nilai",
                "konten": (
                    "[DATASET]\n"
                    "[TITLE]Nilai Ulangan Kelas 5A[/TITLE]\n"
                    "Nama,Nilai\n"
                    "Andi,85\n"
                    "Bela,92\n"
                    "[/DATASET]"
                ),
            }
        ],
    },
    "formula-kode": {
        "nama": "Formula & Kode",
        "roots": [],
        "tags": ["FORMULA", "CODE"],
        "deskripsi": "Rumus matematika/sains dan potongan kode program di dalam materi.",
        "spec": (
            "- [FORMULA]Rumus dalam teks biasa, mis. Luas = p x l[/FORMULA]\n"
            "- [CODE]Potongan kode apa adanya (indentasi dipertahankan).[/CODE]"
        ),
        "contoh": [
            {
                "judul": "Formula dan kode",
                "konten": (
                    "[FORMULA]Keliling persegi = 4 x sisi[/FORMULA]\n"
                    "[CODE]\n"
                    "for i in range(3):\n"
                    "    print(i)\n"
                    "[/CODE]"
                ),
            }
        ],
    },
    "latihan": {
        "nama": "Latihan & Tugas Praktik",
        "roots": ["EXERCISE"],
        "tags": ["TASKS", "TASK", "HINT", "EXPECTED"],
        "deskripsi": "Dokumen latihan [EXERCISE]: daftar tugas praktik yang harus dikerjakan siswa, lengkap dengan petunjuk dan hasil yang diharapkan.",
        "spec": (
            "Root [EXERCISE] berisi: [TITLE] (dari modul inti), lalu:\n"
            "- [TASKS] berisi satu atau lebih [TASK]Instruksi tugas[/TASK] [/TASKS]\n"
            "- [HINT]Petunjuk pengerjaan.[/HINT]\n"
            "- [EXPECTED]Hasil akhir yang diharapkan.[/EXPECTED]"
        ),
        "contoh": [
            {
                "judul": "Latihan praktik",
                "konten": (
                    "[EXERCISE]\n"
                    "[TITLE]Latihan Membuat Tabel[/TITLE]\n"
                    "[TASKS]\n"
                    "[TASK]Buat tabel berisi 3 nama teman dan umur mereka.[/TASK]\n"
                    "[TASK]Hitung rata-rata umurnya.[/TASK]\n"
                    "[/TASKS]\n"
                    "[HINT]Gunakan rumus rata-rata = jumlah / banyak data.[/HINT]\n"
                    "[EXPECTED]Tabel rapi dan rata-rata yang benar.[/EXPECTED]\n"
                    "[/EXERCISE]"
                ),
            }
        ],
    },
    "proyek": {
        "nama": "Proyek",
        "roots": ["PROJECT"],
        "tags": [
            "DESCRIPTION", "REQUIREMENTS", "REQUIREMENT", "OUTPUT",
            "RUBRIC", "CRITERIA",
        ],
        "deskripsi": "Dokumen proyek [PROJECT]: deskripsi, syarat pengerjaan, output yang dikumpulkan, dan rubrik penilaian.",
        "spec": (
            "Root [PROJECT] berisi: [TITLE] (dari modul inti), lalu:\n"
            "- [DESCRIPTION]Deskripsi proyek.[/DESCRIPTION]\n"
            "- [REQUIREMENTS] berisi satu atau lebih [REQUIREMENT]Syarat[/REQUIREMENT] [/REQUIREMENTS]\n"
            "- [OUTPUT]Bentuk hasil yang dikumpulkan.[/OUTPUT]\n"
            "- [RUBRIC]Rubrik penilaian.[/RUBRIC]\n"
            "- [CRITERIA]Kriteria penilaian.[/CRITERIA]"
        ),
        "contoh": [
            {
                "judul": "Proyek mini",
                "konten": (
                    "[PROJECT]\n"
                    "[TITLE]Proyek Poster Hemat Air[/TITLE]\n"
                    "[DESCRIPTION]Buat poster kampanye hemat air untuk sekolah.[/DESCRIPTION]\n"
                    "[REQUIREMENTS]\n"
                    "[REQUIREMENT]Poster ukuran A3.[/REQUIREMENT]\n"
                    "[REQUIREMENT]Mengandung minimal 3 tips hemat air.[/REQUIREMENT]\n"
                    "[/REQUIREMENTS]\n"
                    "[OUTPUT]File foto poster atau poster fisik.[/OUTPUT]\n"
                    "[RUBRIC]Kreativitas 40, isi 40, kerapian 20.[/RUBRIC]\n"
                    "[/PROJECT]"
                ),
            }
        ],
    },
    "kuis-pg": {
        "nama": "Kuis Pilihan Ganda",
        "roots": ["QUIZ"],
        "tags": ["TYPE", "QUESTION_BLOCK", "QUESTION", "OPTIONS", "ANSWER", "WEIGHT"],
        "deskripsi": "Kuis pilihan ganda lengkap: opsi berlabel huruf, kunci jawaban (boleh lebih dari satu), dan bobot per soal.",
        "spec": (
            "Struktur kuis PG:\n"
            "[QUIZ]\n"
            "[TYPE]pilihan_ganda[/TYPE]\n"
            "[QUESTION 1]\n"
            "[QUESTION]Teks pertanyaan[/QUESTION]\n"
            "[OPTIONS]\n"
            "A. Teks opsi A\n"
            "B. Teks opsi B\n"
            "C. Teks opsi C\n"
            "[/OPTIONS]\n"
            "[ANSWER]B[/ANSWER]\n"
            "[/QUESTION 1]\n"
            "[/QUIZ]\n"
            "Aturan:\n"
            "- Nomor soal pada [QUESTION n] dan [/QUESTION n] harus urut mulai 1.\n"
            "- Opsi minimal 2, label huruf kapital berurutan mulai A.\n"
            "- [ANSWER] berisi label jawaban benar; boleh lebih dari satu dipisah koma, mis. [ANSWER]B, C[/ANSWER] (siswa harus memilih persis himpunan itu).\n"
            "- [WEIGHT]2[/WEIGHT] opsional di dalam blok soal untuk bobot (default 1, boleh desimal)."
        ),
        "contoh": [
            {
                "judul": "Kuis PG dengan bobot & multi-jawaban",
                "konten": (
                    "[QUIZ]\n"
                    "[TYPE]pilihan_ganda[/TYPE]\n"
                    "[QUESTION 1]\n"
                    "[QUESTION]Manakah yang termasuk bilangan prima?[/QUESTION]\n"
                    "[OPTIONS]\n"
                    "A. 4\n"
                    "B. 5\n"
                    "C. 7\n"
                    "D. 9\n"
                    "[/OPTIONS]\n"
                    "[ANSWER]B, C[/ANSWER]\n"
                    "[WEIGHT]2[/WEIGHT]\n"
                    "[/QUESTION 1]\n"
                    "[QUESTION 2]\n"
                    "[QUESTION]Ibu kota Indonesia adalah...[/QUESTION]\n"
                    "[OPTIONS]\n"
                    "A. Bandung\n"
                    "B. Jakarta\n"
                    "[/OPTIONS]\n"
                    "[ANSWER]B[/ANSWER]\n"
                    "[/QUESTION 2]\n"
                    "[/QUIZ]"
                ),
            }
        ],
    },
    "kuis-esai": {
        "nama": "Kuis Esai",
        "roots": ["QUIZ"],
        "tags": ["TYPE", "QUESTION_BLOCK", "QUESTION", "ANSWER", "WEIGHT"],
        "deskripsi": "Kuis esai/teks: pertanyaan terbuka dengan jawaban referensi sebagai pedoman penilaian guru, plus bobot per soal.",
        "spec": (
            "Struktur kuis esai:\n"
            "[QUIZ]\n"
            "[TYPE]essay[/TYPE]\n"
            "[QUESTION 1]\n"
            "[QUESTION]Teks pertanyaan[/QUESTION]\n"
            "[ANSWER]Jawaban referensi untuk pedoman penilaian guru.[/ANSWER]\n"
            "[WEIGHT]3[/WEIGHT]\n"
            "[/QUESTION 1]\n"
            "[/QUIZ]\n"
            "Aturan: nomor soal urut mulai 1; [ANSWER] adalah referensi penilaian (bukan ditampilkan ke siswa); [WEIGHT] opsional (default 1)."
        ),
        "contoh": [
            {
                "judul": "Kuis esai singkat",
                "konten": (
                    "[QUIZ]\n"
                    "[TYPE]essay[/TYPE]\n"
                    "[QUESTION 1]\n"
                    "[QUESTION]Jelaskan proses fotosintesis dengan bahasamu sendiri.[/QUESTION]\n"
                    "[ANSWER]Tumbuhan mengubah cahaya matahari, air, dan CO2 menjadi glukosa dan oksigen.[/ANSWER]\n"
                    "[WEIGHT]3[/WEIGHT]\n"
                    "[/QUESTION 1]\n"
                    "[/QUIZ]"
                ),
            }
        ],
    },
    # "scratch": modul khusus Scratch — direncanakan Fase 7 (belum ada renderer).
}

ROOT_BLOCKS = ["MATERIAL", "EXERCISE", "PROJECT", "QUIZ"]

TAG_TO_MODULE = {}
for _slug, _mod in MODULES.items():
    for _tag in _mod["tags"]:
        TAG_TO_MODULE.setdefault(_tag, []).append(_slug)
