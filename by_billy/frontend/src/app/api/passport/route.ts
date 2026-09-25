import { NextRequest, NextResponse } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";

// Server-only: issuing a passport is an admin action (P1-04). Same pattern as
// src/app/api/crash-test/route.ts — see its comment.
const BACKEND_URL = (process.env.MEDSEAL_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export async function POST(req: NextRequest) {
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);

  const token = process.env.MEDSEAL_ADMIN_TOKEN;
  if (!BACKEND_URL || !token) {
    return NextResponse.json(
      { detail: "Admin gateway is not configured: set MEDSEAL_BACKEND_URL and MEDSEAL_ADMIN_TOKEN in .env.local" },
      { status: 503 }
    );
  }

  const body = await req.text();
  const res = await fetch(`${BACKEND_URL}/passport`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body,
  });
  const text = await res.text();
  return new NextResponse(text, { status: res.status, headers: { "Content-Type": "application/json" } });
}
