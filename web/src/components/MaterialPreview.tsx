"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

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
 * Render HTML materi untuk konteks guru/editor. Placeholder [CEK] dari
 * renderer diisi panel soal utuh lewat portal, supaya pratinjau tidak
 * berhenti pada teks "Cek Pemahaman N" saja.
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
  const rootRef = useRef<HTMLElement>(null);
  const [slots, setSlots] = useState<HTMLElement[]>([]);

  useEffect(() => {
    if (!rootRef.current) {
      setSlots([]);
      return;
    }
    const found = Array.from(
      rootRef.current.querySelectorAll<HTMLElement>("[data-cek-index]"),
    );
    // Kosongkan teks placeholder bawaan renderer; panel React menggantikannya.
    found.forEach((el) => el.replaceChildren());
    setSlots(found);
  }, [html, cek]);

  return (
    <>
      <article
        ref={rootRef}
        className={className}
        style={style}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      {cek.map((item, i) => {
        const indeks = item.indeks ?? i;
        const slot = slots.find((el) => Number(el.dataset.cekIndex) === indeks);
        if (!slot) return null;
        return createPortal(
          <PreviewCekPanel item={item} indeks={indeks} />,
          slot,
          `preview-cek-${indeks}`,
        );
      })}
    </>
  );
}
