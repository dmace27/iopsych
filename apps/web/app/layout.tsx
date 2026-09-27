import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SiteHeader } from "./ui/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Role studio · IOPsych",
    template: "%s · IOPsych",
  },
  description:
    "Human-reviewed role profiles for evidence-seeking interview preparation.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
