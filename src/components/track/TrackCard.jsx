import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

export function TrackCard({ track }) {
  return (
    <Card hover className="overflow-hidden">
      {track.album_artwork_url ? (
        <img src={track.album_artwork_url} alt="" className="aspect-square w-full object-cover transition duration-300 hover:scale-105" />
      ) : (
        <div className="grid aspect-square w-full place-items-center bg-iris/20 font-display text-3xl text-neon">
          {(track.track_name || "?").slice(0, 1)}
        </div>
      )}
      <div className="p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <Badge tone={track.is_collaboration ? "featured" : track.album_type}>{track.is_collaboration ? "featured" : track.album_type}</Badge>
          <span className="font-mono text-xs text-comet">{track.release_date}</span>
        </div>
        <div className="truncate font-display text-lg font-semibold">{track.track_name}</div>
        <div className="truncate text-sm text-comet">{track.artist_name}</div>
      </div>
    </Card>
  );
}
