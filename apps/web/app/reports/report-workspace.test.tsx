// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../lib/api-client";
import { ReportWorkspace, RecruiterReportsWorkspace } from "./report-workspace";
import { reportFixture, sourceFixture } from "./report-fixtures";

const api = vi.hoisted(() => ({
  getReport: vi.fn(),
  getRole: vi.fn(),
  getSubmittedAssessments: vi.fn(),
  generateReport: vi.fn(),
}));
vi.mock("../../lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-client")>()),
  ...api,
}));
beforeEach(() => {
  vi.resetAllMocks();
  api.getRole.mockResolvedValue({ title: "Product Engineer" });
  api.getSubmittedAssessments.mockResolvedValue([sourceFixture]);
  api.getReport.mockResolvedValue(reportFixture);
  api.generateReport.mockResolvedValue(reportFixture);
});
afterEach(cleanup);
it("loads sources, generates once, focuses the report and reopens its persisted snapshot", async () => {
  const user = userEvent.setup();
  render(<RecruiterReportsWorkspace roleId="role-id" />);
  expect(screen.getByRole("status")).toHaveTextContent(
    "Loading submitted assessments",
  );
  await user.click(
    await screen.findByRole("button", {
      name: "Generate report for synthetic@example.test",
    }),
  );
  const heading = await screen.findByRole("heading", {
    name: "Report for synthetic@example.test",
  });
  expect(heading).toHaveFocus();
  expect(api.generateReport).toHaveBeenCalledExactlyOnceWith(sourceFixture);
  expect(
    screen.getByRole("link", { name: "Open saved report link" }),
  ).toHaveAttribute("href", `/reports/${reportFixture.id}`);
  await user.click(
    screen.getByRole("button", {
      name: "View report for synthetic@example.test",
    }),
  );
  await screen.findByRole("heading", {
    name: "Report for synthetic@example.test",
  });
  expect(api.getReport).toHaveBeenCalledWith(reportFixture.id);
  expect(api.generateReport).toHaveBeenCalledTimes(1);
});
it("shows empty submissions and allows initial-load retry", async () => {
  const user = userEvent.setup();
  api.getRole.mockRejectedValueOnce(new Error("network"));
  api.getSubmittedAssessments.mockResolvedValue([]);
  render(<RecruiterReportsWorkspace roleId="role-id" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Try again");
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByRole("heading", {
      name: "No submitted assessments yet",
    }),
  ).toBeVisible();
});
it("retries failed generation and offers sign-in for expired sessions", async () => {
  const user = userEvent.setup();
  api.generateReport.mockRejectedValueOnce(
    new ApiClientError("Please sign in again.", {
      status: 401,
      code: "unauthorized",
    }),
  );
  render(<RecruiterReportsWorkspace roleId="role-id" />);
  await user.click(
    await screen.findByRole("button", {
      name: "Generate report for synthetic@example.test",
    }),
  );
  expect(
    await screen.findByRole("link", { name: "Sign in to view reports" }),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByRole("heading", {
      name: "Report for synthetic@example.test",
    }),
  ).toBeVisible();
});
it("preserves chronological pagination and retries a failed next page", async () => {
  const user = userEvent.setup();
  const page = Array.from({ length: 50 }, (_, index) => ({
    ...sourceFixture,
    assessment_id: `assessment-${index}`,
    candidate_email: `candidate-${index}@example.test`,
  }));
  api.getSubmittedAssessments
    .mockResolvedValueOnce(page)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce([{ ...sourceFixture, submitted_at: null }]);
  render(<RecruiterReportsWorkspace roleId="role-id" />);
  await user.click(
    await screen.findByRole("button", { name: "Load more assessments" }),
  );
  await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByText("Profile version 2 · Submission time unavailable"),
  ).toBeVisible();
  expect(api.getSubmittedAssessments).toHaveBeenLastCalledWith("role-id", 50);
  expect(
    screen.queryByRole("button", { name: "Load more assessments" }),
  ).not.toBeInTheDocument();
});
it("locks simultaneous requests and ignores a stale report after the role changes", async () => {
  const user = userEvent.setup();
  let resolve!: (value: typeof reportFixture) => void;
  api.generateReport.mockReturnValue(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const view = render(<RecruiterReportsWorkspace roleId="first" />);
  const button = await screen.findByRole("button", {
    name: "Generate report for synthetic@example.test",
  });
  await user.click(button);
  expect(button).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("Loading report");
  view.rerender(<RecruiterReportsWorkspace roleId="second" />);
  await waitFor(() => expect(api.getRole).toHaveBeenLastCalledWith("second"));
  resolve(reportFixture);
  await screen.findByRole("button", {
    name: "Generate report for synthetic@example.test",
  });
  expect(
    screen.queryByRole("heading", {
      name: "Report for synthetic@example.test",
    }),
  ).not.toBeInTheDocument();
});
it("loads a direct permalink and retries a denied read without generating a report", async () => {
  const user = userEvent.setup();
  api.getReport.mockRejectedValueOnce(
    new ApiClientError("Report not found.", { status: 404, code: "not_found" }),
  );
  render(<ReportWorkspace reportId={reportFixture.id} />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading report");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Report not found.",
  );
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByRole("heading", { name: "Construct comparison report" }),
  ).toBeVisible();
  expect(api.generateReport).not.toHaveBeenCalled();
});
it("discards a stale direct read on unmount", async () => {
  let reject!: (reason: Error) => void;
  api.getReport.mockReturnValue(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  const view = render(<ReportWorkspace reportId={reportFixture.id} />);
  view.unmount();
  reject(new Error("offline"));
  await Promise.resolve();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
