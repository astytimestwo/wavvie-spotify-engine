import { useEffect, useState } from "react";
import { sseUrl } from "../lib/api";

export function useSSE(runId) {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!runId) return undefined;

    const stream = new EventSource(sseUrl(runId));
    stream.onopen = () => setConnected(true);
    stream.onerror = () => setConnected(false);
    stream.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data);
        setEvents((current) => [...current, event]);
      } catch {
        setEvents((current) => [...current, { type: "error", message: "Malformed SSE payload" }]);
      }
    };

    return () => {
      stream.close();
      setConnected(false);
    };
  }, [runId]);

  return { events, connected, setEvents };
}
