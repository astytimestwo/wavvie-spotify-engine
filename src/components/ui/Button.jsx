import { motion } from "framer-motion";

const variants = {
  primary: "bg-iris text-snow shadow-iris hover:bg-neon hover:text-void",
  outline: "border border-mist bg-transparent text-snow hover:border-neon hover:text-neon",
  rose: "border border-rose/60 bg-rose/10 text-rose hover:bg-rose hover:text-void",
  mint: "border border-mint/60 bg-mint/10 text-mint hover:bg-mint hover:text-void",
  ghost: "bg-transparent text-comet hover:bg-mist hover:text-snow",
};

export function Button({ children, variant = "primary", className = "", icon: Icon, ...props }) {
  return (
    <motion.button
      whileHover={{ scale: props.disabled ? 1 : 1.02 }}
      whileTap={{ scale: props.disabled ? 1 : 0.96 }}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition ${variants[variant]} ${className}`}
      {...props}
    >
      {Icon ? <Icon size={17} strokeWidth={2.2} /> : null}
      {children}
    </motion.button>
  );
}
