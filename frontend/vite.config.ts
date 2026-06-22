import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ mode }) => {
  // Load all env vars (empty prefix → includes non-VITE_ secrets like API_KEY).
  // Non-VITE_ vars are NOT exposed to the client bundle — safe to use here.
  const env = loadEnv(mode, process.cwd(), "");
  const apiKey = env.API_KEY || "";
  const backendUrl = env.BACKEND_URL || "http://localhost:8000";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      host: true,
      port: 3000,
      proxy: {
        "/api/v1": {
          target: backendUrl,
          changeOrigin: true,
          ...(apiKey ? { headers: { "X-API-Key": apiKey } } : {}),
        },
        "/health": {
          target: backendUrl,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
  };
});
