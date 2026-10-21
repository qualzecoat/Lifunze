"use client";

/**
 * Pratinjau isi kuis SESUAI URUTAN dokumen (audit #21 & #46).
 *
 * Kuis Lifunze boleh memuat blok konten (paragraf pengantar, NOTE, HINT,
 * EXAMPLE, WARNING, SUMMARY) yang terseling di antara soal. Pratinjau
 * lama hanya menggambar daftar soal sehingga blok-blok itu tak terlihat
 * oleh guru — komponen ini menggambar `items` dari parse_quiz_v2 apa
 * adanya: konten sebagai kotak berlabel, soal bernomor berurutan.
 */

export interface OpsiPratinjau {
  label: string;
  teks: string;
  is_correct: boolean;
}

export interface SoalPratinjau {
  pertanyaan: string;
  bobot: number;
  options: OpsiPratinjau[];
  jawaban_referensi?: string | null;
}

export type ItemPratinjau =
  | { jenis: "konten"; tipe: string; teks: string }
  | { jenis: "soal"; soal: SoalPratinjau };

const LABEL_KONTEN: Record<string, { emoji: string; nama: string; warna: string }> = {
  paragraf: { emoji: "¶", nama: "Paragraf pengantar", warna: "var(--muted)" },
  note: { emoji: "📝", nama: "Catatan", warna: "var(--primary)" },
  hint: { emoji: "💡", nama: "Petunjuk", warna: "var(--accent)" },
  example: { emoji: "🔎", nama: "Contoh", warna: "var(--ok)" },
  warning: { emoji: "⚠️", nama: "Perhatian", warna: "var(--danger)" },
  summary: { emoji: "📌", nama: "Ringkasan", warna: "var(--primary)" },
};

export default function QuizItemsPreview({ items }: { items: ItemPratinjau[] }) {
  if (!items || items.length === 0) {
    return (
      <div className="card">
        <p className="muted">Pratinjau muncul setelah soal valid.</p>
      </div>
    );
  }
  let nomor = 0;
  return (
    <div>
      {items.map((item, i) => {
        if (item.jenis === "konten") {
          const meta = LABEL_KONTEN[item.tipe] ?? LABEL_KONTEN.paragraf;
          return (
            <div
              key={i}
              style={{
                border: "1px dashed var(--border)",
                borderLeft: `4px solid ${meta.warna}`,
                borderRadius: 10,
                padding: "10px 14px",
                marginBottom: 10,
                background: "var(--surface)",
              }}
            >
              <p style={{ margin: 0, fontWeight: 700, fontSize: ".85rem", color: meta.warna }}>
                {meta.emoji} {meta.nama}
              </p>
              <p style={{ margin: "4px 0 0", whiteSpace: "pre-wrap" }}>{item.teks}</p>
            </div>
          );
        }
        nomor += 1;
        const q = item.soal;
        return (
          <div className="card" key={i} style={{ marginBottom: 10 }}>
            <p style={{ margin: 0 }}>
              <strong>
                {nomor}. {q.pertanyaan}
              </strong>{" "}
              <span className="badge">bobot {q.bobot}</span>
            </p>
            {q.options?.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {q.options.map((o) => (
                  <p key={o.label} style={{ margin: "2px 0", color: o.is_correct ? "var(--ok)" : undefined }}>
                    {o.is_correct ? "✅" : "▫️"} {o.label}. {o.teks}
                  </p>
                ))}
              </div>
            )}
            {q.jawaban_referensi && (
              <p className="muted" style={{ marginTop: 4 }}>
                Referensi: {q.jawaban_referensi}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
