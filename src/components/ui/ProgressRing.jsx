export function ProgressRing({ value = 0, total = 1, size = 160, label = "artists" }) {
  const pct = total > 0 ? Math.min(1, value / total) : 0;
  const radius = size / 2 - 8;
  const circumference = 2 * Math.PI * radius;
  const dash = circumference * (1 - pct);
  const angle = pct * 360 - 90;
  const dotX = size / 2 + radius * Math.cos((angle * Math.PI) / 180);
  const dotY = size / 2 + radius * Math.sin((angle * Math.PI) / 180);

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id="ringGradient" x1="0" x2="1" y1="0" y2="1">
            <stop stopColor="var(--iris)" />
            <stop offset="1" stopColor="var(--neon)" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--mist)" strokeWidth="6" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#ringGradient)"
          strokeDasharray={circumference}
          strokeDashoffset={dash}
          strokeLinecap="round"
          strokeWidth="6"
          style={{ transition: "stroke-dashoffset 300ms cubic-bezier(0.4, 0, 0.2, 1)" }}
        />
      </svg>
      <span
        className="absolute h-2 w-2 rounded-full bg-iris shadow-iris"
        style={{ left: dotX - 4, top: dotY - 4, transition: "all 300ms cubic-bezier(0.4, 0, 0.2, 1)" }}
      />
      <div className="absolute text-center">
        <div className="font-display text-2xl font-semibold text-snow">
          {value} / {total || 0}
        </div>
        <div className="text-xs text-comet">{label}</div>
      </div>
    </div>
  );
}
