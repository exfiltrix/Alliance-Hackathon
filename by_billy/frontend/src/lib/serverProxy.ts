import { NextResponse } from "next/server";

// Shared by every doctor/client cabinet route handler (src/app/api/inbox/**, src/app/api/client/**):
// each forwards to the backend with its own server-only bearer token, added here so it never
// reaches the browser — same reasoning as src/app/api/seal/route.ts, just factored out because
// there are many small routes doing exactly this.
export const BACKEND_URL = (process.env.MEDSEAL_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export function notConfigured(varName: string) {
  return NextResponse.json(
    { detail: `Not configured: set MEDSEAL_BACKEND_URL and ${varName} in .env.local` },
    { status: 503 }
  );
}

export async function forward(path: string, token: string, init: RequestInit = {}): Promise<NextResponse> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${token}` },
  });
  const contentType = res.headers.get("content-type") ?? "application/json";
  if (contentType.includes("application/pdf")) {
    return new NextResponse(await res.arrayBuffer(), {
      status: res.status,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": res.headers.get("content-disposition") ?? "attachment",
      },
    });
  }
  const text = await res.text();
  return new NextResponse(text, { status: res.status, headers: { "Content-Type": contentType } });
}
