export function Skeleton({ className = "" }) {
  return (
    <div
      className={`rounded-[20px] ${className}`}
      style={{
        background: "linear-gradient(90deg, var(--obsidian), var(--mist), var(--obsidian))",
        backgroundSize: "200%",
        animation: "shimmer 1.6s infinite",
      }}
    />
  );
}
