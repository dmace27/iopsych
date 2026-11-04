// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  within,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { traceFixture } from "../../lib/report-trace-fixtures";
import { ReportDetail } from "./report-detail";
import { reportFixture } from "./report-fixtures";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json({}, { status: 404 })),
  );
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
  vi.unstubAllGlobals();
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

describe("item evidence", () => {
  it.each(["complete", "skipped", "all-skipped"])(
    "loads %s evidence only on open and shows all four statements",
    async (name) => {
      const { report, trace } = traceFixture(name);
      vi.mocked(fetch).mockResolvedValue(Response.json(trace));
      render(<ReportDetail report={report} />);
      expect(fetch).not.toHaveBeenCalled();
      await userEvent.click(
        screen.getByRole("button", { name: "View evidence for Autonomy" }),
      );
      const dialog = screen.getByRole("dialog");
      await within(dialog).findByRole("heading", {
        name: "Item-level evidence",
      });
      for (const row of trace.constructs[0].items)
        expect(within(dialog).getByText(row.statement)).toBeVisible();
      expect(within(dialog).getByText(/Inclusive rating band/)).toBeVisible();
      expect(within(dialog).getByText(/not a probability/)).toBeVisible();
      expect(within(dialog).getByText(/Completeness:/)).toBeVisible();
      if (name === "all-skipped")
        expect(
          within(dialog).getAllByText(/Block skipped · Contribution: 0/),
        ).toHaveLength(4);
    },
  );
  it("retains the saved report on error and retries inside the dialog", async () => {
    const { report, trace } = traceFixture();
    vi.mocked(fetch)
      .mockResolvedValueOnce(Response.json({}, { status: 409 }))
      .mockResolvedValueOnce(Response.json(trace));
    render(<ReportDetail report={report} />);
    await userEvent.click(
      screen.getByRole("button", { name: "View evidence for Autonomy" }),
    );
    await screen.findByText(
      "Item-level evidence unavailable for this saved report",
    );
    expect(screen.getAllByRole("article")).toHaveLength(6);
    await userEvent.click(
      screen.getByRole("button", { name: "Retry item-level evidence" }),
    );
    await screen.findByRole("heading", { name: "Item-level evidence" });
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it.each([401, 403, 410])(
    "clears trace and shows access handling for %i",
    async (status) => {
      vi.mocked(fetch).mockResolvedValue(Response.json({}, { status }));
      render(<ReportDetail report={traceFixture().report} />);
      await userEvent.click(
        screen.getByRole("button", { name: "View evidence for Autonomy" }),
      );
      await screen.findByText(
        "Item-level evidence unavailable for this saved report",
      );
      expect(
        screen.queryByRole("button", { name: "Retry item-level evidence" }),
      ).not.toBeInTheDocument();
      if (status === 401)
        expect(
          screen.getByRole("link", { name: "Sign in to view reports" }),
        ).toBeVisible();
      expect(screen.getAllByRole("article")).toHaveLength(6);
    },
  );
  it("aborts on close and ignores a late response after switching reports", async () => {
    const { report, trace } = traceFixture();
    let resolve!: (response: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const { rerender } = render(<ReportDetail report={report} />);
    await userEvent.click(
      screen.getByRole("button", { name: "View evidence for Autonomy" }),
    );
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal;
    expect(screen.getByText("Loading item-level evidence…")).toBeVisible();
    rerender(
      <ReportDetail
        report={{ ...report, id: "00000000-0000-4000-8000-000000000099" }}
      />,
    );
    await waitFor(() => expect(signal?.aborted).toBe(true));
    await act(async () => {
      resolve(Response.json(trace));
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.queryByText(trace.constructs[0].items[0].statement),
    ).not.toBeInTheDocument();
  });
});

it("aborts a pending trace when the dialog closes", async () => {
  vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
  render(<ReportDetail report={traceFixture().report} />);
  const trigger = screen.getByRole("button", {
    name: "View evidence for Autonomy",
  });
  await userEvent.click(trigger);
  const signal = vi.mocked(fetch).mock.calls[0][1]?.signal;
  await userEvent.click(screen.getByRole("button", { name: "Close evidence" }));
  expect(signal?.aborted).toBe(true);
  expect(trigger).toHaveFocus();
});
it("never renders rows from a mismatched trace", async () => {
  const { trace, report } = traceFixture();
  trace.report_id = "00000000-0000-4000-8000-000000000099";
  vi.mocked(fetch).mockResolvedValue(Response.json(trace));
  render(<ReportDetail report={report} />);
  await userEvent.click(
    screen.getByRole("button", { name: "View evidence for Autonomy" }),
  );
  await screen.findByText(
    "Item-level evidence unavailable for this saved report",
  );
  expect(
    screen.queryByText(trace.constructs[0].items[0].statement),
  ).not.toBeInTheDocument();
  expect(screen.getAllByRole("article")).toHaveLength(6);
});
