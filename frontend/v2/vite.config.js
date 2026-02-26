import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Custom plugin to redirect /app to /app/
const redirectApp = () => ({
  name: "redirect-app",
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      if (req.url === "/app") {
        res.writeHead(301, { Location: "/app/" });
        res.end();
      } else {
        next();
      }
    });
  },
});

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), redirectApp()],
  base: "/app/",
  build: {
    outDir: "../../src/bedrock_server_manager/web/static/v2",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/static": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/themes": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/auth": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/users": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/setup": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:11325",
        ws: true,
        changeOrigin: true,
        secure: false,
      },
      "/server": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/plugin": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/plugins": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/content": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/audit-log": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
      "/register": {
        target: "http://localhost:11325",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
  },
});
