import { useEffect, useState } from "react";
import { Play, Square } from "lucide-react";
import { TopBar } from "../components/layout/TopBar";
import { AlbumTypePie } from "../components/charts/AlbumTypePie";
import { ArtistQueue } from "../components/run/ArtistQueue";
import { ProgressOrb } from "../components/run/ProgressOrb";
import { RunConsole } from "../components/run/RunConsole";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { useRun } from "../hooks/useRun";

function defaultCutoff() {
  const date = new Date();
  date.setDate(date.getDate() - 30);
  return date.toISOString().slice(0, 10);
}

export function RunPage({ initialConfig }) {
  const [config, setConfig] = useState(initialConfig || { start: 1, end: 9999, cutoff: defaultCutoff(), verbose: false });
  const run = useRun();

  useEffect(() => {
    if (initialConfig) setConfig(initialConfig);
  }, [initialConfig]);

  const albumData = Object.entries(run.stats.albumTypes).map(([name, value]) => ({ name, value }));
  const isRunning = run.runId && !run.stats.done && run.stats.errors === 0;

  async function submit() {
    await run.startRun(config);
  }

  return (
    <>
      <TopBar title="Run" subtitle="Stream a new-release scan as it happens." connected={run.connected} />
      <div className="grid grid-cols-[240px_minmax(420px,1fr)_280px] gap-5">
        <Card className="h-[calc(100vh-180px)] p-4">
          <div className="mb-5 font-display text-xl font-semibold">Controls</div>
          <div className="space-y-3">
            <Input label="Start" type="number" value={config.start} onChange={(event) => setConfig({ ...config, start: Number(event.target.value) })} />
            <Input label="End" type="number" value={config.end} onChange={(event) => setConfig({ ...config, end: Number(event.target.value) })} />
            <Input label="Cutoff" type="date" value={config.cutoff} onChange={(event) => setConfig({ ...config, cutoff: event.target.value })} />
            <label className="flex items-center justify-between rounded-[14px] border border-mist bg-void/50 px-4 py-3 text-sm">
              <span>Verbose</span>
              <input
                type="checkbox"
                checked={config.verbose}
                onChange={(event) => setConfig({ ...config, verbose: event.target.checked })}
                className="h-5 w-5 accent-iris"
              />
            </label>
          </div>
          <Button className="mt-5 w-full" icon={Play} onClick={submit} disabled={run.starting || isRunning}>
            {run.starting ? "Starting..." : "Start run"}
          </Button>
          {isRunning ? (
            <Button className="mt-3 w-full" variant="rose" icon={Square} disabled title="Stop endpoint is not available in the backend yet">
              Stop
            </Button>
          ) : null}
          {run.error ? <div className="mt-4 rounded-2xl bg-rose/10 p-3 text-sm text-rose">{run.error}</div> : null}
        </Card>

        <RunConsole events={run.events} />

        <div className="space-y-4">
          <ProgressOrb processed={run.stats.processedArtists} total={run.stats.totalArtists} />
          <Card className="grid grid-cols-2 gap-3 p-4">
            {[
              [run.stats.tracks, "Tracks found"],
              [run.stats.duplicates, "Dupes blocked"],
              [run.stats.collaborations, "Collaborations"],
              [run.stats.errors, "Errors"],
            ].map(([value, label]) => (
              <div key={label} className="rounded-2xl bg-void/50 p-3">
                <div className="font-display text-3xl font-semibold">{value}</div>
                <div className="text-xs text-comet">{label}</div>
              </div>
            ))}
          </Card>
          <Card className="p-4">
            <div className="label-caps mb-2">Live album mix</div>
            <AlbumTypePie data={albumData} height={150} />
          </Card>
          <Card className="p-4">
            <div className="label-caps mb-3">Artist queue</div>
            <ArtistQueue artists={run.stats.recentArtists} />
          </Card>
        </div>
      </div>
    </>
  );
}
