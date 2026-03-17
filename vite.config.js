import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "src/apps/web/frontend");

export default defineConfig({
  root: frontendRoot,
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, "src/apps/web/frontend_dist"),
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: path.resolve(frontendRoot, "index.html"),
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]"
      }
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: path.resolve(frontendRoot, "src/test/setup.js")
  }
});
