import { motion } from "framer-motion";

export function Card({ children, className = "", hover = false, style }) {
  const Component = hover ? motion.div : "div";
  const motionProps = hover
    ? {
        whileHover: { y: -3 },
        transition: { type: "spring", stiffness: 300, damping: 28 },
      }
    : {};

  return (
    <Component
      className={`rounded-[20px] bg-obsidian shadow-card ${className}`}
      style={style}
      {...motionProps}
    >
      {children}
    </Component>
  );
}
