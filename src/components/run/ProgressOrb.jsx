import { ProgressRing } from "../ui/ProgressRing";

export function ProgressOrb({ processed = 0, total = 0 }) {
  return (
    <div className="grid place-items-center rounded-[20px] border border-mist bg-void/50 p-5">
      <ProgressRing value={processed} total={total} />
    </div>
  );
}
