// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../../../lib/api-client";
import { InvitationIssueForm } from "./invitation-issue-form";
const api = vi.hoisted(() => ({ profiles: vi.fn(), issue: vi.fn() }));
vi.mock("../../../../lib/api-client", async (original) => ({
  ...(await original<typeof import("../../../../lib/api-client")>()),
  getRoleProfiles: api.profiles,
}));
vi.mock("../../../../lib/invitation-issuance-client", () => ({
  issueInvitation: api.issue,
}));
const id = "00000000-0000-4000-8000-000000000002";
beforeEach(() => {
  vi.resetAllMocks();
  api.profiles.mockResolvedValue([
    { id, version: 2, status: "approved" },
    { id: "draft", version: 3, status: "draft" },
    { id: "old", version: 1, status: "superseded" },
  ]);
  api.issue.mockResolvedValue({ status: "pending_delivery" });
});
afterEach(cleanup);
async function preview() {
  const user = userEvent.setup();
  await user.type(
    await screen.findByLabelText("Recipient email"),
    "synthetic@example.invalid",
  );
  await user.selectOptions(
    screen.getByLabelText("Approved profile version"),
    id,
  );
  await user.click(screen.getByRole("button", { name: "Review invitation" }));
  return user;
}
it("shows only approved versions, previews default expiry, and requires explicit confirmation", async () => {
  const refreshed = vi.fn();
  render(<InvitationIssueForm roleId="role" onIssued={refreshed} />);
  const user = await preview();
  expect(screen.getAllByRole("option")).toHaveLength(2);
  expect(screen.getByText("Requested expiry: Server default")).toBeVisible();
  expect(api.issue).not.toHaveBeenCalled();
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  expect(
    await screen.findByText(/Stored status: Pending delivery/),
  ).toBeVisible();
  expect(refreshed).toHaveBeenCalledOnce();
  expect(api.issue).toHaveBeenCalledWith(
    "role",
    { role_profile_id: id, email: "synthetic@example.invalid" },
    expect.any(String),
  );
});
it("locks duplicate clicks, retains key on uncertain retry, resets on explicit new request", async () => {
  let reject!: (reason: unknown) => void;
  api.issue.mockImplementationOnce(
    () =>
      new Promise((_, fail) => {
        reject = fail;
      }),
  );
  render(<InvitationIssueForm roleId="role" onIssued={vi.fn()} />);
  const user = await preview();
  await user.dblClick(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  expect(api.issue).toHaveBeenCalledOnce();
  reject(new Error("private"));
  await user.click(
    await screen.findByRole("button", { name: "Confirm and retry invitation" }),
  );
  expect(api.issue.mock.calls[1][2]).toBe(api.issue.mock.calls[0][2]);
  await user.click(
    await screen.findByRole("button", { name: "Start new invitation" }),
  );
  await user.type(
    screen.getByLabelText("Recipient email"),
    "synthetic@example.invalid",
  );
  await user.click(screen.getByRole("button", { name: "Review invitation" }));
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  expect(api.issue.mock.calls[2][2]).not.toBe(api.issue.mock.calls[0][2]);
});
it("invalidates preview and key on payload change and validates expiry", async () => {
  api.issue.mockRejectedValueOnce(new Error("private"));
  render(<InvitationIssueForm roleId="role" onIssued={vi.fn()} />);
  const user = await preview();
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  await screen.findByRole("alert");
  await user.type(screen.getByLabelText(/Requested expiry in hours/), "721");
  expect(
    screen.queryByRole("button", { name: /Confirm and/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Review invitation" }),
  ).toBeDisabled();
  await user.clear(screen.getByLabelText(/Requested expiry in hours/));
  await user.type(screen.getByLabelText(/Requested expiry in hours/), "24");
  await user.click(screen.getByRole("button", { name: "Review invitation" }));
  expect(
    screen.getByText("Requested expiry: 24 hours from issuance"),
  ).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  expect(api.issue.mock.calls[1][2]).not.toBe(api.issue.mock.calls[0][2]);
  expect(api.issue.mock.calls[1][1].expires_in_hours).toBe(24);
});
it.each([401, 403, 404])(
  "removes issuance after access denial %s",
  async (status) => {
    api.issue.mockRejectedValue(
      new ApiClientError("private-token", { status, code: "failed" }),
    );
    render(<InvitationIssueForm roleId="role" onIssued={vi.fn()} />);
    const user = await preview();
    await user.click(
      screen.getByRole("button", { name: "Confirm and issue invitation" }),
    );
    expect(await screen.findByRole("alert")).not.toHaveTextContent(
      "private-token",
    );
    expect(
      screen.queryByRole("button", { name: /Confirm and/ }),
    ).not.toBeInTheDocument();
  },
);
it("offers safe profile loading retry and handles no approved versions", async () => {
  api.profiles
    .mockRejectedValueOnce(new Error("private"))
    .mockResolvedValueOnce([]);
  render(<InvitationIssueForm roleId="role" onIssued={vi.fn()} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Retry profile loading" }),
  );
  expect(
    await screen.findByText("No approved profile versions are available."),
  ).toBeVisible();
});
it("ignores completion after unmount", async () => {
  let finish!: (value: unknown) => void;
  api.issue.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const refreshed = vi.fn();
  const view = render(
    <InvitationIssueForm roleId="role" onIssued={refreshed} />,
  );
  const user = await preview();
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  view.unmount();
  finish({ status: "active" });
  await waitFor(() => expect(refreshed).not.toHaveBeenCalled());
});
