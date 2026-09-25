# MedSeal — frontend

Next.js (App Router) + React + TypeScript + Tailwind. No Docker.

```bash
npm install
npm run dev          # http://localhost:3000
```

## Connecting the backend

1. Start the FastAPI backend (e.g. `uvicorn app.main:app --port 8000`) with CORS allowing `http://localhost:3000`.
2. `cp .env.example .env.local` and set `NEXT_PUBLIC_API_URL=http://localhost:8000/api`.
3. Restart `npm run dev`.

Without `NEXT_PUBLIC_API_URL` the site runs on demo data (`src/lib/mock.ts`) and shows a "Demo" badge.

Contract: `../docs/API.md`. The TypeScript types in `src/lib/types.ts` match it one-to-one; all requests go through `src/lib/api.ts`.

## Where things are

| Path | What |
|---|---|
| `src/app/seal` | Seal an image (device picker, result, download) |
| `src/app/verify` | Verify: authentic / tampered / unsigned (+ detective) / forged, plus shield |
| `src/app/crash-test` | Attack a model, flip-rate chart, robustness score → passport |
| `src/app/passport/[id]` | Model passport, PDF / print |
| `src/app/dashboard` | Stats |
| `src/lib/dictionary.ts` | All UI strings: Uzbek (default), Russian, English — TypeScript fails the build if a translation is missing |
| `src/components/AccessibilityPanel.tsx`, `src/lib/a11y.ts` | Accessibility panel: text size, high contrast, dark (inverted) mode, greyscale, spacing, link highlighting, no animations, read aloud |
