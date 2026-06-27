const jsonHeaders = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

export const api = {
  status: () => request("/api/status"),
  artists: () => request("/api/artists"),
  clearArtistCache: () => request("/api/artists/cache", { method: "DELETE" }),
  startRun: (payload) =>
    request("/api/run", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  runState: (runId) => request(`/api/runs/${runId}/state`),
  tracklists: () => request("/api/tracklists"),
  tracklist: (filename) => request(`/api/tracklists/${encodeURIComponent(filename)}`),
  playlists: () => request("/api/playlists"),
};

export function sseUrl(runId) {
  return `/api/runs/${runId}`;
}
