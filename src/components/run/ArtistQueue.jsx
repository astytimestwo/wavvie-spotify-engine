import { motion } from "framer-motion";

export function ArtistQueue({ artists = [] }) {
  return (
    <div className="space-y-2">
      {artists.map((artist) => (
        <motion.div
          key={`${artist.index}-${artist.name}`}
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="rounded-2xl border border-mist bg-void/40 px-3 py-2"
        >
          <div className="truncate text-sm font-semibold text-snow">{artist.name}</div>
          <div className="text-xs text-comet">
            {artist.tracks_found > 0 ? `${artist.tracks_found} tracks found` : "no new releases"}
          </div>
        </motion.div>
      ))}
      {artists.length === 0 ? <div className="text-sm text-comet">No artists processed yet.</div> : null}
    </div>
  );
}
