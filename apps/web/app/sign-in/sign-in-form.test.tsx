/** @vitest-environment jsdom */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { SignInForm } from "./sign-in-form";
afterEach(cleanup);
it("uses provider navigation with a safe return path", () => {
  render(<SignInForm returnTo="/reports/report-id" />);
  expect(
    screen.getByRole("link", { name: "Sign in with Auth0" }),
  ).toHaveAttribute("href", "/api/auth/login?returnTo=%2Freports%2Freport-id");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
});
it("announces configuration failure and blocks external return paths", () => {
  render(<SignInForm returnTo="//evil.invalid" error="configuration" />);
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Contact your administrator",
  );
  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    "/api/auth/login?returnTo=%2Froles",
  );
});
it("offers recovery after callback failures without reflecting errors", () => {
  render(<SignInForm error="private-provider-detail" />);
  expect(screen.getByRole("alert")).toHaveTextContent("Try again");
  expect(screen.getByRole("alert")).not.toHaveTextContent(
    "private-provider-detail",
  );
});
