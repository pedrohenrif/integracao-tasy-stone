import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxy = {
  "/api": "http://127.0.0.1:8001",
  "/health": "http://127.0.0.1:8001",
};

const allowedHosts = [
  "localhost",
  "127.0.0.1",
  "10.1.1.190",
  "stone.pequenocotolengo.org.br",
  "stone.financeiro",
];

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts,
    proxy,
  },
  preview: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts,
    proxy,
  },
});
