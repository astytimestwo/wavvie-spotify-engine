import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

export function useArtists({ enabled = true } = {}) {
  const [artists, setArtists] = useState([]);
  const [cached, setCached] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api.artists();
      setArtists(data.artists || []);
      setCached(Boolean(data.cached));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  async function refresh() {
    await api.clearArtistCache();
    await load();
  }

  useEffect(() => {
    load();
  }, [load]);

  return { artists, cached, loading, error, refresh };
}
