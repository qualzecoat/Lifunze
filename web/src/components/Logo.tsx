export default function Logo({ size = 40 }: { size?: number }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
      <svg width={size} height={size} viewBox="0 0 96 96" aria-hidden="true">
        <rect width="96" height="96" rx="24" fill="#6D5DF6" />
        <path
          d="M48,20 L52.5,43.5 L76,48 L52.5,52.5 L48,76 L43.5,52.5 L20,48 L43.5,43.5 Z"
          fill="#FFB020"
        />
      </svg>
      <span
        style={{
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          fontWeight: 800,
          fontSize: size * 0.62,
          letterSpacing: -1,
          color: "#17142B",
        }}
      >
        li<span style={{ color: "#6D5DF6" }}>fun</span>ze
      </span>
    </span>
  );
}
