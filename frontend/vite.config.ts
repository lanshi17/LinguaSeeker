import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ mode }) => {
  // Load all env vars (empty prefix → includes non-VITE_ secrets like API_KEY).
  // Non-VITE_ vars are NOT exposed to the client bundle — safe to use here.
  const env = loadEnv(mode, process.cwd(), "");
  const apiKey = env.API_KEY || "";

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
        // Inject the shared X-API-Key so the backend trusts proxied requests.
        // The browser never sees this key — it lives only in server-side env.
        "/api/v1": {
          target: "http://localhost:8000",
          changeOrigin: true,
          ...(apiKey ? { headers: { "X-API-Key": apiKey } } : {}),
        },
        "/health": {
          target: "http://localhost:8000",
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
