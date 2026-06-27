import { motion } from "framer-motion";
import { Copy, Ellipsis, ExternalLink, Link2, Mic2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "../ui/Badge";
import { ArtworkBlur } from "./ArtworkBlur";

function badgeTone(track) {
  if (track.performer_role === "featured" || track.is_collaboration) return "featured";
  return track.album_type || "muted";
}

export function TrackRow({ track, style }) {
  const [preview, setPreview] = useState(false);
  const artists = track.all_artists?.join(", ") || track.artist_name;
  const spotifyUrl = track.track_id ? `https://open.spotify.com/track/${track.track_id}` : null;

  return (
    <motion.div
      style={style}
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      className="group relative grid h-16 grid-cols-[56px_minmax(220px,1.4fr)_minmax(140px,.8fr)_110px_100px_42px_42px] items-center gap-3 border-b border-mist/70 px-4 text-sm"
    >
      <div className="relative" onMouseEnter={() => setPreview(true)} onMouseLeave={() => setPreview(false)}>
        {track.album_artwork_url ? (
          <img src={track.album_artwork_url} alt="" className="h-12 w-12 rounded-xl object-cover" />
        ) : (
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-iris/30 font-display text-sm text-neon">
            {(track.track_name || "?").slice(0, 1)}
          </div>
        )}
        {preview ? (
          <ArtworkBlur
            artworkUrl={track.album_artwork_url}
            className="absolute left-0 top-14 z-30 w-[220px] rounded-[20px] border border-mist bg-obsidian p-3 shadow-card"
          >
            {track.album_artwork_url ? <img src={track.album_artwork_url} alt="" className="mb-3 h-44 w-full rounded-2xl object-cover" /> : null}
            <div className="truncate font-display text-base font-semibold">{track.track_name}</div>
            <div className="truncate font-mono text-xs text-comet">{track.album_name}</div>
          </ArtworkBlur>
        ) : null}
      </div>

      <div className="min-w-0">
        <div className="truncate font-medium text-snow">{track.track_name}</div>
        <div className="truncate font-mono text-xs text-comet">{track.album_name}</div>
      </div>
      <div className="truncate text-comet">{artists}</div>
      <Badge tone={badgeTone(track)}>{track.performer_role === "featured" ? "featured" : track.album_type || "unknown"}</Badge>
      <div className="font-mono text-xs text-comet">{track.release_date}</div>
      <div className="text-comet">{track.performer_role === "featured" ? <Link2 size={18} /> : <Mic2 size={18} />}</div>
      <div className="flex items-center justify-end gap-1 opacity-0 transition group-hover:opacity-100">
        {spotifyUrl ? (
          <a href={spotifyUrl} target="_blank" rel="noreferrer" title="Open in Spotify" className="rounded-full p-2 text-comet hover:bg-mist hover:text-neon">
            <ExternalLink size={16} />
          </a>
        ) : null}
        <button
          title="Copy Spotify URI"
          onClick={() => navigator.clipboard?.writeText(track.track_id ? `spotify:track:${track.track_id}` : track.track_signature)}
          className="rounded-full p-2 text-comet hover:bg-mist hover:text-neon"
        >
          <Copy size={16} />
        </button>
        <Ellipsis size={16} className="text-ghost" />
      </div>
    </motion.div>
  );
}
