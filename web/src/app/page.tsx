import Logo from "@/components/Logo";

export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 24,
        padding: 24,
        textAlign: "center",
      }}
    >
      <Logo size={56} />
      <h1 style={{ fontSize: "2.6rem", fontWeight: 800, letterSpacing: -1, maxWidth: 640 }}>
        Serunya <span style={{ color: "var(--primary)" }}>Belajar</span>,<br />
        Mudahnya <span style={{ color: "var(--accent)" }}>Mengajar</span>.
      </h1>
      <p style={{ color: "var(--muted)", maxWidth: 520, fontSize: "1.05rem" }}>
        Lifunze adalah LMS modern dengan generate konten AI dan bahasa markup
        TCML — tempat belajar dan mengajar yang seru dan mudah berkat bantuan
        teknologi. <strong>Learning is fun, zero effort.</strong>
      </p>
      <p
        style={{
          fontSize: ".85rem",
          fontWeight: 600,
          color: "var(--primary)",
          background: "var(--surface)",
          border: "1px solid rgba(0,0,0,.08)",
          borderRadius: 999,
          padding: "6px 16px",
        }}
      >
        🚧 Fase 0 — fondasi sedang dibangun
      </p>
    </main>
  );
}
