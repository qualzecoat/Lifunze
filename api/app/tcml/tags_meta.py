# Metadata per tag TCML (penyempurnaan Paket Parser 2026-10-20).
#
# Melengkapi registry.py: setiap tag kini punya nama awam, deskripsi satu
# baris, baris spec untuk prompt AI, dan contoh dokumen UTUH yang memuat tag
# itu (selalu bisa diparse engine — dijaga test). Dipakai oleh:
# - Mode Mudah/Lanjutan halaman /paket (nama, deskripsi, contoh),
# - perakitan spec paket yang memilih tag satu per satu (spec),
# - validasi paket (pilihan tag disimpan di parser_packs.tag_pilihan).

SPEC_INTRO = {
    "inti-materi": (
        "Dokumen materi diawali salah satu root: [MATERIAL], [EXERCISE], atau [PROJECT], "
        "dan diakhiri tag penutupnya. Di dalam root, blok-blok berikut tersedia:"
    ),
    "tabel-data": "Blok data berikut bisa dipakai di dalam materi:",
    "formula-kode": "Blok berikut bisa dipakai di dalam materi:",
    "latihan": "Root [EXERCISE] berisi: [TITLE] (dari modul inti), lalu blok-blok berikut:",
    "proyek": "Root [PROJECT] berisi: [TITLE] (dari modul inti), lalu blok-blok berikut:",
    "kuis-pg": (
        "Struktur kuis PG: dokumen diawali [QUIZ] dan diakhiri [/QUIZ]. "
        "Tag-tag berikut yang dipilih menyusun isi kuis:"
    ),
    "kuis-esai": (
        "Struktur kuis esai: dokumen diawali [QUIZ] dan diakhiri [/QUIZ]. "
        "Tag-tag berikut yang dipilih menyusun isi kuis:"
    ),
    "cek-pemahaman": (
        "Blok soal sisipan berikut bisa dipakai DI DALAM [MATERIAL]/[EXERCISE]/[PROJECT], "
        "di antara blok bacaan, untuk mengecek pemahaman (latihan ringan, bukan ujian):"
    ),
    "scratch": "Modul Scratch dipakai di dalam [MATERIAL]:",
}

_QUIZ_PG = (
    "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
    "[QUESTION 1]\n[QUESTION]Manakah yang termasuk bilangan prima?[/QUESTION]\n"
    "[OPTIONS]\nA. 4\nB. 5\nC. 7\nD. 9\n[/OPTIONS]\n[ANSWER]B, C[/ANSWER]\n[/QUESTION 1]\n"
    "[QUESTION 2]\n[QUESTION]Ibu kota Indonesia adalah...[/QUESTION]\n"
    "[OPTIONS]\nA. Bandung\nB. Jakarta\n[/OPTIONS]\n[ANSWER]B[/ANSWER]\n[/QUESTION 2]\n[/QUIZ]"
)
_QUIZ_PG_BOBOT = (
    "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
    "[QUESTION 1]\n[QUESTION]Hasil 12 x 8 adalah...[/QUESTION]\n"
    "[OPTIONS]\nA. 86\nB. 96\n[/OPTIONS]\n[ANSWER]B[/ANSWER]\n[WEIGHT]2.5[/WEIGHT]\n[/QUESTION 1]\n[/QUIZ]"
)
_QUIZ_ESAI = (
    "[QUIZ]\n[TYPE]essay[/TYPE]\n"
    "[QUESTION 1]\n[QUESTION]Jelaskan proses fotosintesis dengan bahasamu sendiri.[/QUESTION]\n"
    "[ANSWER]Tumbuhan mengubah cahaya matahari, air, dan CO2 menjadi glukosa dan oksigen.[/ANSWER]\n"
    "[/QUESTION 1]\n[/QUIZ]"
)
_QUIZ_ESAI_BOBOT = (
    "[QUIZ]\n[TYPE]essay[/TYPE]\n"
    "[QUESTION 1]\n[QUESTION]Mengapa kita harus menghemat air? Jelaskan dengan contoh.[/QUESTION]\n"
    "[ANSWER]Air bersih terbatas; menghematnya menjaga ketersediaan untuk minum, mandi, dan pertanian.[/ANSWER]\n"
    "[WEIGHT]3[/WEIGHT]\n[/QUESTION 1]\n[/QUIZ]"
)
_CEK_PG = (
    "[MATERIAL]\n[TITLE]Mengenal Pecahan[/TITLE]\n"
    "[PARAGRAPH]Angka di atas garis pecahan disebut pembilang, di bawah disebut penyebut.[/PARAGRAPH]\n"
    "[CEK]\n[QUESTION]Pada pecahan 3/4, angka 4 disebut...[/QUESTION]\n"
    "[OPTIONS]\nA. Pembilang\nB. Penyebut\n[/OPTIONS]\n[ANSWER]B[/ANSWER]\n[WEIGHT]2[/WEIGHT]\n[/CEK]\n[/MATERIAL]"
)
_CEK_ESAI = (
    "[MATERIAL]\n[TITLE]Mengenal Pecahan[/TITLE]\n"
    "[PARAGRAPH]Pecahan senilai adalah pecahan berbeda yang nilainya sama, misalnya 1/2 = 2/4.[/PARAGRAPH]\n"
    "[CEK]\n[TYPE]essay[/TYPE]\n[QUESTION]Jelaskan mengapa 1/2 sama nilainya dengan 2/4.[/QUESTION]\n"
    "[ANSWER]Karena pembilang dan penyebut 1/2 sama-sama dikali 2; nilai bagiannya tidak berubah.[/ANSWER]\n[/CEK]\n[/MATERIAL]"
)
_QUIZ_PG_PROLOG = (
    "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
    "Kuis ini menguji pemahamanmu tentang pecahan. Kerjakan dengan tenang.\n"
    "[NOTE]Setiap soal bernilai sama. Tidak ada pengurangan nilai untuk jawaban salah.[/NOTE]\n"
    "[QUESTION 1]\n[QUESTION]Pada pecahan 3/4, angka 3 disebut...[/QUESTION]\n"
    "[OPTIONS]\nA. Pembilang\nB. Penyebut\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 1]\n"
    "[HINT]Ingat: pembilang ada di atas garis.[/HINT]\n"
    "[QUESTION 2]\n[QUESTION]Pecahan yang senilai dengan 1/2 adalah...[/QUESTION]\n"
    "[OPTIONS]\nA. 2/4\nB. 1/3\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 2]\n[/QUIZ]"
)
_QUIZ_ESAI_PROLOG = (
    "[QUIZ]\n[TYPE]essay[/TYPE]\n"
    "[NOTE]Jawablah dengan kalimatmu sendiri. Nilai berdasarkan ketepatan penjelasan.[/NOTE]\n"
    "[QUESTION 1]\n[QUESTION]Jelaskan proses fotosintesis dengan bahasamu sendiri.[/QUESTION]\n"
    "[ANSWER]Tumbuhan mengubah cahaya matahari, air, dan CO2 menjadi glukosa dan oksigen.[/ANSWER]\n"
    "[/QUESTION 1]\n[/QUIZ]"
)
_EXERCISE_FULL = (
    "[EXERCISE]\n[TITLE]Latihan Membuat Tabel[/TITLE]\n"
    "[TASKS]\n[TASK]Buat tabel berisi 3 nama teman dan umur mereka.[/TASK]\n"
    "[TASK]Hitung rata-rata umurnya.[/TASK]\n[/TASKS]\n"
    "[HINT]Gunakan rumus rata-rata = jumlah / banyak data.[/HINT]\n"
    "[EXPECTED]Tabel rapi dan rata-rata yang benar.[/EXPECTED]\n[/EXERCISE]"
)


def _mat(inner: str) -> str:
    return f"[MATERIAL]\n[TITLE]Contoh Materi[/TITLE]\n{inner}\n[/MATERIAL]"


TAGS_META = {
    "inti-materi": {
        "TITLE": {
            "nama": "Judul Dokumen", "desc": "Judul utama di paling atas dokumen.", "wajib": True,
            "spec": "- [TITLE]Judul utama dokumen[/TITLE] (wajib, satu kali, paling atas)",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Mengenal Pecahan[/TITLE]\nIsi materi ditulis setelah judul.\n[/MATERIAL]",
        },
        "HEADING": {
            "nama": "Subjudul", "desc": "Judul bagian di tengah dokumen.",
            "spec": "- [HEADING]Subjudul bagian[/HEADING]",
            "jenis": "material",
            "contoh": _mat("[HEADING]Pengertian Pecahan[/HEADING]\nPecahan menyatakan bagian dari keseluruhan."),
        },
        "PARAGRAPH": {
            "nama": "Paragraf", "desc": "Teks penjelasan biasa.",
            "spec": "- [PARAGRAPH]Teks paragraf biasa.[/PARAGRAPH] (teks bebas di luar blok juga dianggap paragraf)",
            "jenis": "material",
            "contoh": _mat("[PARAGRAPH]Pecahan menyatakan bagian dari keseluruhan yang dibagi sama besar.[/PARAGRAPH]"),
        },
        "NOTE": {
            "nama": "Kotak Catatan", "desc": "Kotak info tambahan atau pengingat.",
            "spec": "- [NOTE]Catatan tambahan/pengingat.[/NOTE]",
            "jenis": "material",
            "contoh": _mat("[NOTE]Pembilang adalah angka di atas garis, penyebut di bawahnya.[/NOTE]"),
        },
        "WARNING": {
            "nama": "Kotak Peringatan", "desc": "Kotak untuk hal yang wajib diperhatikan.",
            "spec": "- [WARNING]Peringatan penting.[/WARNING]",
            "jenis": "material",
            "contoh": _mat("[WARNING]Penyebut tidak boleh nol.[/WARNING]"),
        },
        "SUMMARY": {
            "nama": "Ringkasan", "desc": "Kotak rangkuman isi materi.",
            "spec": "- [SUMMARY]Ringkasan isi.[/SUMMARY]",
            "jenis": "material",
            "contoh": _mat("[SUMMARY]Pecahan ditulis pembilang/penyebut.[/SUMMARY]"),
        },
        "EXAMPLE": {
            "nama": "Kotak Contoh", "desc": "Contoh penerapan dari konsep yang dibahas.",
            "spec": "- [EXAMPLE]Contoh penerapan.[/EXAMPLE]",
            "jenis": "material",
            "contoh": _mat("[EXAMPLE]Setengah pizza artinya satu dari dua potong sama besar.[/EXAMPLE]"),
        },
        "OBJECTIVE": {
            "nama": "Tujuan Belajar", "desc": "Yang harus bisa dilakukan siswa setelah materi ini.",
            "spec": "- [OBJECTIVE]Tujuan pembelajaran.[/OBJECTIVE]",
            "jenis": "material",
            "contoh": _mat("[OBJECTIVE]Siswa dapat membaca dan menulis pecahan sederhana.[/OBJECTIVE]"),
        },
        "STEPS": {
            "nama": "Langkah-langkah", "desc": "Daftar langkah berurutan.",
            "spec": "- [STEPS] berisi satu atau lebih [STEP]Langkah ke-n[/STEP] [/STEPS]",
            "jenis": "material",
            "contoh": _mat("[STEPS]\n[STEP]Perhatikan gambar pizza yang dibagi 4 sama besar.[/STEP]\n[STEP]Satu potong ditulis 1/4.[/STEP]\n[/STEPS]"),
        },
        "STEP": {
            "nama": "Satu Langkah", "desc": "Satu baris langkah di dalam Langkah-langkah.",
            "spec": "- [STEP]Satu langkah di dalam [STEPS].[/STEP]",
            "jenis": "material",
            "contoh": _mat("[STEPS]\n[STEP]Perhatikan gambar dengan saksama sebelum menjawab.[/STEP]\n[/STEPS]"),
        },
    },
    "tabel-data": {
        "DATASET": {
            "nama": "Dataset (Tabel Data)", "desc": "Data yang tampil sebagai tabel (sel dipisah tanda |).",
            "spec": "- [DATASET] tabel data: baris pertama = judul kolom, tiap sel dipisah tanda | (pipe), satu baris data per baris teks. [/DATASET]",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Data Nilai Ulangan[/TITLE]\n[DATASET]\nNama | Nilai\nAndi | 85\nBela | 92\n[/DATASET]\n[/MATERIAL]",
        },
        "TABLE": {
            "nama": "Tabel Manual", "desc": "Tabel yang ditulis baris per baris (sel dipisah tanda |).",
            "spec": "- [TABLE] sama seperti DATASET: baris pertama = judul kolom, sel dipisah tanda |. [/TABLE]",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Jadwal Pelajaran[/TITLE]\n[TABLE]\nHari | Pelajaran\nSenin | Matematika\nSelasa | IPA\n[/TABLE]\n[/MATERIAL]",
        },
    },
    "formula-kode": {
        "FORMULA": {
            "nama": "Rumus", "desc": "Rumus matematika/sains di dalam materi.",
            "spec": "- [FORMULA]Rumus dalam teks biasa, mis. Luas = p x l[/FORMULA]",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Keliling Persegi[/TITLE]\n[FORMULA]Keliling persegi = 4 x sisi[/FORMULA]\n[/MATERIAL]",
        },
        "CODE": {
            "nama": "Potongan Kode", "desc": "Kode program apa adanya (indentasi dipertahankan).",
            "spec": "- [CODE]Potongan kode apa adanya (indentasi dipertahankan).[/CODE]",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Perulangan Sederhana[/TITLE]\n[CODE]\nfor i in range(3):\n    print(i)\n[/CODE]\n[/MATERIAL]",
        },
    },
    "latihan": {
        "TASKS": {
            "nama": "Daftar Tugas", "desc": "Wadah berisi beberapa tugas.", "wajib": True,
            "spec": "- [TASKS] berisi satu atau lebih [TASK]Instruksi tugas[/TASK] [/TASKS]",
            "jenis": "material", "contoh": _EXERCISE_FULL,
        },
        "TASK": {
            "nama": "Satu Tugas", "desc": "Satu perintah tugas praktik.", "wajib": True,
            "spec": "- [TASK]Instruksi tugas[/TASK] di dalam [TASKS]",
            "jenis": "material", "contoh": _EXERCISE_FULL,
        },
        "HINT": {
            "nama": "Petunjuk Tugas", "desc": "Bantuan untuk mengerjakan tugas.",
            "spec": "- [HINT]Petunjuk pengerjaan.[/HINT]",
            "jenis": "material",
            "contoh": "[EXERCISE]\n[TITLE]Latihan Tabel[/TITLE]\n[TASKS]\n[TASK]Buat tabel berisi 3 nama teman dan umur mereka.[/TASK]\n[/TASKS]\n[HINT]Gunakan penggaris agar tabelmu rapi.[/HINT]\n[/EXERCISE]",
        },
        "EXPECTED": {
            "nama": "Hasil yang Diharapkan", "desc": "Hasil akhir yang dianggap benar.",
            "spec": "- [EXPECTED]Hasil akhir yang diharapkan.[/EXPECTED]",
            "jenis": "material",
            "contoh": "[EXERCISE]\n[TITLE]Latihan Tabel[/TITLE]\n[TASKS]\n[TASK]Buat tabel berisi 3 nama teman dan umur mereka.[/TASK]\n[/TASKS]\n[EXPECTED]Tabel terisi 3 baris data yang benar.[/EXPECTED]\n[/EXERCISE]",
        },
    },
}

_PROYEK_SYARAT = (
    "[PROJECT]\n[TITLE]Proyek Poster Hemat Air[/TITLE]\n"
    "[REQUIREMENTS]\n[REQUIREMENT]Poster ukuran A3.[/REQUIREMENT]\n"
    "[REQUIREMENT]Mengandung minimal 3 tips hemat air.[/REQUIREMENT]\n[/REQUIREMENTS]\n[/PROJECT]"
)

TAGS_META.update({
    "proyek": {
        "DESCRIPTION": {
            "nama": "Deskripsi Proyek", "desc": "Gambaran umum proyek yang dikerjakan.", "wajib": True,
            "spec": "- [DESCRIPTION]Deskripsi proyek.[/DESCRIPTION]",
            "jenis": "material",
            "contoh": "[PROJECT]\n[TITLE]Proyek Poster Hemat Air[/TITLE]\n[DESCRIPTION]Buat poster kampanye hemat air untuk sekolah.[/DESCRIPTION]\n[/PROJECT]",
        },
        "REQUIREMENTS": {
            "nama": "Daftar Syarat", "desc": "Wadah berisi beberapa syarat pengerjaan.", "wajib": True,
            "spec": "- [REQUIREMENTS] berisi satu atau lebih [REQUIREMENT]Syarat[/REQUIREMENT] [/REQUIREMENTS]",
            "jenis": "material", "contoh": _PROYEK_SYARAT,
        },
        "REQUIREMENT": {
            "nama": "Satu Syarat", "desc": "Satu syarat yang harus dipenuhi.",
            "spec": "- [REQUIREMENT]Satu syarat[/REQUIREMENT] di dalam [REQUIREMENTS]",
            "jenis": "material", "contoh": _PROYEK_SYARAT,
        },
        "OUTPUT": {
            "nama": "Output yang Dikumpulkan", "desc": "Bentuk hasil akhir yang harus diserahkan.",
            "spec": "- [OUTPUT]Bentuk hasil yang dikumpulkan.[/OUTPUT]",
            "jenis": "material",
            "contoh": "[PROJECT]\n[TITLE]Proyek Poster Hemat Air[/TITLE]\n[OUTPUT]File foto poster atau poster fisik.[/OUTPUT]\n[/PROJECT]",
        },
        "RUBRIC": {
            "nama": "Rubrik Penilaian", "desc": "Rubrik penilaian proyek.",
            "spec": "- [RUBRIC]Rubrik penilaian.[/RUBRIC]",
            "jenis": "material",
            "contoh": "[PROJECT]\n[TITLE]Proyek Poster Hemat Air[/TITLE]\n[RUBRIC]Kreativitas 40, isi 40, kerapian 20.[/RUBRIC]\n[/PROJECT]",
        },
        "CRITERIA": {
            "nama": "Kriteria Penilaian", "desc": "Satu aspek yang dinilai di dalam rubrik.",
            "spec": "- [CRITERIA]Kriteria penilaian.[/CRITERIA]",
            "jenis": "material",
            "contoh": "[PROJECT]\n[TITLE]Proyek Poster Hemat Air[/TITLE]\n[CRITERIA]Kreativitas: poster menarik, berwarna, dan pesannya jelas.[/CRITERIA]\n[/PROJECT]",
        },
    },
    "kuis-pg": {
        "TYPE": {
            "nama": "Penanda Jenis Kuis", "desc": "Menandai kuis ini pilihan ganda.", "wajib": True,
            "spec": "- [TYPE]pilihan_ganda[/TYPE] wajib sebagai baris pertama isi [QUIZ].",
            "jenis": "kuis-pg", "contoh": _QUIZ_PG,
        },
        "QUESTION_BLOCK": {
            "nama": "Blok Soal", "desc": "Wadah satu soal lengkap (pertanyaan + pilihan + kunci).", "wajib": True,
            "spec": "- Tiap soal dibungkus [QUESTION n] ... [/QUESTION n]; nomor urut mulai 1.",
            "jenis": "kuis-pg", "contoh": _QUIZ_PG,
        },
        "QUESTION": {
            "nama": "Pertanyaan", "desc": "Teks pertanyaan soalnya.", "wajib": True,
            "spec": "- [QUESTION]Teks pertanyaan[/QUESTION]",
            "jenis": "kuis-pg", "contoh": _QUIZ_PG,
        },
        "OPTIONS": {
            "nama": "Pilihan Jawaban", "desc": "Daftar pilihan A, B, C, … untuk dipilih siswa.", "wajib": True,
            "spec": "- [OPTIONS] satu pilihan per baris, label huruf kapital berurutan mulai A; minimal 2 opsi. [/OPTIONS]",
            "jenis": "kuis-pg", "contoh": _QUIZ_PG,
        },
        "ANSWER": {
            "nama": "Kunci Jawaban", "desc": "Jawaban benar — boleh lebih dari satu (mis. B, C).", "wajib": True,
            "spec": "- [ANSWER] berisi label jawaban benar; boleh lebih dari satu dipisah koma, mis. [ANSWER]B, C[/ANSWER] (siswa harus memilih persis himpunan itu).",
            "jenis": "kuis-pg", "contoh": _QUIZ_PG,
        },
        "WEIGHT": {
            "nama": "Bobot Soal", "desc": "Nilai soal ini dibanding soal lain (boleh desimal).",
            "spec": "- [WEIGHT]2[/WEIGHT] opsional di dalam blok soal untuk bobot (default 1, boleh desimal).",
            "jenis": "kuis-pg", "contoh": _QUIZ_PG_BOBOT,
        },
    },
    "kuis-esai": {
        "TYPE": {
            "nama": "Penanda Jenis Kuis", "desc": "Menandai kuis ini esai/uraian.", "wajib": True,
            "spec": "- [TYPE]essay[/TYPE] wajib sebagai baris pertama isi [QUIZ].",
            "jenis": "kuis-esai", "contoh": _QUIZ_ESAI,
        },
        "QUESTION_BLOCK": {
            "nama": "Blok Soal", "desc": "Wadah satu soal lengkap (pertanyaan + referensi).", "wajib": True,
            "spec": "- Tiap soal dibungkus [QUESTION n] ... [/QUESTION n]; nomor urut mulai 1.",
            "jenis": "kuis-esai", "contoh": _QUIZ_ESAI,
        },
        "QUESTION": {
            "nama": "Pertanyaan", "desc": "Teks pertanyaan soalnya.", "wajib": True,
            "spec": "- [QUESTION]Teks pertanyaan[/QUESTION]",
            "jenis": "kuis-esai", "contoh": _QUIZ_ESAI,
        },
        "ANSWER": {
            "nama": "Jawaban Referensi", "desc": "Contoh jawaban benar sebagai pedoman menilai.", "wajib": True,
            "spec": "- [ANSWER]Jawaban referensi untuk pedoman penilaian guru (tidak ditampilkan ke siswa).[/ANSWER]",
            "jenis": "kuis-esai", "contoh": _QUIZ_ESAI,
        },
        "WEIGHT": {
            "nama": "Bobot Soal", "desc": "Nilai soal ini dibanding soal lain (boleh desimal).",
            "spec": "- [WEIGHT]3[/WEIGHT] opsional di dalam blok soal untuk bobot (default 1, boleh desimal).",
            "jenis": "kuis-esai", "contoh": _QUIZ_ESAI_BOBOT,
        },
    },
    "scratch": {
        "SCRATCH": {
            "nama": "Proyek Scratch (Main)", "desc": "Proyek tertanam yang bisa dimainkan siswa di materi.",
            "spec": "- [SCRATCH]id-atau-url[/SCRATCH]: menyematkan pemutar proyek yang bisa dimainkan siswa. Isi HANYA salah satu dari: ID proyek berupa angka, URL https://scratch.mit.edu/projects/<id>, atau URL https://turbowarp.org/<id>.",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Menggerakkan Sprite[/TITLE]\nTekan bendera hijau dan gunakan tombol panah.\n[SCRATCH]104[/SCRATCH]\n[/MATERIAL]",
        },
        "BLOCKS": {
            "nama": "Blok Kode Scratch", "desc": "Susunan blok digambar seperti blok Scratch asli.",
            "spec": "- [BLOCKS]...[/BLOCKS]: blok kode Scratch sebagai notasi teks scratchblocks (Bahasa Inggris, satu blok per baris), mis. 'when green flag clicked', 'move (10) steps'; tampil sebagai gambar blok berwarna.",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Blok Gerak[/TITLE]\n[BLOCKS]\nwhen green flag clicked\nmove (10) steps\n[/BLOCKS]\n[/MATERIAL]",
        },
        "SPRITE": {
            "nama": "Kartu Sprite", "desc": "Kartu pengenalan tokoh/sprite beserta keterangannya.",
            "spec": "- [SPRITE]...[/SPRITE]: kartu info sprite — baris pertama NAMA sprite, baris-baris berikutnya penjelasan peran & cara membuatnya.",
            "jenis": "material",
            "contoh": "[MATERIAL]\n[TITLE]Mengenal Sprite[/TITLE]\n[SPRITE]\nKucing\nSprite utama. Ikuti gerakannya pada stage.\n[/SPRITE]\n[/MATERIAL]",
        },
    },
})

# --- Modul Cek Pemahaman (soal sisipan [CEK]) + blok pengantar kuis ---
TAGS_META["cek-pemahaman"] = {
    "CEK": {
        "nama": "Blok Cek Pemahaman", "desc": "Satu soal latihan PG/esai yang diselipkan di dalam materi.",
        "spec": "- [CEK] ... [/CEK]: satu soal sisipan di dalam materi, berisi [QUESTION] + [OPTIONS] + [ANSWER] (PG) atau [TYPE]essay + [QUESTION] + [ANSWER] referensi (esai).",
        "jenis": "material", "contoh": _CEK_PG,
    },
    "QUESTION": {
        "nama": "Pertanyaan Cek", "desc": "Teks pertanyaan soal sisipannya.",
        "spec": "- [QUESTION]Teks pertanyaan[/QUESTION] di dalam [CEK]",
        "jenis": "material", "contoh": _CEK_PG,
    },
    "OPTIONS": {
        "nama": "Pilihan Jawaban Cek", "desc": "Pilihan A, B, C, … untuk soal sisipan PG.",
        "spec": "- [OPTIONS] satu pilihan per baris, label huruf kapital berurutan mulai A; minimal 2 opsi. [/OPTIONS] di dalam [CEK]",
        "jenis": "material", "contoh": _CEK_PG,
    },
    "ANSWER": {
        "nama": "Kunci / Referensi Cek", "desc": "PG: label jawaban benar. Esai: jawaban referensi cek mandiri.",
        "spec": "- [ANSWER] di dalam [CEK]: untuk PG berisi label benar (boleh lebih dari satu, pisah koma); untuk esai berisi jawaban referensi yang dibuka siswa setelah menjawab.",
        "jenis": "material", "contoh": _CEK_PG,
    },
    "WEIGHT": {
        "nama": "Bobot Cek", "desc": "Bobot soal sisipan dalam nilai materi (boleh desimal).",
        "spec": "- [WEIGHT]2[/WEIGHT] opsional di dalam [CEK] untuk bobot (default 1, boleh desimal).",
        "jenis": "material", "contoh": _CEK_PG,
    },
    "TYPE": {
        "nama": "Penanda Esai Cek", "desc": "Menandai soal sisipan ini esai (cek mandiri).",
        "spec": "- [TYPE]essay[/TYPE] di dalam [CEK] bila soalnya esai; tanpa [TYPE] dan tanpa [OPTIONS], soal juga dianggap esai.",
        "jenis": "material", "contoh": _CEK_ESAI,
    },
}

_PENGANTAR_PG = {
    "NOTE": {
        "nama": "Catatan Pengantar Kuis", "desc": "Kotak info di dalam kuis: prolog, aturan, atau pengingat.",
        "spec": "- [NOTE]Catatan pengantar kuis.[/NOTE] di dalam [QUIZ], sebelum soal pertama atau di antara soal (bukan soal, tidak dinilai).",
        "jenis": "kuis-pg", "contoh": _QUIZ_PG_PROLOG,
    },
    "HINT": {
        "nama": "Petunjuk (Hint) Kuis", "desc": "Petunjuk yang terseling di antara soal kuis.",
        "spec": "- [HINT]Petunjuk untuk soal berikutnya.[/HINT] di dalam [QUIZ] di antara blok soal (bukan soal, tidak dinilai).",
        "jenis": "kuis-pg", "contoh": _QUIZ_PG_PROLOG,
    },
    "EXAMPLE": {
        "nama": "Contoh Pengantar Kuis", "desc": "Contoh pengerjaan sebagai pengantar kuis.",
        "spec": "- [EXAMPLE]Contoh pengerjaan.[/EXAMPLE] di dalam [QUIZ] sebelum soal pertama atau di antara soal (bukan soal, tidak dinilai).",
        "jenis": "kuis-pg", "contoh": _QUIZ_PG_PROLOG,
    },
    "WARNING": {
        "nama": "Peringatan Kuis", "desc": "Peringatan penting di dalam kuis (mis. aturan ujian).",
        "spec": "- [WARNING]Peringatan penting.[/WARNING] di dalam [QUIZ] sebelum soal pertama atau di antara soal (bukan soal, tidak dinilai).",
        "jenis": "kuis-pg", "contoh": _QUIZ_PG_PROLOG,
    },
    # Audit #19: [SUMMARY] valid di engine kuis (KONTEN_KUIS_TAGS) tetapi
    # dulu tidak terdaftar di modul kuis — AI yang memakainya ditolak
    # validasi lapis-2 paket.
    "SUMMARY": {
        "nama": "Ringkasan Kuis", "desc": "Ringkasan materi singkat sebagai pengantar atau penutup bagian kuis.",
        "spec": "- [SUMMARY]Ringkasan singkat.[/SUMMARY] di dalam [QUIZ] sebelum soal pertama atau di antara soal (bukan soal, tidak dinilai).",
        "jenis": "kuis-pg", "contoh": _QUIZ_PG_PROLOG,
    },
}
TAGS_META["kuis-pg"].update(_PENGANTAR_PG)
TAGS_META["kuis-esai"].update(
    {
        tag: {**meta, "jenis": "kuis-esai", "contoh": _QUIZ_ESAI_PROLOG}
        for tag, meta in _PENGANTAR_PG.items()
    }
)
