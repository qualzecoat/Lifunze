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
        "deskripsi": "Menampilkan data dalam bentuk tabel di dalam materi (baris pertama = judul kolom, sel dipisah tanda |).",
        "spec": (
            "- [DATASET] tabel data: baris pertama = judul kolom, tiap sel dipisah tanda | (pipe), satu baris data per baris teks. [/DATASET]\n"
            "- [TABLE] sama seperti DATASET: baris pertama = judul kolom, sel dipisah tanda |. [/TABLE]"
        ),
        "contoh": [
            {
                "judul": "Tabel nilai di dalam materi",
                "konten": (
                    "[MATERIAL]\n"
                    "[TITLE]Nilai Ulangan Kelas 5A[/TITLE]\n"
                    "[PARAGRAPH]Berikut rekap nilai ulangan matematika minggu ini.[/PARAGRAPH]\n"
                    "[DATASET]\n"
                    "Nama | Nilai | Keterangan\n"
                    "Andi | 85 | Tuntas\n"
                    "Bela | 92 | Tuntas\n"
                    "Citra | 72 | Remedial\n"
                    "[/DATASET]\n"
                    "[/MATERIAL]"
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
                "judul": "Formula dan kode di dalam materi",
                "konten": (
                    "[MATERIAL]\n"
                    "[TITLE]Keliling Persegi[/TITLE]\n"
                    "[PARAGRAPH]Keliling persegi dihitung dengan rumus berikut.[/PARAGRAPH]\n"
                    "[FORMULA]Keliling persegi = 4 x sisi[/FORMULA]\n"
                    "[CODE]\n"
                    "for i in range(3):\n"
                    "    print(i)\n"
                    "[/CODE]\n"
                    "[/MATERIAL]"
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
    "cek-pemahaman": {
        "nama": "Cek Pemahaman (Soal Sisipan)",
        "roots": [],
        "tags": ["CEK", "QUESTION", "OPTIONS", "ANSWER", "WEIGHT", "TYPE"],
        "deskripsi": (
            "Soal latihan ringan DI DALAM materi: blok [CEK] berisi satu soal PG atau esai "
            "yang diselipkan di antara bacaan untuk mengecek pemahaman. Dinilai otomatis (PG) "
            "atau cek mandiri dengan referensi (esai), masuk nilai materi, boleh diulang, "
            "TANPA timer/jendela — bukan untuk ujian (ujian memakai modul Kuis)."
        ),
        "spec": (
            "Soal sisipan Cek Pemahaman ditulis dengan blok [CEK] di dalam root materi, "
            "di antara blok bacaan, setelah bagian yang ingin dicek pemahamannya:\n"
            "[CEK]\n"
            "[QUESTION]Teks pertanyaan[/QUESTION]\n"
            "[OPTIONS]\n"
            "A. Pilihan A\n"
            "B. Pilihan B\n"
            "[/OPTIONS]\n"
            "[ANSWER]B[/ANSWER]\n"
            "[/CEK]\n"
            "Untuk esai ganti isi blok menjadi: [TYPE]essay[/TYPE] lalu [QUESTION]...[/QUESTION] "
            "lalu [ANSWER]Jawaban referensi untuk cek mandiri siswa[/ANSWER] (referensi WAJIB ada).\n"
            "Aturan:\n"
            "- Satu blok [CEK] = satu soal. Taruh setelah bagian penting, jangan menumpuk banyak soal berurutan.\n"
            "- PG: [OPTIONS] minimal 2 pilihan berlabel huruf; [ANSWER] label yang benar (boleh lebih dari satu, pisah koma).\n"
            "- [WEIGHT]2[/WEIGHT] opsional untuk bobot (default 1).\n"
            "- Soal [CEK] adalah LATIHAN, bukan ujian: buat yang menguji pemahaman bagian tepat sebelumnya."
        ),
        "contoh": [
            {
                "judul": "Materi pecahan dengan cek pemahaman PG & esai",
                "konten": (
                    "[MATERIAL]\n"
                    "[TITLE]Mengenal Pecahan[/TITLE]\n"
                    "[PARAGRAPH]Pecahan menyatakan bagian dari keseluruhan. Angka di atas garis disebut pembilang, di bawah disebut penyebut.[/PARAGRAPH]\n"
                    "[CEK]\n"
                    "[QUESTION]Pada pecahan 3/4, angka 4 disebut...[/QUESTION]\n"
                    "[OPTIONS]\n"
                    "A. Pembilang\n"
                    "B. Penyebut\n"
                    "[/OPTIONS]\n"
                    "[ANSWER]B[/ANSWER]\n"
                    "[/CEK]\n"
                    "[PARAGRAPH]Pecahan senilai adalah pecahan berbeda yang nilainya sama, misalnya 1/2 = 2/4.[/PARAGRAPH]\n"
                    "[CEK]\n"
                    "[TYPE]essay[/TYPE]\n"
                    "[QUESTION]Jelaskan dengan bahasamu sendiri mengapa 1/2 sama nilainya dengan 2/4.[/QUESTION]\n"
                    "[ANSWER]Karena pembilang dan penyebut 1/2 sama-sama dikali 2; nilai bagiannya tidak berubah.[/ANSWER]\n"
                    "[/CEK]\n"
                    "[/MATERIAL]"
                ),
            }
        ],
    },
    "kuis-pg": {
        "nama": "Kuis Pilihan Ganda",
        "roots": ["QUIZ"],
        "tags": ["TYPE", "QUESTION_BLOCK", "QUESTION", "OPTIONS", "ANSWER", "WEIGHT", "NOTE", "HINT", "EXAMPLE", "WARNING", "SUMMARY"],
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
            "- [WEIGHT]2[/WEIGHT] opsional di dalam blok soal untuk bobot (default 1, boleh desimal).\n"
            "- Blok PENGANTAR (opsional): paragraf bebas, [NOTE], [HINT], [EXAMPLE], atau [WARNING] boleh ditulis di dalam [QUIZ] sebelum soal pertama (prolog: sambutan, konteks, petunjuk pengerjaan) atau di antara soal sebagai selingan/hint. Blok pengantar BUKAN soal dan tidak dinilai."
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
        "tags": ["TYPE", "QUESTION_BLOCK", "QUESTION", "ANSWER", "WEIGHT", "NOTE", "HINT", "EXAMPLE", "WARNING", "SUMMARY"],
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
            "Aturan: nomor soal urut mulai 1; [ANSWER] adalah referensi penilaian (bukan ditampilkan ke siswa); [WEIGHT] opsional (default 1).\n"
            "Blok PENGANTAR (opsional): paragraf bebas, [NOTE], [HINT], [EXAMPLE], atau [WARNING] boleh ditulis di dalam [QUIZ] sebelum soal pertama (prolog: konteks bacaan, petunjuk) atau di antara soal sebagai selingan. Blok pengantar BUKAN soal dan tidak dinilai."
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
    # "scratch": modul khusus Scratch (Fase 7) — renderer di tcml/scratch.py.
    "scratch": {
        "nama": "Scratch",
        "roots": [],
        "tags": ["SCRATCH", "BLOCKS", "SPRITE"],
        "deskripsi": (
            "Konten Scratch: sematan proyek (stage) yang bisa dimainkan langsung di materi, "
            "blok kode visual dari notasi teks, dan kartu info sprite."
        ),
        "spec": (
            "Modul Scratch (di dalam [MATERIAL]):\n"
            "- [SCRATCH]id-atau-url[/SCRATCH]: menyematkan pemutar proyek yang bisa dimainkan siswa langsung di halaman materi. "
            "Isi HANYA salah satu dari: (a) ID proyek berupa angka (mis. 104), (b) URL https://scratch.mit.edu/projects/<id>, "
            "(c) URL https://turbowarp.org/<id>. Cara mendapat ID: buka proyek di scratch.mit.edu, angka pada URL-nya adalah ID proyek.\n"
            "- [BLOCKS]...[/BLOCKS]: blok kode Scratch ditulis sebagai notasi teks scratchblocks (Bahasa Inggris, satu blok per baris), "
            "mis. 'when green flag clicked', 'move (10) steps', 'say [Halo!] for (2) seconds', perulangan dengan 'repeat (10)' ... 'end', "
            "percabangan 'if <...> then' ... 'end'. Di halaman materi, notasi ini tampil sebagai gambar blok Scratch berwarna.\n"
            "- [SPRITE]...[/SPRITE]: kartu info sprite — baris pertama NAMA sprite, baris-baris berikutnya penjelasan peran & cara membuatnya."
        ),
        "contoh": [
            {
                "judul": "Materi Scratch: gerak & sematan proyek",
                "konten": (
                    "[MATERIAL]\n[TITLE]Menggerakkan Sprite[/TITLE]\n"
                    "Tekan bendera hijau pada proyek contoh di bawah, lalu gunakan tombol panah.\n"
                    "[SCRATCH]104[/SCRATCH]\n"
                    "[SPRITE]\nKucing\nSprite utama. Ikuti gerakannya pada stage dan perhatikan blok di bawah.\n[/SPRITE]\n"
                    "[BLOCKS]\nwhen green flag clicked\nforever\nif <key [right arrow v] pressed?> then\nmove (10) steps\nend\nend\n[/BLOCKS]\n"
                    "[NOTE]Blok forever membuat pengecekan tombol terjadi terus-menerus.[/NOTE]\n[/MATERIAL]"
                ),
            }
        ],
    },
}

ROOT_BLOCKS = ["MATERIAL", "EXERCISE", "PROJECT", "QUIZ"]

# Metadata per tag (nama awam, deskripsi, spec per tag, contoh utuh) +
# intro spec per modul + ikon UI — didefinisikan di tags_meta.py agar file
# registry ini tetap ringkas.
from .tags_meta import SPEC_INTRO, TAGS_META  # noqa: E402

_MODULE_ICONS = {
    "inti-materi": "🧱",
    "tabel-data": "📊",
    "formula-kode": "🧮",
    "latihan": "✏️",
    "proyek": "🧩",
    "cek-pemahaman": "🧠",
    "kuis-pg": "🧪",
    "kuis-esai": "📝",
    "scratch": "🐱",
}
for _slug, _mod in MODULES.items():
    _mod["tags_meta"] = TAGS_META.get(_slug, {})
    _mod["spec_intro"] = SPEC_INTRO.get(_slug, "")
    _mod["ikon"] = _MODULE_ICONS.get(_slug, "📦")

TAG_TO_MODULE = {}
for _slug, _mod in MODULES.items():
    for _tag in _mod["tags"]:
        TAG_TO_MODULE.setdefault(_tag, []).append(_slug)
