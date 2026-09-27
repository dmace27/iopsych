import { defineConfig } from "vitest/config";

export default defineConfig({
  // Next preserves JSX for its compiler; Vitest needs an explicit transform in
  // order to exercise semantic React output in the Node test environment.
  oxc: {
    jsx: { runtime: "automatic" },
  },
  test: {
    coverage: {
      include: ["app/api/**/*.ts"],
      provider: "v8",
      reporter: ["text"],
      thresholds: {
        branches: 100,
        functions: 100,
        lines: 100,
        statements: 100,
      },
    },
    environment: "node",
  },
});
