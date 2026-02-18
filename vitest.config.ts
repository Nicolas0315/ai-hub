import { defineConfig } from "vitest/config"
import path from "path"

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
})
