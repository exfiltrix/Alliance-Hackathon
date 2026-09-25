"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import LanguageSwitch from "./LanguageSwitch";

const links = [
  { href: "/seal", key: "seal" },
  { href: "/verify", key: "verify" },
  { href: "/crash-test", key: "crashTest" },
  { href: "/dashboard", key: "dashboard" },
] as const;

export default function Header() {
  const { t } = useLanguage();
  const pathname = usePathname();

  const linkClass = (href: string) =>
    `whitespace-nowrap transition-colors ${
      pathname.startsWith(href) ? "text-foreground" : "text-muted hover:text-foreground"
    }`;

  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/80 backdrop-blur print:hidden">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-sm font-bold text-white">
            M
          </span>
          <span className="text-lg font-semibold tracking-tight">MedSeal</span>
        </Link>

        <nav className="hidden items-center gap-8 text-sm font-medium md:flex">
          {links.map(({ href, key }) => (
            <Link key={href} href={href} className={linkClass(href)}>
              {t(dictionary.nav[key])}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <LanguageSwitch />
          <Link
            href="/seal"
            className="hidden rounded-full bg-foreground px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-foreground/90 sm:inline-flex"
          >
            {t(dictionary.nav.cta)}
          </Link>
        </div>
      </div>

      <nav className="flex gap-5 overflow-x-auto px-4 pb-3 text-sm font-medium md:hidden">
        {links.map(({ href, key }) => (
          <Link key={href} href={href} className={linkClass(href)}>
            {t(dictionary.nav[key])}
          </Link>
        ))}
      </nav>
    </header>
  );
}
