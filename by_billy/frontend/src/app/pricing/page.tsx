"use client";

import PageShell from "@/components/PageShell";
import { Button, Card } from "@/components/ui";
import { PriceTagIcon } from "@/components/icons";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";

const d = dictionary.pricing;

// Static marketing page: no billing and no checkout. "Choose plan" stays disabled until sign-up exists.
type Plan = {
  key: keyof typeof d.plans;
  name: string;
  price: string;
  regular?: string;
  from?: boolean;
  launch?: boolean;
};

const PATIENT_PLANS: Plan[] = [
  { key: "free", name: "FREE", price: "0 сум" },
  { key: "plus", name: "PLUS", price: "49 000 сум", regular: "79 000 сум", launch: true },
  { key: "pro", name: "PRO", price: "99 000 сум", regular: "159 000 сум", launch: true },
];

const BUSINESS_PLANS: Plan[] = [
  { key: "doctor", name: "DOCTOR", price: "199 000 сум", regular: "399 000 сум", launch: true },
  { key: "professional", name: "PROFESSIONAL", price: "499 000 сум", regular: "799 000 сум", launch: true },
  { key: "clinic", name: "CLINIC", price: "999 000 сум", regular: "1 799 000 сум", launch: true },
  { key: "enterprise", name: "ENTERPRISE", price: "$2 000", regular: "$4 000", from: true, launch: true },
];

function PlanCard({ plan }: { plan: Plan }) {
  const { t, lang } = useLanguage();
  const content = d.plans[plan.key];
  // Uzbek puts "dan" after the amount ("$2 000 dan"), Russian/English put it before.
  const withFrom = (amount: string) =>
    !plan.from ? amount : lang === "uz" ? `${amount} ${t(d.from)}` : `${t(d.from)} ${amount}`;
  const perMonth = plan.price.startsWith("0 ") ? "" : ` ${t(d.perMonth)}`;
  const headingId = `plan-${plan.key}`;

  return (
    <Card className="flex h-full flex-col">
      <article aria-labelledby={headingId} className="flex h-full flex-col">
        <h3 id={headingId} className="text-sm font-semibold tracking-wide text-accent">
          {plan.name}
        </h3>
        <p className="mt-3">
          <span className="text-2xl font-semibold">{withFrom(plan.price)}</span>
          <span className="text-sm text-muted">{perMonth}</span>
        </p>
        {plan.regular && (
          <p className="mt-1 text-xs text-muted">
            {t(d.regularPrice)}: <s>{withFrom(plan.regular)}</s>
          </p>
        )}
        <p className="mt-3 text-sm text-muted">{t(content.tagline)}</p>

        <ul className="mt-4 space-y-2 text-sm">
          {content.features.map((f) => (
            <li key={f.ru} className="flex gap-2">
              <span aria-hidden className="text-ok">✓</span>
              <span>{t(f)}</span>
            </li>
          ))}
        </ul>

        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {plan.launch && (
            <p className="font-semibold">
              <span aria-hidden>🔥 </span>
              {t(d.launchPrice)}: {withFrom(plan.price)}
            </p>
          )}
          <ul className={`space-y-1 ${plan.launch ? "mt-2" : ""}`}>
            {content.perks.map((p) => (
              <li key={p.ru}>{t(p)}</li>
            ))}
          </ul>
        </div>

        <div className="mt-auto pt-5">
          <Button variant="ghost" disabled className="w-full" aria-describedby="pricing-soon">
            {t(d.choose)}
          </Button>
        </div>
      </article>
    </Card>
  );
}

function PlanGroup({ title, plans, footnote, cols }: { title: string; plans: Plan[]; footnote: string; cols: string }) {
  return (
    <section aria-label={title} className="mt-10 first:mt-0">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <div className={`mt-4 grid gap-4 ${cols}`}>
        {plans.map((p) => (
          <PlanCard key={p.key} plan={p} />
        ))}
      </div>
      <p className="mt-3 text-xs text-muted">{footnote}</p>
    </section>
  );
}

export default function PricingPage() {
  const { t } = useLanguage();
  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={PriceTagIcon}>
      <p id="pricing-soon" className="mb-8 rounded-xl border border-border bg-white/60 px-4 py-3 text-sm text-muted">
        {t(d.preview)} {t(d.chooseSoon)}.
      </p>
      <PlanGroup title={t(d.patients)} plans={PATIENT_PLANS} footnote={t(d.footnotePatients)} cols="md:grid-cols-3" />
      <PlanGroup
        title={t(d.business)}
        plans={BUSINESS_PLANS}
        footnote={t(d.footnoteBusiness)}
        cols="md:grid-cols-2 lg:grid-cols-4"
      />
    </PageShell>
  );
}
