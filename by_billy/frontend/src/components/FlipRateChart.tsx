"use client";

export default function FlipRateChart({
  flipRate,
  psnr,
  psnrLabel,
  caption,
  epsLabel,
}: {
  flipRate: Record<string, number>;
  psnr: Record<string, number>;
  psnrLabel: string;
  caption: string;
  epsLabel: string;
}) {
  const eps = Object.keys(flipRate).sort((a, b) => Number(a) - Number(b));

  return (
    <div>
      <table className="sr-only">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{epsLabel} (eps)</th>
            <th scope="col">{caption}</th>
            <th scope="col">PSNR</th>
          </tr>
        </thead>
        <tbody>
          {eps.map((e) => (
            <tr key={e}>
              <th scope="row">{e}</th>
              <td>{Math.round(flipRate[e] * 100)}%</td>
              <td>{psnr[e] != null ? `${psnr[e].toFixed(1)} dB` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div aria-hidden>
      <div className="relative mt-6 h-48">
        {[0, 50, 100].map((g) => (
          <div
            key={g}
            className="absolute inset-x-0 border-t border-border/70"
            style={{ bottom: `${g}%` }}
          >
            <span className="absolute -top-2.5 left-0 bg-surface pr-1 text-[10px] text-muted">{g}%</span>
          </div>
        ))}
        <div className="absolute inset-0 left-8 flex items-end justify-around gap-3">
          {eps.map((e) => {
            const v = flipRate[e];
            return (
              <div key={e} className="group relative flex h-full w-full max-w-16 items-end">
                <div
                  className="relative w-full rounded-t-[4px] bg-accent transition-opacity group-hover:opacity-80"
                  style={{ height: `${Math.max(v * 100, 1)}%` }}
                >
                  <span className="absolute inset-x-0 -top-5 text-center text-xs font-semibold">
                    {Math.round(v * 100)}%
                  </span>
                </div>
                <div className="pointer-events-none absolute left-1/2 top-0 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg bg-foreground px-2.5 py-1.5 text-xs text-white group-hover:block">
                  eps {e}: {Math.round(v * 100)}%
                  {psnr[e] != null && ` · PSNR ${psnr[e].toFixed(1)} dB`}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="ml-8 mt-2 flex justify-around gap-3 text-center text-xs text-muted">
        {eps.map((e) => (
          <div key={e} className="w-full max-w-16">
            <p className="font-medium text-foreground">{e}</p>
            {psnr[e] != null && <p className="text-[10px]">{psnr[e].toFixed(0)} dB</p>}
          </div>
        ))}
      </div>
      <p className="ml-8 mt-1 text-[10px] text-muted">{psnrLabel}</p>
      </div>
    </div>
  );
}
