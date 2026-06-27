import { CalendarDays, Wifi, WifiOff } from "lucide-react";

export function TopBar({ title, subtitle, connected }) {
  return (
    <header className="mb-6 flex items-center justify-between gap-4">
      <div>
        <h1 className="font-display text-3xl font-semibold leading-tight text-snow">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-comet">{subtitle}</p> : null}
      </div>
      <div className="flex items-center gap-3 rounded-full border border-mist bg-obsidian px-4 py-2 text-xs text-comet">
        <CalendarDays size={15} className="text-neon" />
        <span className="font-mono">{new Date().toLocaleDateString()}</span>
        {connected ? <Wifi size={15} className="text-mint" /> : <WifiOff size={15} className="text-ghost" />}
      </div>
    </header>
  );
}
