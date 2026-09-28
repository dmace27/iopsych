// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  within,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReportDetail } from "./report-detail";
import { reportFixture } from "./report-fixtures";

beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value() {},
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value() {},
  });
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(
    function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    },
  );
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function (
    this: HTMLDialogElement,
  ) {
    this.removeAttribute("open");
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("report presentation", () => {
  it("shows six independent cards, all outcome states, questions and version references", async () => {
    const user = userEvent.setup();
    render(
      <ReportDetail
        report={reportFixture}
        candidateEmail="synthetic@example.test"
      />,
    );
    expect(screen.getAllByRole("article")).toHaveLength(6);
    expect(screen.getByText("Insufficient evidence")).toBeVisible();
    expect(screen.getByText("Worth discussing")).toBeVisible();
    expect(screen.getByText("Potential friction")).toBeVisible();
    expect(screen.getByText(/Low confidence/)).toBeVisible();
    expect(
      screen.getByText(/Structure uses an inverse comparison: 6 − 4 = 2/),
    ).toBeVisible();
    expect(
      screen.getByRole("complementary", { name: "Responsible use" }),
    ).toHaveTextContent(reportFixture.usage_warning);
    expect(
      screen.getByRole("link", { name: "Jump to interview guide" }),
    ).toHaveAttribute("href", "#interview-guide");
    for (const item of reportFixture.result.items)
      expect(
        screen.getByText(item.interview_questions.primary.text),
      ).toBeVisible();
    await user.click(screen.getByText("Report versions and source references"));
    expect(screen.getByText(reportFixture.assessment_id)).toBeVisible();
    await user.click(screen.getAllByText("Question references")[0]);
    expect(
      screen.getByText(
        reportFixture.result.items[0].interview_questions.primary.id,
        { exact: false },
      ),
    ).toBeVisible();
  });
  it("opens inspectable evidence, closes with Escape and restores trigger focus", async () => {
    const user = userEvent.setup();
    render(<ReportDetail report={reportFixture} />);
    expect(
      screen.getByRole("heading", { name: "Construct comparison report" }),
    ).toBeVisible();
    const trigger = screen.getByRole("button", {
      name: "View evidence for Autonomy",
    });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Evidence: Autonomy" });
    expect(
      within(dialog).getByText("Exact autonomy job evidence"),
    ).toBeVisible();
    expect(
      within(dialog).getByText(
        /4 of 4 assigned statements answered; 0 skipped/,
      ),
    ).toBeVisible();
    expect(within(dialog).getByText(/Combined confidence: low/)).toBeVisible();
    fireEvent(dialog, new Event("cancel", { bubbles: true, cancelable: true }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    await user.click(
      screen.getByRole("button", { name: "View evidence for Structure" }),
    );
    expect(screen.getByRole("dialog")).not.toHaveTextContent("Uncertainty:");
    await user.click(screen.getByRole("button", { name: "Close evidence" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
