import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pre-Flight",
  description:
    "Pre-launch quality gate for AI-generated research surveys. Persona-conditioned probes catch survey-side defects before fielding.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
