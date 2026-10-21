"use client";

import { Fragment, type CSSProperties } from "react";

import { pecahHtmlCek } from "@/lib/cekHtml";

export interface MaterialPreviewCekOption {
  label: string;
  teks: string;
  is_correct?: boolean;
}

export interface MaterialPreviewCek {
  indeks?: number;
  tipe: "pilihan_ganda" | "teks" | string;
  pertanyaan: string;
  bobot?: number;
  options?: MaterialPreviewCekOption[];
  jawaban_referensi?: string | null;
}

const PANEL_STYLE: CSSProperties = {
  border: "2px dashed #FFB020",
  background: "#FFFBEB",
  borderRadius: 12,
  padding: 14,
  margin: "14px 0",
};

function PreviewCekPanel({ item, indeks }: { item: MaterialPreviewCek; indeks: number }) {
  const options = item.options ?? [];
  return (
    <div style={PANEL_STYLE}>
      <p style={{ margin: "0 0 6px" }}>
        <strong>🧠 Cek Pemahaman {indeks + 1}</strong>{" "}
        <span className="badge">pratinjau guru</span>{" "}
        <span className="badge">bobot {item.bobot ?? 1}</span>
      </p>
      <p style={{ margin: "0 0 8px" }}>{item.pertanyaan}</p>

      {item.tipe === "pilihan_ganda" ? (
        <>
          <div>
            {options.map((o) => (
              <p
                key={o.label}
                style={{
                  margin: "5px 0",
                  color: o.is_correct ? "var(--ok)" : undefined,
                  fontWeight: o.is_correct ? 700 : undefined,
                }}
              >
                {o.is_correct ? "✅" : "▫️"} <strong>{o.label}.</strong> {o.teks}
                {o.is_correct ? " — jawaban benar" : ""}
              </p>
            ))}
          </div>
          <p className="muted" style={{ margin: "8px 0 0" }}>
            Di halaman siswa, panel ini interaktif dan kunci tidak ditampilkan sebelum siswa menjawab.
          </p>
        </>
      ) : (
        <>
          <div
            style={{
              background: "#fff",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 10,
            }}
          >
            <strong>📖 Jawaban referensi (khusus pratinjau guru)</strong>
            <p style={{ margin: "4px 0 0", whiteSpace: "pre-wrap" }}>
              {item.jawaban_referensi || "—"}
            </p>
          </div>
          <p className="muted" style={{ margin: "8px 0 0" }}>
            Siswa menulis jawabannya sendiri dulu; referensi ini baru terbuka setelah ia menjawab.
          </p>
        </>
      )}
    </div>
  );
}

/**
 * Render HTML materi untuk konteks guru/editor, dengan panel [CEK] utuh.
 *
 * RIWAYAT BUG (laporan Qualze 2026-10-21, dua kali): versi lama memasang
 * panel soal lewat createPortal ke dalam elemen hasil dangerouslySetInnerHTML
 * yang ditemukan via querySelectorAll di useEffect. Di browser nyata panel
 * tidak pernah muncul — pratinjau berhenti pada teks placeholder
 * "🧠 Cek Pemahaman N" — sementara tes API tetap hijau karena jalur data
 * backend memang benar. Versi ini TIDAK memakai portal/efek/DOM manual:
 * HTML dipecah pada placeholder dan panel digambar sebagai komponen React
 * biasa di sela-selanya. Deterministik di SSR maupun klien.
 */
export default function MaterialPreview({
  html,
  cek = [],
  className = "card tcml",
  style,
}: {
  html: string;
  cek?: MaterialPreviewCek[];
  className?: string;
  style?: CSSProperties;
}) {
  const perIndeks = new Map<number, MaterialPreviewCek>();
  cek.forEach((item, i) => perIndeks.set(item.indeks ?? i, item));
  const segmen = pecahHtmlCek(html);

  return (
    <article className={className} style={style}>
      {segmen.map((s, i) => {
        if (s.jenis === "html") {
          return <div key={i} dangerouslySetInnerHTML={{ __html: s.html }} />;
        }
        const item = perIndeks.get(s.indeks);
        if (!item) {
          // Tak ada definisi untuk indeks ini — tampilkan placeholder apa
          // adanya daripada menghilangkan konten.
          return <div key={i} dangerouslySetInnerHTML={{ __html: s.mentah }} />;
        }
        return (
          <Fragment key={i}>
            <PreviewCekPanel item={item} indeks={s.indeks} />
          </Fragment>
        );
      })}
    </article>
  );
}
