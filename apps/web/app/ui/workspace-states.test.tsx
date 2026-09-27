import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { StatusBadge, statusLabel } from "./status-badge";
import { EmptyState, ErrorState, LoadingState } from "./workspace-states";

describe("accessible workspace states", () => {
  it("announces loading without using motion as the only cue", () => {
    const markup = renderToStaticMarkup(<LoadingState label="Loading roles" />);

    expect(markup).toContain('role="status"');
    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain("Loading roles");
  });

  it("exposes a recoverable error as an alert", () => {
    const markup = renderToStaticMarkup(
      <ErrorState
        message="Try the request again."
        onRetry={vi.fn()}
        title="Roles are unavailable"
      />,
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Try again");
    expect(markup).toContain("Roles are unavailable");
  });

  it("renders an empty state and optional next action", () => {
    const markup = renderToStaticMarkup(
      <EmptyState description="Create the first role." title="No roles yet">
        <button type="button">Create role</button>
      </EmptyState>,
    );

    expect(markup).toContain("No roles yet");
    expect(markup).toContain("Create role");
  });

  it("renders every state with a readable label instead of color alone", () => {
    for (const status of [
      "active",
      "approved",
      "archived",
      "draft",
      "superseded",
    ] as const) {
      const markup = renderToStaticMarkup(<StatusBadge status={status} />);
      expect(markup).toContain(statusLabel(status));
    }
  });
});
