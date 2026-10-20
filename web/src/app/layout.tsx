import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lifunze — Serunya Belajar, Mudahnya Mengajar",
  description:
    "Lifunze adalah LMS modern dengan generate konten AI dan bahasa markup TCML. Learning is fun, zero effort.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
