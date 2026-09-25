"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import LanguageSwitch from "./LanguageSwitch";
import AccessibilityPanel from "./AccessibilityPanel";
import { ChartIcon, CrashTestIcon, SealIcon, VerifyIcon } from "./icons";

const links = [
  { href: "/seal", key: "seal", icon: SealIcon },
  { href: "/verify", key: "verify", icon: VerifyIcon },
  { href: "/crash-test", key: "crashTest", icon: CrashTestIcon, match: ["/crash-test", "/passport"] },
  { href: "/dashboard", key: "dashboard", icon: ChartIcon },
] as const;

export default function Header() {
  const { t } = useLanguage();
  const pathname = usePathname();

  const isActive = (l: (typeof links)[number]) =>
    ("match" in l ? l.match : [l.href]).some((p) => pathname.startsWith(p));

  const linkClass = (active: boolean) =>
    `flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 transition-colors ${
      active ? "bg-white text-foreground shadow-sm" : "text-muted hover:bg-white/60 hover:text-foreground"
    }`;

  return (
    <header className="sticky top-0 z-20 border-b border-white/60 bg-background/70 backdrop-blur-xl print:hidden">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-foreground text-white">
            <SealIcon width={18} height={18} />
          </span>
          <span className="text-lg font-semibold tracking-tight">MedSeal</span>
        </Link>

        <nav aria-label={t(dictionary.nav.menu)} className="hidden items-center gap-1 rounded-full border border-white/70 bg-white/40 p-1 text-sm font-medium md:flex">
          {links.map((l) => {
            const Icon = l.icon;
            const active = isActive(l);
            return (
              <Link key={l.href} href={l.href} className={linkClass(active)} aria-current={active ? "page" : undefined}>
                <Icon width={16} height={16} />
                {t(dictionary.nav[l.key])}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <AccessibilityPanel />
          <LanguageSwitch />
          <Link
            href="/register"
            className={`hidden rounded-full border border-border px-3.5 py-2 text-sm font-medium transition-colors hover:bg-white sm:inline-flex ${
              pathname.startsWith("/register") ? "bg-white text-foreground" : "text-muted"
            }`}
          >
            {t(dictionary.nav.register)}
          </Link>
          <Link
            href="/seal"
            className="hidden rounded-full bg-foreground px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-foreground/90 lg:inline-flex"
          >
            {t(dictionary.nav.cta)}
          </Link>
        </div>
      </div>

      <nav aria-label={t(dictionary.nav.menu)} className="flex gap-1 overflow-x-auto px-3 pb-2.5 text-sm font-medium md:hidden">
        {links.map((l) => {
          const Icon = l.icon;
          const active = isActive(l);
          return (
            <Link key={l.href} href={l.href} className={linkClass(active)} aria-current={active ? "page" : undefined}>
              <Icon width={16} height={16} />
              {t(dictionary.nav[l.key])}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
