import { defineConfig } from "vite";

// The site is static. It is built into ../docs so GitHub Pages can serve it.
export default defineConfig({
  base: "./",
  build: {
    outDir: "../docs",
    emptyOutDir: true,
    target: "es2022",
    // Three pages: the free checker, the bounties, and v2 (two explorers, a bond and a challenge).
    rollupOptions: { input: { main: "index.html", bounties: "bounties.html", twoExplorers: "two-explorers.html" } },
  },
});
