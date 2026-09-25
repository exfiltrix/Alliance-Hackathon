"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { logout, useAuth } from "@/lib/auth";
import LanguageSwitch from "./LanguageSwitch";
import AccessibilityPanel from "./AccessibilityPanel";
import { ChartIcon, CrashTestIcon, SealIcon, VerifyIcon } from "./icons";

const ALL_LINKS = [
  { href: "/seal", key: "seal", icon: SealIcon },
  { href: "/verify", key: "verify", icon: VerifyIcon },
  { href: "/crash-test", key: "crashTest", icon: CrashTestIcon, match: ["/crash-test", "/passport"] },
  { href: "/dashboard", key: "dashboard", icon: ChartIcon },
] as const;

// Individual accounts (doctors) only need to seal/verify their own images;
// legal entities (hospitals, AI vendors) also certify models and see org stats.
const LINKS_BY_TYPE = {
  individual: ["seal", "verify"],
  legal: ["seal", "verify", "crashTest", "dashboard"],
} as const;

export default function Header() {
  const { t } = useLanguage();
  const pathname = usePathname();
  const router = useRouter();
  const session = useAuth();

  const links = session
    ? ALL_LINKS.filter((l) => (LINKS_BY_TYPE[session.type] as readonly string[]).includes(l.key))
    : [];

  const isActive = (l: (typeof ALL_LINKS)[number]) =>
    ("match" in l ? l.match : [l.href]).some((p) => pathname.startsWith(p));

  const linkClass = (active: boolean) =>
    `flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 transition-colors ${
      active ? "bg-white text-foreground shadow-sm" : "text-muted hover:bg-white/60 hover:text-foreground"
    }`;

  const doLogout = () => {
    logout();
    router.push("/");
  };

  return (
    <header className="sticky top-0 z-20 border-b border-white/60 bg-background/70 backdrop-blur-xl print:hidden">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-foreground text-white">
            <SealIcon width={18} height={18} />
          </span>
          <span className="text-lg font-semibold tracking-tight">MedSeal</span>
        </Link>

        {links.length > 0 && (
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
        )}

        <div className="flex items-center gap-2">
          <AccessibilityPanel />
          <LanguageSwitch />

          {session ? (
            <div className="hidden items-center gap-2 sm:flex">
              <span className="max-w-[10rem] truncate rounded-full bg-white/70 px-3 py-1.5 text-xs font-medium text-muted" title={session.org ?? session.name}>
                {session.org ?? session.name}
              </span>
              <button
                onClick={doLogout}
                className="rounded-full border border-border px-3.5 py-2 text-sm font-medium text-muted transition-colors hover:bg-white hover:text-foreground"
              >
                {t(dictionary.nav.logout)}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="hidden rounded-full border border-border px-3.5 py-2 text-sm font-medium text-muted transition-colors hover:bg-white hover:text-foreground sm:inline-flex"
              >
                {t(dictionary.nav.login)}
              </Link>
              <Link
                href="/register"
                className="rounded-full bg-foreground px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-foreground/90"
              >
                {t(dictionary.nav.register)}
              </Link>
            </div>
          )}
        </div>
      </div>

      {links.length > 0 && (
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
      )}

      {session && (
        <div className="flex items-center justify-between gap-2 border-t border-white/60 px-4 py-2 text-xs sm:hidden">
          <span className="truncate text-muted">{session.org ?? session.name}</span>
          <button onClick={doLogout} className="font-medium text-accent">
            {t(dictionary.nav.logout)}
          </button>
        </div>
      )}
    </header>
  );
}
