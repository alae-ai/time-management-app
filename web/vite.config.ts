import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.TM_API_URL ?? "http://127.0.0.1:4317";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": apiTarget,
    },
  },
});
