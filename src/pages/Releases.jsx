import { useEffect, useMemo, useState } from "react";
import { FixedSizeList } from "react-window";
import { GitFork, ListFilter } from "lucide-react";
import { api } from "../lib/api";
import { TopBar } from "../components/layout/TopBar";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TrackRow } from "../components/track/TrackRow";
import { CollabNetwork } from "../components/charts/CollabNetwork";

const filters = ["all", "album", "single", "ep", "featured"];

export function Releases() {
  const [tracks, setTracks] = useState([]);
  const [selectedFilter, setSelectedFilter] = useState("all");
  const [sort, setSort] = useState("date");
  const [showGraph, setShowGraph] = useState(false);

  useEffect(() => {
    api.tracklists().then(async (data) => {
      const first = data.tracklists?.[0];
      if (!first) return;
      const detail = await api.tracklist(first.filename);
      setTracks(detail.tracks || []);
    }).catch(() => {});
  }, []);

  const visibleTracks = useMemo(() => {
    const filtered = tracks.filter((track) => {
      const type = track.performer_role === "featured" || track.is_collaboration ? "featured" : track.album_type;
      return selectedFilter === "all" || type === selectedFilter;
    });
    return [...filtered].sort((a, b) => {
      if (sort === "artist") return (a.artist_name || "").localeCompare(b.artist_name || "");
      if (sort === "type") return (a.album_type || "").localeCompare(b.album_type || "");
      return (b.release_date || "").localeCompare(a.release_date || "");
    });
  }, [tracks, selectedFilter, sort]);

  return (
    <>
      <TopBar title="Releases" subtitle={`${visibleTracks.length} tracks from the latest exported tracklist.`} />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {filters.map((filter) => (
            <button
              key={filter}
              onClick={() => setSelectedFilter(filter)}
              className={`rounded-full px-4 py-2 text-sm font-semibold capitalize transition ${
                selectedFilter === filter ? "bg-iris text-snow shadow-iris" : "border border-mist bg-obsidian text-comet hover:text-snow"
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <ListFilter size={17} className="text-comet" />
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value)}
            className="h-10 rounded-full border border-mist bg-obsidian px-4 text-sm text-snow outline-none focus:border-iris"
          >
            <option value="date">Release Date</option>
            <option value="artist">Artist</option>
            <option value="type">Album Type</option>
          </select>
          <Button variant="outline" icon={GitFork} onClick={() => setShowGraph((value) => !value)}>
            {showGraph ? "Hide graph" : "Show collab graph"}
          </Button>
        </div>
      </div>

      {showGraph ? (
        <Card className="mb-5 p-4">
          <CollabNetwork tracks={visibleTracks} />
        </Card>
      ) : null}

      <Card className="overflow-hidden">
        <div className="grid h-10 grid-cols-[56px_minmax(220px,1.4fr)_minmax(140px,.8fr)_110px_100px_42px_42px] items-center gap-3 border-b border-mist px-4 text-[11px] font-semibold uppercase tracking-[0.08em] text-comet">
          <span />
          <span>Track</span>
          <span>Artist</span>
          <span>Type</span>
          <span>Date</span>
          <span>Role</span>
          <span />
        </div>
        {visibleTracks.length > 200 ? (
          <FixedSizeList height={650} itemCount={visibleTracks.length} itemSize={64} width="100%">
            {({ index, style }) => <TrackRow track={visibleTracks[index]} style={style} />}
          </FixedSizeList>
        ) : (
          <div>
            {visibleTracks.map((track) => <TrackRow key={`${track.track_signature}-${track.track_id}`} track={track} />)}
          </div>
        )}
      </Card>
    </>
  );
}
