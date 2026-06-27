import { motion } from "framer-motion";
import { CheckCircle2, CircleDot, Link2, XCircle } from "lucide-react";
import { Badge } from "../ui/Badge";

function EventRow({ event }) {
  if (event.type === "start") {
    return <div className="rounded-2xl border border-iris/40 bg-iris/10 p-4 text-neon">Run started for {event.total_artists} artists.</div>;
  }

  if (event.type === "artist") {
    return (
      <div className="border-l-4 border-iris bg-slate/30 px-4 py-3">
        <div className="font-semibold text-snow">{event.name}</div>
        <div className="text-xs text-comet">Processing...</div>
      </div>
    );
  }

  if (event.type === "artist_done") {
    return (
      <div className="px-4 py-2 font-mono text-xs text-comet">
        {event.name}: {event.tracks_found} tracks found
      </div>
    );
  }

  if (event.type === "track") {
    return (
      <div className="ml-4 flex items-center gap-3 px-4 py-2">
        <CircleDot size={13} className="text-mint" />
        <span className="truncate text-snow">{event.track_name}</span>
        <Badge tone={event.performer_role === "featured" ? "featured" : event.album_type}>{event.album_type}</Badge>
      </div>
    );
  }

  if (event.type === "duplicate") {
    return (
      <div className="ml-4 flex items-center gap-3 px-4 py-2 font-mono text-xs text-ghost">
        <Link2 size={13} />
        <span className="line-through">{event.track_name}</span>
        <span>skipped from {event.skipped_from}</span>
      </div>
    );
  }

  if (event.type === "error") {
    return (
      <div className="border-l-4 border-rose bg-rose/10 px-4 py-3 text-rose">
        <div className="flex items-center gap-2 font-semibold">
          <XCircle size={16} />
          Error
        </div>
        <div className="mt-1 text-sm">{event.message}</div>
      </div>
    );
  }

  if (event.type === "done") {
    return (
      <div className="my-4 rounded-[20px] border border-mint/40 bg-mint/10 p-6 text-center">
        <CheckCircle2 className="mx-auto mb-3 text-mint" size={32} />
        <div className="font-display text-2xl font-semibold text-mint">Run complete</div>
        <div className="mt-2 text-sm text-comet">
          {event.total_tracks} tracks · {event.duplicates_prevented} duplicates blocked
        </div>
        {event.playlist_url ? (
          <a href={event.playlist_url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-sm font-semibold text-neon">
            Open playlist
          </a>
        ) : null}
      </div>
    );
  }

  return null;
}

export function RunConsole({ events = [] }) {
  return (
    <div className="h-[calc(100vh-180px)] overflow-y-auto rounded-[20px] border border-mist bg-void/60 p-3">
      {events.length === 0 ? (
        <div className="grid h-full place-items-center text-center text-sm text-comet">
          Start a run to stream artists, tracks, duplicates, and completion stats.
        </div>
      ) : (
        <div className="space-y-2">
          {events.map((event, index) => (
            <motion.div
              key={`${event.type}-${index}-${event.track_name || event.name || ""}`}
              initial={{ x: -16, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ duration: 0.16 }}
            >
              <EventRow event={event} />
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
