/** @vitest-environment jsdom */
import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("../../lib/api-client", async (original) => ({
  ...(await original<typeof import("../../lib/api-client")>()),
  getCurrentUser: vi.fn(),
}));
vi.mock("../../lib/account-client", () => ({
  getAccounts: vi.fn(),
  updateAccount: vi.fn(),
}));
import { ApiClientError, getCurrentUser } from "../../lib/api-client";
import { getAccounts, updateAccount } from "../../lib/account-client";
import { AccountsWorkspace } from "./accounts-workspace";
const self = {
  id: "10000000-0000-4000-8000-000000000099",
  email: "admin@alpha.example.invalid",
  name: "Alpha Admin",
  role: "admin" as const,
  is_active: true,
  version: 1,
};
const other = {
  ...self,
  id: "20000000-0000-4000-8000-000000000099",
  name: "Other User",
  email: "other@example.invalid",
  role: "recruiter" as const,
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getCurrentUser).mockResolvedValue({
    ...self,
    organization_id: "30000000-0000-4000-8000-000000000099",
  });
  vi.mocked(getAccounts).mockResolvedValue({
    items: [self, other],
    next_cursor: null,
  });
});
afterEach(cleanup);
it("keeps self read-only and confirms role changes with focus and expected version", async () => {
  const user = userEvent.setup();
  vi.mocked(updateAccount).mockResolvedValue({
    ...other,
    role: "hiring_manager",
    version: 2,
  });
  render(<AccountsWorkspace />);
  await screen.findByText("Alpha Admin (you)");
  expect(screen.getAllByRole("combobox", { name: /^Role for / })).toHaveLength(
    1,
  );
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Role for Other User" }),
    "hiring_manager",
  );
  await user.click(screen.getByRole("button", { name: "Review role change" }));
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  expect(updateAccount).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(
    screen.getByRole("button", { name: "Review role change" }),
  ).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "Review role change" }));
  await user.click(screen.getByRole("button", { name: "Confirm change" }));
  expect(updateAccount).toHaveBeenCalledWith(other.id, {
    expected_version: 1,
    role: "hiring_manager",
  });
  expect(
    await screen.findByText("Access updated for Other User."),
  ).toBeInTheDocument();
});
it("locks uncertain changes until refresh and never retries stale versions automatically", async () => {
  const user = userEvent.setup();
  vi.mocked(updateAccount).mockRejectedValue(
    new ApiClientError("Account details changed. Refresh accounts.", {
      status: 409,
      code: "account_version_conflict",
    }),
  );
  render(<AccountsWorkspace />);
  await user.click(await screen.findByRole("button", { name: "Deactivate" }));
  await user.click(screen.getByRole("button", { name: "Confirm change" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Refresh accounts",
  );
  expect(screen.getByRole("button", { name: "Deactivate" })).toBeDisabled();
  expect(updateAccount).toHaveBeenCalledTimes(1);
  vi.mocked(getAccounts).mockResolvedValue({
    items: [{ ...other, version: 3, is_active: false }],
    next_cursor: null,
  });
  await user.click(screen.getByRole("button", { name: "Refresh accounts" }));
  await user.click(await screen.findByRole("button", { name: "Reactivate" }));
  expect(
    within(screen.getByRole("alertdialog")).getByText(/reactivate access/),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Confirm change" }));
  expect(updateAccount).toHaveBeenLastCalledWith(other.id, {
    expected_version: 3,
    is_active: true,
  });
});
it("uses bounded pages rather than appending and can return to the first page", async () => {
  vi.mocked(getAccounts)
    .mockResolvedValueOnce({ items: [self], next_cursor: self.id })
    .mockResolvedValueOnce({ items: [other], next_cursor: null })
    .mockResolvedValueOnce({ items: [self], next_cursor: self.id });
  const user = userEvent.setup();
  render(<AccountsWorkspace />);
  await user.click(await screen.findByRole("button", { name: "Next page" }));
  await screen.findByText("Other User");
  expect(screen.queryByText("Alpha Admin (you)")).not.toBeInTheDocument();
  expect(getAccounts).toHaveBeenLastCalledWith({ after: self.id });
  await user.click(screen.getByRole("button", { name: "Previous page" }));
  await screen.findByText("Alpha Admin (you)");
  expect(getAccounts).toHaveBeenLastCalledWith({ after: undefined });
});
it("does not fetch accounts for non-admin users", async () => {
  vi.mocked(getCurrentUser).mockResolvedValue({
    ...self,
    role: "hiring_manager",
    organization_id: self.id,
  });
  render(<AccountsWorkspace />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Only administrators",
  );
  expect(getAccounts).not.toHaveBeenCalled();
});
it("provides safe sign-in recovery for expired sessions", async () => {
  vi.mocked(getCurrentUser).mockRejectedValue(
    new ApiClientError("Session expired", { status: 401, code: "expired" }),
  );
  render(<AccountsWorkspace />);
  expect(
    await screen.findByRole("link", { name: "Sign in to continue" }),
  ).toHaveAttribute("href", "/sign-in?returnTo=%2Faccounts");
  expect(getAccounts).not.toHaveBeenCalled();
});
it("prevents duplicate submissions while saving", async () => {
  const user = userEvent.setup();
  vi.mocked(updateAccount).mockReturnValue(new Promise(() => {}));
  render(<AccountsWorkspace />);
  await user.click(await screen.findByRole("button", { name: "Deactivate" }));
  await user.dblClick(screen.getByRole("button", { name: "Confirm change" }));
  await waitFor(() => expect(updateAccount).toHaveBeenCalledTimes(1));
  expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
});
it("shows empty and load-error recovery states", async () => {
  const user = userEvent.setup();
  vi.mocked(getAccounts)
    .mockRejectedValueOnce(
      new ApiClientError("Accounts unavailable", {
        status: 500,
        code: "failed",
      }),
    )
    .mockResolvedValueOnce({ items: [], next_cursor: null });
  render(<AccountsWorkspace />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Accounts unavailable",
  );
  await user.click(screen.getByRole("button", { name: "Refresh accounts" }));
  expect(
    await screen.findByText("No accounts on this page."),
  ).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Accounts" })).toHaveFocus();
});
