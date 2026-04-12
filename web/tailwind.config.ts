import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "hsl(var(--bg))",
        panel: "hsl(var(--panel))",
        line: "hsl(var(--line))",
        ink: "hsl(var(--ink))",
        muted: "hsl(var(--muted))",
        accent: "hsl(var(--accent))",
        good: "hsl(var(--good))",
        warn: "hsl(var(--warn))",
        bad: "hsl(var(--bad))"
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"]
      },
      boxShadow: {
        panel: "0 0 0 1px rgba(24, 35, 52, 0.08), 0 18px 38px rgba(24, 35, 52, 0.06)"
      }
    }
  },
  plugins: [],
};

export default config;
