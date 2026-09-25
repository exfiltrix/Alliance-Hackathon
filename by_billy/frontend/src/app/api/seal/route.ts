import { NextRequest, NextResponse } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";

// Server-only: forwards the upload to the backend with the gateway's own device token, so
// the token never reaches the browser (P0-1). MEDSEAL_DEVICE_TOKEN / MEDSEAL_BACKEND_URL
// are plain env vars (no NEXT_PUBLIC_ prefix) — see backend/scripts/create_demo_device.py
// for how to mint a token, and .env.example for where they go.
const BACKEND_URL = (process.env.MEDSEAL_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export async function POST(req: NextRequest) {
  // Defence in depth: src/proxy.ts already gates this route, but a route handler must not
  // assume the proxy ran in front of it (P1-01).
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);

  const token = process.env.MEDSEAL_DEVICE_TOKEN;
  if (!BACKEND_URL || !token) {
    return NextResponse.json(
      { detail: "Gateway is not configured: set MEDSEAL_BACKEND_URL and MEDSEAL_DEVICE_TOKEN in .env.local" },
      { status: 503 }
    );
  }

  // Reject an oversize body before req.formData() buffers it into memory.
  const contentLength = Number(req.headers.get("content-length"));
  if (!contentLength || Number.isNaN(contentLength) || contentLength > MAX_UPLOAD_BYTES) {
    return NextResponse.json({ detail: "File is too large" }, { status: 413 });
  }

  const form = await req.formData();
  const res = await fetch(`${BACKEND_URL}/seal`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { "Content-Type": "application/json" } });
}
