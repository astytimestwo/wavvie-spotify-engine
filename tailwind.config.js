export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        void: "var(--void)",
        obsidian: "var(--obsidian)",
        slate: "var(--slate)",
        mist: "var(--mist)",
        iris: "var(--iris)",
        "iris-dim": "var(--iris-dim)",
        neon: "var(--neon)",
        mint: "var(--mint)",
        rose: "var(--rose)",
        amber: "var(--amber)",
        sky: "var(--sky)",
        snow: "var(--snow)",
        comet: "var(--comet)",
        ghost: "var(--ghost)",
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        card: "0 0 0 1px var(--mist), 0 8px 32px rgba(0,0,0,.5)",
        iris: "0 0 24px rgba(124,58,237,.35)",
      },
    },
  },
  plugins: [],
};
