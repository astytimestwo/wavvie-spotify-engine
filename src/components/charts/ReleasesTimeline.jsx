import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function ReleasesTimeline({ tracks = [], height = 120 }) {
  const counts = tracks.reduce((acc, track) => {
    const date = track.release_date || "unknown";
    acc[date] = (acc[date] || 0) + 1;
    return acc;
  }, {});
  const data = Object.entries(counts)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-30)
    .map(([date, count]) => ({ date, count }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="timelineFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(124,58,237,0.3)" />
            <stop offset="100%" stopColor="rgba(124,58,237,0)" />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" hide />
        <YAxis hide allowDecimals={false} />
        <Tooltip
          contentStyle={{ background: "var(--obsidian)", border: "1px solid var(--mist)", borderRadius: 14, color: "var(--snow)" }}
          labelStyle={{ color: "var(--neon)" }}
        />
        <Area type="monotone" dataKey="count" stroke="var(--neon)" strokeWidth={2} fill="url(#timelineFill)" isAnimationActive />
      </AreaChart>
    </ResponsiveContainer>
  );
}
