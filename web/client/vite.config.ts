/// <reference types="vitest" />
import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

// The API checks every POST's Origin against HARMONICFITNESS_BASE_URL, so the dev proxy sends the API's own.
// Rewriting Origin bypasses that CSRF check, in development only: production serves the client
// from the API's own origin, with no proxy.
const API = "http://localhost:8000";
const proxy: ProxyOptions = {
  target: API,
  changeOrigin: true,
  configure: (p) => p.on("proxyReq", (req) => req.setHeader("origin", API)),
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": proxy, "/link": proxy } },
  build: { outDir: "dist", emptyOutDir: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
