import { motion } from "framer-motion";
import { BarChart3, Disc3, ListMusic, PlayCircle, Radio, RefreshCw } from "lucide-react";
import { Button } from "../ui/Button";

const nav = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "artists", label: "Artists", icon: Radio },
  { id: "releases", label: "Releases", icon: Disc3 },
  { id: "run", label: "Run", icon: PlayCircle },
  { id: "playlists", label: "Playlists", icon: ListMusic },
];

function WaveIcon() {
  return (
    <div className="flex h-9 w-9 items-center justify-center gap-[3px] rounded-xl bg-iris/20 ring-1 ring-iris/40">
      {[16, 24, 12].map((height, index) => (
        <span key={index} className="w-1.5 rounded-full bg-neon" style={{ height }} />
      ))}
    </div>
  );
}

export function Sidebar({ activePage, onPageChange, user }) {
  const avatar = user?.images?.[0]?.url;

  return (
    <aside className="fixed left-0 top-0 z-20 flex h-screen w-[220px] flex-col border-r border-mist bg-slate px-4 py-5">
      <div className="mb-8 flex items-center gap-3">
        <WaveIcon />
        <div className="font-display text-lg font-semibold text-neon">WAVEFEED</div>
      </div>

      <nav className="space-y-2">
        {nav.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onPageChange(item.id)}
              className="relative flex h-11 w-full items-center gap-3 overflow-hidden rounded-full px-3 text-left text-sm font-medium text-comet transition hover:text-snow"
            >
              {active ? (
                <motion.span
                  layoutId="active-nav-pill"
                  className="absolute inset-0 rounded-full bg-iris-dim/80"
                  transition={{ type: "spring", stiffness: 300, damping: 28 }}
                />
              ) : null}
              {active ? <span className="absolute left-0 top-2 h-7 w-[3px] rounded-full bg-iris" /> : null}
              <Icon size={17} className="relative" />
              <span className="relative">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="mt-auto rounded-[20px] border border-mist bg-void/40 p-3">
        <div className="flex items-center gap-3">
          {avatar ? (
            <img src={avatar} alt="" className="h-8 w-8 rounded-full object-cover" />
          ) : (
            <div className="grid h-8 w-8 place-items-center rounded-full bg-iris text-xs font-bold text-snow">
              {(user?.display_name || "SP").slice(0, 2).toUpperCase()}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">{user?.display_name || "Spotify"}</div>
            <div className="truncate font-mono text-[11px] text-comet">{user?.id || "not connected"}</div>
          </div>
          <Button variant="ghost" className="h-8 w-8 px-0 py-0" title="Refresh status" icon={RefreshCw} />
        </div>
      </div>
    </aside>
  );
}
