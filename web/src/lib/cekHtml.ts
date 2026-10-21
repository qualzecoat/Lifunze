/**
 * Pemecah HTML materi pada placeholder [CEK] dari renderer TCML.
 *
 * Renderer sengaja hanya mengeluarkan penanda posisi
 * `<div class="tc-cek" data-cek-index="N"><p class="tc-cek-placeholder">…</p></div>`
 * (tanpa soal/kunci — aman untuk siswa). Panel soal yang sebenarnya digambar
 * sebagai komponen React biasa di sela-sela segmen HTML hasil pecahan ini.
 *
 * JANGAN kembali ke pola lama (createPortal ke elemen hasil innerHTML yang
 * dicari via querySelectorAll di useEffect): pola itu terbukti gagal di
 * browser nyata dua kali (laporan Qualze 2026-10-21 — pratinjau editor DAN
 * halaman materi siswa hanya menampilkan teks placeholder), sementara pola
 * pecah-HTML ini deterministik dan terverifikasi lewat render sungguhan.
 */
export const CEK_PLACEHOLDER_RE =
  /<div class="tc-cek" data-cek-index="(\d+)"[^>]*>[\s\S]*?<\/div>/g;

export type SegmenCek =
  | { jenis: "html"; html: string }
  | { jenis: "cek"; indeks: number; mentah: string };

export function pecahHtmlCek(html: string): SegmenCek[] {
  const hasil: SegmenCek[] = [];
  let terakhir = 0;
  for (const m of html.matchAll(CEK_PLACEHOLDER_RE)) {
    const idx = m.index ?? 0;
    if (idx > terakhir) hasil.push({ jenis: "html", html: html.slice(terakhir, idx) });
    hasil.push({ jenis: "cek", indeks: Number(m[1]), mentah: m[0] });
    terakhir = idx + m[0].length;
  }
  if (terakhir < html.length) hasil.push({ jenis: "html", html: html.slice(terakhir) });
  return hasil;
}
