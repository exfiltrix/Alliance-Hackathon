"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { FLOW, type FlowKey } from "@/lib/flow";
import { ArrowRightIcon } from "./icons";

export function FlowSteps({ current }: { current: FlowKey }) {
  const { t } = useLanguage();
  const currentIndex = FLOW.findIndex((s) => s.key === current);

  return (
    <nav aria-label={t(dictionary.flow.label)} className="-mx-4 overflow-x-auto px-4 print:hidden">
      <ol className="flex min-w-max items-center gap-2">
        {FLOW.map((step, i) => {
          const active = i === currentIndex;
          const done = i < currentIndex;
          const Icon = step.icon;
          const content = (
            <>
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                  active
                    ? "bg-white/20 text-white"
                    : done
                      ? "bg-accent text-white"
                      : "bg-accent-soft text-accent"
                }`}
              >
                {done ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12l5 5L20 7" />
                  </svg>
                ) : (
                  <Icon width={15} height={15} />
                )}
              </span>
              <span className="text-sm font-medium">
                <span className="opacity-60">{i + 1}.</span> {t(dictionary.flow.steps[step.key].title)}
              </span>
            </>
          );
          const cls = `flex items-center gap-2 rounded-full py-1.5 pl-1.5 pr-4 transition-colors ${
            active
              ? "bg-foreground text-white shadow-lg shadow-foreground/10"
              : "border border-border bg-white/70 text-foreground hover:bg-white"
          }`;
          return (
            <li key={step.key} className="flex items-center gap-2">
              {active ? (
                <span aria-current="step" className={cls}>
                  {content}
                </span>
              ) : (
                <Link href={step.href} className={cls}>
                  {content}
                </Link>
              )}
              {i < FLOW.length - 1 && <span className="h-px w-5 bg-border" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function NextStepCard({ current }: { current: FlowKey }) {
  const { t } = useLanguage();
  const next = FLOW[FLOW.findIndex((s) => s.key === current) + 1];
  if (!next) return null;
  const Icon = next.icon;

  return (
    <Link
      href={next.href}
      className="group mt-12 flex items-center gap-4 rounded-2xl border border-border bg-white/70 p-5 transition-all hover:border-accent/40 hover:bg-white hover:shadow-lg hover:shadow-accent/10 print:hidden"
    >
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent">
        <Icon />
      </span>
      <span className="flex-1">
        <span className="block text-xs font-medium uppercase tracking-wide text-muted">
          {t(dictionary.flow.next)}
        </span>
        <span className="block font-semibold">{t(dictionary.flow.steps[next.key].title)}</span>
        <span className="block text-sm text-muted">{t(dictionary.flow.steps[next.key].desc)}</span>
      </span>
      <ArrowRightIcon className="text-muted transition-transform group-hover:translate-x-1 group-hover:text-accent" />
    </Link>
  );
}
