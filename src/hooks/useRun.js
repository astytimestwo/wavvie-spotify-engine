import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { useSSE } from "./useSSE";

export function useRun() {
  const [runId, setRunId] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const stream = useSSE(runId);

  async function startRun(config) {
    setStarting(true);
    setError("");
    stream.setEvents([]);
    try {
      const run = await api.startRun(config);
      setRunId(run.id);
      return run;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setStarting(false);
    }
  }

  const stats = useMemo(() => {
    const state = {
      totalArtists: 0,
      processedArtists: 0,
      tracks: 0,
      duplicates: 0,
      collaborations: 0,
      errors: 0,
      albumTypes: {},
      recentArtists: [],
      done: null,
    };

    for (const event of stream.events) {
      if (event.type === "start") state.totalArtists = event.total_artists || 0;
      if (event.type === "artist_done") {
        state.processedArtists += 1;
        state.recentArtists = [event, ...state.recentArtists].slice(0, 5);
      }
      if (event.type === "track") {
        state.tracks += 1;
        const type = event.performer_role === "featured" ? "featured" : event.album_type || "unknown";
        state.albumTypes[type] = (state.albumTypes[type] || 0) + 1;
        if (event.is_collaboration || event.performer_role === "featured") state.collaborations += 1;
      }
      if (event.type === "duplicate") state.duplicates += 1;
      if (event.type === "error") state.errors += 1;
      if (event.type === "done") state.done = event;
    }

    return state;
  }, [stream.events]);

  return { runId, startRun, starting, error, events: stream.events, connected: stream.connected, stats };
}
