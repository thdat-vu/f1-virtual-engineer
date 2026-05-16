import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { SupabaseProvider } from "@/components/auth/SupabaseProvider";

const siteTitle = "F1 Virtual Engineer";
const siteDescription =
  "Mission-control UX for telemetry analysis, pit-window reasoning, and explainable Formula 1 strategy signals.";

export const metadata: Metadata = {
  metadataBase: new URL("https://f1-virtual-engineer.local"),
  title: {
    default: siteTitle,
    template: "%s | F1 Virtual Engineer",
  },
  description: siteDescription,
  applicationName: "F1 Virtual Engineer",
  keywords: [
    "Formula 1",
    "F1 telemetry",
    "race engineer",
    "agentic AI",
    "motorsport strategy",
    "mission control",
  ],
  // icons: omitted on purpose. The Next.js App Router file convention
  // picks up `app/icon.png` + `app/apple-icon.png` automatically and
  // injects the right <link> tags. Listing icons here too produces
  // duplicate or conflicting entries.
  manifest: "/manifest.webmanifest",
  openGraph: {
    title: siteTitle,
    description: siteDescription,
    siteName: "F1 Virtual Engineer",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: siteTitle,
    description: siteDescription,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <ThemeProvider />
        <SupabaseProvider>{children}</SupabaseProvider>
      </body>
    </html>
  );
}
