export function topArtistsFromTracks(tracks = []) {
  const counts = tracks.reduce((acc, track) => {
    const artist = track.artist_name || "Unknown";
    acc[artist] = (acc[artist] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts)
    .map(([artist, count]) => ({ artist, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);
}

export function ArtistBar({ tracks = [], data: providedData }) {
  const data = providedData || topArtistsFromTracks(tracks);
  const max = Math.max(1, ...data.map((item) => item.count));

  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.artist} className="grid grid-cols-[120px_1fr_36px] items-center gap-3">
          <div className="truncate text-xs text-snow">{item.artist}</div>
          <div className="h-2 overflow-hidden rounded-full bg-mist">
            <div
              className="h-full rounded-r-md bg-gradient-to-r from-iris to-neon transition-all duration-500"
              style={{ width: `${(item.count / max) * 100}%` }}
            />
          </div>
          <div className="text-right font-mono text-xs text-neon">{item.count}</div>
        </div>
      ))}
      {data.length === 0 ? <div className="py-6 text-center text-sm text-comet">No tracks loaded yet.</div> : null}
    </div>
  );
}
