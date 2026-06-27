import { motion } from "framer-motion";

const tones = {
  album: "bg-iris/20 text-neon ring-iris/40",
  single: "bg-sky/15 text-sky ring-sky/40",
  ep: "bg-amber/15 text-amber ring-amber/40",
  featured: "bg-rose/15 text-rose ring-rose/40",
  main: "bg-mint/15 text-mint ring-mint/40",
  muted: "bg-mist text-comet ring-mist",
};

export function Badge({ children, tone = "muted", className = "" }) {
  return (
    <motion.span
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] ring-1 ${tones[tone] || tones.muted} ${className}`}
    >
      {children}
    </motion.span>
  );
}
