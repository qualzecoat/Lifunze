import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Header keamanan dasar (Fase 8). Iframe Scratch/TurboWarp di halaman
  // materi adalah konten yang KITA sematkan — bukan halaman kita yang
  // disemat pihak lain, jadi SAMEORIGIN aman.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
    ];
  },
};

export default nextConfig;
