import type { Metadata } from "next";
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
    "MedSeal proves a medical image is authentic and that the AI reading it hasn't been fooled.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Attributes on <html> are set before hydration by INIT_SCRIPT (saved language / accessibility mode).
    <html
      lang="uz"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col">
        <LanguageProvider>
          <SkipLink />
          <MockBanner />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
