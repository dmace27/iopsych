import { defineConfig } from "vitest/config";

export default defineConfig({
  // Next preserves JSX for its compiler; Vitest needs an explicit transform in
  // order to exercise semantic React output in the Node test environment.
  oxc: {
    jsx: { runtime: "automatic" },
  },
  test: {
    coverage: {
      // Measure both the security boundary and the phase-one interactive UI.
      // Route wrappers and static page composition contain no behavior of their
      // own, so focused components and shared presentation logic are included.
      include: [
        "app/api/**/*.ts",
        "app/candidate/**/*assessment.tsx",
        "app/roles/**/*workspace.tsx",
        "app/reports/*.tsx",
        "app/sign-in/sign-in-form.tsx",
        "app/ui/**/*.tsx",
        "lib/**/*.ts",
      ],
      provider: "v8",
      reporter: ["text"],
      thresholds: {
        branches: 75,
        functions: 80,
        lines: 80,
        statements: 80,
        // Preserve the original perfect gate around authentication, CSRF, and
        // proxy behavior while broadening global coverage to browser screens.
        "app/api/**/*.ts": {
          branches: 100,
          functions: 100,
          lines: 100,
          statements: 100,
        },
      },
    },
    environment: "node",
  },
});
