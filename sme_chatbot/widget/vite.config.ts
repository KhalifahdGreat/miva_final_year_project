import { defineConfig } from "vite";

export default defineConfig({
  build: {
    lib: {
      entry: "src/main.ts",
      name: "SmeChatbot",
      fileName: () => "widget.js",
      formats: ["iife"],
    },
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        assetFileNames: "widget.[ext]",
      },
    },
  },
  server: {
    port: 5173,
  },
});
