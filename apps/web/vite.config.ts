import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api/v1": {
        target: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on("error", (err, _req, res: any) => {
            if (res.headersSent) return;
            res.writeHead(503, {
              "Content-Type": "application/json",
            });
            res.end(
              JSON.stringify({
                detail: "Unable to connect to ConvoMind API server.",
              })
            );
          });
        },
      },
      "/health": {
        target: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
