import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { api } from "../lib/api";
import { TopBar } from "../components/layout/TopBar";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";

export function Playlists() {
  const [playlists, setPlaylists] = useState([]);

  useEffect(() => {
    api.playlists().then((data) => setPlaylists(data.playlists || [])).catch(() => {});
  }, []);

  return (
    <>
      <TopBar title="Playlists" subtitle="Created playlists from completed dashboard runs." />
      <div className="grid gap-4">
        {playlists.map((playlist) => (
          <Card key={playlist.run_id} hover className="p-5">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="truncate font-display text-xl font-semibold">{playlist.playlist_name}</div>
                <div className="font-mono text-xs text-comet">
                  {new Date(playlist.created_at).toLocaleString()} · Artists {playlist.artist_range?.[0]}-{playlist.artist_range?.[1]}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge tone="album">{playlist.track_count} tracks</Badge>
                {playlist.playlist_url ? (
                  <a href={playlist.playlist_url} target="_blank" rel="noreferrer">
                    <Button variant="mint" icon={ExternalLink}>Open in Spotify</Button>
                  </a>
                ) : null}
              </div>
            </div>
            <div className="mt-4 flex -space-x-3">
              {(playlist.artwork || []).map((url) => (
                <img key={url} src={url} alt="" className="h-12 w-12 rounded-xl border-2 border-obsidian object-cover" />
              ))}
            </div>
          </Card>
        ))}
        {playlists.length === 0 ? (
          <Card className="grid h-[320px] place-items-center p-8 text-center text-comet">
            Completed API runs will appear here after they create playlists.
          </Card>
        ) : null}
      </div>
    </>
  );
}
