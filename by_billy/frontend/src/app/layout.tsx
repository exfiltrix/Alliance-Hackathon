import type { Metadata } from "next";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { LanguageProvider } from "@/lib/language-context";
import { INIT_SCRIPT } from "@/lib/a11y-init";
import SkipLink from "@/components/SkipLink";
import MockBanner from "@/components/MockBanner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "cyrillic"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MedSeal — muhr va antivirus tibbiy suratlar uchun",
  description:
    "MedSeal checks medical image integrity and measures how easily the AI reading it can be fooled; it is not a clinical clearance.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Attributes on <html> are set before hydration by INIT_SCRIPT (saved language / accessibility mode).
    <html
      lang="uz"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/* beforeInteractive: Next injects it into <head> and runs it before hydration. A raw <script>
            inside a React component is never executed on the client (React 19 console error). */}
        <Script id="medseal-init" strategy="beforeInteractive">
          {INIT_SCRIPT}
        </Script>
        <LanguageProvider>
          <SkipLink />
          <MockBanner />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
