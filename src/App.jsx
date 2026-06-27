import { useEffect, useMemo, useState } from "react";
import { Music2, RefreshCw } from "lucide-react";
import { PageShell } from "./components/layout/PageShell";
import { Button } from "./components/ui/Button";
import { Card } from "./components/ui/Card";
import { api } from "./lib/api";
import { useArtists } from "./hooks/useArtists";
import { Dashboard } from "./pages/Dashboard";
import { Artists } from "./pages/Artists";
import { Releases } from "./pages/Releases";
import { RunPage } from "./pages/RunPage";
import { Playlists } from "./pages/Playlists";

function ConnectSpotify({ error, retry }) {
  return (
    <div className="grid min-h-screen place-items-center px-6">
      <Card className="max-w-md p-8 text-center">
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-[#1DB954]/15 text-[#1DB954] ring-1 ring-[#1DB954]/40">
          <Music2 size={28} />
        </div>
        <h1 className="font-display text-3xl font-semibold">Connect Spotify</h1>
        <p className="mt-3 text-sm text-comet">
          Start the FastAPI backend, complete the Spotify OAuth prompt it opens, then refresh this dashboard.
        </p>
        {error ? <div className="mt-4 rounded-2xl bg-rose/10 p-3 text-sm text-rose">{error}</div> : null}
        <Button className="mt-6 w-full bg-[#1DB954] text-void hover:bg-[#1ed760]" icon={RefreshCw} onClick={retry}>
          Check connection
        </Button>
      </Card>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [status, setStatus] = useState({ loading: true, error: "", user: null });
  const [initialRunConfig, setInitialRunConfig] = useState(null);
  const artistsState = useArtists({ enabled: Boolean(status.user) });

  async function loadStatus() {
    setStatus({ loading: true, error: "", user: null });
    try {
      const data = await api.status();
      setStatus({ loading: false, error: "", user: data.user });
    } catch (err) {
      setStatus({ loading: false, error: err.message, user: null });
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  const currentPage = useMemo(() => {
    if (page === "artists") return <Artists {...artistsState} />;
    if (page === "releases") return <Releases />;
    if (page === "run") return <RunPage initialConfig={initialRunConfig} />;
    if (page === "playlists") return <Playlists />;
    return (
      <Dashboard
        user={status.user}
        artists={artistsState.artists}
        setPage={setPage}
        setInitialRunConfig={setInitialRunConfig}
      />
    );
  }, [page, status.user, artistsState, initialRunConfig]);

  if (status.loading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="font-display text-2xl text-neon">Loading Wavefeed...</div>
      </div>
    );
  }

  if (!status.user) {
    return <ConnectSpotify error={status.error} retry={loadStatus} />;
  }

  return (
    <PageShell page={page} setPage={setPage} user={status.user}>
      {currentPage}
    </PageShell>
  );
}
