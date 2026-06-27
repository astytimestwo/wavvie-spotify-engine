import { RefreshCw, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { TopBar } from "../components/layout/TopBar";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Skeleton } from "../components/ui/Skeleton";

function initials(name = "?") {
  return name.split(" ").slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

export function Artists({ artists = [], loading, cached, refresh }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () => artists.filter((artist) => artist.name?.toLowerCase().includes(query.toLowerCase())),
    [artists, query],
  );

  return (
    <>
      <TopBar title={`Your Artists · ${artists.length} followed`} subtitle={cached ? "Loaded from local cache." : "Fetched from Spotify."} />
      <div className="mb-5 flex items-end gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-[42px] text-ghost" size={18} />
          <Input label="Search artists" placeholder="Bonobo, Charli, Fred..." value={query} onChange={(event) => setQuery(event.target.value)} className="[&_input]:pl-11" />
        </div>
        <Button variant="outline" icon={RefreshCw} onClick={refresh} title="Clear cache & refetch">
          Refresh cache
        </Button>
      </div>
      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-4">
          {Array.from({ length: 18 }).map((_, index) => <Skeleton key={index} className="h-[220px]" />)}
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-4">
          {filtered.map((artist) => (
            <Card key={artist.id} hover className="overflow-hidden">
              <div className="aspect-square overflow-hidden">
                {artist.images?.[0]?.url ? (
                  <img src={artist.images[0].url} alt="" className="h-full w-full object-cover transition duration-300 hover:scale-110" />
                ) : (
                  <div className="grid h-full w-full place-items-center bg-gradient-to-br from-iris to-neon font-display text-3xl font-semibold">
                    {initials(artist.name)}
                  </div>
                )}
              </div>
              <div className="p-4">
                <div className="truncate font-display text-base font-semibold">{artist.name}</div>
                <div className="font-mono text-[11px] text-comet">{(artist.followers?.total || 0).toLocaleString()} followers</div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
