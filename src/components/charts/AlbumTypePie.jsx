import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const colorMap = {
  album: "var(--iris)",
  single: "var(--sky)",
  ep: "var(--amber)",
  featured: "var(--rose)",
  compilation: "var(--ghost)",
  unknown: "var(--mist)",
};

export function albumTypeDataFromTracks(tracks = []) {
  const counts = tracks.reduce((acc, track) => {
    const key = track.performer_role === "featured" || track.is_collaboration ? "featured" : track.album_type || "unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts).map(([name, value]) => ({ name, value }));
}

export function AlbumTypePie({ tracks = [], data: providedData, height = 150 }) {
  const data = providedData || albumTypeDataFromTracks(tracks);
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="relative h-full">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie data={data} innerRadius="60%" outerRadius="82%" paddingAngle={3} dataKey="value" nameKey="name">
            {data.map((entry) => (
              <Cell key={entry.name} fill={colorMap[entry.name] || colorMap.unknown} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "var(--obsidian)", border: "1px solid var(--mist)", borderRadius: 14, color: "var(--snow)" }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className="font-display text-2xl font-semibold">{total}</div>
          <div className="text-[11px] uppercase tracking-[0.08em] text-comet">tracks</div>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {data.map((entry) => (
          <span key={entry.name} className="rounded-full px-2 py-1 text-[11px] text-comet ring-1 ring-mist">
            <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: colorMap[entry.name] || colorMap.unknown }} />
            {entry.name}
          </span>
        ))}
      </div>
    </div>
  );
}
