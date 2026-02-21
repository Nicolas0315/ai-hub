import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    globals: true,
    exclude: ["e2e/**", "node_modules/**"],
    deps: {
      inline: [/packages\//],
    },
  },
});
