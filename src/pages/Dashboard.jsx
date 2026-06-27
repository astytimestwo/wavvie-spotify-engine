import { useEffect, useMemo, useState } from "react";
import { ArrowRight, PlayCircle } from "lucide-react";
import { api } from "../lib/api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { TopBar } from "../components/layout/TopBar";
import { ReleasesTimeline } from "../components/charts/ReleasesTimeline";
import { AlbumTypePie } from "../components/charts/AlbumTypePie";
import { ArtistBar } from "../components/charts/ArtistBar";

function defaultCutoff() {
  const date = new Date();
  date.setDate(date.getDate() - 30);
  return date.toISOString().slice(0, 10);
}

export function Dashboard({ user, artists = [], setPage, setInitialRunConfig }) {
  const [tracks, setTracks] = useState([]);
  const [latest, setLatest] = useState(null);
  const [config, setConfig] = useState({ start: 1, end: 9999, cutoff: defaultCutoff(), verbose: false });

  useEffect(() => {
    api.tracklists().then(async (data) => {
      const first = data.tracklists?.[0];
      setLatest(first);
      if (first) {
        const detail = await api.tracklist(first.filename);
        setTracks(detail.tracks || []);
      }
    }).catch(() => {});
  }, []);

  const stats = useMemo(() => {
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const recent = tracks.filter((track) => new Date(track.release_date) >= sevenDaysAgo).length;
    return {
      tracks: tracks.length,
      duplicates: latest?.metadata?.duplicates_prevented || 0,
      recent,
    };
  }, [tracks, latest]);

  function startQuickRun() {
    setInitialRunConfig(config);
    setPage("run");
  }

  return (
    <>
      <TopBar title="Dashboard" subtitle="A live control room for your followed artists." />
      <section className="mb-6 grid min-h-[180px] grid-cols-[1fr_auto] items-center gap-8 rounded-[20px] border border-mist bg-gradient-to-r from-void via-iris-dim/70 to-void px-8 py-7">
        <div>
          <div className="font-display text-3xl font-semibold leading-tight">Good morning, {user?.display_name || "listener"}</div>
          <p className="mt-2 text-comet">You follow <span className="text-snow">{artists.length}</span> artists.</p>
        </div>
        <div className="grid grid-cols-3 gap-5">
          {[
            [stats.tracks, "New since"],
            [stats.duplicates, "Signature dedup"],
            [stats.recent, "Last 7 days"],
          ].map(([value, label]) => (
            <div key={label} className="min-w-[130px] rounded-[20px] border border-mist bg-obsidian/80 p-4">
              <div className="font-display text-4xl font-semibold">{value}</div>
              <div className="label-caps">{label}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="mb-6 grid grid-cols-[420px_1fr] gap-6">
        <Card className="p-5 shadow-iris">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="font-display text-xl font-semibold">Quick run</div>
              <div className="text-sm text-comet">Choose a range and scan from the dashboard.</div>
            </div>
            <PlayCircle className="text-neon" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Start" type="number" value={config.start} onChange={(event) => setConfig({ ...config, start: Number(event.target.value) })} />
            <Input label="End" type="number" value={config.end} onChange={(event) => setConfig({ ...config, end: Number(event.target.value) })} />
            <Input className="col-span-2" label="Cutoff" type="date" value={config.cutoff} onChange={(event) => setConfig({ ...config, cutoff: event.target.value })} />
          </div>
          <Button className="mt-5 w-full" icon={ArrowRight} onClick={startQuickRun}>
            Scan new releases
          </Button>
          <div className="mt-3 font-mono text-xs text-comet">
            Last export: {latest?.modified_at ? new Date(latest.modified_at).toLocaleString() : "none yet"}
          </div>
        </Card>

        <div className="grid grid-cols-3 gap-4">
          <Card className="p-4">
            <div className="label-caps mb-2">Releases per day</div>
            <ReleasesTimeline tracks={tracks} />
          </Card>
          <Card className="p-4">
            <div className="label-caps mb-2">Album type</div>
            <AlbumTypePie tracks={tracks} height={120} />
          </Card>
          <Card className="p-4">
            <div className="label-caps mb-4">Top artists</div>
            <ArtistBar tracks={tracks} />
          </Card>
        </div>
      </div>
    </>
  );
}
