"use client";

/** Bar tab bersama — gaya visual sama persis dengan tab halaman kelas
 * (garis bawah ungu untuk tab aktif, label bisa digeser di layar sempit). */
export interface TabDef {
  key: string;
  label: string;
}

export default function TabsBar({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        borderBottom: "2px solid var(--border)",
        marginTop: 14,
        marginBottom: 14,
        flexWrap: "wrap",
      }}
    >
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          style={{
            border: "none",
            background: "none",
            padding: "9px 14px",
            fontWeight: 700,
            cursor: "pointer",
            whiteSpace: "nowrap",
            fontFamily: "inherit",
            color: active === t.key ? "var(--primary)" : "var(--muted)",
            borderBottom: active === t.key ? "3px solid var(--primary)" : "3px solid transparent",
            marginBottom: -2,
            fontSize: ".95rem",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
